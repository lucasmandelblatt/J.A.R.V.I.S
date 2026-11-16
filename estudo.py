"""Assistir vídeos, gravar a tela e o modo curso (estudar um curso inteiro no Chrome, aula por aula)."""
import asyncio
import course
import datetime
import json
import os
import paths
import pathlib
import projects
import re
import tempfile
import time
import video

from aiohttp import web
from core import VAULT, active_project, broadcast, log, osascript, read_with_gemini, save_setting, settings
from config import USER


async def open_project(app, proj, asked_by=None):
    """Opens a project (or closes the open one when proj is None): every live conversation starts over with that
    project's memory. The window that asked by voice switches after Jarvis finishes his sentence."""
    if (proj.id if proj else None) == settings().get("projeto"):
        return
    for s in list(app["sessions"]):
        s.flush()
    save_setting("projeto", proj.id if proj else None)
    log(f"projeto: {'abriu ' + proj.title if proj else 'saiu do projeto'}")
    await broadcast(app, type="project", project=proj.summary() if proj else None)
    for s in list(app["sessions"]):
        s.handle = None   # a fresh conversation, not a resumed one: the old context must not leak in
        if s is asked_by:
            s.reconnect_after_turn = True
        elif s.gemini is not None and not s.gemini.closed:
            await s.gemini.close()


async def chrome_video_url():
    out, err = await osascript('tell application "Google Chrome" to get URL of active tab of front window')
    if err or not out or not out.strip().startswith("http"):
        raise RuntimeError("Não achei um vídeo aberto no Chrome (a aba da frente precisa ser o vídeo).")
    return out.strip()


async def start_watch(app, fonte, nome="", foco="", proj=None):
    """Registers the video as a source and watches it in the background; returns at once."""
    fonte = (fonte or "").strip()
    try:
        if fonte.lower() in ("chrome", "aba", "aba do chrome", "navegador"):
            fonte = await chrome_video_url()
        src = await video.describe(fonte)
    except RuntimeError as e:
        return {"error": str(e)}
    proj = proj or (projects.find(nome) if nome else None) or active_project()
    if proj is None or (nome and slug_differs(proj, nome)):
        proj = projects.create(nome or src["title"])
    entry = proj.add_source(src)
    if foco:
        proj.update_source(entry["id"], foco=foco)
    await broadcast(app, type="project_update", project=proj.summary())
    job = asyncio.create_task(watch_job(app, proj, entry["id"], src, foco))
    app["jobs"].add(job)
    job.add_done_callback(app["jobs"].discard)
    minutes = src["duration"] / 60
    eta = "menos de um minuto" if minutes < 8 else "uns minutos" if minutes < 40 else "vários minutos, porque o vídeo é longo"
    return {"result": f"Comecei a assistir '{src['title']}'" + (f" ({minutes:.0f} min)" if minutes >= 1 else "") +
                      f" no projeto '{proj.title}'. Deve levar {eta}. Diga isso a {USER} numa frase curta; "
                      "quando terminar, o sistema te avisa."}


def slug_differs(proj, nome):
    return projects.slug(nome) not in projects.slug(proj.title)


async def title_from_analysis(app, proj, sid, analysis, fallback):
    """A short title from what the video is about, for recordings whose only name was the tab's (often just the site's)."""
    overview = re.search(r"## Visão geral\s*(.*?)(?=\n## |\Z)", analysis, re.S)
    r = await read_with_gemini(app["http"], app["key"], [{"text": (
        "Dê um título curto (de 3 a 9 palavras) em português para esta aula ou vídeo, como o nome de uma aula num curso. "
        f"Responda só com o título, sem aspas nem ponto final.\n\nSite onde estava: {fallback}\n\n"
        f"Resumo:\n{(overview[1] if overview else analysis)[:3000]}")}])
    title = re.sub(r"[\"“”*#]", "", ((r.get("result") or "").strip().splitlines() or [""])[0]).strip(" .")
    if not 3 <= len(title) <= 90:
        return fallback
    proj.update_source(sid, titulo=title, titulo_auto=False)
    log(f"gravação: chamei '{fallback}' de '{title}'")
    return title


