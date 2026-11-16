"""Projetos: ferramentas de voz de projeto e estudo, fontes (sites, documentos, arquivos) e as rotas do Studio."""
import asyncio
import datetime
import notebook
import pathlib
import projects
import re
import research
import sources
import time
import urllib.parse
import video

from aiohttp import web
from vault import WEEKDAYS
from core import active_project, bg, broadcast, clean_env, log, need_project, seconds, settings
from estudo import open_project, start_watch
from config import USER


async def project_tool(app, args, session):
    action, nome = args.get("acao"), (args.get("nome") or "").strip()
    if action == "listar":
        projs = projects.all_projects()
        if not projs:
            return {"result": "Ainda não há projetos."}
        return {"result": "Projetos (mais recentes primeiro): " + "; ".join(
            f"{p.title} ({len(p.meta['fontes'])} fontes, atualizado {p.meta['atualizado']})" for p in projs[:20])}
    if action == "sair":
        await open_project(app, None, asked_by=session)
        return {"result": "Saiu do projeto; a próxima resposta já é na conversa normal. Confirme em poucas palavras."}
    if action == "criar":
        proj = projects.create(nome or "Projeto novo")
        await open_project(app, proj, asked_by=session)
        return {"result": f"Projeto '{proj.title}' criado e aberto. Confirme em poucas palavras."}
    if action == "abrir":
        proj = projects.find(nome)
        if not proj:
            names = ", ".join(p.title for p in projects.all_projects()[:15]) or "nenhum"
            return {"error": f"Não achei um projeto '{nome}'. Os que existem: {names}."}
        await open_project(app, proj, asked_by=session)
        return {"result": f"Projeto '{proj.title}' aberto, com {len(proj.meta['fontes'])} fontes. Confirme em poucas palavras; "
                          "na próxima resposta você já terá toda a memória dele."}
    return {"error": "Ação desconhecida."}


async def review_clip(app, args, session):
    proj = active_project()
    if not proj:
        return {"error": "Nenhum projeto aberto. Abra o projeto do vídeo primeiro."}
    key = (args.get("fonte") or "").strip()
    ready = [s for s in proj.meta["fontes"] if s["status"] == "pronto"]
    entry = (proj.source(key) or next((s for s in ready if projects.slug(key) in projects.slug(s["titulo"])), None)
             or (ready[0] if len(ready) == 1 else None))
    if not entry:
        return {"error": "Não sei de qual vídeo é. Fontes: " + "; ".join(f"{s['id']} {s['titulo']}" for s in ready)}
    question = args.get("pergunta", "")
    await session.to_browser(type="task", state="start", text=f"Revendo {entry['titulo']} {args.get('inicio') or ''}".strip())
    try:
        answer = await app["watcher"].clip(proj.watch_source(entry), question, seconds(args.get("inicio")), seconds(args.get("fim")))
        result = {"result": answer[:6000]}
    except Exception as e:   # noqa: BLE001
        result = {"error": f"Não consegui rever o trecho: {e}"}
    await session.to_browser(type="task", state="done", text=(result.get("result") or result["error"])[:300], ok="result" in result)
    return result


def find_source(proj, key, ready_only=True):
    pool = [s for s in proj.meta["fontes"] if (s["status"] == "pronto" or not ready_only) and s["tipo"] in ("youtube", "url", "file")]
    key = (key or "").strip()
    return (proj.source(key) or (next((s for s in pool if projects.slug(key) in projects.slug(s["titulo"])), None) if key else None)
            or (pool[0] if len(pool) == 1 else None))


def study_position(session):
    """'video "Title" (fonte 01-...), minuto 12:34, pausado' for the study screen, or '' when it is closed."""
    st = session.study
    if not st or not st.get("sid"):
        return ""
    pos = float(st.get("pos") or 0) + (time.time() - st["at"] if st.get("playing") else 0)
    return (f'vídeo "{st.get("title")}" (fonte {st["sid"]}), minuto {video.stamp(pos)}, '
            f'{"tocando" if st.get("playing") else "pausado"}')


