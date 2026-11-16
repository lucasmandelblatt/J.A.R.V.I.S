"""Busca: índice SQLite (FTS5) de tudo o que o Jarvis já leu, para achar o trecho certo sem mandar tudo ao Gemini.

Indexa as análises das fontes de cada projeto (e as leituras diárias), o manual de curso e as notas do cofre do
Obsidian. Os arquivos continuam sendo a fonte da verdade; busca.db é só o índice, refeito por arquivo quando muda
(dá para apagar busca.db à vontade, ele se reconstrói).
"""
import json
import pathlib
import re
import sqlite3

HERE = pathlib.Path(__file__).resolve().parent
DB = HERE / "busca.db"
PROJETOS = HERE / "projetos"
CHUNK = 1200
STOP = set("que com para por uma uns umas dos das nos nas não sim mais como qual quais quando onde sobre isso esse essa "
           "este esta aquele aquela ele ela eles elas você voce meu minha seu sua tem ter foi ser são sao está esta "
           "aula fala falou disse jarvis lucas".split())


def _connect():
    c = sqlite3.connect(DB)
    c.execute("create table if not exists docs(path text primary key, mtime real)")
    c.execute("create virtual table if not exists trechos using fts5(titulo, texto, path unindexed, projeto unindexed, "
              "tokenize='unicode61 remove_diacritics 2')")
    return c


def _project_files():
    """(path, título, projeto) de cada análise, leitura diária e manual dos projetos."""
    for meta in PROJETOS.glob("*/projeto.json"):
        folder, pid = meta.parent, meta.parent.name
        try:
            titles = {s["id"]: s["titulo"] for s in json.loads(meta.read_text(encoding="utf-8"))["fontes"]}
        except (ValueError, KeyError):
            titles = {}
        for f in (folder / "fontes").glob("*.md"):
            yield f, titles.get(f.stem, f.stem), pid
        for f in (folder / "fontes").glob("*/*.md"):   # leituras diárias: fontes/<fonte>/AAAA-MM-DD.md
            yield f, f"{titles.get(f.parent.name, f.parent.name)} (leitura de {f.stem})", pid
        if (folder / "manual.md").exists():
            yield folder / "manual.md", "Manual de execução do curso", pid


def _vault_files(vault):
    root = pathlib.Path(vault)
    for f in root.rglob("*.md"):
        if not any(p.startswith(".") for p in f.relative_to(root).parts):
            yield f, f.stem, ""


def _chunks(text):
    text = re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.S)   # tira o cabeçalho YAML do Obsidian
    out, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        if cur and len(cur) + len(para) > CHUNK:
            out.append(cur.strip())
            cur = ""
        cur += para + "\n\n"
    if cur.strip():
        out.append(cur.strip())
    return out


def sync(vault=None):
    """Atualiza o índice só com o que mudou desde a última vez."""
    files = list(_project_files()) + (list(_vault_files(vault)) if vault else [])
    with _connect() as c:
        known = dict(c.execute("select path, mtime from docs"))
        seen = set()
        for f, title, pid in files:
            key, mtime = str(f), f.stat().st_mtime
            seen.add(key)
            if known.get(key) == mtime:
                continue
            c.execute("delete from trechos where path = ?", (key,))
            c.executemany("insert into trechos(titulo, texto, path, projeto) values (?, ?, ?, ?)",
                          [(title, t, key, pid) for t in _chunks(f.read_text(encoding="utf-8", errors="replace"))])
            c.execute("insert or replace into docs values (?, ?)", (key, mtime))
        for key in set(known) - seen:
            c.execute("delete from trechos where path = ?", (key,))
            c.execute("delete from docs where path = ?", (key,))


def _query(pergunta):
    words = {w for w in re.findall(r"\w+", pergunta.lower()) if len(w) > 2 and w not in STOP}
    return " OR ".join(f'"{w}"' for w in words)


def search(pergunta, projeto=None, vault=None, limite=6):
    """Os trechos mais parecidos com a pergunta: [{titulo, texto, projeto}]. projeto=None busca em tudo."""
    sync(vault)
    q = _query(pergunta)
    if not q:
        return []
    sql = "select titulo, texto, projeto from trechos where trechos match ?"
    args = [q]
    if projeto:
        sql += " and projeto = ?"
        args.append(projeto)
    sql += " order by bm25(trechos, 2.0, 1.0) limit ?"
    with _connect() as c:
        return [{"titulo": t, "texto": x, "projeto": p} for t, x, p in c.execute(sql, args + [limite])]


if __name__ == "__main__":   # autoteste: python3 busca.py
    import sys
    import tempfile
    DB = pathlib.Path(tempfile.mkdtemp()) / "t.db"
    PROJETOS = pathlib.Path(tempfile.mkdtemp())
    p = PROJETOS / "curso"
    (p / "fontes").mkdir(parents=True)
    (p / "projeto.json").write_text(json.dumps({"fontes": [{"id": "01-a", "titulo": "Narração com IA"}]}))
    (p / "fontes" / "01-a.md").write_text("## Visão geral\n\nUse o ElevenLabs para a narração.\n\n" + "x " * 700 +
                                          "\n\nNo final, revise a pronúncia.")
    r = search("qual ferramenta de narração?", "curso")
    assert r and r[0]["titulo"] == "Narração com IA" and "ElevenLabs" in r[0]["texto"], r
    assert search("narracao")[0]["projeto"] == "curso"           # sem acento também acha
    assert search("pronúncia") and not search("pronúncia", "outro")
    (p / "fontes" / "01-a.md").unlink()
    assert not search("narração")                                # arquivo apagado sai do índice
    print("busca ok", file=sys.stderr)
