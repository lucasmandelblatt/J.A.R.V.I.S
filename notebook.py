"""The Studio (NotebookLM-style) brain for projects: chat with numbered citations, the project's overview, topic tags,
and the Studio generators (audio overview, video overview, slides, mind map, reports, flashcards, quiz, infographic,
data table). Storage stays in projects.py's folders:

  projetos/<id>/notas.json          notes (the user's own and answers saved from the chat)
  projetos/<id>/studio/<aid>.json   one generated item: {"id","tipo","titulo","status","criado","opcoes","fontes","dados","erro"}
  projetos/<id>/studio/<aid>-N.wav  its audio (podcast: N=0; video: one per slide)
  projetos/colecoes.json            collections of projects

Everything is asked to a regular Gemini model in JSON mode; audio uses Gemini TTS (two hosts for the podcast).
"""
import asyncio
import base64
import datetime
import hashlib
import json
import re
import struct
import uuid

import aiohttp

import gem
import projects
from config import USER

MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash"]
TTS_MODEL = "gemini-3.8-flash-tts"
TTS_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
HOSTS = (("Ana", "Kore"), ("Beto", "Charon"))
NARRATOR = "Charon"
PASSAGE = 700   # characters per citable passage


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _json(text):
    """The JSON object in a model answer (tolerates a code fence)."""
    m = re.search(r"[\[{].*[\]}]", text, re.S)
    if not m:
        raise ValueError("a resposta não veio em JSON")
    return json.loads(m.group(0))