def save_to_vault(proj, sid, analysis):
    """A copy of the analysis in Obsidian (07 - Resources), so what Jarvis watched outlives the project. Returns the path."""
    entry = proj.source(sid) or {}
    how = {"youtube": "vídeo do YouTube", "url": "vídeo da internet", "file": "arquivo de vídeo"}.get(entry.get("tipo"), "vídeo")
    if entry.get("gravado"):
        how = "gravado da tela" + (f" em {entry['pagina']}" if entry.get("pagina") else "")
    elif str(entry.get("origem", "")).startswith("http"):
        how += f": {entry['origem']}"
    try:
        path, _ = VAULT.write_note(f"{entry.get('titulo') or sid} ({proj.title})",
                                   f"Fonte do projeto **{proj.title}** no Studio do Jarvis ({how}), assistida em "
                                   f"{datetime.date.today():%d/%m/%Y}.\n\n{analysis}", area="referencia", kind="reference",
                                   status="completed")
        return str(path)
    except Exception as e:   # noqa: BLE001 — the project copy is already saved; the vault copy must not lose it
        log(f"obsidian: não salvei a fonte {sid}: {e!r}")
        return ""


MAX_RECORDING = 4 * 3600


def recording_info(app):
    if app["rec"].get("curso") and not app["rec"].get("now"):
        c = app["rec"]["curso"]
        return {"gravando": True, "curso": True, "titulo": c["status"], "projeto": c["proj"].id, "desde": c["since"]}
    rec = app["rec"].get("now")
    return {"gravando": bool(rec), **({"titulo": rec["title"], "projeto": rec["proj"].id, "fonte": rec["sid"],
                                       "desde": rec["since"]} if rec else {})}


async def spawn_recorder(path, bundle=None, window_title=None):
    """Starts jarvis-gravar; returns (process, '') once it is recording, or (None, why it didn't start)."""
    args = [str(paths.recorder()), str(path)] + ([bundle] if bundle else []) + ([window_title] if bundle and window_title else [])
    proc = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

    async def started():
        while line := (await proc.stdout.readline()).decode():
            if line.strip() == "gravando":
                return True
            log(f"gravação: {line.strip()}")
        return False
    try:
        ok = await asyncio.wait_for(started(), 15)
    except asyncio.TimeoutError:
        ok = False
    if ok:
        return proc, ""
    if proc.returncode is None:
        try:
            proc.kill()
        except ProcessLookupError:   # it exited between the check and the kill
            pass
    await proc.wait()
    err = (await proc.stderr.read()).decode(errors="replace").strip()[:300]
    log(f"gravação: não começou: {err}")
    return None, err


async def finish_recorder(proc):
    """Asks jarvis-gravar to close the file; returns its error text, '' when the file is good."""
    if proc.returncode is not None:
        return "" if proc.returncode == 0 else "o gravador parou sozinho"
    try:
        proc.stdin.write(b"stop\n")
        await proc.stdin.drain()
        await asyncio.wait_for(proc.wait(), 60)
    except (asyncio.TimeoutError, ConnectionError):
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        await proc.wait()
    return "" if proc.returncode == 0 else (await proc.stderr.read()).decode(errors="replace").strip()[:300] or "o gravador falhou"


