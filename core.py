"""Base compartilhada do Jarvis: configurações, log, cofre do Obsidian, leitura rápida pelo Gemini e o canal de avisos às telas."""
import asyncio
import datetime
import gem
import json
import os
import pathlib
import projects
import subprocess
import sys

from aiohttp import web
from config import CONFIG, DEFAULTS, USER, save_setting, settings  # noqa: F401 (re-exported)
from vault import Vault


HERE = pathlib.Path(__file__).resolve().parent
UPLOADS = HERE / "arquivos"


SWITCHES = {"vision": "visão da tela", "internet": "internet", "actions": "ações no Mac"}


# Screenshots, links and videos are read by a regular Gemini model; the first that isn't overloaded answers.
# Measured 04/11/2026: flash-lite reads a screenshot in ~2 s, 3.5-flash in ~7 s; 3.8-flash often hangs 90 s "high demand".
# The fast ones are asked at the same time and the first answer wins; the others are only a fallback.
READERS = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
READERS_FALLBACK = ["gemini-3.6-flash"]
READ_TIMEOUT = 25


def switches():
    s = settings()
    return {k: bool(s[k]) for k in SWITCHES}


def active_project():
    return projects.get(settings().get("projeto"))


def log_talk(who, text):
    """A spoken or typed turn: into the open project's own conversation, otherwise into today's log in the vault."""
    proj = active_project()
    if proj:
        proj.log(who, text)
    else:
        log_turn(who, text)


def seconds(text):
    """'12:30' or '1:02:03' or '95' -> seconds; None when empty."""
    if text in (None, ""):
        return None
    n = 0
    for part in str(text).strip().split(":"):
        n = n * 60 + float(part or 0)
    return n


def log(line):
    with open(HERE / "jarvis.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {line}\n")


def api_key():
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    r = subprocess.run(["security", "find-generic-password", "-s", "jarvis-gemini", "-w"],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        sys.exit("Chave do Gemini não encontrada no Keychain (serviço jarvis-gemini).")
    return r.stdout.strip()


VAULT = Vault(settings()["vault"])
log_turn = VAULT.log_turn


# Where Jarvis's subprocesses (and paths.py) look for programs. The app starts the server with a minimal PATH, so the
# usual places for Claude Code and Homebrew (Apple silicon and Intel) are listed here.
TOOL_PATH = f"{pathlib.Path.home()}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def clean_env():
    """The environment for Atticus and Claude Code, without anything inherited from a Claude Code session or Atticus run.
    (Restarted from inside a Claude Code session, Jarvis inherits ATTICUS_ASK and CLAUDE_* variables; Atticus then
    refuses every task as 'unknown command', and claude would attach to that session.)"""
    drop = ("CLAUDE", "ATTICUS_", "AI_AGENT", "ANTHROPIC_", "MCP_", "OTEL_")
    env = {k: v for k, v in os.environ.items() if not k.startswith(drop)}
    env["PATH"] = TOOL_PATH
    return env


async def read_with_gemini(http, key, parts, use_web=False):
    """One-shot question to a regular Gemini model (image, page or video in `parts`). The fast models race each other
    and the first good answer wins; if all fail, the slower ones are tried, and the whole thing is repeated twice."""
    body = {"contents": [{"parts": parts}],
            "systemInstruction": {"parts": [{"text": "Responda em português do Brasil, de forma clara e direta, para ser lida em voz alta "
                                                      "(sem markdown, sem listas longas). Seja fiel ao que está no conteúdo."}]}}
    if use_web:
        body["tools"] = [{"urlContext": {}}]   # free; Google Search grounding is not
    try:
        return {"result": (await gem.generate(http, key, body, READERS + READERS_FALLBACK[:1], timeout=READ_TIMEOUT,
                                              race=True, rounds=3, pause=(2, 5), log=log))[:6000]}
    except gem.GeminiError as e:
        return {"error": f"Não consegui ler agora: {e}"}


async def osascript(script, timeout=20):
    proc = await asyncio.create_subprocess_exec("/usr/bin/osascript", "-e", script,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return None, "O Chrome não respondeu a tempo (talvez esteja esperando a permissão 'Jarvis quer controlar o Google Chrome')."
    return (out.decode(errors="replace"), None) if proc.returncode == 0 else (None, err.decode(errors="replace").strip())


async def broadcast(app, **msg):
    """Tells every open screen about a change (agenda, notas, projetos, gravação). Goes through /api/eventos, which
    every page keeps open all the time, not through the voice connection: that one exists only while the mic is on."""
    for q in list(app["events"]):
        q.put_nowait(msg)


async def api_events(request):
    """Server-sent events: one JSON message per change; the browser reconnects by itself if it drops."""
    resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-store"})
    await resp.prepare(request)
    q = asyncio.Queue()
    request.app["events"].add(q)
    try:
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), 25)
            except asyncio.TimeoutError:
                await resp.write(b": ping\n\n")   # keeps the connection alive and notices a closed window
                continue
            if msg is None:   # server shutting down
                break
            await resp.write(f"data: {json.dumps(msg, ensure_ascii=False)}\n\n".encode())
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        request.app["events"].discard(q)
    return resp


@web.middleware
async def notify_projects(request, handler):
    """Every change to a project made through the page (Studio or panel) reaches every open screen, the same way
    Jarvis's own changes by voice do: one project_update, or 'projects' when the list itself changed."""
    resp = await handler(request)
    if request.method != "GET" and request.path.startswith("/api/projects") and resp.status < 400:
        proj = projects.get(request.match_info.get("pid", ""))
        await broadcast(request.app, **({"type": "project_update", "project": proj.summary()} if proj else {"type": "projects"}))
    return resp


def bg(app, coro):
    job = asyncio.create_task(coro)
    app["jobs"].add(job); job.add_done_callback(app["jobs"].discard)
    return job


def need_project(request):
    proj = projects.get(request.match_info["pid"])
    if not proj:
        raise web.HTTPNotFound()
    return proj