async def ask_json(http, key, prompt, parts=None, log=None, timeout=120):
    body = {"contents": [{"parts": (parts or []) + [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}}
    return _json(await gem.generate(http, key, body, MODELS, timeout=timeout, hedge=15, rounds=3, pause=(2, 6), log=log))


# ---------- Sources as numbered passages ----------

def ready_sources(proj, chosen=None):
    out = [s for s in proj.meta["fontes"] if s["status"] == "pronto"]
    return [s for s in out if s["id"] in chosen] if chosen else out


def passages(proj, chosen=None):
    """[(n, source, text)]: each ready source's analysis cut into paragraphs of about PASSAGE characters."""
    out = []
    for s in ready_sources(proj, chosen):
        buf = ""
        for para in re.split(r"\n\s*\n|\n(?=#)", proj.analysis(s["id"])):
            para = para.strip()
            if not para:
                continue
            if buf and len(buf) + len(para) > PASSAGE:
                out.append((len(out) + 1, s, buf))
                buf = ""
            buf = f"{buf}\n{para}".strip()
        if buf:
            out.append((len(out) + 1, s, buf))
    return out


def sources_text(proj, chosen=None, budget=250_000):
    parts = [f'### Fonte: {s["titulo"]} ({s["origem"]})\n{proj.analysis(s["id"])}' for s in ready_sources(proj, chosen)]
    return "\n\n".join(parts)[:budget]


# ---------- Chat with citations ----------

GOALS = {"padrao": "Responda como um assistente de pesquisa: claro, objetivo e completo.",
         "guia": "Aja como um guia de aprendizagem: explique passo a passo, use exemplos, verifique o entendimento e "
                 f"termine com uma pergunta curta que faça {USER} pensar."}
SIZES = {"padrao": "", "maior": "Responda de forma detalhada e longa.", "menor": "Responda de forma curta, em poucas linhas."}


async def chat(http, key, proj, question, chosen=None, log=None):
    ps = passages(proj, chosen)
    if not ps:
        return {"resposta": "Ainda não há fontes prontas selecionadas neste projeto. Adicione ou selecione fontes à esquerda.",
                "cit": {}, "sugestoes": []}
    cfg = proj.meta.get("chat") or {}
    goal = cfg.get("prompt") if cfg.get("objetivo") == "personalizado" and cfg.get("prompt") else GOALS.get(cfg.get("objetivo"), GOALS["padrao"])
    talk = "\n".join(f'{t["who"]}: {t["text"][:600]}' for t in proj.talk(12))
    prompt = f"""Você é o Jarvis, assistente de {USER}, respondendo dentro do projeto "{proj.title}".
{goal} {SIZES.get(cfg.get("tamanho"), "")}
Responda em português do Brasil, usando SOMENTE os trechos numerados abaixo. Depois de cada afirmação, cite o número do trecho
entre colchetes, ex.: [3] ou [3][8]. Nunca cite um número que não existe. Se as fontes não respondem, diga isso claramente.
Formate em Markdown simples: parágrafos curtos, **negrito** nos termos-chave, listas com "- " ou "1. ", títulos com "### " se ajudar.

Responda SOMENTE com JSON: {{"resposta": "markdown com as citações", "sugestoes": ["3 perguntas curtas de continuação"]}}

CONVERSA ANTERIOR:
{talk or "(nenhuma)"}

TRECHOS DAS FONTES:
""" + "\n\n".join(f"[{n}] (fonte: {s['titulo']})\n{t}" for n, s, t in ps)[:300_000] + f"\n\nPERGUNTA DE {USER}: {question}"
    data = await ask_json(http, key, prompt, log=log)
    text = str(data.get("resposta") or "").strip()
    by_n = {n: (s, t) for n, s, t in ps}
    cit = {}
    for n in sorted({int(x) for x in re.findall(r"\[(\d{1,4})\]", text)}):
        if n in by_n:
            s, t = by_n[n]
            cit[str(n)] = {"fonte": s["id"], "titulo": s["titulo"], "trecho": t}
    text = re.sub(r"\[(\d{1,4})\]", lambda m: m.group(0) if m.group(1) in cit else "", text)
    return {"resposta": text, "cit": cit, "sugestoes": [str(x) for x in (data.get("sugestoes") or [])][:3]}


# ---------- Project overview (the summary at the top of the chat) ----------

def sources_key(proj):
    return hashlib.sha1(json.dumps([(s["id"], s.get("lido")) for s in ready_sources(proj)]).encode()).hexdigest()[:12]


async def overview(http, key, proj, log=None):
    """{"texto","perguntas","emoji"} for the project's current sources (cached until the sources change)."""
    cached = proj.meta.get("resumo") or {}
    if cached.get("chave") == sources_key(proj):
        return cached
    if not ready_sources(proj):
        return {"texto": "", "perguntas": []}
    data = await ask_json(http, key, f"""Fontes do projeto "{proj.title}":\n\n{sources_text(proj, budget=150_000)}\n\n
Responda SOMENTE com JSON em português do Brasil: {{"titulo": "título curto e descritivo para o projeto (até 8 palavras)",
"emoji": "um emoji que represente o assunto", "texto": "um parágrafo de 3 a 5 frases resumindo o que as fontes tratam, com os
termos-chave em **negrito**", "perguntas": ["3 perguntas interessantes que {USER} poderia fazer sobre as fontes"]}}""", log=log)
    res = {"chave": sources_key(proj), "texto": str(data.get("texto", "")), "perguntas": [str(q) for q in data.get("perguntas", [])][:3],
           "titulo": str(data.get("titulo", ""))[:120], "emoji": str(data.get("emoji", ""))[:4]}
    proj.reload()
    proj.meta["resumo"] = res
    if not proj.meta.get("emoji") and res["emoji"]:
        proj.meta["emoji"] = res["emoji"]
    proj.save()
    return res


async def tag_sources(http, key, proj, log=None):
    """Groups the sources by topic: each one gets an "etiqueta"."""
    items = [{"id": s["id"], "titulo": s["titulo"], "inicio": proj.analysis(s["id"])[:600]} for s in ready_sources(proj)]
    if not items:
        return proj
    data = await ask_json(http, key, "Agrupe estas fontes por tópico, com 2 a 6 tópicos de 1 a 3 palavras em português. "
                          'Responda SOMENTE com JSON: {"etiquetas": {"<id da fonte>": "<tópico>"}}\n\n' + json.dumps(items, ensure_ascii=False), log=log)
    tags = data.get("etiquetas") or {}
    proj.reload()
    for s in proj.meta["fontes"]:
        if s["id"] in tags:
            s["etiqueta"] = str(tags[s["id"]])[:40]
    proj.save()
    return proj


# ---------- Notes ----------

def notes(proj):
    f = proj.folder / "notas.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def save_notes(proj, items):
    (proj.folder / "notas.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- Collections ----------

COLLECTIONS = projects.ROOT / "colecoes.json"


def collections():
    return json.loads(COLLECTIONS.read_text(encoding="utf-8")) if COLLECTIONS.exists() else []


def save_collections(items):
    projects.ROOT.mkdir(exist_ok=True)
    COLLECTIONS.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- Studio ----------

KINDS = {"audio": "Resumo de áudio", "video": "Resumo de vídeo", "slides": "Apresentação de slides", "mapa": "Mapa mental",
         "relatorio": "Relatório", "cartoes": "Cartões de estudo", "quiz": "Questionário", "infografia": "Infografia",
         "tabela": "Tabela de dados"}

REPORTS = {"briefing": "um documento de briefing (visão geral, pontos-chave, implicações, citações importantes)",
           "estudo": "um guia de estudo (resumo, conceitos-chave com definições, perguntas de revisão com respostas, glossário)",
           "blog": "um post de blog envolvente e bem estruturado",
           "faq": "uma lista de perguntas frequentes com respostas",
           "linha": "uma linha do tempo dos acontecimentos, com datas, e uma lista das pessoas/entidades principais"}

LENGTHS = {"curta": "curta", "padrao": "média", "longa": "longa"}


def _focus(o):
    return f'\nFoco e instruções de {USER}: {o["foco"]}' if o.get("foco") else ""


def prompt_for(kind, o):
    """The JSON-shaped request for each Studio item."""
    lang = "Escreva tudo em português do Brasil."
    if kind == "audio":
        fmt = {"conversa": "uma conversa aprofundada e animada entre os dois apresentadores, que se complementam",
               "breve": "um resumo breve e direto, só o essencial",
               "critica": "uma crítica construtiva: pontos fortes, fracos e o que poderia melhorar",
               "debate": "um debate em que cada apresentador defende um lado"}.get(o.get("formato"), "uma conversa aprofundada")
        turns = {"curta": "12 a 16", "longa": "40 a 50"}.get(o.get("duracao"), "24 a 30")
        return (f"Escreva o roteiro de um podcast sobre as fontes: {fmt}. Apresentadores: Ana e Beto. Tom natural, falado, com "
                f"exemplos e transições; nada de markdown, listas ou símbolos. {turns} falas.{_focus(o)} {lang}\n"
                'JSON: {"titulo": "...", "falas": [{"quem": "Ana" | "Beto", "texto": "..."}]}')
    if kind == "video":
        n = {"curta": "5", "longa": "10 a 12"}.get(o.get("duracao"), "7 a 8")
        return (f"Crie um vídeo explicativo narrado sobre as fontes, com {n} cenas.{_focus(o)} {lang} Cada cena tem um slide "
                "(título, até 4 tópicos curtos, um emoji grande que ilustra) e a narração falada daquela cena (3 a 5 frases, sem símbolos).\n"
                'JSON: {"titulo": "...", "cenas": [{"titulo": "...", "topicos": ["..."], "emoji": "🎯", "narracao": "..."}]}')
    if kind == "slides":
        n = {"curta": "6", "longa": "14 a 16"}.get(o.get("tamanho"), "9 a 11")
        style = ("slides de apoio para um apresentador: pouco texto, frases de impacto" if o.get("formato") == "apoio"
                 else "uma apresentação detalhada que se lê sozinha")
        return (f"Crie {style}, com {n} slides, sobre as fontes.{_focus(o)} {lang} Tipos de slide: capa, topicos, citacao, numeros, conclusao.\n"
                'JSON: {"titulo": "...", "slides": [{"tipo": "capa|topicos|citacao|numeros|conclusao", "titulo": "...", '
                '"subtitulo": "...", "topicos": ["..."], "numeros": [{"valor": "42%", "rotulo": "..."}], "citacao": "...", '
                '"autor": "...", "notas": "o que dizer neste slide"}]}')
    if kind == "mapa":
        return (f"Crie um mapa mental das fontes: um tema central, 4 a 7 ramos principais, cada um com 2 a 5 sub-ramos, e "
                f"sub-sub-ramos quando útil (no máximo 4 níveis). Rótulos curtos (até 6 palavras).{_focus(o)} {lang}\n"
                'JSON: {"titulo": "...", "raiz": {"rotulo": "...", "filhos": [{"rotulo": "...", "filhos": [...]}]}}')
    if kind == "relatorio":
        what = REPORTS.get(o.get("formato")) or (o.get("foco") and "o relatório pedido") or REPORTS["briefing"]
        return (f"Escreva {what} a partir das fontes, em Markdown (### títulos, listas com '- ', **negrito**, tabelas se "
                f"ajudar).{_focus(o)} {lang}\n" 'JSON: {"titulo": "...", "markdown": "..."}')
    if kind == "cartoes":
        n = {"menos": "10", "mais": "30"}.get(o.get("quantidade"), "20")
        lvl = {"facil": "fácil", "dificil": "difícil"}.get(o.get("dificuldade"), "média")
        return (f"Crie {n} cartões de estudo (flashcards) de dificuldade {lvl} sobre as fontes: frente com uma pergunta ou termo, "
                f"verso com a resposta curta.{_focus(o)} {lang}\n" 'JSON: {"titulo": "...", "cartoes": [{"frente": "...", "verso": "..."}]}')
    if kind == "quiz":
        n = {"menos": "5", "mais": "20"}.get(o.get("quantidade"), "10")
        lvl = {"facil": "fácil", "dificil": "difícil"}.get(o.get("dificuldade"), "média")
        return (f"Crie um questionário de {n} perguntas de múltipla escolha, dificuldade {lvl}, sobre as fontes. 4 opções por "
                f"pergunta, uma correta; uma dica e a explicação de cada opção.{_focus(o)} {lang}\n"
                'JSON: {"titulo": "...", "perguntas": [{"pergunta": "...", "dica": "...", "opcoes": [{"texto": "...", '
                '"correta": true, "explicacao": "..."}]}]}')
    if kind == "infografia":
        return (f"Crie o conteúdo de um infográfico vertical sobre as fontes: título, subtítulo, 3 a 4 números de destaque, "
                f"3 a 5 seções com emoji e texto curto, e uma conclusão.{_focus(o)} {lang}\n"
                'JSON: {"titulo": "...", "subtitulo": "...", "destaques": [{"valor": "...", "rotulo": "..."}], '
                '"secoes": [{"emoji": "📌", "titulo": "...", "texto": "...", "itens": ["..."]}], "conclusao": "..."}')
    if kind == "tabela":
        return (f"Extraia das fontes uma tabela de dados útil (entidades, datas, números, comparações), com 3 a 7 colunas e "
                f"quantas linhas fizer sentido.{_focus(o)} {lang}\n"
                'JSON: {"titulo": "...", "descricao": "...", "colunas": ["..."], "linhas": [["..."]]}')
    raise ValueError(f"tipo desconhecido: {kind}")


class Studio:
    def __init__(self, proj):
        self.proj = proj
        self.folder = proj.folder / "studio"

    def path(self, aid):
        return self.folder / f"{re.sub(r'[^a-z0-9-]', '', aid)}.json"

    def all(self):
        if not self.folder.exists():
            return []
        items = [json.loads(f.read_text(encoding="utf-8")) for f in self.folder.glob("*.json")]
        return sorted(items, key=lambda a: a["criado"], reverse=True)

    def get(self, aid):
        f = self.path(aid)
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None

    def save(self, item):
        self.folder.mkdir(exist_ok=True)
        tmp = self.path(item["id"]).with_suffix(".tmp")
        tmp.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path(item["id"]))

    def create(self, kind, options, chosen):
        item = {"id": uuid.uuid4().hex[:10], "tipo": kind, "titulo": KINDS[kind], "status": "gerando", "criado": now(),
                "opcoes": options, "fontes": chosen or [], "dados": None, "erro": None}
        self.save(item)
        return item

    def delete(self, aid):
        for f in list(self.folder.glob(f"{aid}*")):
            f.unlink()

    def audio(self, aid, n):
        return self.folder / f"{aid}-{int(n)}.wav"


async def generate(http, key, proj, item, log=None):
    """Fills one Studio item (runs in the background)."""
    st = Studio(proj)
    try:
        o = item["opcoes"] or {}
        src = sources_text(proj, item["fontes"] or None)
        if not src:
            raise RuntimeError("não há fontes prontas selecionadas")
        data = await ask_json(http, key, prompt_for(item["tipo"], o) + "\n\nFONTES:\n" + src, log=log, timeout=180)
        item["titulo"] = str(data.get("titulo") or item["titulo"])[:140]
        item["dados"] = data
        if item["tipo"] == "audio":
            lines = [(str(f.get("quem", "Ana")), str(f.get("texto", ""))) for f in data.get("falas", []) if f.get("texto")]
            wav = await podcast(http, key, lines, log=log)
            st.audio(item["id"], 0).write_bytes(wav)
            item["duracao"] = wav_seconds(wav)
        elif item["tipo"] == "video":
            total = 0.0
            for i, c in enumerate(data.get("cenas", [])):
                wav = await tts(http, key, [{"text": c.get("narracao") or c.get("titulo", "")}], log=log)
                st.audio(item["id"], i).write_bytes(wav)
                c["duracao"] = wav_seconds(wav)
                total += c["duracao"]
            item["duracao"] = total
        item["status"] = "pronto"
    except Exception as e:   # noqa: BLE001 — shown on the item's card
        if log:
            log(f"studio {item['tipo']} falhou: {e!r}")
        item["status"], item["erro"] = "erro", str(e)[:300]
    st.save(item)
    return item


# ---------- Text to speech (Gemini TTS, 24 kHz mono PCM in WAV) ----------

async def tts(http, key, parts, speakers=None, log=None):
    """WAV bytes for the text parts; with speakers, each part carries speechMetadata.speaker."""
    speech = ({"multiSpeakerVoiceConfig": {"speakerVoiceConfigs": [
        {"speaker": name, "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}} for name, voice in speakers]}}
        if speakers else {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": NARRATOR}}})
    body = {"contents": [{"parts": parts}], "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": speech}}
    last = ""
    for attempt in range(5):
        if attempt:
            await asyncio.sleep(4 * attempt)
        try:
            async with http.post(TTS_URL.format(TTS_MODEL), headers={"x-goog-api-key": key}, json=body,
                                 timeout=aiohttp.ClientTimeout(total=180)) as r:
                d = await r.json(content_type=None)
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            last = repr(e)
            continue
        if "error" in d:
            last = f'{d["error"].get("code")} {d["error"].get("message", "")[:160]}'
            if d["error"].get("code") == 400:
                break
            continue
        for p in ((d.get("candidates") or [{}])[0].get("content") or {}).get("parts", []):
            if p.get("inlineData"):
                raw = base64.b64decode(p["inlineData"]["data"])
                return raw if raw[:4] == b"RIFF" else wav_from_pcm(raw)
        last = "sem áudio na resposta"
    if log:
        log(f"tts falhou: {last}")
    raise RuntimeError(f"a voz falhou: {last}")


async def podcast(http, key, lines, log=None, per_call=14):
    names = {n for n, _ in HOSTS}
    chunks = [lines[i:i + per_call] for i in range(0, len(lines), per_call)]
    wavs = []
    for chunk in chunks:
        parts = [{"text": t, "speechMetadata": {"speaker": who if who in names else HOSTS[0][0]}} for who, t in chunk]
        wavs.append(await tts(http, key, parts, speakers=HOSTS, log=log))
    return join_wavs(wavs)


def pcm_of(wav):
    """The raw PCM inside a WAV file (walks the chunks)."""
    i = 12
    while i + 8 <= len(wav):
        cid, size = wav[i:i + 4], struct.unpack("<I", wav[i + 4:i + 8])[0]
        if cid == b"data":
            return wav[i + 8:i + 8 + size]
        i += 8 + size + (size & 1)
    return wav[44:]


def wav_from_pcm(pcm, rate=24000):
    return (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", len(pcm)) + pcm)


def join_wavs(wavs, gap=0.35):
    silence = b"\0\0" * int(24000 * gap)
    return wav_from_pcm(silence.join(pcm_of(w) for w in wavs))


def wav_seconds(wav):
    return round(len(pcm_of(wav)) / 48000, 1)


if __name__ == "__main__":   # self-check, no network
    a, b = wav_from_pcm(b"\1\0" * 2400), wav_from_pcm(b"\2\0" * 4800)
    j = join_wavs([a, b], gap=0.1)
    assert pcm_of(a) == b"\1\0" * 2400 and wav_seconds(j) == round((2400 + 2400 + 4800) / 24000, 1)
    assert _json('```json\n{"a": 1}\n```') == {"a": 1}
    for k in KINDS:
        assert "JSON" in prompt_for(k, {})
    print("ok")