async def start_recording(app, titulo="", projeto="", foco="", minutos=0, proj=None):
    if app["rec"].get("now") or app["rec"].get("curso"):
        return {"error": "Já estou gravando " + (f"'{app['rec']['now']['title']}'" if app["rec"].get("now") else "um curso") +
                         ". Peça para parar antes."}
    if not paths.recorder().exists():
        return {"error": "O gravador da tela não está instalado: é preciso recompilar o Jarvis (app/build.sh)."}
    page_title, _ = await osascript('tell application "Google Chrome" to get title of active tab of front window', timeout=5)
    page_url, _ = await osascript('tell application "Google Chrome" to get URL of active tab of front window', timeout=5)
    title = (titulo or "").strip() or (page_title or "").strip() or f"Gravação da tela {datetime.datetime.now():%d/%m %H:%M}"
    proj = proj or (projects.find(projeto) if projeto else None) or active_project() or projects.create(title)
    entry = proj.add_source({"kind": "file", "source": "", "title": title, "status": "gravando"})
    sid = entry["id"]
    path = proj.source_dir(sid) / "video.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    proj.update_source(sid, origem=str(path), local=str(path), gravado=True, foco=foco or None,
                       titulo_auto=not (titulo or "").strip(),   # the tab's title ("TubeClub") is renamed from the content
                       pagina=(page_url or "").strip() if (page_url or "").startswith("http") else None)
    proc, err = await spawn_recorder(path)
    if proc is None:
        proj.remove_source(sid)
        return {"error": "Não consegui gravar a tela" + (f" ({err})" if err else "") + ". Talvez falte a permissão de "
                         "Gravação de Tela e Áudio do Sistema para o Jarvis."}
    limit = min(MAX_RECORDING, (float(minutos) + 1) * 60) if minutos else MAX_RECORDING

    async def auto_stop():
        await asyncio.sleep(limit)
        await stop_recording(app, reason="o tempo combinado acabou")
    app["rec"]["now"] = {"proc": proc, "proj": proj, "sid": sid, "title": title, "foco": foco, "path": path,
                        "since": time.time(), "timer": asyncio.create_task(auto_stop())}
    log(f"gravação: começou '{title}' no projeto '{proj.title}'")
    await broadcast(app, type="recording", **recording_info(app))
    await broadcast(app, type="project_update", project=proj.summary())
    return {"result": f"Estou gravando a tela e o som do Mac para assistir '{title}' (projeto '{proj.title}'). Diga a {USER}, "
                      "numa frase, para colocar o vídeo em tela cheia, dar play com o som ligado e, se quiser, apertar F5 para "
                      "você não ouvir a aula. Para terminar, ele aperta Parar no aviso 'Gravando' do Jarvis ou te pede. "
                      "Enquanto grava, fique em silêncio: não comente o que o vídeo fala."}


async def stop_recording(app, reason=""):
    if app["rec"].get("curso") and not app["rec"].get("now"):
        return await stop_course(app)
    rec = app["rec"].pop("now", None)
    if not rec:
        return {"error": "Não estou gravando nada agora."}
    if asyncio.current_task() is not rec["timer"]:
        rec["timer"].cancel()
    proc, proj, sid, path = rec["proc"], rec["proj"], rec["sid"], rec["path"]
    failed = await finish_recorder(proc)
    await broadcast(app, type="recording", gravando=False)
    minutes = (time.time() - rec["since"]) / 60
    log(f"gravação: parou '{rec['title']}' depois de {minutes:.0f} min" + (f" ({reason})" if reason else ""))
    try:
        if failed or not path.exists():
            raise RuntimeError(failed or "a gravação não gerou arquivo")
        src = await video.describe(str(path))
        src["title"] = rec["title"]
    except RuntimeError as e:
        proj.update_source(sid, status="erro", erro=f"Gravação falhou: {e}")
        await broadcast(app, type="project_update", project=proj.summary())
        return {"error": f"A gravação falhou: {e}"}
    proj.update_source(sid, status="assistindo", duracao=src["duration"])
    await broadcast(app, type="project_update", project=proj.summary())
    job = asyncio.create_task(watch_job(app, proj, sid, src, rec["foco"]))
    app["jobs"].add(job)
    job.add_done_callback(app["jobs"].discard)
    note = f"Parei de gravar '{rec['title']}' ({minutes:.0f} min)" + (f", porque {reason}" if reason else "") + \
           f". Agora estou assistindo à gravação; quando terminar, o sistema te avisa. Diga isso a {USER} numa frase curta."
    if reason:   # nobody asked: tell Jarvis so it can tell the user
        for s in list(app["sessions"]):
            await s.notify("[sistema] " + note)
    return {"result": note}


