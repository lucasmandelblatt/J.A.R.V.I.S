"""Jarvis's memory in the user's Obsidian vault, kept organized by the vault's own rules (VAULT-INDEX.md):
frontmatter on every note, wikilinks, folder indexes kept in sync, append before create.

08 - Jarvis/
  08 - Jarvis.md            folder index, plus the list of notes Jarvis wrote elsewhere in the vault
  Memória do Jarvis.md      durable facts by topic (Claude Code imports this file too)
  Conversas/Conversas.md    index of the daily transcripts
  Conversas/YYYY-MM-DD.md   one transcript per day; past days get a short "## Resumo" so Jarvis reads less
"""
import datetime
import difflib
import pathlib
import re
from config import HERE, USER, settings

WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
# The sections of the "Memória do Jarvis" note. config.json "vault_topics" renames any of them (the keys stay), e.g. to
# keep the headings an existing memory file already has.
TOPICS = {"quem": f"Quem é {USER}", "preferencias": "Preferências", "pessoas": "Pessoas",
          "projetos": "Projetos e ideias", "rotina": "Rotina e compromissos", "outros": "Outros",
          **settings().get("vault_topics", {})}
# Where Jarvis may write notes: area -> (folder, frontmatter project). config.json "vault_areas" replaces the default:
# {"area": {"pasta": "02 - Projetos", "projeto": "projetos", "descricao": "what goes there, for Gemini"}}. "inbox" is
# where a note goes when no area fits, so it always exists.
DEFAULT_AREAS = {
    "inbox": {"pasta": "00 - Inbox", "projeto": "inbox", "descricao": "ideias novas ou quando não souber"},
    "projetos": {"pasta": "01 - Projetos", "projeto": "projetos", "descricao": "trabalho e projetos em andamento"},
    "pessoal": {"pasta": "02 - Pessoal", "projeto": "pessoal", "descricao": "vida pessoal"},
    "referencia": {"pasta": "03 - Recursos", "projeto": "recursos", "descricao": "material de consulta"},
}
_areas = settings().get("vault_areas") or DEFAULT_AREAS
_areas.setdefault("inbox", DEFAULT_AREAS["inbox"])
AREAS = {k: (v["pasta"], v.get("projeto", k)) for k, v in _areas.items()}
AREA_HELP = "; ".join(f"{k} = {v.get('descricao', v['pasta'])}" for k, v in _areas.items())
KINDS = ("plan", "reference", "guide", "log")
STATUSES = ("active", "idea", "parked", "completed")


def _write(path, text, encoding="utf-8"):
    """Write then rename: a crash or an Obsidian save mid-write never leaves a note half-written (the day's transcript is
    the only copy). The temp name starts with a dot so Obsidian doesn't list it."""
    path = pathlib.Path(path)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding=encoding)
    tmp.replace(path)


