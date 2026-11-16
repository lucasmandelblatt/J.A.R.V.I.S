"""Jarvis's research: a headless Claude Code run that researches the way Claude does in a chat, then hands back
a short spoken answer plus the full written answer with sources. Nothing opens in Chrome.

Claude runs with only WebSearch and WebFetch (no files, no shell, no MCP servers), on the user's Claude plan.
"""
import asyncio
import datetime
import json
import pathlib
import re
import urllib.parse

import paths
from config import USER


DEPTHS = {
    # depth: (model, effort, how many searches and sources, time limit in seconds)
    "rapida": ("sonnet", "low", "de 2 a 4 buscas e abra de 1 a 3 fontes", 150),
    "profunda": ("sonnet", "high", "de 6 a 12 buscas (em português e em inglês) e abra de 4 a 8 fontes", 420),
}

METHOD = """Você é o motor de pesquisa do Jarvis, o assistente de voz de {user}. Pesquise e responda como um analista cuidadoso.

Método:
1. Entenda o que {user} realmente quer saber e quebre em 2 a 5 perguntas menores.
2. Pesquise com WebSearch: {searches}. Rode buscas independentes em paralelo. Varie os termos; use inglês quando as melhores fontes forem em inglês.
3. Abra com WebFetch as fontes mais confiáveis e diretas (oficiais, dados primários, veículos sérios, especialistas). Não confie só no trecho do resultado de busca.
4. Cruze as fontes. Verifique datas: hoje é {today}; prefira o mais recente e diga quando um dado pode estar desatualizado. Se as fontes discordarem, diga isso.
5. Nunca invente número, data ou fonte. Se não achou algo, diga o que faltou. Para previsões e opiniões, apresente os cenários e quem defende cada um, sem fingir certeza.

Responda SOMENTE com um objeto JSON válido, sem texto antes ou depois, neste formato:
{{"titulo": "título curto do assunto",
  "fala": "a resposta para ser dita em voz alta: 2 a 4 frases naturais em português do Brasil, com o essencial e os números principais, sem markdown, sem links, sem listas",
  "resposta": "a resposta completa em Markdown, em português do Brasil: comece pela conclusão, depois seções curtas com ## e listas, com os números e as datas, e marque as fontes como [1], [2]",
  "fontes": [{{"titulo": "nome da fonte ou página", "url": "https://..."}}]}}"""


def _parse(text):
    """The JSON object in Claude's final message (tolerates a code fence or stray text around it)."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) and data.get("fala") else None


def step(event, seen):
    """One line for the progress display from a stream-json event of Claude Code, or None."""
    if event.get("type") == "user" and any(isinstance(c, dict) and c.get("type") == "tool_result"
                                           for c in event.get("message", {}).get("content", [])):
        b, f = seen["buscas"], seen["fontes"]
        return f"Comparando o que achou: {b} busca{'s' if b != 1 else ''}, {f} fonte{'s lidas' if f != 1 else ' lida'}"
    line = None
    for c in event.get("message", {}).get("content", []) if event.get("type") == "assistant" else []:
        if not isinstance(c, dict) or c.get("type") != "tool_use":
            continue
        args = c.get("input") or {}
        if c.get("name") == "WebSearch":
            seen["buscas"] += 1
            line = "Pesquisando: " + str(args.get("query", ""))[:90]
        elif c.get("name") == "WebFetch":
            seen["fontes"] += 1
            site = urllib.parse.urlparse(str(args.get("url", ""))).netloc.removeprefix("www.")
            line = f"Lendo {site} ({seen['fontes']}ª fonte)"
    return line


async def research(question, depth, env, progress=None):
    """Returns {"titulo","fala","resposta","fontes","segundos"} or {"error"}. `progress(text)` (async) gets each step."""
    model, effort, searches, limit = DEPTHS.get(depth, DEPTHS["rapida"])
    started = asyncio.get_running_loop().time()
    system = METHOD.format(user=USER, searches=searches, today=datetime.date.today().strftime("%d/%m/%Y"))
    proc = await asyncio.create_subprocess_exec(
        paths.claude(), "-p", question,
        "--model", model, "--effort", effort,
        "--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch", "WebFetch",
        "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence",
        # The user's own hooks (memory, modes) would start with every research and add their text to its prompt.
        "--settings", '{"disableAllHooks": true}',
        "--output-format", "stream-json", "--verbose", "--append-system-prompt", system,
        cwd=str(pathlib.Path.home()), env=env, limit=64 * 1024 * 1024,   # one event per line; a page read can be large
        # Without stdin closed, claude waits 3 s for it ("no stdin data received in 3s"), measured 13/11.
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    seen, envelope = {"buscas": 0, "fontes": 0}, None
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
            elif progress and (text := step(event, seen)):
                await progress(text)
        await proc.wait()
    try:
        await asyncio.wait_for(pump(), limit)
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": f"A pesquisa passou de {limit // 60} minutos e foi interrompida."}
    if envelope is None:
        return {"error": (await errors).decode(errors="replace").strip()[-500:] or "A pesquisa falhou."}
    if envelope.get("is_error"):
        return {"error": str(envelope.get("result") or envelope.get("subtype"))[:500]}
    data = _parse(envelope.get("result", ""))
    if not data:
        text = envelope.get("result", "").strip()
        return {"titulo": question[:60], "fala": text[:600], "resposta": text, "fontes": [],
                "segundos": round(asyncio.get_running_loop().time() - started)}
    data["fontes"] = [f for f in data.get("fontes") or [] if isinstance(f, dict) and f.get("url")]
    data["segundos"] = round(asyncio.get_running_loop().time() - started)
    return data


def as_note(question, data):
    """Markdown body for the Obsidian note of a deep research."""
    sources = "\n".join(f"{i}. [{f.get('titulo') or f['url']}]({f['url']})" for i, f in enumerate(data["fontes"], 1))
    # The first sentence becomes the line in the folder index, so it states what was researched.
    return (f"Pergunta pesquisada: {question.rstrip('?.')}? (Jarvis, {datetime.date.today():%d/%m/%Y})\n\n"
            f"{data['resposta'].strip()}\n\n## Fontes\n{sources or '(sem fontes listadas)'}")
