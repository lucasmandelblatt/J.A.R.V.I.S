"""Jarvis watches videos: Gemini sees the picture (1 frame per second) and hears the sound together, not just a transcript.

- YouTube (public): the link goes straight to Gemini.
- Any other site yt-dlp knows (Instagram, TikTok, X, Vimeo...) and files on the Mac: the video is kept in the project
  folder and uploaded to Google's Files API when Gemini needs it (Google deletes uploads after 48 hours).
- Long videos are watched in 20-minute parts, two at a time, and then joined into one analysis.
"""
import asyncio
import json
import mimetypes
import pathlib
import re
import time

import aiohttp

import gem
import paths
from config import USER

API = "https://generativelanguage.googleapis.com"
# Video: the best models first, one at a time (a whole video is too many tokens to send to two models at once).
MODELS = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"]
PART = 20 * 60          # seconds per part for long videos
LOW_RES_AFTER = 30 * 60  # longer videos use low resolution (66 tokens a frame instead of 258)
YOUTUBE = re.compile(r"^https?://(?:(?:www\.|m\.|music\.)?youtube\.com/(?:watch\?\S*\bv=|shorts/|live/)|youtu\.be/)\S+$", re.I)

ANALYSIS = """Você é o analista de vídeos do Jarvis, o assistente de {user}. Assista ao vídeo inteiro com atenção, \
vendo a imagem e ouvindo o áudio, e escreva uma análise completa em português do Brasil, em Markdown, para {user} \
estudar e para o Jarvis responder perguntas depois sem precisar assistir de novo.

Regras:
- Separe sempre o que APARECE NA TELA do que é FALADO. Textos, slides, gráficos, tabelas, código, demonstrações, \
pessoas e lugares contam como tela.
- Use marcações de tempo [MM:SS] (ou [H:MM:SS]) do vídeo{offset_rule}.
- Copie com exatidão números, nomes, fórmulas, código e textos importantes da tela.
- Nunca invente. Se não houver fala, diga "sem fala". Se algo estiver ilegível ou cortado, diga isso.

Formato:
## Visão geral
3 a 6 frases: do que trata, quem fala, para quem é, a mensagem central.

## Linha do tempo
Um item por momento importante (a cada mudança de assunto, slide ou cena; não pule partes):
- **[MM:SS] Título curto** — Na tela: ... | Fala: ...

## Conceitos e ideias principais
Cada conceito com uma explicação clara e didática, citando onde aparece [MM:SS].

## Dados, números e referências
Tudo que for número, data, nome, livro, ferramenta, link ou fonte citada, com [MM:SS].

## Glossário
Termos técnicos com uma definição simples.

## Pontos que merecem atenção
Exemplos práticos, avisos, dúvidas que ficaram em aberto ou afirmações que valem conferir."""

JOIN = """Abaixo estão as análises de cada parte de um mesmo vídeo, em ordem. Junte tudo numa análise única em \
português do Brasil, em Markdown, com estas seções: ## Visão geral (do vídeo inteiro), ## Linha do tempo (todos os \
itens, em ordem, sem cortar nenhum), ## Conceitos e ideias principais, ## Dados, números e referências, ## Glossário, \
## Pontos que merecem atenção. Mantenha todas as marcações de tempo e todos os detalhes; só tire repetições. \
Não acrescente nada que não esteja nas partes."""

# Course mode: the Jarvis is a student who will have to DO what the course teaches, so the analysis is a lesson notebook.
LESSON = """Você é o Jarvis, o assistente de {user}, estudando um curso como um aluno dedicado. Depois do curso inteiro você \
vai EXECUTAR o que foi ensinado, então nada pode faltar. Assista à aula inteira, vendo a imagem e ouvindo o áudio, e \
escreva o caderno desta aula em português do Brasil, em Markdown.{speed_rule}

Regras:
- Nunca invente e nunca resuma demais: cada passo, número, ferramenta, configuração, nome, link e exemplo ensinado \
precisa estar aqui. Copie com exatidão o que aparece na tela (textos, slides, telas de programas, valores).
- Separe o que APARECE NA TELA do que é FALADO quando isso importar.
- Use marcações de tempo [MM:SS] (ou [H:MM:SS]) do vídeo{offset_rule}.
- Se algo estiver ilegível, cortado ou sem fala, diga isso.

Formato:
## Visão geral
Do que trata a aula, o objetivo dela e onde ela se encaixa no curso (3 a 6 frases).

## Passo a passo ensinado
Lista NUMERADA, na ordem da aula, de tudo o que o aluno deve fazer, com o detalhe exato de como fazer \
(onde clicar, o que configurar, o que escrever, quais critérios usar), citando [MM:SS]. Não pule etapas.

## Estratégias e o porquê
Cada estratégia ou princípio ensinado, com a explicação do professor de por que funciona.

## Ferramentas, números e referências
Tudo que for ferramenta, site, preço, métrica, meta, prazo, nome, canal, livro ou fonte citada, com [MM:SS].

## Exemplos e casos mostrados
Os exemplos reais mostrados, com os números e o que se aprende de cada um.

## Erros a evitar
Avisos, armadilhas e o que o professor diz para não fazer.

## Tarefas para executar
O que o aluno precisa fazer depois desta aula, como uma lista de ações concretas (checklist).

## Linha do tempo
- **[MM:SS] Título curto** — Na tela: ... | Fala: ...

## Glossário
Termos técnicos com uma definição simples."""

