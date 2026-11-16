"""Course mode: Jarvis studies a whole course in the user's Chrome, lesson after lesson, like a student who will have to
run the business taught. This file holds what isn't tied to the server:

- the course state (projetos/<id>/curso.json): the lessons in order and which ones are done, so a restart resumes;
- the Chrome side: the JavaScript that reads the lesson list and drives the course's video player through the
  player's own public embed API (Panda Video: postMessage play / speed / currentTime, panda_timeupdate events);
- the execution manual (projetos/<id>/manual.md), rewritten after every lesson from the lesson notebook.

Nothing here downloads a video: Jarvis watches the lesson play in the browser, like the user would.
"""
import json
import pathlib

import gem
import video
from config import USER

MANUAL = """Você é o Jarvis, o assistente de {user}. Você está estudando o curso "{course}" aula por aula e, no fim, vai \
EXECUTAR o negócio ensinado. Abaixo está o seu MANUAL DE EXECUÇÃO atual (o que você aprendeu até agora) e o caderno da \
aula que você acabou de assistir ("{lesson}").

Reescreva o manual inteiro, em português do Brasil, em Markdown, incorporando TUDO o que esta aula acrescenta, corrige \
ou detalha. Não perca nada do manual atual (só junte o que se repete) e não invente nada que não esteja nas aulas. \
Seja concreto: passos, ferramentas, números, critérios e ordem de execução.

Formato:
## O negócio em uma página
O que é, como ganha dinheiro, para quem, e o resultado esperado.

## Plano de execução
Fases em ordem; em cada fase, passos NUMERADOS e acionáveis, com o detalhe de como fazer e a aula de onde veio \
(ex.: "(aula 3)").

## Estratégias e princípios
## Ferramentas, custos e configurações
## Métricas e metas
## Erros a evitar
## Dúvidas em aberto
O que ainda não ficou claro e pode ser respondido nas próximas aulas.

## Aulas estudadas
Uma linha por aula, em ordem: número, título e a ideia principal.

MANUAL ATUAL:
{manual}

CADERNO DA AULA "{lesson}":
{analysis}"""

# Runs in the lesson page (top frame): opens every collapsed module of the course menu so all lessons are listed.
EXPAND = r"""(() => { let n = 0;
  for (const b of document.querySelectorAll('button[aria-expanded="false"]'))
    if (/^\s*\d{2}\s/.test(b.innerText || '') && /conclu/i.test(b.innerText || '')) { b.click(); n++; }
  return n; })()"""

# Reads the course's lessons in page order (with their module and whether they're a video or a material), the lesson
# title, and whether the page has the course's player; also starts listening to the player's events once.
PAGE_INFO = r"""(() => {
  const isMod = (b) => /^\s*\d{2}\s/.test(b.innerText || '') && /conclu/i.test(b.innerText || '');
  const mods = [...document.querySelectorAll('button')].filter(isMod);
  const seen = new Set(), aulas = [];
  for (const a of document.querySelectorAll('a[href*="/aula/"]')) {
    const url = a.href.split('#')[0];
    if (seen.has(url)) continue; seen.add(url);
    const lines = (a.innerText || a.title || '').split('\n').map((x) => x.replace(/\s+/g, ' ').trim()).filter(Boolean);
    const raw = lines.slice(1).join(' ');   // first line: the title; then tags like "Aula 3", "Concluída", "Material 2 · PDF"
    let modulo = '';
    for (const m of mods) if (m.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING) modulo = m.innerText.replace(/\s+/g, ' ').trim();
    aulas.push({ url, modulo: modulo.replace(/\s*\d+\/\d+ conclu.*$/i, '').slice(0, 120),
      material: /Material \d+/i.test(raw),
      titulo: (lines[0] || '').slice(0, 160) });
  }
  const frame = document.querySelector('iframe[src*="pandavideo"]');
  if (frame && !window.__jarvis) {
    window.__jarvis = { t: 0, d: 0, at: 0, eventos: {} };
    addEventListener('message', (e) => {
      const m = e.data; if (!m || typeof m !== 'object' || !m.message) return;
      const f = document.querySelector('iframe[src*="pandavideo"]');   // only the lesson on screen (the site swaps players)
      if (m.video && f && new URL(f.src).searchParams.get('v') !== m.video) return;
      const j = window.__jarvis; j.eventos[m.message] = (j.eventos[m.message] || 0) + 1;
      if (m.message === 'panda_timeupdate') { j.t = +m.currentTime || j.t; j.at = Date.now(); }
      const pd = m.playerData; if (pd) { if (+pd.duration) j.d = +pd.duration; j.pausado = !!pd.paused; }
      if (+m.duration) j.d = +m.duration;
      if (/end|finish|complete/i.test(m.message)) j.fim = true;
    });
  }
  const h = document.querySelector('h1');
  const curso = document.querySelector('a[href*="/curso/"]');
  return JSON.stringify({ url: location.href.split('#')[0], curso: curso ? curso.innerText.replace(/\s+/g, ' ').trim() : '', titulo: (h ? h.innerText : document.title).replace(/\s+/g, ' ').trim(),
    pagina: document.title, player: !!frame, aulas });
})()"""

