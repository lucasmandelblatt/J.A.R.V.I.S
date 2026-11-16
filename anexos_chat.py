"""Anexos do chat (o botão + da caixa de texto): imagens, recortes de tela, PDFs e textos que o usuário manda no meio da
conversa. Vão só para a conversa atual: nada é gravado em disco, nem no projeto, nem no cofre (a transcrição guarda só os nomes).

Medido em 15/11/2026 no gemini-3.8-live: uma imagem em clientContent, junto do texto, é vista ("Vermelho."); a mesma
imagem em realtimeInput.video seguida de texto não é (o modelo chamou olhar_tela). PDF em inlineData derruba a conexão
(1007 invalid argument), por isso o PDF é transcrito em memória por um Gemini comum e entra como texto."""
import asyncio
import os
import pathlib
import tempfile
import uuid

from aiohttp import web

import gem
import paths
from core import READERS, READERS_FALLBACK, log, log_talk, osascript
from config import USER

MAX_ITEMS = 10
MAX_TEXT = 120_000   # caracteres por arquivo de texto ou PDF transcrito
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}

PDF_PROMPT = ("Transcreva fielmente todo o texto deste PDF, na ordem, sem resumir nem comentar. Reproduza tabelas como "
              "linhas de texto. Para cada imagem ou gráfico com conteúdo importante, escreva uma linha entre colchetes "
              "descrevendo o que mostra.")


async def pdf_text(http, key, data_b64):
    body = {"contents": [{"parts": [{"inlineData": {"mimeType": "application/pdf", "data": data_b64}}, {"text": PDF_PROMPT}]}]}
    try:
        return (await gem.generate(http, key, body, READERS + READERS_FALLBACK[:1], timeout=90, race=True, rounds=2,
                                   pause=(3,), log=log))[:MAX_TEXT], None
    except gem.GeminiError as e:
        return None, str(e)


async def build_turn(session, msg, where=None):
    """The user turn (parts) for Gemini Live, and a short label of what came, for the transcript."""
    parts, names, failed, kept = [], [], [], []
    for it in (msg.get("items") or [])[:MAX_ITEMS]:
        kind, name = it.get("kind"), str(it.get("name") or "arquivo")[:120]
        if kind == "image" and it.get("data"):
            mime = it.get("mime") if it.get("mime") in IMAGE_TYPES else "image/jpeg"
            parts.append({"inlineData": {"mimeType": mime, "data": it["data"]}})
            names.append(f"imagem «{name}»")
        elif kind == "text":
            parts.append({"text": f"--- Conteúdo do arquivo «{name}»:\n{str(it.get('text', ''))[:MAX_TEXT]}\n--- fim de «{name}»"})
            names.append(f"arquivo «{name}»")
        elif kind == "saved" and it.get("path"):
            kept.append(f"«{name}» em {it['path']}")
        elif kind == "pdf" and it.get("data"):
            cid = f"pdf-{uuid.uuid4().hex[:8]}"
            await session.to_browser(type="busy", id=cid, text=f"Lendo o PDF {name}", done=False)
            text, err = await pdf_text(session.http, session.key, it["data"])
            await session.to_browser(type="busy", id=cid, text=None, done=True)
            if text:
                parts.append({"text": f"--- Texto do PDF «{name}» (transcrito agora):\n{text}\n--- fim de «{name}»"})
                names.append(f"PDF «{name}»")
            else:
                log(f"anexo: PDF {name} não foi lido: {err}")
                failed.append(name)
    said = str(msg.get("text") or "").strip()
    head = (f"[{USER} anexou no chat: " + ", ".join(names) + ". É só para esta conversa: não foi salvo no Mac, nem no "
            "projeto, nem na memória. O conteúdo está aqui nesta mensagem; não procure o arquivo nem use olhar_tela para vê-lo.]") if names else ""
    if kept:
        head += (f" [{USER} também mandou, e isto ficou guardado no Mac: " + "; ".join(kept) + ". Se for um vídeo e ele quiser "
                 "que você assista ou estude, use assistir_video com o caminho; para outros arquivos, "
                 + ("peça ao Claude pela ferramenta executar_no_mac o que ele pedir.]" if paths.atticus().exists()
                    else "diga o que você consegue fazer com eles.]"))
    if failed:
        head += f" [Não consegui ler: {', '.join(failed)}. Avise {USER} disso.]"
    ask = said or ("Ele não escreveu nada junto: diga em uma frase curta o que você vê e pergunte o que ele quer fazer."
                   if names or kept else "")
    if where:
        ask = f"[tela de estudo: {where}] {ask}"
    parts.append({"text": f"{head} {ask}".strip()})
    label = (f"[anexou {', '.join(names + failed + kept)}] " if names or failed or kept else "") + said
    return parts, label


async def send(session, msg, where=None):
    """Runs outside the browser loop (a PDF takes seconds) so the microphone keeps flowing meanwhile."""
    try:
        parts, label = await build_turn(session, msg, where)
        session.flush()
        session.tool_since_user = False
        log_talk(f"{USER}", label)
        await session.to_gemini({"clientContent": {"turns": [{"role": "user", "parts": parts}], "turnComplete": True}})
    except Exception as e:
        log(f"anexo: falhou: {e!r}")
        await session.to_browser(type="warning", text=f"Não consegui mandar o anexo: {e}")


async def _set_visible(visible):
    """Hides the Jarvis window while the user picks an area, so it isn't in the way. Best effort: without permission for
    System Events the window just stays where it is (and the space bar still picks a whole window)."""
    if visible:
        await asyncio.create_subprocess_exec("/usr/bin/open", "-a", str(paths.app()))
        return
    _, err = await osascript(f'tell application "System Events" to set visible of (first process whose unix id is {os.getppid()}) to false', timeout=5)
    if err:
        log(f"recorte: não escondi a janela: {err[:200]}")


async def api_snip(request):
    """macOS's own area selection (screencapture -i). The PNG comes back to the page and is deleted at once.
    204 when the user pressed Esc."""
    shot = pathlib.Path(tempfile.gettempdir()) / f"jarvis-recorte-{uuid.uuid4().hex}.png"
    hide = request.query.get("esconder") != "0"
    if hide:
        await _set_visible(False)
        await asyncio.sleep(0.35)   # the window's fade-out, or it lands in the capture
    try:
        proc = await asyncio.create_subprocess_exec("/usr/sbin/screencapture", "-i", "-x", "-t", "png", str(shot),
                                                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            _, err = await asyncio.wait_for(proc.communicate(), 300)
        except asyncio.TimeoutError:
            proc.kill()
            return web.json_response({"error": "O recorte demorou demais e foi cancelado."}, status=408)
        if not shot.exists():
            if proc.returncode:
                log(f"recorte: screencapture falhou ({proc.returncode}): {err.decode(errors='replace')[:200]}")
            return web.Response(status=204)
        return web.Response(body=shot.read_bytes(), content_type="image/png", headers={"Cache-Control": "no-store"})
    finally:
        shot.unlink(missing_ok=True)
        if hide:
            await _set_visible(True)
