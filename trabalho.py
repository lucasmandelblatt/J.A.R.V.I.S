"""Jarvis's long work: a headless Claude Code run that does a big job for real (a diagnosis of a codebase, a study plan
from the vault, a long analysis) in the background, shows each step under the purple reactor, and when it ends puts the
full text in the chat, saves it as a note in Obsidian and tells Jarvis, who tells the user.

Before this, "faz um diagnóstico do Jarvis" went to Atticus, which only does short actions: Claude answered "iniciei em
segundo plano" and nothing ran (12/11 20:01). Claude here can read files and the web but not change anything.
"""
import asyncio
import datetime
import json
import pathlib
import time
import urllib.parse

import paths
from core import VAULT, clean_env, log, log_turn
from config import USER

LIMIT = 25 * 60   # seconds; past this the job is killed and the user is told it was not done
TOOLS = ["Read", "Glob", "Grep", "WebSearch", "WebFetch"]
# Only the web tools are pre-approved. Claude Code lets the read-only tools in by itself only inside its working folders
# (the Jarvis code, plus the vault via --add-dir); a read anywhere else (~/.ssh, .env) needs a yes that print mode never
# gives, so it is refused. With the web on, that keeps a page's hidden instructions from sending secrets out.
WEB = ["WebSearch", "WebFetch"]

METHOD = """Você é o motor de trabalho longo do Jarvis, o assistente de voz de {user}. O Jarvis te passou um pedido de {user} \
para fazer AGORA, inteiro, nesta execução: ninguém continua depois, e {user} só recebe o que você responder no fim.

Onde as coisas estão no Mac dele:
Você só consegue ler estas duas pastas; o resto do Mac é bloqueado.
- O código do Jarvis: {code} (server.py é o centro).
- O cofre do Obsidian (memória de {user}, projetos, notas): {vault}. Leia VAULT-INDEX.md antes de procurar nele.
- Hoje é {today}.

Você pode ler arquivos e pesquisar na internet, mas não pode criar, mudar nem apagar nada. Se o pedido envolver mudar \
algo, entregue pronto o que {user} precisa para fazer a mudança (o texto, o plano, o prompt para o Claude Code) e diga \
isso. Baseie cada afirmação no que você leu ou achou; separe o que verificou do que é suposição; nunca invente número, \
arquivo ou fonte.

Responda em português do Brasil, neste formato exato:
FALA: duas ou três frases naturais para o Jarvis dizer em voz alta, com o essencial (sem markdown, sem listas, sem links).

Depois uma linha em branco e o trabalho completo em Markdown: comece pela conclusão, depois seções curtas com ## e \
listas, com os detalhes, os caminhos dos arquivos e as fontes."""


def step(event, seen):
    """One line for the progress display from a stream-json event of Claude Code, or None."""
    line = None
    for c in event.get("message", {}).get("content", []) if event.get("type") == "assistant" else []:
        if not isinstance(c, dict) or c.get("type") != "tool_use":
            continue
        a, name = c.get("input") or {}, c.get("name")
        seen[name] = seen.get(name, 0) + 1
        if name == "Read":
            line = "Lendo " + pathlib.Path(str(a.get("file_path", ""))).name
        elif name in ("Grep", "Glob"):
            line = "Procurando: " + str(a.get("pattern", ""))[:80]
        elif name == "WebSearch":
            line = "Pesquisando: " + str(a.get("query", ""))[:80]
        elif name == "WebFetch":
            line = "Lendo " + urllib.parse.urlparse(str(a.get("url", ""))).netloc.removeprefix("www.")
    return line


def split(text):
    """(fala, documento) from Claude's final message."""
    text = text.strip()
    if text.upper().startswith("FALA:"):
        first, _, rest = text.partition("\n")
        return first[5:].strip(), rest.strip() or first[5:].strip()
    return text[:400], text