JOIN_LESSON = """Abaixo estão os cadernos de cada parte de uma mesma aula, em ordem. Junte tudo num caderno único em \
português do Brasil, em Markdown, com as mesmas seções (## Visão geral, ## Passo a passo ensinado, ## Estratégias e o \
porquê, ## Ferramentas, números e referências, ## Exemplos e casos mostrados, ## Erros a evitar, ## Tarefas para \
executar, ## Linha do tempo, ## Glossário). Mantenha todos os passos, na ordem, com a numeração refeita, e todas as \
marcações de tempo e detalhes; só tire repetições. Não acrescente nada que não esteja nas partes."""

CLIP = """Assista a este trecho do vídeo (imagem e áudio) e responda em português do Brasil, de forma clara e \
didática, para ser lida em voz alta (sem markdown). Diga o que aparece na tela e o que é falado quando importar, com o \
minuto exato. Se o trecho não mostrar ou não disser algo necessário, diga isso. Pergunta de {user}: {question}"""


def stamp(seconds):
    s = int(seconds)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


async def _run(*cmd, timeout=120):
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"{pathlib.Path(cmd[0]).name} passou de {timeout} s")
    if proc.returncode != 0:
        lines = [l for l in err.decode(errors="replace").splitlines() if "ERROR" in l] or err.decode(errors="replace").splitlines()
        raise RuntimeError((lines[-1] if lines else "falhou")[:300])
    return out.decode(errors="replace")


async def describe(source):
    """{'kind': youtube|url|file, 'source', 'title', 'duration'} without downloading the video."""
    if re.match(r"^https?://", source):
        try:
            info = json.loads(await _run(paths.ytdlp(), "-J", "--no-playlist", "--no-warnings", source, timeout=60))
        except RuntimeError as e:
            if not YOUTUBE.match(source):
                raise RuntimeError(f"Não consegui abrir esse vídeo ({e}). Se for privado ou pedir login, dá para assistir gravando a tela (gravar_tela, ou Gravar da tela no Studio).")
            info = {}
        return {"kind": "youtube" if YOUTUBE.match(source) else "url", "source": source,
                "title": info.get("title") or source, "duration": float(info.get("duration") or 0)}
    path = pathlib.Path(source).expanduser()
    if not path.exists():
        raise RuntimeError(f"Não achei o arquivo {path}.")
    try:
        dur = float((await _run(paths.ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path))).strip() or 0)
    except (RuntimeError, ValueError):
        dur = 0
    return {"kind": "file", "source": str(path), "title": path.stem, "duration": dur}


async def download(url, folder):
    """Saves a non-YouTube video (720p at most) in the project folder and returns its path."""
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / "video.%(ext)s"
    await _run(paths.ytdlp(), "--no-playlist", "--no-warnings", "-f", "bv*[height<=720]+ba/b[height<=720]/b",
               "--merge-output-format", "mp4", "-o", str(out), url, timeout=900)
    found = sorted(folder.glob("video.*"))
    if not found:
        raise RuntimeError("o download terminou sem arquivo")
    return found[0]