async def record_tool(app, args):
    acao = args.get("acao")
    if acao == "iniciar":
        return await start_recording(app, args.get("titulo", ""), args.get("projeto", ""), args.get("foco", ""),
                                     args.get("minutos") or 0)
    if acao == "parar":
        return await stop_recording(app)
    info = recording_info(app)
    return {"result": f"Gravando '{info['titulo']}' há {(time.time() - info['desde']) / 60:.0f} min." if info["gravando"]
            else "Não estou gravando nada."}


async def api_recording(request):
    """GET: is Jarvis recording? POST {acao: iniciar|parar, titulo?, foco?, minutos?} (pid in the path = that project)."""
    app = request.app
    if request.method == "GET":
        return web.json_response(recording_info(app))
    body = await request.json()
    proj = projects.get(request.match_info["pid"]) if "pid" in request.match_info else None
    if body.get("acao") == "iniciar":
        r = await start_recording(app, body.get("titulo", ""), "", body.get("foco", ""), body.get("minutos") or 0, proj=proj)
    else:
        r = await stop_recording(app)
    return web.json_response({**r, "gravacao": recording_info(app)}, status=400 if "error" in r else 200)


async def chrome_js(win, tab, js, timeout=20):
    """Runs JavaScript in one Chrome tab (needs Chrome › View › Developer › Allow JavaScript from Apple Events)."""
    f = pathlib.Path(tempfile.gettempdir()) / f"jarvis-js-{os.getpid()}.js"
    f.write_text(js, encoding="utf-8")
    out, err = await osascript(f'tell application "Google Chrome" to execute tab id {tab} of window id {win} '
                               f'javascript (read POSIX file "{f}" as «class utf8»)', timeout=timeout)
    if err:
        raise RuntimeError("O Chrome não deixou o Jarvis ler a página: ligue Visualizar › Desenvolvedor › Permitir "
                           "JavaScript de Eventos da Apple." if "turned off" in err else f"Chrome: {err.strip()[:200]}")
    return out.strip()


async def chrome_json(win, tab, js):
    out = await chrome_js(win, tab, js)
    try:
        return json.loads(out) if out and out != "missing value" else None
    except json.JSONDecodeError:
        return None


async def start_course(app, projeto="", velocidade=1.5, proj=None, limite=0):
    """Takes the course lesson open in Chrome's front tab and studies every lesson of the course from there."""
    if app["rec"].get("now") or app["rec"].get("curso"):
        return {"error": "Já estou gravando. Peça para parar antes."}
    if not paths.recorder().exists():
        return {"error": "O gravador não está instalado: é preciso recompilar o Jarvis (app/build.sh)."}
    out, err = await osascript('tell application "Google Chrome" to get {id of front window, id of active tab of front window}', timeout=5)
    if err or not out:
        return {"error": "Abra uma aula do curso no Chrome (na aba da frente) e peça de novo."}
    win, tab = [x.strip() for x in out.split(",")[:2]]
    try:
        await chrome_js(win, tab, course.EXPAND)   # every module open, so the whole course is listed
        await asyncio.sleep(1.5)
        info = await chrome_json(win, tab, course.PAGE_INFO)
        clicked = await chrome_json(win, tab, course.ACTIVE)
    except RuntimeError as e:
        return {"error": str(e)}
    if not info or not info.get("player") or not info.get("aulas"):
        return {"error": "A aba da frente do Chrome não parece ser uma aula do curso (não achei o player e a lista de aulas)."}
    if not clicked:   # Chrome plays a video with sound only after a real click on the page
        return {"error": f"Antes de começar, {USER} precisa clicar uma vez na página da aula no Chrome (no título da aula, "
                         "não no vídeo). Um clique vale para o curso inteiro. Peça isso a ele e tente de novo."}
    name = info.get("curso") or info.get("pagina") or "Curso"
    proj = proj or (projects.find(projeto) if projeto else None) or active_project() or projects.create(name)
    c = course.Course(proj.folder)
    c.data.setdefault("nome", name)
    c.data["velocidade"] = min(2.0, max(1.0, float(velocidade or 1.5)))
    c.merge_lessons(info["aulas"])
    done, total = c.progress()
    state = {"proj": proj, "course": c, "win": win, "tab": tab, "stop": False, "since": time.time(), "limite": int(limite or 0),
             "status": f"Curso: {done} de {total} aulas", "proc": None}
    app["rec"]["curso"] = state
    state["task"] = asyncio.create_task(course_job(app, state))
    app["jobs"].add(state["task"])
    state["task"].add_done_callback(app["jobs"].discard)
    await broadcast(app, type="recording", **recording_info(app))
    log(f"curso: começou '{name}' no projeto '{proj.title}' ({done}/{total} feitas, {c.data['velocidade']:g}x)")
    return {"result": f"Comecei a estudar o curso no projeto '{proj.title}': {total - done} aulas pela frente, em "
                      f"{c.data['velocidade']:g}x, uma por vez. Cada aula vira fonte no Studio e nota no Obsidian, e eu "
                      f"reescrevo o manual de execução a cada aula. Diga a {USER} numa frase que ele pode usar o Mac (sem "
                      "minimizar a janela do Chrome do curso, sem bloquear a tela e com a tampa aberta) e que eu aviso no fim."}


