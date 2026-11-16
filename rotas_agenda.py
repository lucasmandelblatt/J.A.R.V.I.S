"""Agenda e Notas: as ferramentas de voz (agenda, notas) e as rotas que a página usa; toda mudança avisa as telas."""
import agenda
import datetime
import notas
import pathlib
import re

from aiohttp import web
from core import broadcast, log_turn
from config import USER


async def agenda_tool(app, args):
    acao, date = args.get("acao"), (args.get("data") or datetime.date.today().isoformat()).strip()
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        return {"error": "Data inválida: use AAAA-MM-DD."}
    if acao in ("abrir", "fechar"):
        await broadcast(app, type="calendar", action=acao, date=date, by="jarvis")
        return {"result": "Agenda aberta na tela." if acao == "abrir" else "Agenda fechada.", "scheduling": "SILENT"}
    if acao == "ver":
        end = (args.get("ate") or date).strip()
        days = {d: v["tasks"] for d, v in agenda.load()["days"].items() if date <= d <= end}
        await broadcast(app, type="calendar", action="ver", date=date, by="jarvis")
        return {"result": days or "Nada marcado nesses dias."}
    tasks = agenda.tasks(date)
    if acao == "adicionar":
        text = " ".join((args.get("tarefa") or "").split())
        if not text:
            return {"error": "Falta o texto da tarefa."}
        task = {"id": agenda.new_id(), "text": text, "done": False, "priority": bool(args.get("prioridade")),
                "note": args.get("nota", ""), "link": ""}
        agenda.set_day(date, tasks + [task], "jarvis")
        said = f"Adicionei '{text}' em {date}."
    else:
        found = agenda.find(date, args.get("tarefa", ""))
        if not found:
            return {"error": f"Não achei essa tarefa em {date}. Tarefas do dia: " + ("; ".join(t["text"] for t in tasks) or "nenhuma")}
        if len(found) > 1:
            return {"error": "Mais de uma tarefa bate com isso: " + "; ".join(t["text"] for t in found) + f". Pergunte a {USER} qual."}
        task = found[0]
        if acao == "mover":
            dest = (args.get("nova_data") or "").strip()
            try:
                datetime.date.fromisoformat(dest)
            except ValueError:
                return {"error": "Para mover, diga a nova data em AAAA-MM-DD."}
            agenda.set_day(date, [t for t in tasks if t["id"] != task["id"]], "jarvis")
            agenda.set_day(dest, agenda.tasks(dest) + [task], "jarvis")
            await broadcast(app, type="calendar", action="mover", date=dest, task=task["id"], by="jarvis")
            log_turn("Agenda", f"moveu '{task['text']}' de {date} para {dest}")
            return {"result": f"Movi '{task['text']}' para {dest}.", "scheduling": "SILENT"}
        if acao == "remover":
            tasks = [t for t in tasks if t["id"] != task["id"]]
        else:
            change = {"concluir": {"done": True}, "reabrir": {"done": False}, "priorizar": {"priority": True},
                      "despriorizar": {"priority": False}}.get(acao)
            if acao == "editar":
                change = {k: v for k, v in (("text", args.get("novo_texto")), ("note", args.get("nota"))) if v}
            if change is None:
                return {"error": f"Ação desconhecida: {acao}"}
            task.update(change)
            tasks = [task if t["id"] == task["id"] else t for t in tasks]
        agenda.set_day(date, tasks, "jarvis")
        said = {"remover": "Removi", "concluir": "Marquei como feita", "reabrir": "Reabri", "priorizar": "Marquei como prioridade",
                "despriorizar": "Tirei a prioridade de", "editar": "Atualizei"}[acao] + f" '{task['text']}' ({date})."
    log_turn("Agenda", said)
    await broadcast(app, type="calendar", action=acao, date=date, task=task["id"], by="jarvis")
    return {"result": said, "scheduling": "SILENT"}


async def api_calendar(request):
    return web.json_response(agenda.load())


async def api_calendar_day(request):
    date = request.match_info["date"]
    body = await request.json()
    try:
        agenda.set_day(date, body.get("tasks") or [], "lucas")
    except ValueError:
        return web.json_response({"error": "data inválida"}, status=400)
    await broadcast(request.app, type="calendar", action="sync", date=date, by="lucas")
    return web.json_response(agenda.load())