async def upload(http, key, path):
    """Uploads a file to the Gemini Files API, waits until Google has processed it, and returns its uri."""
    path = pathlib.Path(path)
    mime = mimetypes.guess_type(path.name)[0] or "video/mp4"
    size = path.stat().st_size
    if size > 2 * 1024 ** 3:
        raise RuntimeError("o vídeo passa de 2 GB, o limite da conta gratuita do Gemini")
    async with http.post(f"{API}/upload/v1beta/files", headers={
            "x-goog-api-key": key, "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(size), "X-Goog-Upload-Header-Content-Type": mime},
            json={"file": {"display_name": path.name[:100]}}) as r:
        target = r.headers.get("X-Goog-Upload-URL")
        if not target:
            raise RuntimeError(f"o Google recusou o envio: {(await r.text())[:200]}")
    with open(path, "rb") as f:
        async with http.post(target, data=f, headers={"X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize",
                                                       "Content-Length": str(size)},
                             timeout=aiohttp.ClientTimeout(total=1800)) as r:
            info = (await r.json(content_type=None)).get("file") or {}
    name = info.get("name")
    if not name:
        raise RuntimeError("o envio para o Google não terminou")
    for _ in range(180):   # processing usually takes seconds; long videos up to a few minutes
        if info.get("state") == "ACTIVE":
            return info["uri"], mime
        if info.get("state") == "FAILED":
            raise RuntimeError("o Google não conseguiu processar esse vídeo")
        await asyncio.sleep(2)
        async with http.get(f"{API}/v1beta/{name}", headers={"x-goog-api-key": key}) as r:
            info = await r.json(content_type=None)
    raise RuntimeError("o Google demorou demais para processar o vídeo")


class Watcher:
    """Watches one source. Keeps the uploaded file's uri for 46 hours so follow-up questions don't upload again."""

    def __init__(self, http, key, log=None):
        self.http, self.key, self.log = http, key, log
        self.uploads = {}   # local path -> (uri, mime, time)

    async def video_part(self, src):
        """The part that shows Gemini the video: a YouTube link or an uploaded file."""
        if src["kind"] == "youtube":
            return {"fileData": {"fileUri": src["source"]}}
        local = src["local"]
        cached = self.uploads.get(local)
        if not cached or time.time() - cached[2] > 46 * 3600:
            uri, mime = await upload(self.http, self.key, local)
            cached = self.uploads[local] = (uri, mime, time.time())
        return {"fileData": {"fileUri": cached[0], "mimeType": cached[1]}}

    async def ask(self, src, prompt, start=None, end=None, low_res=False, max_tokens=None, timeout=600):
        part = dict(await self.video_part(src))
        if start is not None or end is not None:
            part["videoMetadata"] = {k: f"{int(v)}s" for k, v in (("startOffset", start), ("endOffset", end)) if v is not None}
        config = {"temperature": 0.2}
        if low_res:
            config["mediaResolution"] = "MEDIA_RESOLUTION_LOW"
        if max_tokens:
            config["maxOutputTokens"] = max_tokens
        body = {"contents": [{"parts": [part, {"text": prompt}]}], "generationConfig": config}
        # How long a healthy model needs grows with the stretch watched; past that, the next model starts alongside.
        span = ((end if end is not None else src.get("duration") or 600) - (start or 0))
        hedge = min(240, 40 + span * 0.12)
        return await gem.generate(self.http, self.key, body, MODELS, timeout=timeout, hedge=hedge, rounds=3,
                                  pause=(5, 15), log=self.log)

    async def analyze(self, src, progress=None, lesson=False, speed=1):
        """The full Markdown analysis of the whole video, starting at its first heading (no "Here is..." preamble).
        lesson: the course-mode notebook (LESSON) instead of the general analysis; speed: how fast it was played."""
        text = await self._analyze(src, progress, lesson, speed)
        i = text.find("## ")
        return text[i:] if 0 < i < 400 else text

    async def _analyze(self, src, progress=None, lesson=False, speed=1):
        speed_rule = (f" A aula foi gravada em velocidade {speed:g}x: a fala está acelerada, preste atenção redobrada a "
                      f"cada palavra; as marcações de tempo são as do arquivo gravado." if speed != 1 else "")
        template = (lambda rule: LESSON.format(user=USER, offset_rule=rule, speed_rule=speed_rule)) if lesson else \
            (lambda rule: ANALYSIS.format(user=USER, offset_rule=rule))
        dur = src.get("duration") or 0
        low = dur > LOW_RES_AFTER
        if dur <= PART * 1.25:
            return await self.ask(src, template(""), low_res=low)
        parts = [(s, min(s + PART, dur)) for s in range(0, int(dur), PART)]
        done = [None] * len(parts)
        gate = asyncio.Semaphore(2)

        async def one(i, s, e):
            async with gate:
                rule = (f". Este pedido mostra só o trecho de {stamp(s)} a {stamp(e)}: use os tempos do vídeo inteiro "
                        f"(o trecho começa em [{stamp(s)}]) e analise só esse trecho")
                done[i] = f"### Parte {i + 1} ({stamp(s)} a {stamp(e)})\n\n" + await self.ask(src, template(rule), s, e, low_res=low)
                if progress:
                    await progress(f"Parte {i + 1} de {len(parts)} assistida")

        await asyncio.gather(*(one(i, s, e) for i, (s, e) in enumerate(parts)))
        body = {"contents": [{"parts": [{"text": (JOIN_LESSON if lesson else JOIN) + "\n\n" + "\n\n".join(done)}]}], "generationConfig": {"temperature": 0.2}}
        try:
            return await gem.generate(self.http, self.key, body, MODELS, timeout=300, hedge=60, rounds=3, log=self.log)
        except gem.GeminiError:
            return "\n\n".join(done)   # the parts themselves are still a complete analysis

    async def clip(self, src, question, start=None, end=None):
        """Re-watches a stretch (or the whole video) to answer one precise question."""
        if start is not None and end is None:
            end = start + 120
        if start is not None:
            start = max(0, start - 15)   # a little context before the moment
        return await self.ask(src, CLIP.format(user=USER, question=question), start, end, low_res=False, timeout=300)