async def study_tool(app, args, session):
    if args.get("acao") == "onde_estou":
        where = study_position(session)
        return {"result": f"{USER} está na tela de estudo: {where}." if where else
                          f"A tela de estudo está fechada; {USER} não está vendo nenhum vídeo no app agora."}
    proj = active_project()
    if not proj:
        return {"error": "Nenhum projeto aberto. Abra o projeto do vídeo primeiro."}
    current = (session.study or {}).get("sid") if (session.study or {}).get("pid") == proj.id else None
    entry = find_source(proj, args.get("fonte") or current or "")
    if not entry:
        return {"error": "Não sei de qual vídeo é. Fontes: " + "; ".join(f"{s['id']} {s['titulo']}" for s in proj.meta["fontes"])}
    secs = seconds(args.get("minuto")) or 0
    await session.to_browser(type="study_seek", pid=proj.id, sid=entry["id"], t=secs)
    return {"result": f"Pulei para {video.stamp(secs)} em '{entry['titulo']}'. Diga em poucas palavras o que aparece ali."}


async def api_source_video(request):
    """The video file of a source, for the study screen's player (sources that aren't on YouTube)."""
    proj = projects.get(request.match_info["pid"])
    entry = proj.source(request.match_info["sid"]) if proj else None
    if not entry or entry["tipo"] == "youtube":
        raise web.HTTPNotFound()
    local = proj.watch_source(entry).get("local")
    if not local or not pathlib.Path(local).is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(local)


async def api_projects(request):
    if request.method == "POST":
        proj = projects.create((await request.json()).get("titulo", "Projeto novo"))
        return web.json_response(proj.summary())
    proj = active_project()
    return web.json_response({"projetos": [p.summary() for p in projects.all_projects()], "ativo": proj.id if proj else None})


async def api_project(request):
    proj = projects.get(request.match_info["pid"])
    if request.method == "DELETE":
        if proj and settings().get("projeto") == proj.id:
            await open_project(request.app, None)
        return web.json_response({"ok": projects.delete(request.match_info["pid"])})
    if not proj:
        raise web.HTTPNotFound()
    if request.method == "PATCH":
        body = await request.json()
        if body.get("titulo", "").strip():
            proj.meta["titulo"] = body["titulo"].strip()[:120]
        for k in ("emoji", "fixado", "colecoes", "chat", "resumo_proprio"):
            if k in body:
                proj.meta[k] = body[k]
        proj.save()
        proj = projects.get(proj.id)
    return web.json_response({**proj.summary(), "conversa": proj.talk(300)})


async def api_project_open(request):
    pid = request.match_info.get("pid")
    proj = projects.get(pid) if pid else None
    if pid and not proj:
        raise web.HTTPNotFound()
    await open_project(request.app, proj)
    return web.json_response({"ativo": proj.id if proj else None})


async def api_project_video(request):
    proj = projects.get(request.match_info["pid"])
    if not proj:
        raise web.HTTPNotFound()
    body = await request.json()
    return web.json_response(await start_watch(request.app, body.get("fonte", ""), foco=body.get("foco", ""), proj=proj))


async def api_source(request):
    proj = projects.get(request.match_info["pid"])
    entry = proj.source(request.match_info["sid"]) if proj else None
    if not entry:
        raise web.HTTPNotFound()
    return web.json_response({**entry, "analise": proj.analysis(entry["id"])})


def today_label():
    d = datetime.date.today()
    return f"{WEEKDAYS[d.weekday()]}, {d:%d/%m/%Y}"


async def add_site(app, proj, url, diario=False, foco=""):
    url = url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    if sources.is_video_link(url):
        return await start_watch(app, url, foco=foco, proj=proj)
    host = urllib.parse.urlparse(url).netloc.removeprefix("www.")
    entry = proj.add_source({"kind": "site", "source": url, "title": host, "status": "lendo", "diario": diario})
    await broadcast(app, type="project_update", project=proj.summary())
    job = asyncio.create_task(read_site_job(app, proj, entry["id"], url, foco))
    app["jobs"].add(job); job.add_done_callback(app["jobs"].discard)
    return {"result": f"Lendo {host}{' (todo dia)' if diario else ''} no projeto '{proj.title}'.", "fonte": entry["id"]}


async def read_site_job(app, proj, sid, url, foco=""):
    try:
        await broadcast(app, type="project_progress", project=proj.id, source=sid, text="Lendo o site")
        title, analysis = await sources.read_site(app["http"], app["key"], url, today_label(), foco, log=log)
        day = datetime.date.today().isoformat()
        proj.set_analysis(sid, analysis)
        folder = proj.source_dir(sid); folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{day}.md").write_text(analysis, encoding="utf-8")
        proj.update_source(sid, status="pronto", titulo=title[:120], lido=day, erro=None)
        log(f"site lido: {url}")
    except Exception as e:   # noqa: BLE001 — reported in the source card and to Jarvis
        log(f"site falhou: {url}: {e!r}")
        proj.update_source(sid, status="erro", erro=str(e)[:300])
    await broadcast(app, type="project_update", project=proj.summary())


