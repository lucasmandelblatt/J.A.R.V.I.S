"""Non-video sources for projects (like Google AI Studio: links, documents and videos side by side).

- Sites: opened from the user's own Mac with a normal browser identity (news sites such as g1 refuse Claude's and Google's
  fetchers, not a browser), reduced to text and headline links, then read by Gemini into a Markdown analysis.
  A site marked "diario" is read again every day; each day's reading is kept in fontes/<id>/AAAA-MM-DD.md.
- Documents: PDF and images go to Gemini as they are; text files as text; Word/RTF/Pages through macOS textutil.
"""
import asyncio
import base64
import html
import mimetypes
import pathlib
import re
import urllib.parse
from html.parser import HTMLParser

import gem
from config import USER

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
      "Version/17.5 Safari/605.1.15")
MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash"]
VIDEO_HOSTS = re.compile(r"^https?://([a-z0-9-]+\.)*(youtube\.com|youtu\.be|instagram\.com|tiktok\.com|vimeo\.com|"
                         r"facebook\.com/(watch|reel)|fb\.watch|twitch\.tv|dailymotion\.com)/", re.I)
TEXT_EXT = {".txt", ".md", ".csv", ".json", ".html", ".htm", ".xml", ".srt", ".vtt", ".log", ".py", ".js"}
CONVERT_EXT = {".docx", ".doc", ".rtf", ".rtfd", ".pages", ".odt", ".webarchive"}
INLINE_MIME = ("application/pdf", "image/")
INLINE_MAX = 18 * 1024 * 1024   # inline request limit is 20 MB


def is_video_link(url):
    return bool(VIDEO_HOSTS.match(url.strip()))


class _Text(HTMLParser):
    """Visible text plus the links with their labels (a news front page is mostly headline links)."""
    SKIP = {"script", "style", "noscript", "svg", "template", "iframe", "head"}
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "section", "article", "header", "footer"}

    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.skip, self.out, self.links, self.title, self._a, self._in_title = base, 0, [], [], "", None, False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "a":
            href = dict(attrs).get("href") or ""
            self._a = [urllib.parse.urljoin(self.base, href), ""] if href and not href.startswith(("#", "javascript:")) else None
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag == "a" and self._a:
            label = " ".join(self._a[1].split())
            if len(label) >= 25:   # headline-sized link texts only
                self.links.append((label, self._a[0]))
            self._a = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self.skip:
            return
        self.out.append(data)
        if self._a is not None:
            self._a[1] += data


async def fetch_page(http, url):
    """(title, text, headline links) of a web page, fetched like Safari would."""
    async with http.get(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                                      "Accept": "text/html,application/xhtml+xml"},
                        timeout=__import__("aiohttp").ClientTimeout(total=30), allow_redirects=True) as r:
        if r.status >= 400:
            raise RuntimeError(f"o site respondeu {r.status}")
        raw = await r.text(errors="replace")
        final = str(r.url)
    p = _Text(final)
    p.feed(raw)
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.out))
    text = "\n".join(l.strip() for l in text.splitlines() if len(l.strip()) > 2)
    seen, links = set(), []
    for label, href in p.links:
        if href not in seen and urllib.parse.urlparse(href).scheme in ("http", "https"):
            seen.add(href)
            links.append((label, href))
    return html.unescape(p.title).strip() or final, text[:60000], links[:150]


SITE_PROMPT = """Você é o leitor de fontes do Jarvis, assistente de {user}. Abaixo está o conteúdo de {url} lido hoje ({today}).
{focus}Escreva em português do Brasil, em Markdown limpo, sem inventar nada que não esteja no conteúdo:
## Visão geral
Um parágrafo: o que é o site/página e o que ele traz hoje.
## Destaques
{shape}
## Para entender melhor
Contexto curto para os 2 ou 3 assuntos mais importantes (por que importam, o que observar).
Use títulos de matéria e links exatamente como aparecem na lista de manchetes. Se o conteúdo vier vazio ou for uma página de login/bloqueio, diga isso em uma frase."""