# Commands to the player through its public embed API (the same messages Panda's api.v2.js sends).
PLAYER = r"""(() => {
  const f = document.querySelector('iframe[src*="pandavideo"]'); if (!f) return 'sem player';
  const send = (type, parameter) => f.contentWindow.postMessage(parameter === undefined ? { type } : { type, parameter }, '*');
  %s
  return 'ok';
})()"""

STATUS = r"""JSON.stringify(window.__jarvis ? { t: window.__jarvis.t, d: window.__jarvis.d, parado: (Date.now() - window.__jarvis.at) / 1000,
  fim: !!window.__jarvis.fim, pausado: !!window.__jarvis.pausado, eventos: window.__jarvis.eventos } : null)"""


def play(speed):
    """Starts the lesson from the beginning at `speed`. Chrome only lets it play with sound after the user has clicked the
    course page once (sticky user activation); the course moves between lessons inside that same page (GO), so one
    click at the start lasts the whole course."""
    return PLAYER % ("if (window.__jarvis) Object.assign(window.__jarvis, { t: 0, d: 0, fim: false, at: Date.now(), eventos: {} });"
                     f"send('currentTime', 0); send('speed', {float(speed)}); send('play');")


def resume(speed):
    """Play again from where it stopped (a stall or a pause in the middle of the lesson)."""
    return PLAYER % f"send('speed', {float(speed)}); send('play');"


# Opens a lesson by clicking its link in the course menu: the site changes lessons without reloading the page, so
# the click the user gave the page at the start still counts and the player may play with sound.
GO = r"""((url) => {
  const a = [...document.querySelectorAll('a[href*="/aula/"]')].find((x) => x.href.split('#')[0] === url);
  if (!a) return 'sem link';
  a.click(); return 'ok';
})(%s)"""

ACTIVE = "JSON.stringify(navigator.userActivation.hasBeenActive)"


def go(url):
    return GO % json.dumps(url)


class Course:
    """The course being studied in a project: its lessons in order and how far Jarvis got."""

    def __init__(self, folder):
        self.file = pathlib.Path(folder) / "curso.json"
        self.manual_file = pathlib.Path(folder) / "manual.md"
        self.data = json.loads(self.file.read_text(encoding="utf-8")) if self.file.exists() else {"aulas": []}

    def save(self):
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.file)

    def merge_lessons(self, found):
        """Adds lessons seen on the page that aren't known yet, keeping the page order and what is already done."""
        known = {a["url"] for a in self.data["aulas"]}
        for a in found:
            if a["url"] not in known:
                self.data["aulas"].append({"url": a["url"], "titulo": a["titulo"], "modulo": a.get("modulo", ""),
                                           "status": "material" if a.get("material") else "pendente"})
                known.add(a["url"])
        self.save()

    def next_lesson(self):
        """The first lesson still to record (a failed one gets one more try before being skipped). Lessons recorded but
        not yet analyzed ("analisar": the Gemini quota ran out, say) keep their recording and are retried, not re-recorded."""
        for a in self.data["aulas"]:
            if a["status"] == "pendente" or (a["status"] == "erro" and a.get("tentativas", 0) < 2):
                return a
        return None

    def to_analyze(self):
        return [a for a in self.data["aulas"] if a["status"] == "analisar"]

    def mark(self, url, **fields):
        for a in self.data["aulas"]:
            if a["url"] == url:
                a.update(fields)
        self.save()

    def progress(self):
        lessons = [a for a in self.data["aulas"] if a["status"] != "material"]   # PDFs/XLSX aren't watched
        return sum(a["status"] == "feita" for a in lessons), len(lessons)

    @property
    def manual(self):
        return self.manual_file.read_text(encoding="utf-8") if self.manual_file.exists() else ""

    async def learn(self, http, key, course_title, lesson_title, analysis, log=None):
        """Rewrites the execution manual with what this lesson taught; returns it."""
        prompt = MANUAL.format(user=USER, course=course_title, lesson=lesson_title, analysis=analysis,
                               manual=self.manual or "(vazio: esta é a primeira aula)")
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2}}
        text = await gem.generate(http, key, body, video.MODELS, timeout=300, hedge=90, rounds=3, pause=(5, 15), log=log)
        i = text.find("## ")
        text = text[i:] if 0 <= i < 400 else text
        self.manual_file.write_text(text, encoding="utf-8")
        return text


if __name__ == "__main__":   # self-check of the lesson queue
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        c = Course(d)
        c.merge_lessons([{"url": "u1", "titulo": "Aula 1"}, {"url": "u2", "titulo": "Aula 2"}, {"url": "u1", "titulo": "x"}])
        assert [a["url"] for a in c.data["aulas"]] == ["u1", "u2"]
        c.mark("u1", status="feita")
        assert c.next_lesson()["url"] == "u2"
        c.mark("u2", status="erro", tentativas=2)
        assert c.next_lesson() is None and c.progress() == (1, 2)
        assert Course(d).progress() == (1, 2)   # resumes from disk
        print("ok")