async def read_doc_job(app, proj, sid, path, foco=""):
    try:
        await broadcast(app, type="project_progress", project=proj.id, source=sid, text="Lendo o documento")
        proj.set_analysis(sid, await sources.read_doc(app["http"], app["key"], path, foco, log=log))
        proj.update_source(sid, status="pronto", erro=None)
    except Exception as e:   # noqa: BLE001
        log(f"documento falhou: {path}: {e!r}")
        proj.update_source(sid, status="erro", erro=str(e)[:300])
    await broadcast(app, type="project_update", project=proj.summary())


async def daily_reader(app):
    """Every half hour: sites marked 'diario' that haven't been read today (after 6 AM) are read again."""
    while True:
        try:
            if datetime.datetime.now().hour >= 6:
                day = datetime.date.today().isoformat()
                for proj in projects.all_projects():
                    for s in proj.meta["fontes"]:
                        if s["tipo"] == "site" and s.get("diario") and s.get("lido") != day and s["status"] != "lendo":
                            proj.update_source(s["id"], status="lendo")
                            await read_site_job(app, proj, s["id"], s["origem"])
        except Exception as e:   # noqa: BLE001 — never let the loop die
            log(f"leitura diária falhou: {e!r}")
        await asyncio.sleep(1800)


async def source_tool(app, args):
    proj = projects.find(args["projeto"]) if args.get("projeto") else active_project()
    if not proj:
        return {"error": "Nenhum projeto aberto. Abra um projeto (ferramenta projeto) ou diga o nome."}
    if args.get("acao") == "reler":
        s = next((x for x in proj.meta["fontes"] if x["tipo"] == "site" and
                  (x["id"] == args.get("fonte") or projects.slug(args.get("fonte", "")) in projects.slug(x["titulo"] + " " + x["origem"]))), None)
        if not s:
            return {"error": "Não achei esse site entre as fontes do projeto."}
        proj.update_source(s["id"], status="lendo")
        await read_site_job(app, proj, s["id"], s["origem"])
        return {"result": f"Reli {s['titulo']}. A leitura nova já está nas fontes."}
    if not args.get("url"):
        return {"error": "Falta o endereço do site."}
    return await add_site(app, proj, args["url"], bool(args.get("diario")))


async def api_project_sources(request):
    proj = projects.get(request.match_info["pid"])
    if not proj:
        raise web.HTTPNotFound()
    body = await request.json()
    return web.json_response(await add_site(request.app, proj, body.get("url", ""), bool(body.get("diario")), body.get("foco", "")))


VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".mp3", ".m4a", ".wav"}


async def api_project_files(request):
    """Files dropped into a project: videos are watched, everything else is read as a document. No conversation needed."""
    proj = projects.get(request.match_info["pid"])
    if not proj:
        raise web.HTTPNotFound()
    folder = proj.folder / "arquivos"; folder.mkdir(exist_ok=True)
    reader, added = await request.multipart(), []
    async for part in reader:
        if not part.filename:
            continue
        dest = folder / re.sub(r"[/\\:]", "_", part.filename)
        with open(dest, "wb") as f:
            while chunk := await part.read_chunk(1 << 20):
                await asyncio.to_thread(f.write, chunk)
        if dest.suffix.lower() in VIDEO_EXT:
            r = await start_watch(request.app, str(dest), proj=proj)
        else:
            entry = proj.add_source({"kind": "doc", "source": str(dest), "title": dest.stem, "status": "lendo"})
            job = asyncio.create_task(read_doc_job(request.app, proj, entry["id"], dest))
            request.app["jobs"].add(job); job.add_done_callback(request.app["jobs"].discard)
            r = {"result": f"Lendo {dest.name}."}
        added.append(r)
    return web.json_response({"added": added})


async def api_project_source(request):
    proj = projects.get(request.match_info["pid"])
    s = proj.source(request.match_info["sid"]) if proj else None
    if not s:
        raise web.HTTPNotFound()
    if request.method == "DELETE":
        proj.remove_source(s["id"])
    elif request.method == "PATCH":
        body = await request.json()
        if "diario" in body:
            proj.update_source(s["id"], diario=bool(body["diario"]))
        if body.get("titulo", "").strip():
            proj.update_source(s["id"], titulo=body["titulo"].strip()[:120])
        if body.get("reler") and s["tipo"] == "site":
            proj.update_source(s["id"], status="lendo")
            job = asyncio.create_task(read_site_job(request.app, proj, s["id"], s["origem"]))
            request.app["jobs"].add(job); job.add_done_callback(request.app["jobs"].discard)
    proj.reload()   # the notify_projects middleware tells every screen
    return web.json_response(proj.summary())


