"""The user's calendar, kept by Jarvis: one file, same shape as the original calendar artifact
({"days": {"YYYY-MM-DD": {"date", "tasks": [{id, text, done, priority, note, link, files}], "updatedAt", "updatedBy"}}}),
so the artifact copy can be refreshed from it. Edited from the page (PUT a day) and by voice (the agenda tool)."""
import datetime
import json
import pathlib
import random
import string
import unicodedata

FILE = pathlib.Path(__file__).resolve().parent / "calendario.json"
ARTIFACT = "https://claude.ai/artifact/MXcB5Y4UPrKJjxjdPXfDVZ"


def load():
    if FILE.exists():
        return json.loads(FILE.read_text(encoding="utf-8"))
    return {"days": {}, "source": ARTIFACT}


def _write(data):
    tmp = FILE.with_suffix(".tmp")   # write then rename, so a crash never leaves half a calendar
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FILE)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def new_id():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


def set_day(date, tasks, by):
    """Replaces one day's tasks (an empty list removes the day). Returns the whole calendar."""
    datetime.date.fromisoformat(date)   # rejects anything that isn't YYYY-MM-DD
    clean = []
    for t in tasks:
        clean.append({"id": str(t.get("id") or new_id())[:20], "text": str(t.get("text", ""))[:500],
                      "done": bool(t.get("done")), "priority": bool(t.get("priority")),
                      "note": str(t.get("note", ""))[:8000], "link": str(t.get("link", ""))[:1000],
                      "files": [{"name": str(f.get("name", ""))[:300], "file": str(f.get("file", ""))[:300]}
                                for f in (t.get("files") or [])[:50] if isinstance(f, dict)]})
    data = load()
    if clean:
        data["days"][date] = {"date": date, "tasks": clean, "updatedAt": _now(), "updatedBy": by}
    else:
        data["days"].pop(date, None)
    _write(data)
    return data


def tasks(date):
    return list(load()["days"].get(date, {}).get("tasks", []))


def _norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn").strip()


def find(date, text):
    """The tasks of a day whose text contains `text` (accents and case ignored)."""
    n = _norm(text)
    return [t for t in tasks(date) if n and n in _norm(t["text"])]


def overdue(today):
    return [(d, t) for d, day in sorted(load()["days"].items()) if d < today for t in day["tasks"] if not t["done"]]


def summary(today):
    """A few lines for Jarvis's context: today, tomorrow and what is overdue."""
    tomorrow = (datetime.date.fromisoformat(today) + datetime.timedelta(days=1)).isoformat()
    line = lambda t: f"{'[feita] ' if t['done'] else ''}{'(prioridade) ' if t['priority'] else ''}{t['text']}"
    out = [f"Hoje ({today}): " + ("; ".join(line(t) for t in tasks(today)) or "nada marcado"),
           f"Amanhã ({tomorrow}): " + ("; ".join(line(t) for t in tasks(tomorrow)) or "nada marcado")]
    late = overdue(today)
    if late:
        out.append("Atrasadas: " + "; ".join(f"{t['text']} (de {d})" for d, t in late[-12:]))
    return "\n".join(out)


if __name__ == "__main__":   # self-check on a scratch file
    import tempfile
    FILE = pathlib.Path(tempfile.mkdtemp()) / "c.json"
    set_day("2026-11-06", [{"text": "Ligar para o contador"}, {"text": "MEI", "priority": True}], "jarvis")
    assert [t["text"] for t in find("2026-11-06", "contador")] == ["Ligar para o contador"]
    assert len(overdue("2026-11-07")) == 2 and "MEI" in summary("2026-11-06")
    set_day("2026-11-06", [], "lucas")
    assert load()["days"] == {}
    print("ok")