async def stop_course(app):
    state = app["rec"].get("curso")
    if not state:
        return {"error": "Não estou estudando nenhum curso agora."}
    state["stop"] = True   # the recording loop sees it within seconds; the lesson being recorded stays pending
    return {"result": "Parei de estudar o curso. As aulas já assistidas continuam salvas; da próxima vez eu sigo de onde parei."}


class CourseAway(Exception):
    """The course tab isn't on the course any more: stop the course instead of failing every lesson."""


class LessonSkipped(Exception):
    """The menu item isn't a video lesson (a material page)."""


async def course_job(app, state):
    proj, c, speed = state["proj"], state["course"], state["course"].data["velocidade"]
    awake = await asyncio.create_subprocess_exec("/usr/bin/caffeinate", "-dis")   # no sleep, no screen lock, while studying
    volume, _ = await osascript("output volume of (get volume settings) & output muted of (get volume settings)")
    await osascript("set volume with output muted")   # the recording hears Chrome directly; the room stays quiet
    learning = None   # lessons are learned (manual rewritten) strictly in order, while the next one is recorded
    failures = 0
    try:
        recorded = 0
        while not state["stop"]:
            lesson = c.next_lesson()
            if lesson is None or (state["limite"] and recorded >= state["limite"]):
                break
            done, total = c.progress()
            state["status"] = f"Curso: aula {done + 1} de {total}"
            await broadcast(app, type="recording", **recording_info(app))
            try:
                sid, path, title = await record_lesson(app, state, lesson, speed)
            except LessonSkipped:
                continue
            except RuntimeError as e:
                log(f"curso: aula falhou: {lesson['titulo']}: {e}")
                c.mark(lesson["url"], status="erro", erro=str(e)[:300], tentativas=lesson.get("tentativas", 0) + 1)
                failures += 1
                if failures >= 3:
                    raise RuntimeError(f"três aulas seguidas falharam; a última: {e}")
                continue
            failures = 0
            if state["stop"]:
                break
            c.mark(lesson["url"], status="gravada", fonte=sid, titulo=title)
            recorded += 1
            learning = asyncio.create_task(learn_lesson(app, state, lesson["url"], sid, path, title, speed, learning))
        if learning:
            state["status"] = "Curso: terminando a última aula"
            await broadcast(app, type="recording", **recording_info(app))
            await learning
        for round_ in range(6):   # lessons whose analysis failed (Gemini quota): wait, then analyze the kept recordings
            pending = c.to_analyze()
            if not pending or state["stop"]:
                break
            state["status"] = f"Curso: reanalisando {len(pending)} aulas (tentativa {round_ + 1})"
            await broadcast(app, type="recording", **recording_info(app))
            log(f"curso: {len(pending)} aulas para analisar de novo; esperando {10 * (round_ + 1)} min")
            await asyncio.sleep(600 * (round_ + 1))
            for a in pending:
                if state["stop"]:
                    break
                proj.update_source(a["fonte"], status="assistindo", erro=None)
                await learn_lesson(app, state, a["url"], a["fonte"], pathlib.Path(a["caminho"]), a["titulo"], speed, None)
        done, total = c.progress()
        bad = [a["titulo"] for a in c.data["aulas"] if a["status"] == "erro"]
        note = (f"[sistema] Terminei de estudar o curso no projeto '{proj.title}': {done} de {total} aulas aprendidas" +
                (f"; falharam: {', '.join(bad[:5])}" if bad else "") + ". O manual de execução está no Obsidian. "
                f"Conte isso a {USER} em uma ou duas frases." if not state["stop"] else "")
    except Exception as e:   # noqa: BLE001 — reported to the user, never swallowed
        log(f"curso: parou com erro: {e!r}")
        note = f"[sistema] Parei de estudar o curso por um erro: {str(e)[:300]}. Diga isso a {USER} com honestidade."
    finally:
        awake.terminate()
        vol, muted = (volume or "").split(",")[:2] if "," in (volume or "") else ("", "false")
        if vol.strip().isdigit():
            await osascript(f"set volume output volume {vol.strip()}")
        await osascript("set volume with output muted" if muted.strip() == "true" else "set volume without output muted")
        app["rec"].pop("curso", None)
        await broadcast(app, type="recording", gravando=False)
        await broadcast(app, type="project_update", project=proj.summary())
    log(f"curso: fim ({c.progress()[0]}/{c.progress()[1]} aulas feitas)")
    if note:
        for s in list(app["sessions"]):
            await s.notify(note)