class Vault:
    def __init__(self, root):
        self.root = pathlib.Path(root)
        self.folder = self.root / "08 - Jarvis"
        self.facts_file = self.folder / "Memória do Jarvis.md"
        self.talks = self.folder / "Conversas"
        self.talks_index = self.talks / "Conversas.md"
        self.index = self.folder / "08 - Jarvis.md"

    # ---------- setup ----------

    def ensure(self):
        self.talks.mkdir(parents=True, exist_ok=True)
        today = datetime.date.today().isoformat()
        if not self.index.exists():
            _write(self.index, f"""---
status: active
project: meta
type: index
created: {today}
---
# 08 - Jarvis

Memória do Jarvis, o assistente de voz de {USER} (app no Mac; código em `{HERE}`). O Jarvis escreve aqui \
sozinho a cada conversa, e o Claude Code lê a memória em toda sessão.

## Notes in this folder
- [[Memória do Jarvis]] — fatos duradouros sobre {USER}, organizados por assunto.
- [[Conversas]] — índice das transcrições diárias das conversas por voz.
""", encoding="utf-8")
        if "## Notas que o Jarvis escreveu" not in self.index.read_text(encoding="utf-8"):
            with open(self.index, "a", encoding="utf-8") as f:
                f.write("\n## Notas que o Jarvis escreveu\nNotas criadas ou atualizadas pelo Jarvis em outras pastas do cofre.\n")
        if not self.facts_file.exists():
            _write(self.facts_file, self._facts_header(today) + "".join(f"\n## {t}\n" for t in TOPICS.values()), encoding="utf-8")
        else:
            self._migrate_flat_facts()
        if not self.talks_index.exists():
            _write(self.talks_index, f"""---
status: active
project: personal
type: index
created: {today}
---
# Conversas

Transcrições das conversas por voz com o Jarvis, um arquivo por dia. Parte de [[08 - Jarvis]].

## Notes in this folder
""", encoding="utf-8")

    @staticmethod
    def _facts_header(created):
        return f"""---
status: active
project: personal
type: reference
created: {created}
---
# Memória do Jarvis

Fatos duradouros sobre {USER}, guardados pelo Jarvis (e por qualquer sessão do Claude Code), organizados por assunto. \
Um fato por linha, curto, com a data. O Jarvis atualiza um fato em vez de repetir. Pode editar à vontade.
"""

    def _migrate_flat_facts(self):
        """The first version kept one flat '## Fatos' list; move those lines under the topics."""
        text = self.facts_file.read_text(encoding="utf-8")
        # Only the exact old heading line: the words "## Fatos" inside a fact must not trigger a rewrite of the file.
        head = re.search(r"^## Fatos[ \t]*$", text, re.M)
        if not head:
            return
        old = [l for l in text[head.end():].splitlines() if l.startswith("- ")]
        created = re.search(r"^created: (.+)$", text, re.M)
        body = self._facts_header(created[1] if created else datetime.date.today().isoformat())
        for t in TOPICS.values():
            body += f"\n## {t}\n" + ("".join(l + "\n" for l in old) if t == TOPICS["preferencias"] else "")
        _write(self.facts_file, body, encoding="utf-8")

    # ---------- facts ----------

    def facts(self):
        """[{topic, text}] in file order."""
        if not self.facts_file.exists():
            return []
        out, topic = [], TOPICS["outros"]
        for line in self.facts_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                topic = line[3:].strip()
            elif line.startswith("- "):
                out.append({"topic": topic, "text": line[2:].strip()})
        return out

    def remember(self, fact, topic="outros"):
        """Adds a fact under its topic; a near-duplicate is replaced (an update), not repeated. Returns 'added' or 'updated'."""
        self.ensure()
        fact = " ".join(fact.split()).rstrip(".")
        heading = TOPICS.get(topic, TOPICS["outros"])
        stamp = f"- {fact}. ({datetime.date.today():%d/%m/%Y})"
        lines = self.facts_file.read_text(encoding="utf-8").splitlines()
        bare = lambda l: re.sub(r"\s*\(\d\d/\d\d/\d{4}\)$", "", l[2:]).rstrip(".").lower()
        for i, line in enumerate(lines):
            if line.startswith("- ") and difflib.SequenceMatcher(None, bare(line), fact.lower()).ratio() > 0.82:
                lines[i] = stamp
                _write(self.facts_file, "\n".join(lines) + "\n", encoding="utf-8")
                return "updated"
        if f"## {heading}" not in lines:
            lines += ["", f"## {heading}"]
        at = lines.index(f"## {heading}") + 1
        while at < len(lines) and not lines[at].startswith("## "):
            at += 1
        while at > 0 and not lines[at - 1].strip():   # insert right after the section's last line, before blank gaps
            at -= 1
        lines.insert(at, stamp)
        _write(self.facts_file, "\n".join(lines) + "\n", encoding="utf-8")
        return "added"

    def facts_about(self, subject):
        """Facts that mention every word of `subject` (accents and case ignored)."""
        words = [w for w in re.findall(r"\w+", _plain(subject)) if len(w) > 2]
        return [f for f in self.facts() if words and all(w in _plain(f["text"]) for w in words)]

    def replace_facts(self, subject, new_facts, topic="outros"):
        """'Substituir': drops every fact about `subject` and writes `new_facts` in its place. Returns the removed texts."""
        self.ensure()
        old = {f["text"] for f in self.facts_about(subject)}
        lines = [l for l in self.facts_file.read_text(encoding="utf-8").splitlines() if not (l.startswith("- ") and l[2:].strip() in old)]
        _write(self.facts_file, "\n".join(lines) + "\n", encoding="utf-8")
        for fact in new_facts:
            if fact.strip():
                self.remember(fact, topic)
        return sorted(old)

    def rewrite_note(self, title, content, area, kind, status, history_dir):
        """'Substituir' for a note: the note keeps its place and name but its body becomes the new version only.
        The old version is kept outside the vault, in `history_dir`, so the vault holds one truth. Returns (path, how)."""
        existing = self.find_note(title)
        if not existing:
            return self.write_note(title, content, area, kind, status)
        history = pathlib.Path(history_dir)
        history.mkdir(parents=True, exist_ok=True)
        (history / f"{existing.stem} — até {datetime.datetime.now():%Y-%m-%d %H%M}.md").write_text(
            existing.read_text(encoding="utf-8"), encoding="utf-8")
        old = existing.read_text(encoding="utf-8")
        front = re.match(r"\A---\n.*?\n---\n", old, re.S)
        front = front[0] if front else f"---\nstatus: {status}\nproject: personal\ntype: {kind}\n---\n"
        front = re.sub(r"^updated: .*\n", "", front, flags=re.M).replace("\n---\n", f"\nupdated: {datetime.date.today().isoformat()}\n---\n", 1) \
            if front.endswith("\n---\n") else front
        body = self._link(content.strip(), existing.stem)
        _write(existing, f"{front}# {existing.stem}\n\n{body}\n\n---\nReescrita pelo [[08 - Jarvis|Jarvis]] em "
                            f"{datetime.date.today():%d/%m/%Y} (versão anterior guardada fora do cofre).\n", encoding="utf-8")
        self._list_in_jarvis_index(existing.stem, existing.parent.name)
        return existing, "rewritten"

    # ---------- notes elsewhere in the vault ----------

    def find_note(self, title):
        name = self._filename(title)
        for p in self.root.rglob("*.md"):
            if ".obsidian" not in p.parts and p.stem.lower() == name.lower():
                return p
        return None

    @staticmethod
    def _filename(title):
        return re.sub(r'[\\/:*?"<>|#^\[\]]', "", " ".join(title.split())).strip()[:120] or "Sem título"

    def _note_names(self):
        skip = {"VAULT-INDEX"}
        return sorted({p.stem for p in self.root.rglob("*.md") if ".obsidian" not in p.parts and p.stem not in skip
                       and not re.match(r"\d{4}-\d\d-\d\d$", p.stem) and len(p.stem) > 3}, key=len, reverse=True)

    def _link(self, content, own):
        """Links the first mention of each existing note (people, brands, projects), never twice, never itself."""
        for name in self._note_names():
            if name == own or f"[[{name}" in content:
                continue
            m = re.search(rf"(?<![\w\[]){re.escape(name)}(?![\w\]])", content)
            if m and not content[:m.start()].count("`") % 2:
                content = content[:m.start()] + f"[[{name}]]" + content[m.end():]
        return content

    def write_note(self, title, content, area="inbox", kind="plan", status="active"):
        """Creates the note in its area folder, or appends a dated update when it already exists anywhere in the vault.
        Keeps the folder index and Jarvis's own list in sync. Returns (path, 'created'|'updated')."""
        self.ensure()
        folder_name, project = AREAS.get(area, AREAS["inbox"])
        kind = kind if kind in KINDS else "plan"
        status = status if status in STATUSES else "active"
        name = self._filename(title)
        content = self._link(content.strip(), name)
        today = datetime.date.today()
        existing = self.find_note(name)
        if existing:
            with open(existing, "a", encoding="utf-8") as f:
                f.write(f"\n\n## Atualização — {today:%d/%m/%Y}\n\n{content}\n")
            self._list_in_jarvis_index(existing.stem, existing.parent.name)
            return existing, "updated"
        path = self.root / folder_name / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        _write(path, f"""---
status: {status}
project: {project}
type: {kind}
created: {today.isoformat()}
---
# {name}

{content}

---
Criada pelo [[08 - Jarvis|Jarvis]] em {today:%d/%m/%Y}.
""", encoding="utf-8")
        self._add_to_folder_index(path.parent, name, content)
        self._list_in_jarvis_index(name, folder_name)
        return path, "created"

    def read_note(self, title):
        p = self.find_note(title)
        if not p:
            return None
        return re.sub(r"\A---\n.*?\n---\n", "", p.read_text(encoding="utf-8"), count=1, flags=re.S).strip()

    @staticmethod
    def _summary_line(content):
        text = re.sub(r"[#*_`>\[\]]", "", content).strip()
        first = re.split(r"(?<=[.!?])\s|\n", text, maxsplit=1)[0]
        return (first[:117] + "…") if len(first) > 120 else first

    def _add_to_folder_index(self, folder, name, content):
        index = next((p for p in folder.glob("*.md") if re.search(r"^type: index$", p.read_text(encoding="utf-8"), re.M)), None)
        if index is None:
            return
        lines = index.read_text(encoding="utf-8").splitlines()
        if any(f"[[{name}]]" in l for l in lines):
            return
        lines = [l for l in lines if not re.match(r"^\*\((Vazio|Nenhuma nota)", l.strip())]
        if "## Notes in this folder" not in lines:
            lines += ["", "## Notes in this folder"]
        at = lines.index("## Notes in this folder") + 1
        while at < len(lines) and not lines[at].startswith("## "):
            at += 1
        while at > 0 and not lines[at - 1].strip():
            at -= 1
        lines.insert(at, f"- [[{name}]] — {self._summary_line(content)}")
        _write(index, "\n".join(lines) + "\n", encoding="utf-8")

    def _list_in_jarvis_index(self, name, folder_name):
        text = self.index.read_text(encoding="utf-8")
        if f"[[{name}]]" not in text.split("## Notas que o Jarvis escreveu", 1)[-1]:
            with open(self.index, "a", encoding="utf-8") as f:
                f.write(f"- [[{name}]] ({folder_name})\n")

    def jarvis_notes(self):
        text = self.index.read_text(encoding="utf-8") if self.index.exists() else ""
        part = text.split("## Notas que o Jarvis escreveu", 1)[-1] if "## Notas que o Jarvis escreveu" in text else ""
        return re.findall(r"^- \[\[(.+?)\]\]", part, re.M)

    # ---------- conversations ----------

    def log_turn(self, who, text):
        text = " ".join(text.split())
        if not text:
            return
        self.ensure()
        now = datetime.datetime.now()
        day = self.talks / f"{now:%Y-%m-%d}.md"
        if not day.exists():
            d = now.date()
            _write(day, f"""---
status: active
project: personal
type: log
created: {d.isoformat()}
---
# Conversas com o Jarvis — {WEEKDAYS[d.weekday()]}, {d:%d/%m/%Y}

Parte de [[Conversas]].

""", encoding="utf-8")
            with open(self.talks_index, "a", encoding="utf-8") as f:
                f.write(f"- [[{d.isoformat()}]] — conversas de {d:%d/%m/%Y}.\n")
        with open(day, "a", encoding="utf-8") as f:
            f.write(f"- **{now:%H:%M} {who}:** {text}\n")

    def day_files(self):
        return sorted(self.talks.glob("????-??-??.md"))

    @staticmethod
    def spoken_lines(path):
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^- \*\*(\d\d:\d\d) (.+?):\*\* (.*)$", line)
            if m:
                out.append({"day": path.stem, "time": m[1], "who": m[2], "text": m[3]})
        return out

    def transcript_lines(self, limit):
        lines = []
        for p in self.day_files()[-4:]:
            lines += self.spoken_lines(p)
        return lines[-limit:]

    @staticmethod
    def summary(path):
        m = re.search(r"^## Resumo\n(.*?)(?=^## |^- \*\*|\Z)", path.read_text(encoding="utf-8"), re.S | re.M)
        return m[1].strip() if m else ""

    def days_needing_summary(self):
        today = datetime.date.today().isoformat()
        return [p for p in self.day_files() if p.stem < today and not self.summary(p) and self.spoken_lines(p)]

    def set_summary(self, path, text):
        body = path.read_text(encoding="utf-8")
        anchor = "Parte de [[Conversas]].\n"
        block = f"\n## Resumo\n{text.strip()}\n\n## Transcrição\n"
        body = body.replace(anchor, anchor + block, 1) if anchor in body else body + block
        _write(path, body, encoding="utf-8")
        for line in self.talks_index.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"- [[{path.stem}]]"):
                first = self._summary_line(text)
                idx = self.talks_index.read_text(encoding="utf-8").replace(line, f"- [[{path.stem}]] — {first}")
                _write(self.talks_index, idx, encoding="utf-8")
                break

    # ---------- what Jarvis reads when a conversation starts ----------

    def context(self, conversations=True):
        parts = []
        index = self.root / "VAULT-INDEX.md"
        if index.exists():
            t = index.read_text(encoding="utf-8")
            who = "\n\n".join(s for s in (_section(t, "Who I Am"), _section(t, "Key People")) if s)
            if who:
                parts.append(f"Quem é {USER} (do cofre do Obsidian):\n" + who[:3000])
        prio = self.root / "Active Priorities.md"
        if prio.exists():
            open_items = [l for l in prio.read_text(encoding="utf-8").splitlines() if l.startswith("- [ ]")]
            if open_items:
                parts.append(f"Prioridades abertas de {USER}:\n" + "\n".join(open_items[:15]))
        facts = self.facts()
        if facts:
            by_topic = {}
            for f in facts:
                by_topic.setdefault(f["topic"], []).append(f["text"])
            parts.append(f"O que você já sabe sobre {USER} (Memória do Jarvis):\n" + "\n".join(
                f"{t}:\n" + "\n".join("- " + x for x in xs[-40:]) for t, xs in by_topic.items()))
        notes = self.jarvis_notes()
        if notes:
            parts.append("Notas que você já escreveu no cofre (leia com ler_nota antes de continuar um assunto delas): "
                         + "; ".join(notes[-40:]))
        if not conversations:   # inside a project only who the user is matters, not the everyday chat
            return "\n\n".join(parts)
        days = self.day_files()
        summaries = [f"{p.stem}: {self.summary(p)}" for p in days[-15:-1] if self.summary(p)]
        if summaries:
            parts.append("Resumo das conversas dos últimos dias:\n" + "\n".join(summaries))
        recent = [x for p in days[-2:] for x in self.spoken_lines(p) if p.stem == datetime.date.today().isoformat() or not self.summary(p)]
        if recent:
            text = "\n".join(f"[{x['day']} {x['time']}] {x['who']}: {x['text']}" for x in recent)[-12000:]
            parts.append("Conversa mais recente (para continuar de onde parou):\n" + text)
        return "\n\n".join(parts)


def _plain(text):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def _section(text, heading):
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, flags=re.S | re.M)
    return m.group(1).strip() if m else ""