ANEXOS = pathlib.Path(__file__).resolve().parent / "anexos"   # files attached to calendar tasks


async def api_calendar_upload(request):
    """Saves files attached to a task; the page keeps the returned {name, file} list in the task."""
    ANEXOS.mkdir(exist_ok=True)
    saved = []
    async for part in await request.multipart():
        if not part.filename:
            continue
        name = re.sub(r"[/\\:]", "_", part.filename)
        file = f"{datetime.datetime.now():%Y%m%d-%H%M%S}-{name}"
        with open(ANEXOS / file, "wb") as f:
            while chunk := await part.read_chunk(1 << 20):
                f.write(chunk)
        saved.append({"name": name, "file": file})
    return web.json_response({"files": saved})


async def api_calendar_file(request):
    path = ANEXOS / request.match_info["file"]
    if path.parent != ANEXOS or not path.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(path)


async def notes_tool(app, args):
    acao, data = args.get("acao"), notas.load()
    if acao == "fechar":
        await broadcast(app, type="notes", action="fechar", by="jarvis")
        return {"result": "Notas fechado.", "scheduling": "SILENT"}
    if acao == "listar":
        await broadcast(app, type="notes", action="abrir", by="jarvis")
        return {"result": notas.summary()}
    if acao in ("criar", "criar_pasta"):
        f = notas.folder(data, args.get("pasta") or "Notas", create=True)
        if f["id"] == "apagadas":
            return {"error": "Não dá para criar nota em Apagadas Recentemente."}
        note = None
        if acao == "criar":
            body = (args.get("texto") or "").strip()
            if not body:
                return {"error": "Falta o texto da nota."}
            note = {"id": notas.new_id(), "folder": f["id"], "body": body, "pinned": False, "updatedAt": notas.now()}
            data["notes"].append(note)
        notas.save(data)
        said = f"Criei a nota '{notas.title(note)}' em {f['name']}." if note else f"Pasta {f['name']} pronta."
        await broadcast(app, type="notes", action="abrir", folder=f["id"], note=note and note["id"], by="jarvis")
        log_turn("Notas", said)
        return {"result": said, "scheduling": "SILENT"}
    f = notas.folder(data, args["pasta"]) if args.get("pasta") else None
    found = notas.find(data, args.get("nota", ""), f and f["id"])
    if not found:
        return {"error": "Não achei essa nota. Notas atuais:\n" + notas.summary()}
    if len(found) > 1 and acao != "ler":
        return {"error": "Mais de uma nota bate com isso: " + "; ".join(notas.title(n) for n in found) + f". Pergunte a {USER} qual."}
    note = found[0]
    if acao == "ler":
        await broadcast(app, type="notes", action="abrir", folder=note["folder"], note=note["id"], by="jarvis")
        return {"result": note["body"][-8000:]}
    if acao == "abrir":
        await broadcast(app, type="notes", action="abrir", folder=note["folder"], note=note["id"], by="jarvis")
        return {"result": f"Abri '{notas.title(note)}'.", "scheduling": "SILENT"}
    if acao == "acrescentar":
        add = (args.get("texto") or "").strip()
        if not add:
            return {"error": "Falta o texto para acrescentar."}
        note["body"] = note["body"].rstrip() + "\n" + add
        said = f"Acrescentei em '{notas.title(note)}'."
    elif acao == "apagar":
        note["folder"] = "apagadas"
        said = f"Mandei '{notas.title(note)}' para Apagadas Recentemente."
    else:
        return {"error": f"Ação desconhecida: {acao}"}
    note["updatedAt"] = notas.now()
    notas.save(data)
    log_turn("Notas", said)
    await broadcast(app, type="notes", action="abrir" if acao != "apagar" else "sync", folder=note["folder"], note=note["id"], by="jarvis")
    return {"result": said, "scheduling": "SILENT"}


async def api_notes(request):
    if request.method == "PUT":
        data = notas.save(await request.json())
        await broadcast(request.app, type="notes", action="sync", by="lucas")
        return web.json_response(data)
    return web.json_response(notas.load())