async def record_lesson(app, state, lesson, speed):
    """Opens the lesson in the course tab, plays it through the player's API and records it; returns (sid, path, title)."""
    proj, c, win, tab = state["proj"], state["course"], state["win"], state["tab"]
    # A hidden page (Chrome behind other apps or in another Space) never starts a new video: bring the course forward.
    await osascript(f'tell application "Google Chrome"\nset index of window id {win} to 1\nactivate\nend tell')
    await asyncio.sleep(1.5)
    here, _ = await osascript(f'tell application "Google Chrome" to get URL of tab id {tab} of window id {win}')
    if "tubeclub.com.br/aula/" not in (here or ""):   # someone used the course tab: opening by URL would lose the sound
        raise CourseAway(f"a aba do curso saiu da TubeClub ({(here or '?')[:60]}); "
                         f"{USER} precisa voltar a aba para a aula e clicar uma vez nela")
    await chrome_js(win, tab, course.EXPAND)
    await asyncio.sleep(1)
    if await chrome_js(win, tab, course.go(lesson["url"])) != "ok":   # a reload would lose the user's click (no sound)
        await osascript(f'tell application "Google Chrome" to set URL of tab id {tab} of window id {win} to "{lesson["url"]}"')
        log("curso: a aula não estava no menu; abri pelo endereço (o som pode ser bloqueado)")
    info = None
    for _ in range(30):   # the lesson and its player loading
        await asyncio.sleep(2)
        try:
            info = await chrome_json(win, tab, course.PAGE_INFO)
        except RuntimeError as e:
            if "Permitir" in str(e):
                raise
        if info and info.get("player") and info.get("url") == lesson["url"]:
            break
    if not info or info.get("url") != lesson["url"]:
        raise RuntimeError("a página da aula não abriu")
    if not info.get("player"):
        c.mark(lesson["url"], status="material")   # a PDF/XLSX page: no video to watch
        raise LessonSkipped()
    await asyncio.sleep(3)   # the new player finishing loading
    c.merge_lessons(info.get("aulas") or [])   # later modules show up as we move through the course
    title = info.get("titulo") or lesson["titulo"]
    entry = proj.add_source({"kind": "file", "source": "", "title": title, "status": "gravando"})
    sid = entry["id"]
    path = proj.source_dir(sid) / "video.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    proj.update_source(sid, origem=str(path), local=str(path), gravado=True, curso=True, pagina=lesson["url"], velocidade=speed)
    await broadcast(app, type="project_update", project=proj.summary())
    window_title, _ = await osascript(f'tell application "Google Chrome" to get title of tab id {tab} of window id {win}')
    proc, err = await spawn_recorder(path, "com.google.Chrome", (window_title or "").strip()[:40])
    if proc is None:
        proj.remove_source(sid)
        raise RuntimeError(f"não consegui gravar ({err})")
    state["proc"] = proc
    try:
        await chrome_js(win, tab, course.play(speed))
        started, last_t, last_move, stalls = time.time(), -1.0, time.time(), 0
        while not state["stop"]:
            await asyncio.sleep(4)
            st = await chrome_json(win, tab, course.STATUS) or {}
            t, d = float(st.get("t") or 0), float(st.get("d") or 0)
            if t > last_t + 0.5:
                last_t, last_move = t, time.time()
            elif t < 1 and time.time() - started > 20:   # never started: bring Chrome forward and try again
                await osascript(f'tell application "Google Chrome"\nset index of window id {win} to 1\nactivate\nend tell')
                if time.time() - started > 60:
                    raise RuntimeError("o player não começou a tocar")
                await chrome_js(win, tab, course.play(speed))
            if (d and t >= d - 3) or (st.get("fim") and not d):
                break
            if t > 5 and time.time() - last_move > 20:   # stopped in the middle: play again, don't take it as the end
                stalls += 1
                if stalls > 9:
                    if d and t < d * 0.9:
                        raise RuntimeError(f"o vídeo travou em {t / 60:.0f} de {d / 60:.0f} min")
                    break
                log(f"curso: o vídeo parou em {t / 60:.1f} min; dando play de novo")
                await chrome_js(win, tab, course.resume(speed))
                last_move = time.time()
            if time.time() - started > 4 * 3600:
                raise RuntimeError("a aula passou de 4 horas gravando")
    except Exception:
        state["proc"] = None
        await finish_recorder(proc)
        proj.remove_source(sid)
        raise
    state["proc"] = None
    failed = await finish_recorder(proc)
    if state["stop"]:
        proj.remove_source(sid)
        return sid, path, title
    if failed or not path.exists():
        proj.remove_source(sid)
        raise RuntimeError(failed or "a gravação não gerou arquivo")
    proj.update_source(sid, status="assistindo")
    await broadcast(app, type="project_update", project=proj.summary())
    log(f"curso: gravou '{title}' ({last_t / 60:.0f} min de aula)")
    return sid, path, title


