"""Projects: separate study rooms inside Jarvis. Each one keeps its own sources (videos and their analyses) and its own
conversation, so what is said in one never mixes with another or with the everyday chat.

On disk, in jarvis-voz/projetos/<id>/:
  projeto.json            title, dates, sources
  conversa.jsonl          one line per turn: {"t": "2026-11-05 10:12", "who": "Ana", "text": "..."}
  fontes/<fonte>.md       the full analysis of each video
  fontes/<fonte>/video.*  the video itself, for sources that aren't on YouTube
  fontes/<fonte>/AAAA-MM-DD.md  each day's reading of a site marked "diario"
  arquivos/               documents and videos dropped into the project

Source types: youtube / url / file are videos; site is a web page (optionally read every day); doc is a document.
"""
import datetime
import json
import pathlib
import re
import shutil
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent / "projetos"


def slug(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:48] or "projeto"


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


class Project:
    def __init__(self, folder):
        self.folder = pathlib.Path(folder)
        self.meta_file = self.folder / "projeto.json"
        self.talk_file = self.folder / "conversa.jsonl"
        self.meta = json.loads(self.meta_file.read_text(encoding="utf-8"))

    @property
    def id(self):
        return self.folder.name

    @property
    def title(self):
        return self.meta["titulo"]

    def reload(self):
        self.meta = json.loads(self.meta_file.read_text(encoding="utf-8"))
        return self

    def save(self):
        self.meta["atualizado"] = now()
        tmp = self.meta_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.meta, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.meta_file)

    # Sources
    def add_source(self, src):
        self.reload()
        used = [int(x["id"][:2]) for x in self.meta["fontes"] if x["id"][:2].isdigit()]
        sid = f"{max(used, default=0) + 1:02d}-{slug(src['title'])[:32]}"
        entry = {"id": sid, "tipo": src["kind"], "origem": src["source"], "titulo": src["title"],
                 "duracao": src.get("duration") or 0, "status": src.get("status", "assistindo"), "adicionado": now()}
        if src.get("diario"):
            entry["diario"] = True
        self.meta["fontes"].append(entry)
        self.save()
        return entry

    def source(self, sid):
        return next((s for s in self.meta["fontes"] if s["id"] == sid), None)

    def update_source(self, sid, **fields):
        s = self.reload().source(sid)
        if s:
            s.update(fields)
            self.save()
        return s

    def source_dir(self, sid):
        return self.folder / "fontes" / sid

    def analysis_file(self, sid):
        return self.folder / "fontes" / f"{sid}.md"

    def set_analysis(self, sid, text):
        f = self.analysis_file(sid)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")

    def analysis(self, sid):
        f = self.analysis_file(sid)
        return f.read_text(encoding="utf-8") if f.exists() else ""

    def remove_source(self, sid):
        self.reload()
        self.meta["fontes"] = [s for s in self.meta["fontes"] if s["id"] != sid]
        self.save()
        for p in (self.analysis_file(sid), self.source_dir(sid)):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink()

    def watch_source(self, entry):
        """What video.Watcher needs to show this source to Gemini again."""
        src = {"kind": entry["tipo"], "source": entry["origem"], "title": entry["titulo"], "duration": entry.get("duracao", 0)}
        if entry["tipo"] == "url":
            found = sorted(self.source_dir(entry["id"]).glob("video.*"))
            src["local"] = str(found[0]) if found else None
        elif entry["tipo"] == "file":
            src["local"] = entry.get("local") or entry["origem"]
        return src

    # Conversation
    def log(self, who, text):
        text = " ".join(text.split())
        if text:
            with open(self.talk_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": now(), "who": who, "text": text}, ensure_ascii=False) + "\n")

    def log_entry(self, who, text, **extra):
        """A turn that keeps its formatting and extras (the Studio chat: citations, suggestions)."""
        with open(self.talk_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": now(), "who": who, "text": text.strip(), **extra}, ensure_ascii=False) + "\n")

    def talk(self, limit=None):
        if not self.talk_file.exists():
            return []
        lines = [json.loads(l) for l in self.talk_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        return lines[-limit:] if limit else lines

    # What Gemini reads when the project is open
    def context(self, budget=180_000):
        parts = [f'PROJETO ABERTO: "{self.title}". Você está numa sessão de estudo separada da conversa do dia a dia. '
                 "Tudo o que importa aqui são as fontes abaixo e a conversa deste projeto."]
        manual = self.folder / "manual.md"   # course mode: what Jarvis learned from the whole course, kept up to date
        if manual.exists():
            parts.append("MANUAL DE EXECUÇÃO do curso deste projeto (o que você aprendeu aula por aula; é com ele que você "
                         "vai executar o negócio):\n" + manual.read_text(encoding="utf-8"))
        ready = [s for s in self.meta["fontes"] if s["status"] == "pronto"]
        pending = [s for s in self.meta["fontes"] if s["status"] != "pronto"]
        kind = {"site": "site", "doc": "documento"}
        texts = {s["id"]: self.analysis(s["id"]) for s in ready}
        # Too much to send whole: send each source's overview and let buscar_memoria fetch the details on demand,
        # instead of silently cutting the last sources off.
        short = sum(map(len, texts.values())) > budget // 2
        if short:
            parts.append("As fontes abaixo vêm só com a visão geral (o projeto é grande). Para qualquer detalhe, use "
                         "buscar_memoria antes de responder.")
        for s in ready:
            label = kind.get(s["tipo"], "vídeo")
            if s.get("diario"):
                label += f', lido todo dia; leitura de {s.get("lido", "?")}'
            text = texts[s["id"]]
            if short and len(text) > 1500:
                text = text[:1500].rsplit("\n", 1)[0] + "\n[…resto via buscar_memoria]"
            parts.append(f'### Fonte {s["id"]} ({label}): {s["titulo"]} ({s["origem"]})\n{text}')
        if pending:
            parts.append("Fontes ainda sem análise: " + "; ".join(f'{s["titulo"]} ({s["status"]})' for s in pending))
        if not self.meta["fontes"]:
            parts.append("Este projeto ainda não tem fontes. Vídeos: assistir_video; sites e notícias: fonte_projeto.")
        talk = self.talk(80)
        if talk:
            parts.append("Conversa anterior neste projeto (as mais recentes por último):\n" +
                         "\n".join(f'- {t["t"]} {t["who"]}: {t["text"]}' for t in talk))
        text = "\n\n".join(parts)
        return text[:budget]

    def summary(self):
        return {"id": self.id, "titulo": self.title, "criado": self.meta["criado"], "atualizado": self.meta["atualizado"],
                "emoji": self.meta.get("emoji") or "", "fixado": bool(self.meta.get("fixado")), "colecoes": self.meta.get("colecoes") or [],
                "fontes": [{k: s.get(k) for k in ("id", "tipo", "origem", "titulo", "duracao", "status", "erro", "diario", "lido", "etiqueta", "gravado")}
                           for s in self.meta["fontes"]],
                "mensagens": sum(1 for _ in open(self.talk_file, encoding="utf-8")) if self.talk_file.exists() else 0}


def create(title):
    ROOT.mkdir(exist_ok=True)
    base = slug(title)
    folder, n = ROOT / base, 2
    while folder.exists():
        folder, n = ROOT / f"{base}-{n}", n + 1
    folder.mkdir(parents=True)
    (folder / "projeto.json").write_text(json.dumps(
        {"titulo": title.strip()[:120] or "Projeto", "criado": now(), "atualizado": now(), "fontes": []},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return Project(folder)


def all_projects():
    if not ROOT.exists():
        return []
    found = [Project(f) for f in ROOT.iterdir() if (f / "projeto.json").exists()]
    return sorted(found, key=lambda p: p.meta["atualizado"], reverse=True)


def get(pid):
    f = ROOT / pathlib.Path(pid or "").name
    return Project(f) if pid and (f / "projeto.json").exists() else None


def find(name):
    """A project by id or by (part of) its title, ignoring accents and case."""
    p = get(name)
    if p:
        return p
    key = slug(name)
    projs = all_projects()
    return (next((p for p in projs if slug(p.title) == key), None)
            or next((p for p in projs if key and key in slug(p.title)), None))


def copy(pid):
    """A copy of the project (sources, notes and Studio items; not the conversation)."""
    p = get(pid)
    if not p:
        return None
    new = create("Cópia de " + p.title)
    shutil.rmtree(new.folder)
    shutil.copytree(p.folder, new.folder, ignore=shutil.ignore_patterns("conversa.jsonl"))
    new = Project(new.folder)
    new.meta.update(titulo="Cópia de " + p.title, criado=now(), fixado=False)
    new.save()
    return new


def rename(pid, title):
    p = get(pid)
    if p:
        p.meta["titulo"] = title.strip()[:120]
        p.save()
    return p


def delete(pid):
    """Moves the project folder to the Mac's Trash (recoverable)."""
    p = get(pid)
    if not p:
        return False
    trash = pathlib.Path.home() / ".Trash" / f"Jarvis - {p.id}"
    shutil.move(str(p.folder), str(trash))
    return True