async def read_site(http, key, url, today, focus="", log=None):
    title, text, links = await fetch_page(http, url)
    if len(text) < 3000:   # a newsletter or archive page that only lists editions: open the newest ones on the same site
        host = urllib.parse.urlparse(url).netloc
        for _, href in [l for l in links if urllib.parse.urlparse(l[1]).netloc == host][:2]:
            try:
                t2, x2, _ = await fetch_page(http, href)
                text += f"\n\n--- {t2} ({href})\n{x2[:30000]}"
            except Exception:   # noqa: BLE001 — the listing alone is still worth reading
                pass
    heads = "\n".join(f"- {l} — {h}" for l, h in links)
    shape = ("Se for uma página inicial de notícias: as principais notícias agrupadas por tema (### Política, ### Economia, "
             "### Mundo…), uma linha cada com o título como link [título](url) e uma frase do que diz. Se for uma matéria ou "
             "artigo: os pontos principais em tópicos.")
    body = {"contents": [{"parts": [{"text": SITE_PROMPT.format(user=USER, url=url, today=today, shape=shape,
                                                                focus=f"Foco pedido por {USER}: {focus}\n" if focus else "")
                                     + f"\n\nTÍTULO: {title}\n\nMANCHETES E LINKS:\n{heads}\n\nTEXTO DA PÁGINA:\n{text}"}]}]}
    analysis = await gem.generate(http, key, body, MODELS, timeout=90, hedge=15, rounds=2, pause=(2, 5), log=log)
    return title, analysis


DOC_PROMPT = ("Você é o leitor de fontes do Jarvis, assistente de {user}. Leia o documento \"{name}\" e escreva em português do Brasil, "
              "em Markdown limpo, fiel ao conteúdo: ## Visão geral (um parágrafo), ## Pontos principais (tópicos), "
              "## Dados e números (o que houver), ## Para entender melhor (contexto e o que observar). {focus}")


async def doc_parts(path):
    """The Gemini parts that show a document: inline for PDF/images, text otherwise."""
    path = pathlib.Path(path)
    ext, mime = path.suffix.lower(), mimetypes.guess_type(path.name)[0] or ""
    if mime.startswith(INLINE_MIME) and path.stat().st_size <= INLINE_MAX:
        return [{"inlineData": {"mimeType": mime, "data": base64.b64encode(path.read_bytes()).decode()}}]
    if ext in TEXT_EXT:
        return [{"text": path.read_text(encoding="utf-8", errors="replace")[:200000]}]
    if ext in CONVERT_EXT:
        proc = await asyncio.create_subprocess_exec("/usr/bin/textutil", "-convert", "txt", "-stdout", str(path),
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(proc.communicate(), 60)
        if proc.returncode == 0 and out.strip():
            return [{"text": out.decode("utf-8", "replace")[:200000]}]
        raise RuntimeError("não consegui extrair o texto desse arquivo")
    raise RuntimeError(f"ainda não sei ler arquivos {ext or 'sem extensão'} (PDF, imagens, Word, texto e vídeos funcionam)")


async def read_doc(http, key, path, focus="", log=None):
    parts = await doc_parts(path) + [{"text": DOC_PROMPT.format(user=USER, name=pathlib.Path(path).name,
                                                                 focus=f"Foco pedido por {USER}: {focus}" if focus else "")}]
    return await gem.generate(http, key, {"contents": [{"parts": parts}]}, MODELS, timeout=120, hedge=15, rounds=2,
                              pause=(2, 5), log=log)


if __name__ == "__main__":   # self-check of the parser, no network
    p = _Text("https://ex.com/")
    p.feed("<html><head><title>Ex &amp; Co</title><script>x()</script></head><body><h1>Oi</h1>"
           "<a href='/n/1'>Uma manchete bem comprida sobre política hoje</a><a href='#'>topo</a></body></html>")
    assert html.unescape(p.title) == "Ex & Co" and "x()" not in "".join(p.out)
    assert p.links == [("Uma manchete bem comprida sobre política hoje", "https://ex.com/n/1")]
    assert is_video_link("https://youtu.be/abc") and not is_video_link("https://g1.globo.com/")
    print("ok")