async def learn_lesson(app, state, url, sid, path, title, speed, previous):
    """Watches the recorded lesson as a student, saves it (Studio + Obsidian) and rewrites the execution manual."""
    proj, c = state["proj"], state["course"]
    try:
        src = await video.describe(str(path))
        src["title"], src["local"] = title, str(path)
        analysis = await app["watcher"].analyze(src, lesson=True, speed=speed)
        proj.set_analysis(sid, analysis)
        proj.update_source(sid, status="pronto", obsidian=save_to_vault(proj, sid, analysis), duracao=src["duration"])
        if previous:
            await previous   # the manual learns lessons in course order
        manual = await c.learn(app["http"], app["key"], c.data.get("nome") or proj.title, title, analysis, log=log)
        VAULT.rewrite_note(f"Manual de execução — {c.data.get('nome') or proj.title}", manual, "referencia", "guide", "active",
                           proj.folder / "manual-historico")
        c.mark(url, status="feita")
        log(f"curso: aprendeu '{title}'")
    except Exception as e:   # noqa: BLE001 — this lesson goes back to the queue; the course goes on
        log(f"curso: não aprendeu '{title}': {e!r}")
        proj.update_source(sid, status="erro", erro=str(e)[:300])
        c.mark(url, status="analisar", erro=str(e)[:300], caminho=str(path))   # recording kept; analyzed again later
    await broadcast(app, type="project_update", project=proj.summary())


