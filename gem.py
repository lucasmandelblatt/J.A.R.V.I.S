"""One reliable way to ask Gemini (REST generateContent), shared by the screen, links and video.

Google's free models are often "experiencing high demand" (HTTP 503) or rate-limited (429), and one of them can hang
for a minute and a half. So every call tries several models, either all at once (race: the first good answer wins)
or one after another, and repeats the whole round a few times with a pause before giving up.
"""
import asyncio
import re

import aiohttp

REST = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
OLLAMA = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "qwen3:8b"
OLLAMA_MAX = 60_000   # characters; qwen3:8b reads ~32k tokens


class GeminiError(Exception):
    pass


def _text(d):
    cands = d.get("candidates") or []
    if not cands:
        reason = (d.get("promptFeedback") or {}).get("blockReason", "sem resposta")
        raise GeminiError(f"sem resposta ({reason})")
    text = "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []) if not p.get("thought"))
    if not text.strip():
        raise GeminiError(f"resposta vazia ({cands[0].get('finishReason', '?')})")
    return text.strip()


async def _ask(http, key, model, body, timeout):
    try:
        async with http.post(REST.format(model), headers={"x-goog-api-key": key}, json=body,
                             timeout=aiohttp.ClientTimeout(total=timeout)) as r:
            d = await r.json(content_type=None)
    except asyncio.TimeoutError:
        raise GeminiError(f"{model}: passou de {timeout:.0f} s")
    except aiohttp.ClientError as e:
        raise GeminiError(f"{model}: rede ({e.__class__.__name__})")
    if "error" in d:
        raise GeminiError(f"{model}: {d['error'].get('code', '')} {d['error'].get('message', '')[:160]}")
    try:
        return _text(d)
    except GeminiError as e:
        raise GeminiError(f"{model}: {e}")


async def generate(http, key, body, models, *, timeout=60, race=False, hedge=None, rounds=1, pause=(3, 8), log=None):
    """The text of the first good answer.
    race:  all models at once, the first good answer wins (cheap requests: a screenshot, a page).
    hedge: one model at a time, but if one has not answered after `hedge` seconds the next one starts too, and the
           first good answer wins (expensive requests: a whole video). A failure starts the next model at once.
    rounds: how many times the whole list is tried, waiting pause[i] seconds between rounds."""
    errors = []
    loop = asyncio.get_running_loop()
    for attempt in range(rounds):
        if attempt:
            await asyncio.sleep(pause[min(attempt - 1, len(pause) - 1)])
        started = loop.time()
        queue = list(models)
        running = {}
        try:
            while queue or running:
                if queue and (race or not running):
                    m = queue.pop(0)
                    running[asyncio.create_task(_ask(http, key, m, body, timeout))] = m
                    if race:
                        continue
                wait = hedge if (hedge and queue and not race) else None
                done, _ = await asyncio.wait(running, timeout=wait, return_when=asyncio.FIRST_COMPLETED)
                if not done:   # the running model is slow: start the next one alongside it
                    m = queue.pop(0)
                    running[asyncio.create_task(_ask(http, key, m, body, timeout))] = m
                    if log:
                        log(f"gemini: {', '.join(running.values())} ainda sem resposta após {loop.time() - started:.0f}s; chamando {m} junto")
                    continue
                for t in done:
                    m = running.pop(t)
                    try:
                        text = t.result()
                        if log:
                            log(f"gemini: {m} em {loop.time() - started:.1f}s")
                        return text
                    except GeminiError as e:
                        errors.append(str(e))
                        if log and not race:
                            log(f"gemini: falhou {e}")
                        if re.search(r": 400 ", str(e)) and "API key" not in str(e):
                            raise
                        if queue and not race and running:   # a model failed while another is still working
                            m = queue.pop(0)
                            running[asyncio.create_task(_ask(http, key, m, body, timeout))] = m
        finally:
            for t in running:
                t.cancel()
    if log:
        log("gemini falhou: " + " | ".join(errors)[-600:])
    text = await _local(http, body, log)
    if text:
        return text
    raise GeminiError(errors[-1] if errors else "sem resposta")


def _text_only(body):
    """The prompt as plain text when the request has no image, video, file or web tool (else None)."""
    if body.get("tools"):
        return None
    parts = [p for c in body.get("contents", []) for p in c.get("parts", [])]
    parts += (body.get("systemInstruction") or {}).get("parts", [])
    if not parts or any(set(p) != {"text"} for p in parts):
        return None
    return "\n\n".join(p["text"] for p in parts)


async def _local(http, body, log=None):
    """Last resort when every Gemini model failed: the same text task on the local Ollama (free, no quota).
    shortcut: long prompts are cut to OLLAMA_MAX characters, so a huge source list loses its end on this path only."""
    prompt = _text_only(body)
    if prompt is None:
        return None
    req = {"model": OLLAMA_MODEL, "stream": False, "think": False, "options": {"num_ctx": 32768},
           "messages": [{"role": "user", "content": prompt[:OLLAMA_MAX]}]}
    if (body.get("generationConfig") or {}).get("responseMimeType") == "application/json":
        req["format"] = "json"
    try:
        async with http.post(OLLAMA, json=req, timeout=aiohttp.ClientTimeout(total=600)) as r:
            text = (await r.json(content_type=None)).get("message", {}).get("content", "").strip()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
        if log:
            log(f"ollama: não respondeu ({e.__class__.__name__}); abra o Ollama para ter o plano B local")
        return None
    if log:
        log(f"ollama: {OLLAMA_MODEL} respondeu no lugar do Gemini" if text else "ollama: resposta vazia")
    return text or None
