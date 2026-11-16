"""The user's notes, the iPhone Notes way: folders and notes, the first line of a note is its title.
One file, {"folders": [{id, name}], "notes": [{id, folder, body, pinned, updatedAt}]}. Edited from the page (PUT everything)
and by voice (the notas tool). Deleting moves a note to "Apagadas Recentemente"; deleting it there removes it for good."""
import datetime
import json
import pathlib
import random
import string
import unicodedata

FILE = pathlib.Path(__file__).resolve().parent / "notas.json"
BUILTIN = [{"id": "notas", "name": "Notas"}, {"id": "apagadas", "name": "Apagadas Recentemente"}]


def load():
    if FILE.exists():
        return json.loads(FILE.read_text(encoding="utf-8"))
    return {"folders": [dict(f) for f in BUILTIN], "notes": []}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def new_id():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


def save(data):
    """Validates and writes the whole notebook (what the page sends). Returns the clean copy."""
    folders, seen = [], set()
    for f in [*BUILTIN, *(data.get("folders") or [])]:
        fid = str(f.get("id") or new_id())[:20]
        if fid not in seen:
            seen.add(fid)
            folders.append({"id": fid, "name": " ".join(str(f.get("name", "")).split())[:80] or "Sem nome"})
    notes = [{"id": str(n.get("id") or new_id())[:20], "folder": n.get("folder") if n.get("folder") in seen else "notas",
              "body": str(n.get("body", ""))[:100000], "pinned": bool(n.get("pinned")),
              "updatedAt": str(n.get("updatedAt") or now())[:40]} for n in data.get("notes") or []]
    clean = {"folders": folders, "notes": notes}
    tmp = FILE.with_suffix(".tmp")   # write then rename, so a crash never leaves half a notebook
    tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FILE)
    return clean


def title(note):
    return next((l.strip() for l in note["body"].splitlines() if l.strip()), "Nova nota")[:120]


def _norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn").strip()


def folder(data, name, create=False):
    """The folder whose name matches `name` (accents and case ignored); created if asked and missing."""
    n = _norm(name or "Notas")
    f = next((f for f in data["folders"] if _norm(f["name"]) == n), None) or \
        next((f for f in data["folders"] if n and n in _norm(f["name"])), None)
    if not f and create:
        f = {"id": new_id(), "name": " ".join(name.split())[:80]}
        data["folders"].append(f)
    return f


def find(data, text, folder_id=None):
    """Notes (not deleted) whose title, or else body, contains `text`."""
    n = _norm(text or "")
    live = [x for x in data["notes"] if x["folder"] != "apagadas" and (not folder_id or x["folder"] == folder_id)]
    return [x for x in live if n and n in _norm(title(x))] or [x for x in live if n and n in _norm(x["body"])]


def summary():
    """One line per folder with its note titles, for Jarvis's context."""
    data = load()
    out = []
    for f in data["folders"]:
        if f["id"] == "apagadas":
            continue
        ts = [title(n) for n in sorted(data["notes"], key=lambda n: n["updatedAt"], reverse=True) if n["folder"] == f["id"]]
        out.append(f"{f['name']}: " + ("; ".join(ts[:15]) or "vazia"))
    return "\n".join(out)


if __name__ == "__main__":   # self-check on a scratch file
    import tempfile
    FILE = pathlib.Path(tempfile.mkdtemp()) / "n.json"
    d = load()
    f = folder(d, "Ideias", create=True)
    d["notes"].append({"id": "a", "folder": f["id"], "body": "Loja online\nusar Shopify"})
    d["notes"].append({"id": "b", "folder": "sumiu", "body": ""})
    d = save(d)
    assert [x["name"] for x in d["folders"]] == ["Notas", "Apagadas Recentemente", "Ideias"]
    assert d["notes"][1]["folder"] == "notas" and title(d["notes"][1]) == "Nova nota"
    assert find(d, "loja")[0]["id"] == "a" and find(d, "shopify")[0]["id"] == "a"
    assert folder(d, "ideias")["id"] == f["id"] and "Ideias: Loja online" in summary()
    print("ok")