async def course_tool(app, args):
    acao = args.get("acao")
    if acao == "iniciar":
        return await start_course(app, args.get("projeto", ""), args.get("velocidade") or 1.5, limite=args.get("aulas") or 0)
    if acao == "parar":
        return await stop_course(app)
    st = app["rec"].get("curso")
    if st:
        return {"result": st["status"]}
    proj = active_project()
    if proj and (proj.folder / "curso.json").exists():
        done, total = course.Course(proj.folder).progress()
        return {"result": f"Não estou estudando agora. No projeto '{proj.title}': {done} de {total} aulas aprendidas."}
    return {"result": "Não estou estudando nenhum curso agora."}


async def api_course(request):
    """POST {acao: iniciar|parar, velocidade?} for the project in the path; GET: progress of that project's course."""
    proj = projects.get(request.match_info["pid"])
    if not proj:
        raise web.HTTPNotFound()
    if request.method == "GET":
        c = course.Course(proj.folder)
        return web.json_response({"aulas": c.data["aulas"], "progresso": c.progress(), **recording_info(request.app)})
    body = await request.json()
    r = await (start_course(request.app, velocidade=body.get("velocidade") or 1.5, proj=proj, limite=body.get("aulas") or 0)
               if body.get("acao") == "iniciar"
               else stop_course(request.app))
    return web.json_response({**r, "gravacao": recording_info(request.app)}, status=400 if "error" in r else 200)


async def watch_job(app, proj, sid, src, foco=""):
    watcher = app["watcher"]
    started = asyncio.get_running_loop().time()
    try:
        if src["kind"] == "url":
            await broadcast(app, type="project_progress", project=proj.id, source=sid, text="Baixando o vídeo")
            src["local"] = str(await video.download(src["source"], proj.source_dir(sid)))
        elif src["kind"] == "file":
            src["local"] = src["source"]
            proj.update_source(sid, local=src["source"])
        await broadcast(app, type="project_progress", project=proj.id, source=sid, text="Assistindo")

        async def progress(text):
            await broadcast(app, type="project_progress", project=proj.id, source=sid, text=text)

        analysis = await watcher.analyze(src, progress)
        if foco:
            analysis = f"> Foco pedido por {USER}: {foco}\n\n" + analysis
        proj.set_analysis(sid, analysis)
        if (proj.source(sid) or {}).get("titulo_auto"):
            src["title"] = await title_from_analysis(app, proj, sid, analysis, src["title"])
        took = asyncio.get_running_loop().time() - started
        proj.update_source(sid, status="pronto", segundos=round(took), obsidian=save_to_vault(proj, sid, analysis))
        log(f"vídeo assistido em {took:.0f}s: {src['title']}")
        overview = re.search(r"## Visão geral\s*(.*?)(?=\n## |\Z)", analysis, re.S)
        note = (f"[sistema] Terminei de assistir '{src['title']}' (projeto '{proj.title}'). Visão geral: "
                f"{(overview[1] if overview else analysis)[:1200]} Conte a {USER} em uma ou duas frases que terminou e o essencial; "
                "a análise completa já aparece na tela dele e você vai recebê-la inteira na próxima resposta.")
    except Exception as e:   # noqa: BLE001 — any failure is reported to the user, never swallowed
        log(f"vídeo falhou: {src.get('title')}: {e!r}")
        proj.update_source(sid, status="erro", erro=str(e)[:300])
        note = (f"[sistema] Não consegui assistir '{src.get('title')}': {str(e)[:300]}. Diga isso a {USER} com honestidade, "
                "em uma frase, sem inventar nada sobre o vídeo.")
    await broadcast(app, type="project_update", project=proj.summary())
    for s in list(app["sessions"]):
        if settings().get("projeto") == proj.id:
            s.reconnect_after_turn = True   # the next turn starts with the full analysis loaded
        await s.notify(note)