async def run(task, progress, limit=LIMIT):
    """Runs Claude Code on `task`. Returns {"fala", "texto", "passos", "segundos"} or {"error"}."""
    started, seen, envelope = time.monotonic(), {}, None
    system = METHOD.format(user=USER, code=paths.code(), vault=paths.vault(), today=datetime.date.today().strftime("%d/%m/%Y"))
    proc = await asyncio.create_subprocess_exec(
        paths.claude(), "-p", task, "--model", "sonnet", "--effort", "high",
        "--tools", ",".join(TOOLS), "--allowedTools", *WEB, "--add-dir", str(paths.vault()),
        "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence",
        "--settings", '{"disableAllHooks": true}',   # the user's own hooks would run inside every job (see research.py)
        "--output-format", "stream-json", "--verbose", "--append-system-prompt", system,
        cwd=str(paths.code()), env=clean_env(), limit=64 * 1024 * 1024,
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    errors = asyncio.create_task(proc.stderr.read())

    async def pump():
        nonlocal envelope
        while line := await proc.stdout.readline():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "result":
                envelope = event
            elif text := step(event, seen):
                await progress(text)
        await proc.wait()
    try:
        await asyncio.wait_for(pump(), limit)
    except (asyncio.TimeoutError, asyncio.CancelledError) as e:
        proc.kill()
        await asyncio.shield(proc.wait())   # no zombie left behind
        if isinstance(e, asyncio.CancelledError):
            raise
        return {"error": f"O trabalho passou de {limit // 60} minutos e foi interrompido."}
    if envelope is None:
        return {"error": (await errors).decode(errors="replace").strip()[-500:] or "O trabalho falhou."}
    if envelope.get("is_error") or not str(envelope.get("result", "")).strip():
        return {"error": str(envelope.get("result") or envelope.get("subtype") or "sem resposta")[:500]}
    fala, texto = split(envelope["result"])
    return {"fala": fala, "texto": texto, "passos": sum(seen.values()), "segundos": round(time.monotonic() - started)}


async def to_sessions(app, method, *args, **kw):
    for s in list(app["sessions"]):
        try:
            await getattr(s, method)(*args, **kw)
        except Exception as e:   # noqa: BLE001 — one closing window must not stop the others or the job
            log(f"trabalho: aviso para uma janela falhou: {e!r}")


async def job(app, task, title):
    state = app["trabalho"]   # one dict for the app's lifetime: empty when no job runs

    async def progress(text):
        state["passo"] = text
        await to_sessions(app, "busy", "trabalho", text)
    try:
        await progress("Trabalho longo: " + title)
        done = await run(task, progress)
    except asyncio.CancelledError:
        await to_sessions(app, "busy", "trabalho", None)
        log_turn("Resultado", f"Trabalho longo cancelado: {title}")
        state.clear()
        raise
    except Exception as e:   # noqa: BLE001
        log(f"trabalho falhou: {e!r}")
        done = {"error": f"Falhou: {e}"}
    await to_sessions(app, "busy", "trabalho", None)
    state.clear()
    if "error" in done:
        log_turn("Resultado", f"Trabalho longo não concluído ({title}): {done['error']}")
        await to_sessions(app, "notify", f"[sistema] O trabalho longo “{title}” NÃO foi concluído: {done['error']} "
                                         f"Diga isso a {USER} em uma frase e ofereça tentar de novo.", work=False)
        return
    try:   # the vault copy outlives the chat; the chat copy is what the user reads now
        path, _ = VAULT.write_note(f"Trabalho — {title}", f"Pedido: {task}\n(Feito pelo Claude a pedido do Jarvis em "
                                   f"{datetime.date.today():%d/%m/%Y}, com leitura da web: confira antes de tratar como fato.)"
                                   f"\n\n{done['texto']}", "referencia", "reference", "completed")
        note = str(path.relative_to(VAULT.root))
    except Exception as e:   # noqa: BLE001
        log(f"trabalho: não salvei a nota: {e!r}")
        note = None
    log_turn("Resultado", f"Trabalho longo concluído ({title}): {done['fala']}")
    await to_sessions(app, "to_browser", type="document", title=title, text=done["texto"])
    await to_sessions(app, "notify", f"[sistema] O trabalho longo “{title}” terminou em {done['segundos'] // 60 or 1} min. "
                                     f"O texto completo já está no chat de {USER}" + (f" e na nota {note} do Obsidian" if note else "")
                                     + f". Diga a {USER}, em duas ou três frases, o essencial: {done['fala']}")


async def tool(app, args):
    """The voice tool trabalho_longo: iniciar (returns at once), status, cancelar."""
    acao, state = args.get("acao") or "iniciar", app["trabalho"]
    if acao == "status":
        if not state:
            return {"result": "Nenhum trabalho longo está rodando agora."}
        mins = int(time.time() - state["desde"]) // 60
        return {"result": f"Rodando há {mins} min: “{state['titulo']}”. Passo atual: {state.get('passo', 'começando')}."}
    if acao == "cancelar":
        if not state:
            return {"result": "Nenhum trabalho longo está rodando."}
        state["task"].cancel()
        return {"result": f"Cancelei o trabalho “{state['titulo']}”."}
    task = (args.get("tarefa") or "").strip()
    if not task:
        return {"error": "Falta o pedido. Chame de novo com a tarefa completa."}
    if state:
        return {"error": f"Já tem um trabalho longo rodando (“{state['titulo']}”). Espere terminar ou cancele antes."}
    title = " ".join((args.get("titulo") or task).split())[:70]
    log_turn("Tarefa", f"Trabalho longo: {task}")
    state.update(titulo=title, desde=time.time())
    state["task"] = t = asyncio.create_task(job(app, task, title))
    app["jobs"].add(t)
    t.add_done_callback(app["jobs"].discard)
    return {"result": f"Comecei o trabalho longo “{title}”. Leva alguns minutos; o andamento aparece na tela e o sistema "
                      f"te avisa quando terminar. Diga isso a {USER} numa frase curta."}