async def api_nb_chat(request):
    """Typed questions in the Studio: answered from the chosen sources with numbered citations."""
    proj = need_project(request)
    if request.method == "DELETE":
        proj.talk_file.unlink(missing_ok=True)
        return web.json_response({"ok": True})
    body = await request.json()
    q = (body.get("pergunta") or "").strip()
    if not q:
        return web.json_response({"error": "pergunta vazia"}, status=400)
    proj.log_entry(f"{USER}", q)
    try:
        r = await notebook.chat(request.app["http"], request.app["key"], proj, q, body.get("fontes") or None, log=log)
    except Exception as e:   # noqa: BLE001 — shown in the chat
        log(f"studio chat falhou: {e!r}")
        return web.json_response({"error": f"Não consegui responder agora: {e}"}, status=502)
    proj.log_entry("Jarvis", r["resposta"], cit=r["cit"], sugestoes=r["sugestoes"])
    return web.json_response(r)


async def api_nb_overview(request):
    proj = need_project(request)
    try:
        r = await notebook.overview(request.app["http"], request.app["key"], proj, log=log)
    except Exception as e:   # noqa: BLE001
        log(f"resumo do projeto falhou: {e!r}")
        r = {"texto": "", "perguntas": [], "erro": str(e)[:200]}
    proj.reload()
    if proj.meta.get("resumo_proprio"):
        r = {**r, "texto": proj.meta["resumo_proprio"]}
    return web.json_response(r)


async def api_nb_tags(request):
    proj = need_project(request)
    try:
        await notebook.tag_sources(request.app["http"], request.app["key"], proj, log=log)
    except Exception as e:   # noqa: BLE001
        return web.json_response({"error": str(e)[:200]}, status=502)
    return web.json_response(proj.reload().summary())


async def api_nb_text(request):
    """'Texto copiado': pasted text becomes a document source."""
    proj = need_project(request)
    body = await request.json()
    text, title = (body.get("texto") or "").strip(), (body.get("titulo") or "").strip() or "Texto colado"
    if not text:
        return web.json_response({"error": "texto vazio"}, status=400)
    folder = proj.folder / "arquivos"; folder.mkdir(exist_ok=True)
    dest = folder / (re.sub(r"[/\\:]", "_", title)[:80] + ".md")
    dest.write_text(text, encoding="utf-8")
    entry = proj.add_source({"kind": "doc", "source": str(dest), "title": title, "status": "lendo"})
    bg(request.app, read_doc_job(request.app, proj, entry["id"], dest))
    return web.json_response(entry)


async def api_nb_copy(request):
    new = projects.copy(request.match_info["pid"])
    if not new:
        raise web.HTTPNotFound()
    return web.json_response(new.summary())


async def discover_job(app, proj, query, mode):
    r = await research.research(f"Encontre as melhores fontes na web sobre: {query}", "profunda" if mode == "profunda" else "rapida", clean_env())
    proj.reload()
    d = proj.meta.get("descoberta") or {}
    if d.get("consulta") != query:
        return   # cleared or replaced meanwhile
    if "error" in r:
        d.update(status="erro", erro=r["error"][:300])
    else:
        d.update(status="pronto", resultados=[{"titulo": f.get("titulo") or f["url"], "url": f["url"]} for f in r["fontes"]][:15],
                 relatorio=r.get("resposta", "") if mode == "profunda" else "", titulo=r.get("titulo", query))
    proj.meta["descoberta"] = d
    proj.save()


async def api_nb_discover(request):
    """Source discovery: a quick or deep web search (research.py) whose results can be imported as sources."""
    proj = need_project(request)
    if request.method == "GET":
        return web.json_response(proj.reload().meta.get("descoberta") or {})
    if request.method == "DELETE":
        proj.meta.pop("descoberta", None); proj.save()
        return web.json_response({})
    body = await request.json()
    if body.get("importar") is not None:
        d = proj.meta.get("descoberta") or {}
        for url in body["importar"]:
            await add_site(request.app, proj, url)
        if body.get("relatorio") and d.get("relatorio"):
            folder = proj.folder / "arquivos"; folder.mkdir(exist_ok=True)
            dest = folder / f"Pesquisa - {projects.slug(d.get('consulta', 'web'))[:40]}.md"
            dest.write_text(d["relatorio"], encoding="utf-8")
            entry = proj.reload().add_source({"kind": "doc", "source": str(dest), "title": "Relatório: " + d.get("titulo", d.get("consulta", "")), "status": "lendo"})
            bg(request.app, read_doc_job(request.app, proj, entry["id"], dest))
        proj.reload(); proj.meta.pop("descoberta", None); proj.save()
        return web.json_response(proj.summary())
    query = (body.get("consulta") or "").strip()
    if not query:
        return web.json_response({"error": "consulta vazia"}, status=400)
    proj.meta["descoberta"] = {"consulta": query, "modo": body.get("modo", "rapida"), "status": "buscando", "inicio": notebook.now()}
    proj.save()
    bg(request.app, discover_job(request.app, proj, query, body.get("modo")))
    return web.json_response(proj.meta["descoberta"])


async def api_nb_notes(request):
    proj = need_project(request)
    items, nid = notebook.notes(proj), request.match_info.get("nid")
    if request.method == "POST":
        body = await request.json()
        item = {"id": uuid_hex(), "titulo": (body.get("titulo") or "Nota").strip()[:120], "texto": body.get("texto", ""),
                "cit": body.get("cit") or {}, "origem": body.get("origem", "manual"), "criado": notebook.now()}
        items.insert(0, item)
    elif request.method == "PATCH":
        body = await request.json()
        for it in items:
            if it["id"] == nid:
                it.update({k: body[k] for k in ("titulo", "texto") if k in body})
        if body.get("virar_fonte"):
            it = next((x for x in items if x["id"] == nid), None)
            if it:
                folder = proj.folder / "arquivos"; folder.mkdir(exist_ok=True)
                dest = folder / f"Nota - {projects.slug(it['titulo'])[:40]}.md"
                dest.write_text(f"# {it['titulo']}\n\n{it['texto']}", encoding="utf-8")
                entry = proj.add_source({"kind": "doc", "source": str(dest), "title": it["titulo"], "status": "lendo"})
                bg(request.app, read_doc_job(request.app, proj, entry["id"], dest))
    elif request.method == "DELETE":
        items = [x for x in items if x["id"] != nid]
    notebook.save_notes(proj, items)
    return web.json_response(items)


def uuid_hex():
    return __import__("uuid").uuid4().hex[:10]


async def api_nb_studio(request):
    proj = need_project(request)
    st = notebook.Studio(proj)
    if request.method == "GET":
        return web.json_response(st.all())
    body = await request.json()
    kind = body.get("tipo")
    if kind not in notebook.KINDS:
        return web.json_response({"error": "tipo desconhecido"}, status=400)
    item = st.create(kind, body.get("opcoes") or {}, body.get("fontes") or [])
    bg(request.app, notebook.generate(request.app["http"], request.app["key"], proj, item, log=log))
    return web.json_response(item)


async def api_nb_item(request):
    proj = need_project(request)
    st, aid = notebook.Studio(proj), request.match_info["aid"]
    item = st.get(aid)
    if not item:
        raise web.HTTPNotFound()
    if request.method == "DELETE":
        st.delete(aid)
        return web.json_response({"ok": True})
    if request.method == "PATCH":
        body = await request.json()
        if body.get("titulo", "").strip():
            item["titulo"] = body["titulo"].strip()[:140]
            st.save(item)
    return web.json_response(item)


async def api_nb_audio(request):
    proj = need_project(request)
    f = notebook.Studio(proj).audio(request.match_info["aid"], request.match_info["n"])
    if not f.exists():
        raise web.HTTPNotFound()
    return web.FileResponse(f, headers={"Content-Type": "audio/wav"})


async def api_collections(request):
    items, cid = notebook.collections(), request.match_info.get("cid")
    if request.method == "POST":
        items.append({"id": uuid_hex(), "nome": ((await request.json()).get("nome") or "Coleção").strip()[:80], "criado": notebook.now()})
    elif request.method == "PATCH":
        nome = ((await request.json()).get("nome") or "").strip()
        for c in items:
            if c["id"] == cid and nome:
                c["nome"] = nome[:80]
    elif request.method == "DELETE":
        items = [c for c in items if c["id"] != cid]
        for p in projects.all_projects():
            if cid in (p.meta.get("colecoes") or []):
                p.meta["colecoes"].remove(cid); p.save()
    if request.method != "GET":
        notebook.save_collections(items)
    return web.json_response(items)
