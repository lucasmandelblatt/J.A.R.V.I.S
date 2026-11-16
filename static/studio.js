// Studio: Jarvis projects as notebooks, in the spirit of NotebookLM (sources · chat with citations · Studio generators).
// Loaded after the main script in index.html: it reuses $, h, api, esc, fmtDur, openProject, setVoice, openStudy and the
// audio analyser (bins) that feeds the voice band. The voice-to-voice conversation is the same Gemini Live one as the rest
// of Jarvis; turning it on here opens this project so Jarvis talks about its sources.

const SV = (d) => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
const IC = {
  back: SV('<path d="M15 6l-6 6 6 6"/>'), close: SV('<path d="M6 6l12 12M18 6L6 18"/>'), plus: SV('<path d="M12 5v14M5 12h14"/>'),
  more: SV('<circle cx="12" cy="5.5" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="12" cy="18.5" r="1.2"/>'),
  search: SV('<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4 4"/>'), grid: SV('<path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z"/>'),
  list: SV('<path d="M4 6h16M4 12h16M4 18h16"/>'), sort: SV('<path d="M4 7h16M7 12h10M10 17h4"/>'), pin: SV('<path d="M9 4h6l-1 6 3 3H7l3-3zM12 13v7"/>'),
  panelL: SV('<rect x="3.5" y="4.5" width="17" height="15" rx="3"/><path d="M9.5 4.5v15"/>'), panelR: SV('<rect x="3.5" y="4.5" width="17" height="15" rx="3"/><path d="M14.5 4.5v15"/>'),
  send: SV('<path d="M12 19V5M6 11l6-6 6 6"/>'), mic: SV('<rect x="9" y="3.5" width="6" height="11" rx="3"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v2.5"/>'),
  tune: SV('<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>'),
  tag: SV('<path d="M4 12V4h8l8 8-8 8z"/><circle cx="8.5" cy="8.5" r="1.3"/>'), web: SV('<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.6 2.5 14.4 0 17M12 3.5c-2.5 2.6-2.5 14.4 0 17"/>'),
  spark: SV('<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/>'),
  arrow: SV('<path d="M5 12h14M13 6l6 6-6 6"/>'), pencil: SV('<path d="M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4"/>'), trash: SV('<path d="M5 7h14M10 7V5h4v2M7 7l1 13h8l1-13"/>'),
  copy: SV('<rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V5.5A1.5 1.5 0 0 0 14.5 4h-9A1.5 1.5 0 0 0 4 5.5v9A1.5 1.5 0 0 0 5.5 16H8"/>'),
  up: SV('<path d="M7 10h3V4h4v6h3l-5 5zM6 14v4h12v-4"/>'), thumbU: SV('<path d="M7 11v9H4v-9zM7 11l4-7c1.5 0 2.3 1 2 2.5L12.5 10H19a1.5 1.5 0 0 1 1.5 1.8l-1.4 6.5A2 2 0 0 1 17.2 20H7"/>'),
  thumbD: SV('<path d="M7 13V4H4v9zM7 13l4 7c1.5 0 2.3-1 2-2.5L12.5 14H19a1.5 1.5 0 0 0 1.5-1.8l-1.4-6.5A2 2 0 0 0 17.2 4H7"/>'),
  note: SV('<path d="M6 3.5h9l3.5 3.5v13.5H6zM14.5 3.5V7.5h4M9 12h6M9 16h6"/>'), save: SV('<path d="M9 4h6l-1 6 3 3H7l3-3zM12 13v7"/>'),
  doc: SV('<path d="M6 3.5h9l3.5 3.5v13.5H6zM14.5 3.5V7.5h4M9 12h6M9 16h4"/>'), pdf: SV('<path d="M6 3.5h9l3.5 3.5v13.5H6zM14.5 3.5V7.5h4"/><path d="M8.5 16v-4h1.5a1.2 1.2 0 0 1 0 2.4H8.5M13 12v4h1a2 2 0 0 0 0-4z"/>'),
  play: SV('<path d="M7 4.5v15l13-7.5z"/>'), pause: SV('<path d="M7 4.5h3.5v15H7zM13.5 4.5H17v15h-3.5z"/>'), film: SV('<rect x="3.5" y="5" width="17" height="14" rx="2.5"/><path d="M10 9.5l4.5 2.5-4.5 2.5z"/>'),
  image: SV('<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><circle cx="9" cy="10" r="1.6"/><path d="M4 17l5-4.5 4 3.5 3-2.5 4 3.5"/>'),
  wave: SV('<path d="M4 12h2M8 8v8M12 5v14M16 8v8M20 12h-2"/>'), yt: SV('<rect x="3" y="6" width="18" height="12" rx="4"/><path d="M10.5 9.5l4 2.5-4 2.5z"/>'),
  text: SV('<path d="M5 6h14M5 10h14M5 14h10M5 18h7"/>'), link: SV('<path d="M10 14l4-4M8.5 11.5l-2 2a3 3 0 0 0 4 4l2-2M15.5 12.5l2-2a3 3 0 0 0-4-4l-2 2"/>'),
  folder: SV('<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>'), chev: SV('<path d="M6 9l6 6 6-6"/>'),
  full: SV('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>'), shuffle: SV('<path d="M4 7h3l10 10h3M4 17h3l3-3M14 10l3-3h3M17 4l3 3-3 3M17 14l3 3-3 3"/>'),
  rec: SV('<rect x="3" y="4.5" width="18" height="12.5" rx="2.5"/><path d="M8.5 20.5h7"/><circle cx="12" cy="10.75" r="2.6" fill="currentColor"/>'),
  download: SV('<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>'), prev: SV('<path d="M15 6l-6 6 6 6"/>'), next: SV('<path d="M9 6l6 6-6 6"/>'), check: SV('<path d="M5 12.5l4.5 4.5L19 7.5"/>'),
};
const KINDS = [
  ['audio', 'Resumo de áudio', SV('<path d="M5 10v4M9 7v10M13 4v16M17 8v8M21 11v2"/>'), 'Podcast com dois apresentadores sobre as fontes'],
  ['slides', 'Apresentação de slides', SV('<rect x="3.5" y="5" width="17" height="12" rx="2"/><path d="M8 21h8M12 17v4"/>'), 'Deck pronto para apresentar'],
  ['video', 'Resumo de vídeo', IC.film, 'Vídeo narrado com cenas'],
  ['mapa', 'Mapa mental', SV('<circle cx="6" cy="12" r="2.2"/><circle cx="18" cy="5.5" r="2"/><circle cx="18" cy="12" r="2"/><circle cx="18" cy="18.5" r="2"/><path d="M8.2 12H16M8 11l8-5M8 13l8 5"/>'), 'Conceitos e ligações'],
  ['relatorio', 'Relatórios', SV('<path d="M6 3.5h9l3.5 3.5v13.5H6zM9 12h6M9 16h6M9 8h3"/>'), 'Briefing, guia de estudo, FAQ…'],
  ['cartoes', 'Cartões de estudo', SV('<rect x="7" y="3.5" width="13" height="15" rx="2.5"/><path d="M4 7v12a2 2 0 0 0 2 2h10"/>'), 'Flashcards para memorizar'],
  ['quiz', 'Questionário', SV('<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .8-1 1.5M12 16.5v.01"/>'), 'Teste de múltipla escolha'],
  ['infografia', 'Infografia', SV('<path d="M5 20V12M10 20V6M15 20v-9M20 20V4"/>'), 'Resumo visual em um pôster'],
  ['tabela', 'Tabela de dados', SV('<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M3.5 14.5h17M9.5 9.5v10"/>'), 'Dados extraídos das fontes'],
];
const SKIND = Object.fromEntries(KINDS.map(([k, label, icon, desc]) => [k, { label, icon, desc }]));
SKIND.nota = { label: 'Nota', icon: IC.note };
const OPTS = {
  audio: [['formato', 'Formato', [['conversa', 'Conversa aprofundada', 'Dois apresentadores destrinchando as fontes'], ['breve', 'Resumo breve', 'Só o essencial, rápido'],
    ['critica', 'Crítica', 'Avaliação construtiva das fontes'], ['debate', 'Debate', 'Cada um defende um lado']]], ['duracao', 'Duração', [['curta', 'Curta'], ['padrao', 'Padrão'], ['longa', 'Longa']]]],
  video: [['duracao', 'Duração', [['curta', 'Curta'], ['padrao', 'Padrão'], ['longa', 'Longa']]]],
  slides: [['formato', 'Formato', [['detalhada', 'Apresentação detalhada', 'Lê-se sozinha, com texto completo'], ['apoio', 'Slides de apoio', 'Pouco texto, para você falar']]],
    ['tamanho', 'Tamanho', [['curta', 'Curta'], ['padrao', 'Padrão'], ['longa', 'Longa']]]],
  relatorio: [['formato', 'Formato', [['briefing', 'Documento de briefing', 'Visão geral e pontos-chave'], ['estudo', 'Guia de estudo', 'Conceitos, perguntas e glossário'],
    ['blog', 'Post de blog', 'Texto envolvente e organizado'], ['faq', 'Perguntas frequentes', 'FAQ sobre as fontes'], ['linha', 'Linha do tempo', 'Datas e pessoas principais'],
    ['personalizado', 'Personalizado', 'Descreva abaixo o que quer']]]],
  cartoes: [['quantidade', 'Número de cartões', [['menos', 'Menos'], ['padrao', 'Padrão'], ['mais', 'Mais']]], ['dificuldade', 'Dificuldade', [['facil', 'Fácil'], ['media', 'Média'], ['dificil', 'Difícil']]]],
  quiz: [['quantidade', 'Número de perguntas', [['menos', 'Menos'], ['padrao', 'Padrão'], ['mais', 'Mais']]], ['dificuldade', 'Dificuldade', [['facil', 'Fácil'], ['media', 'Média'], ['dificil', 'Difícil']]]],
};
const FOCUS_HINT = { audio: 'Ex.: foque nas implicações para o Brasil; explique para iniciante', tabela: 'Que dados extrair? Ex.: empresas, valores e datas citados',
  relatorio: 'Ex.: um resumo executivo de uma página para meu chefe' };
const EMOJIS = '📔📘📗📕📙🧠💡🎯🚀🌎🇧🇷📈💰🏛️⚖️🧪🔬🎓✍️🎬🎧📰🗺️🏢🤝🧢👕🌱⚡🔥✨🫧🤖💼📊🧩🛠️🎨📷🍳'.match(/\p{Extended_Pictographic}(️)?(\p{Emoji_Modifier}|‍\p{Extended_Pictographic}|\p{Regional_Indicator})*|\p{Regional_Indicator}{2}/gu);

const studio = $('studio');
const nb = { open: false, view: 'home', tab: 'todos', layout: 'grid', sort: 'recente', q: '', col: null, pid: null, p: null, sel: new Set(), known: new Set(),
  items: [], notes: [], srcView: null, artView: null, timer: null, busy: false, ov: null, leftMin: false, rightMin: false };
let studioOpen = false;   // draw() in the main script paints the voice band while this is true
try { nb.layout = localStorage.getItem('st-layout') || 'grid'; } catch {}

const hue = (s) => [...s].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7);
const dateBR = (t) => t ? new Date(t.replace(' ', 'T')).toLocaleDateString('pt-BR') : '';
const ago = (t) => { const m = (Date.now() - new Date(t.replace(' ', 'T'))) / 60000; return m < 1 ? 'agora' : m < 60 ? `há ${m | 0} min` : m < 1440 ? `há ${m / 60 | 0} h` : dateBR(t); };
const nFontes = (n) => `${n} ${n === 1 ? 'fonte' : 'fontes'}`;
function btn(cls, html, title, on) { const b = h('button', { class: cls, type: 'button', html, title, 'aria-label': title }); if (on) b.onclick = on; return b; }
function toast(text) { document.querySelector('.st-toast')?.remove(); const t = h('div', { class: 'st-toast', role: 'status', text }); studio.append(t); setTimeout(() => t.remove(), 2600); }
async function jpost(url, body, method = 'POST') {
  const r = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  const d = await r.json().catch(() => ({})); if (!r.ok || d.error) throw new Error(d.error || r.status); return d;
}

// ---------- Rich text with citations ----------
function mdInline(s, cit) {
  return esc(s).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/(^|[^*])\*([^*\s][^*]*?)\*(?!\*)/g, '$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\[(\d{1,4})\]/g, (m, n) => cit && cit[n] ? `<button class="cite" type="button" data-n="${n}">${n}</button>` : (cit ? '' : m))
    .replace(/\[(\d{1,2}:\d{2}(?::\d{2})?)\]/g, '<button class="ts" type="button" data-ts="$1">$1</button>');
}
function md(text, cit) {
  const out = []; let list = null, para = [], table = null;
  const flush = () => { if (para.length) { out.push('<p>' + para.map((l) => mdInline(l, cit)).join('<br>') + '</p>'); para = []; } };
  const endList = () => { if (list) { out.push(`</${list}>`); list = null; } };
  const endTable = () => { if (table) { out.push('<table>' + table.map((r, i) => '<tr>' + r.map((c) => i ? `<td>${mdInline(c, cit)}</td>` : `<th>${mdInline(c, cit)}</th>`).join('') + '</tr>').join('') + '</table>'); table = null; } };
  for (const raw of String(text || '').split('\n')) {
    const line = raw.trim();
    if (/^\|.*\|$/.test(line)) { flush(); endList(); if (/^\|[\s:|-]+\|$/.test(line)) continue; (table ||= []).push(line.slice(1, -1).split('|').map((c) => c.trim())); continue; }
    endTable();
    let m;
    if ((m = line.match(/^[-*•] (.*)/)) || (m = line.match(/^\d+[.)] (.*)/))) {
      flush(); const kind = /^\d/.test(line) ? 'ol' : 'ul'; if (list !== kind) { endList(); out.push(`<${kind}>`); list = kind; }
      out.push('<li>' + mdInline(m[1], cit) + '</li>'); continue;
    }
    if ((m = line.match(/^(#{1,4}) (.*)/))) { flush(); endList(); out.push(`<h${Math.min(4, m[1].length + 1)}>${mdInline(m[2], cit)}</h${Math.min(4, m[1].length + 1)}>`); continue; }
    if (!line) { flush(); endList(); continue; }
    endList(); para.push(line);
  }
  flush(); endList(); endTable();
  return out.join('');
}
function mdEl(text, cit) { const d = h('div', { class: 'st-md', html: md(text, cit) }); d._cit = cit; return d; }

// Hovering a citation shows the passage; clicking opens the source with the passage highlighted
let tip = null;
studio.addEventListener('mouseover', (e) => {
  const c = e.target.closest('.cite'); if (!c) return;
  const cit = c.closest('.st-md')?._cit?.[c.dataset.n]; if (!cit) return;
  tip?.remove(); tip = h('div', { class: 'st-tip' }, h('b', { text: cit.titulo }), cit.trecho.length > 420 ? cit.trecho.slice(0, 420) + '…' : cit.trecho);
  studio.append(tip); const r = c.getBoundingClientRect(), t = tip.getBoundingClientRect();
  tip.style.left = Math.max(8, Math.min(innerWidth - t.width - 8, r.left - t.width / 2 + r.width / 2)) + 'px';
  tip.style.top = (r.top - t.height - 8 < 8 ? r.bottom + 8 : r.top - t.height - 8) + 'px';
  c.addEventListener('mouseleave', () => { tip?.remove(); tip = null; }, { once: true });
});
studio.addEventListener('click', (e) => {
  const c = e.target.closest('.cite');
  if (c) { const cit = c.closest('.st-md')?._cit?.[c.dataset.n]; if (cit) { tip?.remove(); openSource(cit.fonte, cit.trecho); } return; }
  const ts = e.target.closest('.ts');
  if (ts && nb.srcView) { const [a, b, d] = ts.dataset.ts.split(':').map(Number); openStudy(nb.pid, nb.srcView, d == null ? a * 60 + b : a * 3600 + b * 60 + d); }
});

// ---------- Menus and dialogs ----------
let openMenu = null;
function menu(anchor, items) {
  closeMenu();
  const m = h('div', { class: 'st-menu', role: 'menu' });
  for (const it of items) {
    if (it === '-') { m.append(h('hr')); continue; }
    const b = h('button', { type: 'button', role: 'menuitem', class: it.danger ? 'danger' : '' });
    if (it.icon) b.insertAdjacentHTML('beforeend', it.icon);
    b.append(h('span', {}, it.label, it.sub ? h('small', { text: it.sub }) : null));
    if (it.checked) b.insertAdjacentHTML('beforeend', `<span class="ck">${IC.check}</span>`);
    b.onclick = (e) => { e.stopPropagation(); closeMenu(); it.on(); };
    m.append(b);
  }
  studio.append(m); openMenu = m;
  const r = anchor.getBoundingClientRect(), mr = m.getBoundingClientRect();
  m.style.left = Math.max(8, Math.min(innerWidth - mr.width - 8, r.right - mr.width)) + 'px';
  m.style.top = (r.bottom + mr.height + 8 > innerHeight ? Math.max(8, r.top - mr.height - 6) : r.bottom + 6) + 'px';
  m.querySelector('button')?.focus();
  setTimeout(() => addEventListener('pointerdown', outside, true), 0);
}
function outside(e) { if (openMenu && !openMenu.contains(e.target)) closeMenu(); }
function closeMenu() { openMenu?.remove(); openMenu = null; removeEventListener('pointerdown', outside, true); }
let openDlg = null;
function dialog({ title, sub, body, ok, okText = 'Guardar', cancel = true, wide }) {
  closeDialog();
  const okB = ok ? h('button', { class: 'st-btn primary', type: 'button', text: okText }) : null;
  const d = h('div', { class: 'st-dlg' + (wide ? ' wide' : ''), role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
    h('header', {}, h('div', { style: 'flex:1' }, h('h2', { text: title }), sub ? h('p', { text: sub }) : null), btn('ib', IC.close, 'Fechar', closeDialog)),
    h('div', { class: 'body' }, body),
    ok || cancel ? h('footer', {}, cancel ? h('button', { class: 'st-btn ghost', type: 'button', text: 'Cancelar', onclick: null }) : null, okB) : null);
  const cancelB = d.querySelector('footer .ghost'); if (cancelB) cancelB.onclick = closeDialog;
  if (okB) okB.onclick = async () => { okB.disabled = true; try { if (await ok() !== false) closeDialog(); } catch (e) { toast('Erro: ' + e.message); } finally { okB.disabled = false; } };
  const s = h('div', { class: 'st-scrim' }, d); s.onpointerdown = (e) => { if (e.target === s) closeDialog(); };
  studio.append(s); openDlg = s;
  (d.querySelector('input, textarea') || okB || d.querySelector('button'))?.focus();
  return d;
}
function closeDialog() { openDlg?.remove(); openDlg = null; }
function choice(options, value, onPick, cards) {
  const box = h('div', { class: cards ? 'st-cards' : 'st-opts', role: 'radiogroup' });
  for (const [v, label, desc] of options) {
    const b = h('button', { type: 'button', role: 'radio', 'aria-pressed': String(v === value), 'aria-checked': String(v === value) }, cards ? h('b', { text: label }) : label, cards && desc ? h('span', { text: desc }) : null);
    b.onclick = () => { box.querySelectorAll('button').forEach((x) => { x.setAttribute('aria-pressed', String(x === b)); x.setAttribute('aria-checked', String(x === b)); }); onPick(v); };
    box.append(b);
  }
  return box;
}
function ask(title, value, okText = 'Guardar') {
  return new Promise((res) => { const inp = h('input', { type: 'text', value: value || '' });
    inp.onkeydown = (e) => { if (e.key === 'Enter') openDlg.querySelector('.primary').click(); };
    dialog({ title, body: inp, okText, ok: () => res(inp.value.trim()) });
    const sc = openDlg; new MutationObserver((_, o) => { if (!sc.isConnected) { o.disconnect(); res(null); } }).observe(studio, { childList: true }); });
}
function confirmDlg(title, sub, okText = 'Eliminar') { return new Promise((res) => { dialog({ title, sub, body: '', okText, ok: () => res(true) });
  const sc = openDlg; new MutationObserver((_, o) => { if (!sc.isConnected) { o.disconnect(); res(false); } }).observe(studio, { childList: true }); }); }

// ---------- Opening and closing ----------
function openStudio(pid) {
  if (study.open) closeStudy();
  setDrawer(false); nb.open = true; studio.classList.add('open'); studio.inert = false;
  if (pid) openNotebook(pid); else renderHome();
}
function closeStudio() {
  if (!nb.open) return;
  nb.open = false; studioOpen = false; clearInterval(nb.timer); closeMenu(); closeDialog(); undockReactor();
  studio.classList.remove('open'); studio.inert = true; audioStop();
}
$('openStudio').onclick = () => openStudio();
addEventListener('keydown', (e) => {
  if (e.key !== 'Escape' || !nb.open || study.open || drawer.classList.contains('open') || calx.classList.contains('open') || wxx.classList.contains('open')) return;
  e.stopPropagation();
  if (openMenu) closeMenu(); else if (openDlg) closeDialog(); else if (document.fullscreenElement) return;
  else if (nb.view === 'nb' && nb.artView) closeArt(); else if (nb.view === 'nb' && nb.srcView) closeSource();
  else if (nb.view === 'nb') renderHome(); else closeStudio();
}, true);

function topBar(kids) { return h('header', { class: 'st-top' }, ...kids); }
function logoBtn() {
  const b = h('button', { class: 'st-logo', type: 'button', title: 'Início do Studio' }, h('img', { src: '/static/jarvis-logo.png', alt: 'J.A.R.V.I.S.', onerror: "this.onerror=null;this.src='/static/logo.svg'" }), h('small', { text: 'STUDIO' }));
  b.onclick = () => renderHome(); return b;
}
function closeBtn() { return btn('ib', IC.close, 'Fechar o Studio (voltar ao painel)', closeStudio); }

// ---------- Home: projects as cards ----------
async function renderHome() {
  nb.view = 'home'; nb.pid = null; nb.p = null; studioOpen = false; clearInterval(nb.timer); audioStop(); undockReactor();
  let data, cols;
  try { [data, cols] = await Promise.all([api('/api/projects'), api('/api/colecoes')]); } catch { data = { projetos: [] }; cols = []; }
  const all = data.projetos;
  const tabs = h('div', { class: 'st-tabs', role: 'tablist' });
  for (const [k, label] of [['todos', 'Todos'], ['fixados', 'Fixados'], ['colecoes', 'Coleções']]) {
    const b = h('button', { role: 'tab', type: 'button', 'aria-selected': String(nb.tab === k), text: label }); b.onclick = () => { nb.tab = k; nb.col = null; renderHome(); }; tabs.append(b);
  }
  const search = h('label', { class: 'st-search', html: IC.search }, h('input', { placeholder: 'Pesquisar projetos', value: nb.q, 'aria-label': 'Pesquisar projetos' }));
  const inp = search.querySelector('input'); inp.oninput = () => { nb.q = inp.value; paint(); };
  const seg = h('div', { class: 'st-seg' });
  for (const [k, icon, t] of [['grid', IC.grid, 'Vista em grade'], ['list', IC.list, 'Vista em lista']]) {
    const b = btn('', icon, t, () => { nb.layout = k; try { localStorage.setItem('st-layout', k); } catch {} renderHome(); }); b.setAttribute('aria-pressed', String(nb.layout === k)); seg.append(b);
  }
  const body = h('div', { class: 'st-home-in' });
  studio.replaceChildren(topBar([logoBtn(), tabs, h('span', { class: 'st-grow' }), search, seg, closeBtn()]), h('main', { class: 'st-home' }, body));
  function paint() {
    const q = nb.q.trim().toLowerCase();
    const col = nb.col && cols.find((c) => c.id === nb.col);
    let list = all.filter((p) => !q || p.titulo.toLowerCase().includes(q));
    if (nb.tab === 'fixados') list = list.filter((p) => p.fixado);
    if (col) list = list.filter((p) => p.colecoes.includes(col.id));
    list.sort(nb.sort === 'titulo' ? (a, b) => a.titulo.localeCompare(b.titulo, 'pt') : (a, b) => b.atualizado.localeCompare(a.atualizado));
    if (nb.tab === 'todos' && !q) list.sort((a, b) => b.fixado - a.fixado);
    body.replaceChildren();
    if (nb.tab === 'colecoes' && !col) {
      const nw = h('button', { class: 'st-btn primary', type: 'button', html: IC.plus + 'Nova coleção' });
      nw.onclick = async () => { const n = await ask('Nova coleção', '', 'Criar'); if (n) { await jpost('/api/colecoes', { nome: n }); renderHome(); } };
      body.append(h('div', { class: 'st-home-head' }, h('h1', { text: 'As minhas coleções' }), h('span', { class: 'st-grow' }), nw));
      if (!cols.length) { body.append(h('div', { class: 'st-empty' }, h('b', { text: 'Nenhuma coleção ainda' }), 'Agrupe projetos relacionados em coleções, como pastas.')); return; }
      const g = h('div', { class: 'st-grid' });
      for (const c of cols) {
        const n = all.filter((p) => p.colecoes.includes(c.id)).length;
        const card = h('div', { class: 'st-card col', role: 'button', tabindex: '0' }, h('div', { class: 'emo', html: IC.folder }), h('h3', { text: c.nome }), h('div', { class: 'meta', text: `${n} ${n === 1 ? 'projeto' : 'projetos'}` }));
        card.onclick = () => { nb.col = c.id; paint(); }; card.onkeydown = (e) => { if (e.key === 'Enter') card.click(); };
        const more = btn('ib', IC.more, 'Ações da coleção', (e) => { e.stopPropagation(); menu(more, [
          { label: 'Mudar nome', icon: IC.pencil, on: async () => { const t = await ask('Nome da coleção', c.nome); if (t) { await jpost('/api/colecoes/' + c.id, { nome: t }, 'PATCH'); renderHome(); } } },
          { label: 'Eliminar coleção', icon: IC.trash, danger: true, sub: 'Os projetos continuam', on: async () => { if (await confirmDlg(`Eliminar a coleção "${c.nome}"?`, 'Os projetos dentro dela não são apagados.')) { await fetch('/api/colecoes/' + c.id, { method: 'DELETE' }); renderHome(); } } }]); });
        card.append(more); g.append(card);
      }
      body.append(g); return;
    }
    const sortB = btn('ib sm', IC.sort, 'Ordenar projetos', () => menu(sortB, [
      { label: 'Mais recente', checked: nb.sort === 'recente', on: () => { nb.sort = 'recente'; paint(); } },
      { label: 'Título', checked: nb.sort === 'titulo', on: () => { nb.sort = 'titulo'; paint(); } }]));
    const nw = h('button', { class: 'st-btn primary', type: 'button', html: IC.plus + 'Novo projeto' }); nw.onclick = newProject;
    const back = col ? btn('ib', IC.back, 'Voltar às coleções', () => { nb.col = null; paint(); }) : null;
    body.append(h('div', { class: 'st-home-head' }, back, h('h1', { text: col ? col.nome : nb.tab === 'fixados' ? 'Projetos fixados' : 'Projetos recentes' }), sortB, h('span', { class: 'st-grow' }), nw));
    if (!list.length && (q || nb.tab !== 'todos')) { body.append(h('div', { class: 'st-empty' }, h('b', { text: q ? 'Nada encontrado' : 'Nenhum projeto aqui' }), q ? 'Tente outro termo.' : col ? 'Adicione projetos pelo menu ⋮ de cada card.' : 'Fixe projetos pelo menu ⋮ de cada card.')); return; }
    if (nb.layout === 'list') {
      const L = h('div', { class: 'st-list' });
      for (const p of list) {
        const row = h('div', { class: 'st-row', role: 'button', tabindex: '0' }, h('div', { class: 'emo', text: p.emoji || '📔' }), h('b', { text: p.titulo }),
          h('span', { text: nFontes(p.fontes.length) }), h('span', { text: dateBR(p.atualizado) }));
        const more = btn('ib sm', IC.more, 'Ações do projeto', (e) => { e.stopPropagation(); cardMenu(more, p, cols); }); row.append(more);
        row.onclick = () => openNotebook(p.id); row.onkeydown = (e) => { if (e.key === 'Enter') row.click(); }; L.append(row);
      }
      body.append(L); return;
    }
    const g = h('div', { class: 'st-grid' });
    if (!col && nb.tab === 'todos' && !q) { const c = h('button', { class: 'st-card new', type: 'button' }, h('div', { class: 'plus', html: IC.plus }), h('span', { text: 'Criar projeto' })); c.onclick = newProject; g.append(c); }
    for (const p of list) {
      const card = h('div', { class: 'st-card', role: 'button', tabindex: '0', style: `--hue:${hue(p.id)}` }, h('div', { class: 'emo', text: p.emoji || '📔' }),
        p.fixado ? h('span', { class: 'pin', html: IC.pin, title: 'Fixado' }) : null, h('h3', { text: p.titulo }), h('div', { class: 'meta', text: `${dateBR(p.atualizado)} · ${nFontes(p.fontes.length)}` }));
      const more = btn('ib', IC.more, 'Ações do projeto', (e) => { e.stopPropagation(); cardMenu(more, p, cols); }); card.append(more);
      card.onclick = () => openNotebook(p.id); card.onkeydown = (e) => { if (e.key === 'Enter') card.click(); }; g.append(card);
    }
    body.append(g);
  }
  paint();
}
function cardMenu(anchor, p, cols) {
  const toCol = () => {
    const box = h('div');
    const pick = new Set(p.colecoes);
    for (const c of cols) { const cb = h('input', { type: 'checkbox', class: 'st-check', ...(pick.has(c.id) ? { checked: true } : {}) });
      cb.onchange = () => cb.checked ? pick.add(c.id) : pick.delete(c.id); box.append(h('label', { class: 'st-toggle', style: 'margin-top:8px;cursor:pointer' }, cb, h('span', { text: c.nome }))); }
    const nm = h('input', { type: 'text', placeholder: 'Ou crie uma coleção nova…' });
    box.append(h('label', { class: 'f', text: cols.length ? 'Nova coleção' : 'Nome da coleção' }), nm);
    dialog({ title: 'Adicionar à coleção', body: box, ok: async () => {
      if (nm.value.trim()) { const all = await jpost('/api/colecoes', { nome: nm.value.trim() }); pick.add(all[all.length - 1].id); }
      await jpost('/api/projects/' + p.id, { colecoes: [...pick] }, 'PATCH'); renderHome(); } });
  };
  menu(anchor, [
    { label: 'Editar título', icon: IC.pencil, on: async () => { const t = await ask('Título do projeto', p.titulo); if (t) { await jpost('/api/projects/' + p.id, { titulo: t }, 'PATCH'); renderHome(); } } },
    { label: 'Adicionar à coleção', icon: IC.folder, on: toCol },
    { label: p.fixado ? 'Desafixar' : 'Afixar na parte superior', icon: IC.pin, on: async () => { await jpost('/api/projects/' + p.id, { fixado: !p.fixado }, 'PATCH'); renderHome(); } },
    { label: 'Copiar projeto', icon: IC.copy, on: async () => { await jpost(`/api/projects/${p.id}/copiar`); toast('Projeto copiado'); renderHome(); } },
    '-',
    { label: 'Eliminar', icon: IC.trash, danger: true, on: async () => { if (await confirmDlg(`Eliminar "${p.titulo}"?`, 'O projeto vai para a Lixeira do Mac, com fontes, notas e itens do Studio.')) {
      await fetch('/api/projects/' + p.id, { method: 'DELETE' }); if (activeProject?.id === p.id) setActive(null); renderHome(); } } },
  ]);
}
async function newProject() {
  const p = await jpost('/api/projects', { titulo: 'Projeto sem nome' });
  await openNotebook(p.id); setTimeout(() => addSources(), 250);
}

// ---------- Notebook ----------
async function openNotebook(pid) {
  nb.view = 'nb'; nb.pid = pid; nb.el = null; nb.srcView = null; nb.artView = null; nb.ov = null; nb.sel = new Set(); nb.known = new Set(); audioStop();
  studio.replaceChildren(h('div', { class: 'st-empty' }, h('div', { class: 'st-spin', style: 'margin:30vh auto 0' })));
  try { await loadNotebook(); } catch { toast('Não consegui abrir o projeto'); return renderHome(); }
  const p = nb.p;
  const emo = h('button', { class: 'emo', type: 'button', title: 'Personalizar', text: p.emoji || '📔' }); emo.onclick = personalize;
  const title = h('input', { value: p.titulo, 'aria-label': 'Título do projeto', spellcheck: 'false' });
  title.onkeydown = (e) => { if (e.key === 'Enter') title.blur(); if (e.key === 'Escape') { title.value = nb.p.titulo; title.blur(); } };
  title.onchange = async () => { const t = title.value.trim(); if (!t) { title.value = nb.p.titulo; return; } await jpost('/api/projects/' + pid, { titulo: t }, 'PATCH'); nb.p.titulo = t; renderOverview(); };
  const create = h('button', { class: 'st-btn', type: 'button', html: IC.plus + 'Criar projeto' }); create.onclick = newProject;
  const more = btn('ib', IC.more, 'Configuração do projeto', () => menu(more, [
    { label: 'Configurar chat', icon: IC.tune, on: chatConfig },
    { label: 'Personalizar projeto', icon: IC.pencil, on: personalize },
    { label: 'Copiar projeto', icon: IC.copy, on: async () => { const c = await jpost(`/api/projects/${pid}/copiar`); toast('Cópia criada'); openNotebook(c.id); } },
    { label: 'Eliminar histórico do chat', icon: IC.trash, sub: 'Apaga as mensagens deste projeto', on: async () => { if (await confirmDlg('Eliminar o histórico do chat?', 'As mensagens deste projeto serão apagadas. As fontes, notas e itens do Studio ficam.')) {
      await fetch(`/api/projects/${pid}/chat`, { method: 'DELETE' }); nb.p.conversa = []; renderChat(); } } },
  ]));
  nb.el = { left: h('section', { class: 'st-panel', 'aria-label': 'Fontes' }), chat: h('section', { class: 'st-panel st-chat', 'aria-label': 'Chat' }), right: h('section', { class: 'st-panel', 'aria-label': 'Studio' }) };
  nb.grid = h('main', { class: 'st-nb' }, nb.el.left, nb.el.chat, nb.el.right);
  studio.replaceChildren(topBar([logoBtn(), h('div', { class: 'st-title' }, emo, title), create, more, closeBtn()]), nb.grid);
  nb.el.title = title; nb.el.emo = emo;
  buildChat(); renderSources(); renderStudio(); renderChat(); layout();
  studioOpen = true; wakeDraw();
  clearInterval(nb.timer); nb.timer = setInterval(poll, 4000);
}
async function loadNotebook() {
  const [p, items, notes, disc] = await Promise.all([api('/api/projects/' + nb.pid), api(`/api/projects/${nb.pid}/studio`), api(`/api/projects/${nb.pid}/notas`), api(`/api/projects/${nb.pid}/descobrir`)]);
  nb.p = p; nb.items = items; nb.notes = notes; nb.disc = disc;
  for (const s of p.fontes) if (!nb.known.has(s.id)) { nb.known.add(s.id); nb.sel.add(s.id); }
  for (const id of [...nb.sel]) if (!p.fontes.some((s) => s.id === id)) nb.sel.delete(id);
}
function layout() {
  if (!nb.grid) return;
  nb.grid.classList.toggle('l-min', nb.leftMin && !nb.srcView); nb.grid.classList.toggle('r-min', nb.rightMin && !nb.artView);
  nb.grid.classList.toggle('l-wide', !!nb.srcView); nb.grid.classList.toggle('r-wide', !!nb.artView);
  nb.el.left.classList.toggle('min', nb.leftMin && !nb.srcView); nb.el.right.classList.toggle('min', nb.rightMin && !nb.artView);
}
// Background work (sources being read, Studio items, web discovery): refresh those panels until it's done
async function poll() {
  if (!nb.open || nb.view !== 'nb' || nb.busy) return;
  const pending = nb.p.fontes.some((s) => ['lendo', 'assistindo'].includes(s.status)) || nb.items.some((a) => a.status === 'gerando') || nb.disc?.status === 'buscando';
  if (!pending) return;
  const before = JSON.stringify([nb.p.fontes, nb.items.map((a) => a.status), nb.disc]);
  try { await loadNotebook(); } catch { return; }
  if (JSON.stringify([nb.p.fontes, nb.items.map((a) => a.status), nb.disc]) === before) return;
  if (!nb.srcView) renderSources();
  if (!nb.artView) renderStudio();
  renderOverview(); countSel();
}
// Changes made elsewhere (by voice, the panel or another window) arrive as project messages: redraw what is on screen.
// Coalesced, and only the sources and Studio panels: the overview would ask Gemini again.
let studioSync = null;
window.jarvisStudio = (m) => {
  if (!nb.open || !['project_update', 'projects', 'project_progress'].includes(m.type)) return;
  if (m.type === 'project_progress') return void (nb.view === 'nb' && m.project === nb.pid && poll());
  if (nb.view === 'nb' && m.type === 'project_update' && m.project?.id !== nb.pid) return;
  clearTimeout(studioSync);
  studioSync = setTimeout(() => {
    if (nb.view === 'home') renderHome();
    else if (nb.view === 'nb' && !nb.busy) refresh('panels').catch(() => {});
  }, 400);
};
async function refresh(parts = 'all') { await loadNotebook(); if (!nb.srcView) renderSources(); if (!nb.artView) renderStudio(); if (parts === 'all') renderOverview(); countSel(); }

// ---------- Sources panel ----------
function srcKind(s) {
  const ext = (s.origem.split('?')[0].match(/\.(\w+)$/) || [])[1]?.toLowerCase();
  if (s.tipo === 'youtube') return ['yt', IC.yt]; if (s.tipo === 'site') return ['site', IC.web];
  if (s.gravado) return ['vid', IC.rec];
  if (s.tipo === 'url' || s.tipo === 'file') return ['vid', IC.film];
  if (ext === 'pdf') return ['pdf', IC.pdf]; if (/^(png|jpe?g|gif|webp|heic)$/.test(ext)) return ['img', IC.image];
  if (/^(mp3|m4a|wav|aac)$/.test(ext)) return ['aud', IC.wave]; if (/^(md|txt)$/.test(ext)) return ['txt', IC.text];
  return ['doc', IC.doc];
}
function panelHead(title, side) {
  const min = side === 'left' ? nb.leftMin : nb.rightMin;
  const t = btn('ib sm', side === 'left' ? IC.panelL : IC.panelR, min ? 'Expandir painel' : 'Recolher painel', () => {
    if (side === 'left') nb.leftMin = !nb.leftMin; else nb.rightMin = !nb.rightMin; layout(); side === 'left' ? renderSources() : renderStudio(); });
  return h('div', { class: 'st-ph' }, h('h2', { text: title }), t);
}
function renderSources() {
  const P = nb.el.left, p = nb.p; P.replaceChildren();
  if (nb.srcView) return renderSourceView();
  P.append(panelHead('Fontes', 'left'));
  const body = h('div', { class: 'st-pbody' }); P.append(body, orbBox());
  const rail = h('div', { class: 'st-rail' }, btn('ib', IC.plus, 'Adicionar fontes', addSources));
  for (const s of p.fontes.slice(0, 12)) { const [k, icon] = srcKind(s); rail.append(btn('ib', `<span class="ico ${k}" style="display:grid;place-items:center;width:26px;height:26px;border-radius:8px">${icon}</span>`, s.titulo, () => openSource(s.id))); }
  body.append(rail);
  const add = h('button', { class: 'st-btn st-add', type: 'button', html: IC.plus + 'Adicionar fontes' }); add.onclick = addSources; body.append(add);
  body.append(discoveryBox());
  if (!p.fontes.length) { body.append(h('div', { class: 'st-zero' }, h('div', { html: IC.doc }), h('b', { text: 'As fontes guardadas aparecem aqui' }),
    'Clique em Adicionar fontes para incluir PDFs, sites, vídeos do YouTube, áudio, documentos ou texto colado. Ou pesquise na web acima.')); return; }
  const all = h('input', { type: 'checkbox', class: 'st-check', 'aria-label': 'Selecionar todas as fontes' });
  all.checked = p.fontes.every((s) => nb.sel.has(s.id)); all.indeterminate = !all.checked && p.fontes.some((s) => nb.sel.has(s.id));
  all.onchange = () => { p.fontes.forEach((s) => all.checked ? nb.sel.add(s.id) : nb.sel.delete(s.id)); renderSources(); countSel(); };
  const tagB = btn('ib sm', IC.tag, 'Etiquetar fontes por tópico (automático)', async () => {
    tagB.replaceChildren(h('span', { class: 'st-spin' })); try { await jpost(`/api/projects/${nb.pid}/etiquetas`); await refresh(); toast('Fontes agrupadas por tópico'); } catch (e) { toast('Não consegui etiquetar: ' + e.message); renderSources(); } });
  const sortB = btn('ib sm', IC.sort, 'Ordenar fontes', () => menu(sortB, [
    { label: 'Mais recentes primeiro', checked: nb.srcSort !== 'antigo' && nb.srcSort !== 'nome', on: () => { nb.srcSort = 'recente'; renderSources(); } },
    { label: 'Mais antigas primeiro', checked: nb.srcSort === 'antigo', on: () => { nb.srcSort = 'antigo'; renderSources(); } },
    { label: 'Nome', checked: nb.srcSort === 'nome', on: () => { nb.srcSort = 'nome'; renderSources(); } }]));
  body.append(h('div', { class: 'st-tools' }, tagB, sortB, h('span', { class: 'lbl', text: 'Selecionar tudo' }), all));
  let list = [...p.fontes];
  if (nb.srcSort === 'nome') list.sort((a, b) => a.titulo.localeCompare(b.titulo, 'pt')); else if (nb.srcSort !== 'antigo') list.reverse();
  const tags = [...new Set(list.map((s) => s.etiqueta).filter(Boolean))];
  const groups = tags.length ? [...tags.map((t) => [t, list.filter((s) => s.etiqueta === t)]), ['Outras', list.filter((s) => !s.etiqueta)]] : [[null, list]];
  for (const [tag, items] of groups) {
    if (!items.length) continue;
    if (tag) body.append(h('div', { class: 'st-tag', text: tag }));
    for (const s of items) body.append(sourceRow(s));
  }
}
function sourceRow(s) {
  const [k, icon] = srcKind(s), busy = ['lendo', 'assistindo', 'gravando'].includes(s.status);
  const cb = h('input', { type: 'checkbox', class: 'st-check', 'aria-label': 'Selecionar ' + s.titulo, ...(nb.sel.has(s.id) ? { checked: true } : {}) });
  cb.onclick = (e) => e.stopPropagation(); cb.onchange = () => { cb.checked ? nb.sel.add(s.id) : nb.sel.delete(s.id); countSel(); };
  const more = btn('ib sm', IC.more, 'Mais', (e) => { e.stopPropagation(); sourceMenu(more, s); });
  const row = h('div', { class: 'st-src' + (s.status === 'erro' ? ' err' : ''), role: 'button', tabindex: '0', title: s.status === 'erro' ? 'Falhou: ' + (s.erro || '') : s.titulo },
    h('span', { class: 'ico ' + k, html: busy ? '<span class="st-spin"></span>' : icon }), h('span', { class: 't', text: s.titulo }), more, cb);
  row.onclick = () => openSource(s.id); row.onkeydown = (e) => { if (e.key === 'Enter') row.click(); };
  return row;
}
function sourceMenu(anchor, s) {
  const items = [
    { label: 'Mudar nome da fonte', icon: IC.pencil, on: async () => { const t = await ask('Nome da fonte', s.titulo); if (t) { await jpost(`/api/projects/${nb.pid}/sources/${s.id}/edit`, { titulo: t }, 'PATCH'); refresh(); } } },
  ];
  if (s.tipo === 'site') items.push(
    { label: 'Ler agora', icon: IC.web, on: async () => { await jpost(`/api/projects/${nb.pid}/sources/${s.id}/edit`, { reler: true }, 'PATCH'); refresh(); } },
    { label: 'Ler todo dia', icon: IC.spark, checked: !!s.diario, sub: 'O Jarvis relê toda manhã', on: async () => { await jpost(`/api/projects/${nb.pid}/sources/${s.id}/edit`, { diario: !s.diario }, 'PATCH'); refresh(); } });
  if (VIDEO_T.has(s.tipo) && s.status === 'pronto') items.push({ label: 'Estudar na tela grande', icon: IC.film, on: () => { closeStudio(); openStudy(nb.pid, s.id); } });
  if (/^https?:/.test(s.origem)) items.push({ label: 'Abrir original', icon: IC.link, on: () => open(s.origem, '_blank') });
  items.push('-', { label: 'Remover fonte', icon: IC.trash, danger: true, on: async () => { if (await confirmDlg(`Remover "${s.titulo}"?`, 'A fonte e a leitura dela saem do projeto.', 'Remover')) {
    await fetch(`/api/projects/${nb.pid}/sources/${s.id}/edit`, { method: 'DELETE' }); if (nb.srcView === s.id) nb.srcView = null; refresh(); } } });
  menu(anchor, items);
}
function countSel() {
  const ready = nb.p.fontes.filter((s) => nb.sel.has(s.id) && s.status === 'pronto').length;
  if (nb.el.cnt) nb.el.cnt.textContent = nFontes(ready);
}
// Source viewer: the "source guide" (the overview part of Jarvis's reading) and the full reading, with the cited passage lit
async function openSource(sid, passage) {
  nb.srcView = sid; nb.leftMin = false; layout(); renderSourceView(passage);
}
function closeSource() { nb.srcView = null; layout(); renderSources(); }
async function renderSourceView(passage) {
  const P = nb.el.left, s = nb.p.fontes.find((x) => x.id === nb.srcView);
  if (!s) return closeSource();
  const head = h('div', { class: 'st-ph' }, btn('ib sm', IC.back, 'Voltar às fontes', closeSource), h('h2', { text: 'Fonte' }), btn('ib sm', IC.more, 'Mais', (e) => sourceMenu(e.currentTarget, s)));
  const body = h('div', { class: 'st-pbody st-srcview' });
  P.replaceChildren(head, body, orbBox());
  body.append(h('h3', { text: s.titulo }));
  const orig = h('div', { class: 'orig' });
  if (/^https?:/.test(s.origem)) orig.append(h('a', { class: 'st-chipbtn', href: s.origem, target: '_blank', rel: 'noopener', html: IC.link + 'Abrir original' }));
  if (VIDEO_T.has(s.tipo) && s.status === 'pronto') { const b = h('button', { class: 'st-chipbtn', type: 'button', html: IC.film + 'Estudar na tela grande' }); b.onclick = () => { closeStudio(); openStudy(nb.pid, s.id); }; orig.append(b); }
  if (s.tipo === 'site' && s.lido) orig.append(h('span', { class: 'st-chipbtn', text: 'Lido em ' + dateBR(s.lido + ' 12:00') + (s.diario ? ' · todo dia' : '') }));
  body.append(orig);
  if (s.status === 'erro') { body.append(h('p', { style: 'color:#ff9a9a', text: 'Não consegui ler esta fonte: ' + (s.erro || 'erro desconhecido') })); return; }
  if (s.status !== 'pronto') { body.append(h('div', { class: 'st-zero' }, h('div', { class: 'st-spin', style: 'margin:0 auto 10px' }),
    s.status === 'gravando' ? 'Gravando a tela. Quando o vídeo acabar, aperte Parar no aviso "Gravando" e o Jarvis assiste à gravação.' : 'O Jarvis ainda está lendo esta fonte.')); return; }
  let full; try { full = await api(`/api/projects/${nb.pid}/sources/${s.id}`); } catch { return; }
  if (nb.srcView !== s.id) return;
  const text = full.analise || '';
  const ov = (text.match(/##\s*Vis[aã]o geral\s*\n([\s\S]*?)(\n##\s|$)/i) || [])[1] || text.split(/\n\s*\n/).find((x) => x.trim() && !x.startsWith('#')) || '';
  const kws = [...new Set([...text.matchAll(/\*\*([^*]{3,40})\*\*/g)].map((m) => m[1].replace(/[:.]$/, '').trim()))].filter((k) => k.length > 2 && !/^[\[\d(-]/.test(k)).slice(0, 8);
  const guide = h('div', { class: 'st-guide' }, h('button', { type: 'button', html: IC.spark + '<span>Guia da fonte</span>' + IC.chev }),
    h('div', { class: 'in' }, mdEl(ov.trim()), kws.length ? h('div', { class: 'kw' }, ...kws.map((k) => h('span', { text: k }))) : null));
  guide.firstChild.onclick = () => guide.classList.toggle('closed');
  const content = mdEl(text);
  body.append(guide, content);
  if (passage) {
    const norm = (x) => x.toLowerCase().normalize('NFD').replace(/[^a-z0-9]/g, '');
    const whole = norm(passage), hits = [...content.querySelectorAll('p, li, h3, h4, td')].filter((el) => { const t = norm(el.textContent); return t.length > 12 && whole.includes(t.slice(0, 60)); });
    hits.forEach((el) => el.classList.add('st-hl'));
    const target = hits[0];
    if (target) { guide.classList.add('closed'); setTimeout(() => target.scrollIntoView({ block: 'center', behavior: 'smooth' }), 60); }
  }
}
// "Search the web for new sources": quick or deep research (Claude with web search), results imported as sources
function discoveryBox() {
  const d = nb.disc || {};
  const box = h('div', { class: 'st-disc' });
  if (d.status) {
    const res = h('div', { class: 'st-res' });
    if (d.status === 'buscando') res.append(h('div', { class: 'st-res-head' }, h('span', { class: 'st-spin' }), `${d.modo === 'profunda' ? 'Pesquisa profunda' : 'Pesquisa rápida'}: "${d.consulta}"… pode levar ${d.modo === 'profunda' ? 'alguns minutos' : 'um minuto'}.`));
    else if (d.status === 'erro') res.append(h('div', { class: 'st-res-head', text: 'A pesquisa falhou: ' + (d.erro || '') }));
    else {
      res.append(h('div', { class: 'st-res-head', html: IC.web }, h('span', { text: `${d.resultados.length} fontes para "${d.consulta}"` })));
      const picks = [];
      if (d.relatorio) { const cb = h('input', { type: 'checkbox', class: 'st-check', checked: true }); picks.push(['__rel', cb]);
        res.append(h('label', {}, cb, h('span', {}, h('b', { text: 'Relatório da pesquisa' }), h('small', { text: 'O texto completo que o Jarvis escreveu' })))); }
      for (const r of d.resultados) { const cb = h('input', { type: 'checkbox', class: 'st-check', checked: true }); picks.push([r.url, cb]);
        res.append(h('label', {}, cb, h('span', {}, r.titulo, h('small', { text: r.url.replace(/^https?:\/\/(www\.)?/, '') })))); }
      const imp = h('button', { class: 'st-btn primary', type: 'button', html: IC.plus + 'Importar' });
      imp.onclick = async () => { imp.disabled = true; const urls = picks.filter(([u, c]) => u !== '__rel' && c.checked).map(([u]) => u);
        await jpost(`/api/projects/${nb.pid}/descobrir`, { importar: urls, relatorio: picks.some(([u, c]) => u === '__rel' && c.checked) }); toast('Importando fontes'); refresh(); };
      res.append(h('div', { class: 'st-res-actions' }, h('button', { class: 'st-btn ghost', type: 'button', text: 'Descartar', onclick: null }), imp));
    }
    if (d.status !== 'pronto') res.append(h('div', { class: 'st-res-actions' }, h('button', { class: 'st-btn ghost', type: 'button', text: d.status === 'buscando' ? 'Cancelar' : 'Fechar' })));
    res.querySelector('.st-res-actions .ghost').onclick = async () => { await fetch(`/api/projects/${nb.pid}/descobrir`, { method: 'DELETE' }); nb.disc = {}; renderSources(); };
    box.append(res);
    return box;
  }
  const ta = h('textarea', { rows: 1, placeholder: 'Pesquise novas fontes na web', 'aria-label': 'Pesquisar novas fontes na web' });
  let mode = 'rapida';
  const modeB = h('button', { class: 'st-chipbtn', type: 'button', html: IC.spark + '<span>Pesquisa rápida</span>' + IC.chev });
  modeB.onclick = () => menu(modeB, [
    { label: 'Pesquisa rápida', sub: 'Resultados em cerca de um minuto', checked: mode === 'rapida', on: () => { mode = 'rapida'; modeB.querySelector('span').textContent = 'Pesquisa rápida'; } },
    { label: 'Pesquisa profunda', sub: 'Relatório completo e mais fontes (minutos)', checked: mode === 'profunda', on: () => { mode = 'profunda'; modeB.querySelector('span').textContent = 'Pesquisa profunda'; } }]);
  const go = btn('ib sm', IC.arrow, 'Pesquisar', async () => { const q = ta.value.trim(); if (!q) return ta.focus();
    nb.disc = await jpost(`/api/projects/${nb.pid}/descobrir`, { consulta: q, modo: mode }); renderSources(); });
  ta.onkeydown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); go.click(); } };
  box.append(ta, h('div', { class: 'st-disc-row' }, h('span', { class: 'st-chipbtn', html: IC.web + 'Web' }), modeB, h('span', { class: 'st-grow' }), go));
  return box;
}
function addSources() {
  const n = nb.p.fontes.length;
  const input = h('input', { type: 'file', multiple: true, hidden: true });
  const drop = h('div', { class: 'st-drop', role: 'button', tabindex: '0' }, h('div', { class: 'up', html: IC.up }), h('b', { text: 'Carregar fontes' }),
    h('span', { text: 'Arraste e solte ou clique para escolher: PDF, imagens, Word, textos, áudio e vídeo' }), input);
  drop.onclick = () => input.click(); drop.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } };
  input.onchange = () => { sendFiles(input.files); closeDialog(); };
  drop.ondragover = (e) => { e.preventDefault(); e.stopPropagation(); drop.classList.add('over'); };
  drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = (e) => { e.preventDefault(); e.stopPropagation(); $('drop').classList.remove('on'); sendFiles(e.dataTransfer.files); closeDialog(); };
  const sub = h('div');
  const linkB = h('button', { class: 'st-chipbtn', type: 'button', html: IC.link + 'Site ou link' }), ytB = h('button', { class: 'st-chipbtn', type: 'button', html: IC.yt + 'YouTube e vídeos' }),
    txtB = h('button', { class: 'st-chipbtn', type: 'button', html: IC.text + 'Texto copiado' }), recB = h('button', { class: 'st-chipbtn', type: 'button', html: IC.rec + 'Gravar da tela' }), curB = h('button', { class: 'st-chipbtn', type: 'button', html: IC.folder + 'Curso inteiro' }), webB = h('button', { class: 'st-chipbtn', type: 'button', html: IC.web + 'Pesquisar na web' });
  const showLink = (video) => {
    const u = h('input', { type: 'text', placeholder: video ? 'Cole o link do YouTube, Instagram, TikTok, Vimeo…' : 'Cole o endereço do site (ex.: g1.globo.com)' });
    const daily = h('input', { type: 'checkbox', class: 'st-check' });
    const go = h('button', { class: 'st-btn primary', type: 'button', text: 'Inserir' });
    go.onclick = async () => { const url = u.value.trim(); if (!url) return u.focus(); go.disabled = true;
      try { await jpost(`/api/projects/${nb.pid}/sources`, { url, diario: daily.checked }); closeDialog(); toast(video ? 'O Jarvis está assistindo' : 'O Jarvis está lendo o site'); refresh(); } catch (e) { toast('Erro: ' + e.message); go.disabled = false; } };
    u.onkeydown = (e) => { if (e.key === 'Enter') go.click(); };
    sub.replaceChildren(h('div', { class: 'st-sub' }, h('label', { class: 'f', style: 'margin-top:0', text: video ? 'Link do vídeo' : 'Endereço do site' }), u,
      h('div', { class: 'r' }, video ? null : h('label', { style: 'display:flex;gap:8px;align-items:center;cursor:pointer;font-size:13px' }, daily, 'Ler este site de novo todo dia'), h('span', { class: 'st-grow' }), go)));
    u.focus();
  };
  linkB.onclick = () => showLink(false); ytB.onclick = () => showLink(true);
  txtB.onclick = () => {
    const t = h('input', { type: 'text', placeholder: 'Título (opcional)' }), ta = h('textarea', { placeholder: 'Cole o texto aqui' });
    const go = h('button', { class: 'st-btn primary', type: 'button', text: 'Inserir' });
    go.onclick = async () => { if (!ta.value.trim()) return ta.focus(); go.disabled = true; await jpost(`/api/projects/${nb.pid}/texto`, { titulo: t.value, texto: ta.value }); closeDialog(); refresh(); };
    sub.replaceChildren(h('div', { class: 'st-sub' }, t, h('div', { style: 'height:8px' }), ta, h('div', { class: 'r' }, h('span', { class: 'st-grow' }), go))); ta.focus();
  };
  recB.onclick = () => {   // for videos that can't be downloaded (courses behind a login): Jarvis records the screen and the Mac's sound
    const t = h('input', { type: 'text', placeholder: 'Nome da aula (vazio = título da aba do Chrome)' });
    const m = h('input', { type: 'number', min: '1', placeholder: 'Duração em minutos (opcional: para sozinho)', style: 'margin-top:8px' });
    const go = h('button', { class: 'st-btn primary', type: 'button', text: 'Começar a gravar' });
    go.onclick = async () => { go.disabled = true;
      try { const r = await jpost(`/api/projects/${nb.pid}/gravacao`, { acao: 'iniciar', titulo: t.value.trim(), minutos: +m.value || 0 });
        closeDialog(); window.jarvisRec?.(r.gravacao); toast('Gravando: coloque o vídeo em tela cheia e dê play'); refresh(); }
      catch (e) { toast('Não consegui gravar: ' + e.message); go.disabled = false; } };
    sub.replaceChildren(h('div', { class: 'st-sub' }, h('label', { class: 'f', style: 'margin-top:0', text: 'Gravar o vídeo que está na tela' }), t, m,
      h('p', { style: 'font-size:12.5px;opacity:.75;margin:10px 0 0', text: 'Use para aulas de cursos e vídeos que pedem login. O Jarvis grava a tela e o som do Mac (não o microfone); deixe o som do vídeo ligado e em tela cheia. Ao parar, ele assiste à gravação e ela fica nas fontes do projeto e no Obsidian.' }),
      h('div', { class: 'r' }, h('span', { class: 'st-grow' }), go))); t.focus();
  };
  curB.onclick = () => {   // course mode: every lesson of the course open in Chrome, one after another, learned like a student
    const sp = h('select', {}, ...[['1.5', '1,5x (recomendado)'], ['1', '1x (mais fiel, mais lento)'], ['2', '2x (perde detalhes)']].map(([v, t]) => h('option', { value: v, text: t })));
    const go = h('button', { class: 'st-btn primary', type: 'button', text: 'Estudar o curso' });
    go.onclick = async () => { go.disabled = true;
      try { const r = await jpost(`/api/projects/${nb.pid}/curso`, { acao: 'iniciar', velocidade: +sp.value });
        closeDialog(); window.jarvisRec?.(r.gravacao); toast('O Jarvis começou a estudar o curso'); refresh(); }
      catch (e) { toast('Não consegui: ' + e.message); go.disabled = false; } };
    sub.replaceChildren(h('div', { class: 'st-sub' }, h('label', { class: 'f', style: 'margin-top:0', text: 'Velocidade das aulas' }), sp,
      h('p', { style: 'font-size:12.5px;opacity:.75;margin:10px 0 0', text: 'Abra uma aula do curso na aba da frente do Chrome. O Jarvis toca cada aula, grava só a janela do Chrome, estuda como um aluno e guarda cada aula aqui e no Obsidian, com um manual de execução que ele reescreve a cada aula. Ele segue de onde parou. Deixe a tampa aberta (pode baixar o brilho), não minimize o Chrome e não bloqueie a tela.' }),
      h('div', { class: 'r' }, h('span', { class: 'st-grow' }), go)));
  };
  webB.onclick = () => { closeDialog(); nb.el.left.querySelector('.st-disc textarea')?.focus(); };
  dialog({ title: 'Adicionar fontes', sub: 'As fontes são a base do Jarvis neste projeto: ele responde, cita e cria tudo a partir delas.', wide: true, cancel: false,
    body: h('div', {}, drop, h('div', { class: 'st-addrow' }, linkB, ytB, recB, curB, txtB, webB), sub,
      h('div', { class: 'st-limit' }, h('span', { text: 'Limite de fontes' }), h('i', {}, h('b', { style: `width:${Math.min(100, n * 2)}%` })), h('span', { text: `${n}/50` }))) });
}
async function sendFiles(files) {
  if (!files?.length || !nb.pid) return;
  toast(`Enviando ${files.length} ${files.length === 1 ? 'arquivo' : 'arquivos'}…`);
  const fd = new FormData(); for (const f of files) fd.append('file', f, f.name);
  try { await fetch(`/api/projects/${nb.pid}/files`, { method: 'POST', body: fd }); } catch (e) { toast('Falha no envio: ' + e.message); }
  refresh();
}
// Files dropped anywhere while a project is open in the Studio go into that project
const _studioUpload = upload;
upload = async function (files) { if (nb.open && nb.view === 'nb') return sendFiles(files); return _studioUpload(files); };

// ---------- Chat ----------
function buildChat() {
  const C = nb.el.chat;
  const cfg = btn('ib sm', IC.tune, 'Configurar chat', chatConfig);
  const scroll = h('div', { class: 'st-pbody' }), inner = h('div', { class: 'st-chat-in' }); scroll.append(inner);
  const ta = h('textarea', { rows: 1, placeholder: 'Faça uma pergunta ou peça algo sobre as fontes', 'aria-label': 'Pergunta' });
  const cnt = h('span', { class: 'cnt' });
  const mic = btn('st-mic', IC.mic, 'Conversar por voz com o Jarvis', voiceToggle); mic.setAttribute('aria-pressed', 'false');
  const send = btn('st-send', IC.send, 'Enviar', () => sendQuestion(ta.value)); send.disabled = true;
  ta.oninput = () => { ta.style.height = 'auto'; ta.style.height = Math.min(180, ta.scrollHeight) + 'px'; send.disabled = !ta.value.trim(); };
  ta.onkeydown = (e) => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (ta.value.trim()) sendQuestion(ta.value); } };
  C.append(h('div', { class: 'st-ph' }, h('h2', { text: 'Chat' }), cfg), scroll,
    h('div', { class: 'st-composer-wrap' }, h('div', { class: 'st-composer' }, ta, cnt, mic, send), h('div', { class: 'st-foot', text: 'O Jarvis pode errar. Confira nas fontes citadas.' })));
  Object.assign(nb.el, { scroll, inner, ta, cnt, send, mic });
  countSel();
}
function renderChat() {
  const inner = nb.el.inner; inner.replaceChildren(h('div', { class: 'st-ov' }));
  const bottom = () => nb.el.scroll.scrollTo({ top: nb.el.scroll.scrollHeight, behavior: 'instant' });
  renderOverview().then(bottom);
  let day = '';
  for (const l of nb.p.conversa || []) {
    const d = l.t.slice(0, 10);
    if (d !== day) { day = d; inner.append(h('div', { class: 'st-day', text: new Date(d + 'T12:00').toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' }) })); }
    inner.append(l.who === USER_NAME ? userMsg(l.text) : modelMsg(l.text, l.cit, null, !('cit' in l)));
  }
  const last = (nb.p.conversa || []).slice(-1)[0];
  if (last?.sugestoes?.length) inner.append(suggestions(last.sugestoes));
  bottom();
}
async function renderOverview() {
  const box = nb.el.inner?.querySelector('.st-ov'); if (!box) return;
  const p = nb.p, ready = p.fontes.filter((s) => s.status === 'pronto').length;
  nb.el.emo.textContent = p.emoji || '📔';
  box.replaceChildren(h('div', { class: 'emo', text: p.emoji || '📔' }), h('h1', { text: p.titulo }), h('div', { class: 'cnt', text: nFontes(p.fontes.length) }));
  if (!ready) { box.append(h('p', { class: 'st-muted', text: p.fontes.length ? 'O Jarvis está lendo as fontes. O resumo do projeto aparece aqui quando ele terminar.' : 'Adicione fontes para começar. Depois pergunte o que quiser: o Jarvis responde citando de onde tirou cada informação.' }));
    if (!p.fontes.length) { const b = h('button', { class: 'st-btn primary', type: 'button', html: IC.plus + 'Adicionar fontes', style: 'margin-top:12px' }); b.onclick = addSources; box.append(b); } return; }
  const slot = h('div', {}, h('div', { class: 'st-think' }, h('i'), h('i'), h('i'))); box.append(slot);
  const key = p.fontes.filter((s) => s.status === 'pronto').map((s) => s.id + s.lido).join();
  if (!nb.ov || nb.ov.key !== key) { try { nb.ov = { key, ...(await api(`/api/projects/${nb.pid}/resumo`)) }; } catch { nb.ov = { key, texto: '', perguntas: [] }; } }
  if (!slot.isConnected) return;
  const ov = nb.ov;
  if (ov.emoji && !p.emoji) { p.emoji = ov.emoji; box.firstChild.textContent = ov.emoji; nb.el.emo.textContent = ov.emoji; }
  if (/^Projeto sem nome$|^Projeto novo$/.test(p.titulo) && ov.titulo) { await jpost('/api/projects/' + nb.pid, { titulo: ov.titulo }, 'PATCH'); p.titulo = ov.titulo; nb.el.title.value = ov.titulo; box.children[1].textContent = ov.titulo; }
  slot.replaceChildren(ov.texto ? mdEl(ov.texto) : h('p', { class: 'st-muted', text: 'Não consegui gerar o resumo agora.' }));
  if (ov.texto) slot.append(msgActions(ov.texto, null, 'Resumo do projeto'));
  if (ov.perguntas?.length && !(p.conversa || []).length) slot.append(suggestions(ov.perguntas));
}
function suggestions(list) {
  const box = h('div', { class: 'st-sugs' });
  for (const q of list) { const b = h('button', { class: 'st-sug', type: 'button', text: q }); b.onclick = () => sendQuestion(q); box.append(b); }
  return box;
}
function userMsg(text) { return h('div', { class: 'st-msg user', text }); }
function modelMsg(text, cit, sugs, voice) {
  const m = h('div', { class: 'st-msg model' });
  if (voice) m.append(h('div', { class: 'who' }, 'JARVIS', h('i', { text: 'VOZ' })));
  m.append(mdEl(text, cit || null), msgActions(text, cit));
  return m;
}
function msgActions(text, cit, title) {
  const save = h('button', { class: 'st-chipbtn', type: 'button', html: IC.save + 'Guardar na nota' });
  save.onclick = async () => { nb.notes = await jpost(`/api/projects/${nb.pid}/notas`, { titulo: title || text.replace(/[#*>`[\]]/g, '').trim().split('\n')[0].slice(0, 60), texto: text, cit, origem: 'chat' });
    if (!nb.artView) renderStudio(); toast('Guardado nas notas'); };
  const copy = btn('ib sm', IC.copy, 'Copiar', () => { navigator.clipboard?.writeText(text.replace(/\[\d+\]/g, '')); toast('Copiado'); });
  const up = btn('ib sm', IC.thumbU, 'Boa resposta', () => { up.classList.toggle('on'); down.classList.remove('on'); });
  const down = btn('ib sm', IC.thumbD, 'Resposta ruim', () => { down.classList.toggle('on'); up.classList.remove('on'); });
  return h('div', { class: 'st-actions' }, save, copy, up, down);
}
async function sendQuestion(q) {
  q = q.trim(); if (!q || nb.busy) return;
  const ta = nb.el.ta; ta.value = ''; ta.style.height = 'auto'; nb.el.send.disabled = true;
  nb.el.inner.querySelectorAll('.st-sugs').forEach((s) => s.remove());
  const inner = nb.el.inner; inner.append(userMsg(q));
  const wait = h('div', { class: 'st-msg model' }, h('div', { class: 'st-think' }, h('i'), h('i'), h('i'))); inner.append(wait);
  nb.el.scroll.scrollTop = nb.el.scroll.scrollHeight; nb.busy = true;
  const ready = nb.p.fontes.filter((s) => s.status === 'pronto'), chosen = ready.filter((s) => nb.sel.has(s.id)).map((s) => s.id);
  try {
    const r = await jpost(`/api/projects/${nb.pid}/chat`, { pergunta: q, fontes: chosen.length === ready.length ? [] : chosen.length ? chosen : ['-'] });
    wait.replaceWith(modelMsg(r.resposta, r.cit));
    if (r.sugestoes?.length) inner.append(suggestions(r.sugestoes));
    (nb.p.conversa ||= []).push({ t: new Date().toISOString().slice(0, 16).replace('T', ' '), who: USER_NAME, text: q }, { who: 'Jarvis', text: r.resposta, cit: r.cit, sugestoes: r.sugestoes, t: '' });
  } catch (e) { wait.replaceWith(h('div', { class: 'st-msg model' }, h('p', { style: 'color:#ff9a9a', text: e.message }))); }
  nb.busy = false; nb.el.scroll.scrollTop = nb.el.scroll.scrollHeight; ta.focus();
}
// Typed or clicked prompts from elsewhere (mind map nodes, flashcards) ask the chat
function askChat(q) { if (nb.artView) closeArt(); sendQuestion(q); }

function chatConfig() {
  const c = { objetivo: 'padrao', tamanho: 'padrao', prompt: '', ...(nb.p.chat || {}) };
  const custom = h('textarea', { placeholder: 'Ex.: Responda como um professor de economia, com exemplos do Brasil e uma pergunta no final.', value: c.prompt });
  custom.value = c.prompt || ''; custom.hidden = c.objetivo !== 'personalizado';
  const desc = h('p', { class: 'hint' });
  const D = { padrao: 'Melhor para pesquisa geral e para debater ideias.', guia: 'Explica passo a passo e faz perguntas para você aprender.', personalizado: 'Defina o papel, o estilo ou o objetivo do Jarvis neste projeto.' };
  desc.textContent = D[c.objetivo];
  dialog({ title: 'Configurar o chat', sub: 'Os projetos podem ter um objetivo próprio: pesquisar, ajudar a aprender ou conversar num estilo e tom específicos.',
    body: h('div', {}, h('label', { class: 'f', text: 'Objetivo, estilo ou papel' }),
      choice([['padrao', 'Predefinição'], ['guia', 'Guia de aprendizagem'], ['personalizado', 'Personalizado']], c.objetivo, (v) => { c.objetivo = v; custom.hidden = v !== 'personalizado'; desc.textContent = D[v]; }),
      desc, custom, h('label', { class: 'f', text: 'Tamanho das respostas' }), choice([['padrao', 'Predefinição'], ['maior', 'Mais longas'], ['menor', 'Mais curtas']], c.tamanho, (v) => { c.tamanho = v; })),
    ok: async () => { c.prompt = custom.value.trim(); await jpost('/api/projects/' + nb.pid, { chat: c }, 'PATCH'); nb.p.chat = c; toast('Chat configurado'); } });
}
function personalize() {
  const p = nb.p; let emoji = p.emoji || '📔';
  const grid = h('div', { class: 'st-emojis' });
  for (const e of EMOJIS) { const b = h('button', { type: 'button', text: e, 'aria-pressed': String(e === emoji) }); b.onclick = () => { emoji = e; grid.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); }; grid.append(b); }
  const title = h('input', { type: 'text', value: p.titulo });
  const own = h('input', { type: 'checkbox', class: 'st-check', ...(p.resumo_proprio ? { checked: true } : {}) });
  const ta = h('textarea', { placeholder: 'Escreva o resumo que aparece no topo do chat' }); ta.value = p.resumo_proprio || nb.ov?.texto || ''; ta.hidden = !own.checked;
  own.onchange = () => { ta.hidden = !own.checked; };
  dialog({ title: 'Personalizar o projeto', body: h('div', {}, h('label', { class: 'f', style: 'margin-top:0', text: 'Ícone' }), grid, h('label', { class: 'f', text: 'Título' }), title,
    h('label', { class: 'st-toggle' }, h('div', { class: 'txt' }, h('b', { text: 'Resumo personalizado' }), h('span', { text: 'Por padrão o Jarvis escreve o resumo sozinho e o atualiza quando as fontes mudam.' })), own), ta),
    okText: 'Concluído', ok: async () => {
      const body = { emoji, titulo: title.value.trim() || p.titulo, resumo_proprio: own.checked ? ta.value.trim() : '' };
      await jpost('/api/projects/' + nb.pid, body, 'PATCH'); Object.assign(p, body); nb.el.title.value = p.titulo; nb.ov = null; renderOverview(); } });
}

// ---------- Jarvis's reactor as a widget in the Sources panel ----------
// The main page's reactor itself moves here (same drawing loop, states and click), and goes back when the notebook closes.
// Clicking it starts or ends the voice conversation, after opening this project so Jarvis talks about its sources.
const reactorHome = document.createComment('reactor');
let reactorClick = null;
function dockReactor(box) {
  if (!reactor.isConnected || reactor.parentNode !== box) {
    if (!reactorHome.isConnected) reactor.before(reactorHome);
    reactorClick ||= reactor.onclick;
    reactor.onclick = async () => { if (!ws && activeProject?.id !== nb.pid) await openProject(nb.pid); ws ? stop() : start(); };
    reactor.style.animation = 'none'; box.append(reactor); wakeDraw();
  }
}
function undockReactor() {
  if (!reactorHome.isConnected) return;
  reactorHome.replaceWith(reactor); reactor.onclick = reactorClick; reactorClick = null; wakeDraw();
}
function orbBox() {
  nb.el.orb ||= h('div', { class: 'st-orb', title: 'Clique para falar com o Jarvis; clique de novo para encerrar' });
  dockReactor(nb.el.orb);
  return nb.el.orb;
}

// ---------- Voice-to-voice (Gemini Live) ----------
async function voiceToggle() {
  const on = !(ws && !textOnly);
  if (on && activeProject?.id !== nb.pid) { await openProject(nb.pid); }
  await setVoice(on);
  wakeDraw();
}
// Live transcripts also show up in the chat while this project's voice conversation is on
const _studioAppend = appendTo;
let vUser = null, vModel = null;
appendTo = function (kind, text) {
  const fresh = kind === 'user' ? !lastUser : !lastModel;
  _studioAppend(kind, text);
  if (!(nb.open && nb.view === 'nb' && activeProject?.id === nb.pid && nb.el?.inner)) return;
  if (kind === 'user') { if (fresh || !vUser) { vUser = userMsg(''); nb.el.inner.append(vUser); vModel = null; } vUser.textContent += text; }
  else { if (fresh || !vModel) { vModel = h('div', { class: 'st-msg model' }, h('div', { class: 'who' }, 'JARVIS', h('i', { text: 'VOZ' })), h('div', { class: 'st-md' }, h('p'))); nb.el.inner.append(vModel); vUser = null; }
    vModel.querySelector('p').textContent += text; }
  nb.el.scroll.scrollTop = nb.el.scroll.scrollHeight;
};
// A text Jarvis delivers by voice (mostrar_texto) also lands in this project's chat, with Copiar and Guardar na nota
window.jarvisDoc = (m) => {
  if (!(nb.open && nb.view === 'nb' && activeProject?.id === nb.pid && nb.el?.inner)) return false;
  nb.el.inner.append(modelMsg(m.text, null, null, true)); vUser = vModel = null; nb.el.scroll.scrollTop = nb.el.scroll.scrollHeight;
  return true;
};
// Called by the main draw loop while a notebook is open: keeps the mic button in step with the voice
function drawStudio() {
  const on = !!(ws && !textOnly);
  if (nb.el?.mic && nb.el.mic.getAttribute('aria-pressed') !== String(on)) nb.el.mic.setAttribute('aria-pressed', String(on));
}

// ---------- Studio panel ----------
function renderStudio() {
  const P = nb.el.right; P.replaceChildren();
  if (nb.artView) return renderArt();
  P.append(panelHead('Studio', 'right'));
  const body = h('div', { class: 'st-pbody' }); P.append(body);
  const rail = h('div', { class: 'st-rail' });
  for (const [k, label, icon] of KINDS) rail.append(btn('ib', `<span style="color:var(--c-${k})">${icon}</span>`, label, () => k === 'relatorio' ? customize(k) : generate(k)));
  body.append(rail);
  const tiles = h('div', { class: 'st-tiles' });
  for (const [k, label, icon, desc] of KINDS) {
    const t = h('div', { class: 'st-tile', role: 'button', tabindex: '0', style: `--c:var(--c-${k})`, title: desc, html: icon }, h('span', { text: label }), k === 'relatorio' ? h('span', { class: 'new', text: 'Novo!' }) : null);
    const ed = btn('ib sm ed', IC.pencil, 'Personalizar ' + label, (e) => { e.stopPropagation(); customize(k); }); t.append(ed);
    t.onclick = () => k === 'relatorio' ? customize(k) : generate(k); t.onkeydown = (e) => { if (e.key === 'Enter') t.click(); };
    tiles.append(t);
  }
  body.append(tiles, h('div', { class: 'st-div' }));
  const list = [...nb.items.map((a) => ({ ...a, _k: a.tipo })), ...nb.notes.map((n) => ({ ...n, _k: 'nota', status: 'pronto' }))].sort((a, b) => b.criado.localeCompare(a.criado));
  if (!list.length) body.append(h('div', { class: 'st-zero' }, h('div', { html: IC.spark }), h('b', { text: 'O que o Studio criar fica guardado aqui.' }),
    'Depois de adicionar fontes, clique para criar um resumo em áudio, um guia de estudo, um mapa mental e muito mais.'));
  const L = h('div', { class: 'st-items' });
  for (const a of list) {
    const busy = a.status === 'gerando', K = SKIND[a._k];
    const meta = busy ? [h('span', { class: 'st-spin' }), 'Gerando… pode levar alguns minutos'] : a.status === 'erro' ? ['Falhou: ' + (a.erro || '')]
      : [a._k === 'nota' ? (a.origem === 'chat' ? 'Resposta guardada' : 'Nota') : K.label, a.duracao ? ' · ' + fmtDur(a.duracao) : '', ' · ' + ago(a.criado)];
    const row = h('div', { class: 'st-item' + (busy ? ' busy' : '') + (a.status === 'erro' ? ' err' : ''), role: 'button', tabindex: '0', style: `--c:var(--c-${a._k})`, html: K.icon },
      h('div', { class: 't' }, h('b', { text: a.titulo }), h('small', {}, ...meta)));
    const more = btn('ib sm', IC.more, 'Mais', (e) => { e.stopPropagation(); itemMenu(more, a); }); row.append(more);
    if (!busy) { row.onclick = () => a.status === 'erro' ? itemMenu(more, a) : openArt(a); row.onkeydown = (e) => { if (e.key === 'Enter') row.click(); }; }
    L.append(row);
  }
  body.append(L);
  const noteB = h('button', { class: 'st-btn light st-float', type: 'button', html: IC.note + 'Adicionar nota' }); noteB.onclick = newNote; P.append(noteB);
}
function itemMenu(anchor, a) {
  const isNote = a._k === 'nota';
  const items = [{ label: 'Mudar nome', icon: IC.pencil, on: async () => { const t = await ask('Nome', a.titulo); if (!t) return;
    if (isNote) nb.notes = await jpost(`/api/projects/${nb.pid}/notas/${a.id}`, { titulo: t }, 'PATCH'); else await jpost(`/api/projects/${nb.pid}/studio/${a.id}`, { titulo: t }, 'PATCH');
    refresh('items'); } }];
  if (isNote) items.push({ label: 'Converter em fonte', icon: IC.doc, on: async () => { await jpost(`/api/projects/${nb.pid}/notas/${a.id}`, { virar_fonte: true }, 'PATCH'); toast('A nota virou fonte'); refresh(); } });
  if (a.tipo === 'audio' && a.status === 'pronto') items.push({ label: 'Baixar áudio', icon: IC.download, on: () => { const l = h('a', { href: `/api/projects/${nb.pid}/studio/${a.id}/audio/0`, download: a.titulo + '.wav' }); l.click(); } });
  if (a.status === 'erro') items.push({ label: 'Tentar de novo', icon: IC.spark, on: async () => { await fetch(`/api/projects/${nb.pid}/studio/${a.id}`, { method: 'DELETE' }); generate(a.tipo, a.opcoes); } });
  items.push('-', { label: 'Eliminar', icon: IC.trash, danger: true, on: async () => { if (!await confirmDlg(`Eliminar "${a.titulo}"?`, 'Isto não pode ser desfeito.')) return;
    await fetch(isNote ? `/api/projects/${nb.pid}/notas/${a.id}` : `/api/projects/${nb.pid}/studio/${a.id}`, { method: 'DELETE' }); if (nb.artView?.id === a.id) closeArt(); refresh('items'); } });
  menu(anchor, items);
}
async function generate(kind, opcoes = {}) {
  const ready = nb.p.fontes.filter((s) => s.status === 'pronto');
  if (!ready.length) { toast('Adicione fontes (e espere o Jarvis lê-las) antes de criar no Studio'); return; }
  const chosen = ready.filter((s) => nb.sel.has(s.id)).map((s) => s.id);
  if (!chosen.length) { toast('Selecione ao menos uma fonte à esquerda'); return; }
  try { const a = await jpost(`/api/projects/${nb.pid}/studio`, { tipo: kind, opcoes, fontes: chosen.length === ready.length ? [] : chosen }); nb.items.unshift(a); if (!nb.artView) renderStudio(); }
  catch (e) { toast('Erro: ' + e.message); }
}
function customize(kind) {
  const o = {}, body = h('div');
  for (const [key, label, options] of OPTS[kind] || []) {
    o[key] = options.find(([v]) => v === 'padrao')?.[0] || options[0][0];
    body.append(h('label', { class: 'f', text: label }), choice(options, o[key], (v) => { o[key] = v; }, options.some((x) => x[2])));
  }
  const foco = h('textarea', { placeholder: FOCUS_HINT[kind] || 'Ex.: concentre-se em um tema, um público ou um formato específico' });
  body.append(h('label', { class: 'f', text: kind === 'relatorio' ? 'Descreva o relatório (opcional; obrigatório no personalizado)' : 'Em que o Jarvis deve se concentrar? (opcional)' }), foco);
  const sel = nb.p.fontes.filter((s) => s.status === 'pronto' && nb.sel.has(s.id)).length;
  body.append(h('p', { class: 'hint', text: `Vai usar ${nFontes(sel)} selecionada${sel === 1 ? '' : 's'}.` }));
  dialog({ title: kind === 'relatorio' ? 'Criar relatório' : 'Personalizar: ' + SKIND[kind].label, sub: SKIND[kind].desc, body, okText: 'Gerar', wide: kind === 'relatorio' || kind === 'audio',
    ok: async () => { o.foco = foco.value.trim(); if (kind === 'relatorio' && o.formato === 'personalizado' && !o.foco) { toast('Descreva o relatório que você quer'); foco.focus(); return false; } await generate(kind, o); } });
}
function newNote() { openArt({ _k: 'nota', id: null, titulo: '', texto: '', criado: '', edit: true }); }

// ---------- Studio item viewers (the right panel widens) ----------
async function openArt(a) {
  nb.rightMin = false;
  if (a._k !== 'nota') { try { a = { ...(await api(`/api/projects/${nb.pid}/studio/${a.id}`)), _k: a.tipo }; } catch { return; } }
  nb.artView = a; layout(); renderArt();
}
function closeArt() { audioStop(); nb.artView = null; layout(); renderStudio(); }
function renderArt() {
  const a = nb.artView, P = nb.el.right, K = SKIND[a._k];
  audioStop();
  const body = h('div', { class: 'st-pbody st-view' });
  const more = a.id ? btn('ib sm', IC.more, 'Mais', () => itemMenu(more, a)) : null;
  P.replaceChildren(h('div', { class: 'st-ph' }, btn('ib sm', IC.back, 'Voltar ao Studio', closeArt), h('h2', { text: 'Studio › ' + K.label }), more), body);
  if (a._k !== 'nota' || !a.edit) body.append(h('h3', { class: 'vt', text: a.titulo }), h('p', { class: 'vm', text: [a.fontes?.length ? nFontes(a.fontes.length) : 'Todas as fontes selecionadas', a.criado && ago(a.criado)].filter(Boolean).join(' · ') }));
  const d = a.dados || {};
  ({ audio: viewAudio, video: viewVideo, slides: viewSlides, mapa: viewMap, relatorio: viewReport, cartoes: viewCards, quiz: viewQuiz, infografia: viewInfo, tabela: viewTable, nota: viewNote })[a._k](body, d, a);
}
function copyBtn(get, label = 'Copiar') { const b = h('button', { class: 'st-chipbtn', type: 'button', html: IC.copy + label }); b.onclick = () => { navigator.clipboard?.writeText(get()); toast('Copiado'); }; return b; }
function fmtT(s) { s = Math.max(0, s | 0); return `${s / 60 | 0}:${String(s % 60).padStart(2, '0')}`; }
let stPlayer = null;
function audioStop() { if (stPlayer) { stPlayer.pause(); stPlayer.src = ''; stPlayer = null; } }
function viewAudio(body, d, a) {
  const url = `/api/projects/${nb.pid}/studio/${a.id}/audio/0`;
  stPlayer = new Audio(url); const au = stPlayer;
  const play = h('button', { class: 'st-play', type: 'button', html: IC.play, 'aria-label': 'Tocar' });
  const seek = h('input', { type: 'range', class: 'st-seek', min: 0, max: 1000, value: 0, 'aria-label': 'Posição' });
  const time = h('span', { class: 'st-time', text: '0:00 / ' + fmtT(a.duracao) });
  const speeds = [1, 1.25, 1.5, 2, .75]; let si = 0;
  const speed = h('button', { class: 'st-speed', type: 'button', text: '1×' }); speed.onclick = () => { si = (si + 1) % speeds.length; au.playbackRate = speeds[si]; speed.textContent = speeds[si] + '×'; };
  play.onclick = () => au.paused ? au.play() : au.pause();
  au.onplay = () => { play.innerHTML = IC.pause; }; au.onpause = () => { play.innerHTML = IC.play; };
  seek.oninput = () => { if (au.duration) au.currentTime = seek.value / 1000 * au.duration; };
  const lines = (d.falas || []).map((f) => h('p', { class: f.quem }, h('b', { text: f.quem }), f.texto));
  const total = (d.falas || []).reduce((s, f) => s + f.texto.length + 40, 0);
  au.ontimeupdate = () => {
    if (!au.duration) return; seek.value = au.currentTime / au.duration * 1000; time.textContent = `${fmtT(au.currentTime)} / ${fmtT(au.duration)}`;
    let acc = 0, at = au.currentTime / au.duration * total, cur = 0;
    for (let i = 0; i < lines.length; i++) { acc += d.falas[i].texto.length + 40; if (acc >= at) { cur = i; break; } }
    lines.forEach((l, i) => l.classList.toggle('on', i === cur));
  };
  const dl = h('a', { class: 'st-chipbtn', href: url, download: a.titulo + '.wav', html: IC.download + 'Baixar' });
  body.append(h('div', { class: 'st-audio' }, h('div', { class: 'row' }, play, seek, time), h('div', { class: 'row', style: 'margin-top:12px;justify-content:space-between' },
    h('span', { class: 'st-muted', style: 'font-size:12.5px', text: 'Ana e Beto · ' + ({ breve: 'Resumo breve', critica: 'Crítica', debate: 'Debate' }[a.opcoes?.formato] || 'Conversa aprofundada') }), h('span', {}, speed, ' ', dl))),
  h('div', { class: 'st-script' }, ...lines));
}
function slideEl(s, i, n) {
  const el = h('div', { class: 'st-slide ' + (s.tipo || 'topicos') });
  if (s.emoji) el.append(h('div', { class: 'big', text: s.emoji }));
  if (s.tipo === 'citacao') { el.append(h('blockquote', { text: '“' + (s.citacao || s.titulo) + '”' }), s.autor ? h('cite', { text: '— ' + s.autor }) : null); }
  else {
    el.append(h('div', { class: 'k', text: s.tipo === 'capa' ? 'Jarvis · Studio' : s.tipo === 'conclusao' ? 'Conclusão' : `${i + 1} / ${n}` }), h('h2', { text: s.titulo || '' }));
    if (s.subtitulo) el.append(h('div', { class: 'sub', text: s.subtitulo }));
    if (s.numeros?.length) el.append(h('div', { class: 'nums' }, ...s.numeros.map((x) => h('div', {}, h('b', { text: x.valor }), h('span', { text: x.rotulo })))));
    if (s.topicos?.length) el.append(h('ul', {}, ...s.topicos.map((t) => h('li', { text: t }))));
  }
  el.append(h('div', { class: 'pg', text: `${i + 1}/${n}` }));
  return el;
}
function deck(body, slides, onShow) {
  let i = 0; const stage = h('div', { class: 'st-stage', tabindex: '0' }), count = h('span');
  const show = (k) => { i = Math.max(0, Math.min(slides.length - 1, k)); stage.replaceChildren(slideEl(slides[i], i, slides.length)); count.textContent = `${i + 1} / ${slides.length}`; onShow?.(i); };
  const prev = btn('ib', IC.prev, 'Anterior', () => show(i - 1)), next = btn('ib', IC.next, 'Próximo', () => show(i + 1));
  const full = btn('ib', IC.full, 'Tela cheia', () => stage.requestFullscreen?.());
  stage.onkeydown = (e) => { if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); show(i + 1); } if (e.key === 'ArrowLeft') show(i - 1); };
  stage.onclick = (e) => show(i + (e.offsetX > stage.clientWidth / 3 ? 1 : -1));
  body.append(stage, h('div', { class: 'st-nav' }, prev, count, next, full));
  show(0); return { show, get i() { return i; } };
}
function viewSlides(body, d) {
  const slides = d.slides || []; if (!slides.length) return body.append(h('p', { text: 'Sem slides.' }));
  const notes = h('div', { class: 'st-notes' });
  deck(body, slides, (i) => { notes.textContent = slides[i].notas ? 'Notas: ' + slides[i].notas : ''; notes.hidden = !slides[i].notas; });
  body.append(notes, h('div', { class: 'st-vbar', style: 'margin-top:12px' }, copyBtn(() => slides.map((s, i) => `${i + 1}. ${s.titulo}\n${(s.topicos || []).map((t) => '- ' + t).join('\n')}`).join('\n\n'), 'Copiar texto')));
}
function viewVideo(body, d, a) {
  const scenes = (d.cenas || []).map((c) => ({ ...c, tipo: 'topicos' })); if (!scenes.length) return;
  const cap = h('div', { class: 'st-caption' }), prog = h('div', { class: 'st-prog' }, ...scenes.map(() => h('i', {}, h('b'))));
  let playing = false;
  const playB = h('button', { class: 'st-btn primary', type: 'button', html: IC.play + 'Assistir' });
  const D = deck(body, scenes, (i) => { cap.textContent = scenes[i].narracao || ''; if (playing) run(i); });
  function run(i) {
    audioStop(); stPlayer = new Audio(`/api/projects/${nb.pid}/studio/${a.id}/audio/${i}`); const au = stPlayer;
    prog.querySelectorAll('b').forEach((b, k) => { b.style.width = k < i ? '100%' : '0'; });
    au.ontimeupdate = () => { if (au.duration) prog.children[i].firstChild.style.width = (au.currentTime / au.duration * 100) + '%'; };
    au.onended = () => { if (i + 1 < scenes.length) D.show(i + 1); else { playing = false; playB.innerHTML = IC.play + 'Assistir de novo'; } };
    au.play().catch(() => {});
  }
  playB.onclick = () => { if (playing) { playing = false; audioStop(); playB.innerHTML = IC.play + 'Continuar'; } else { playing = true; playB.innerHTML = IC.pause + 'Pausar'; run(D.i); } };
  body.append(prog, cap, h('div', { class: 'st-vbar', style: 'margin-top:12px' }, playB, h('span', { class: 'st-muted', style: 'align-self:center;font-size:12.5px', text: fmtDur(a.duracao) + ' · narrado pelo Jarvis' })));
}
function viewMap(body, d) {
  const colors = ['--c-audio', '--c-slides', '--c-video', '--c-mapa', '--c-cartoes', '--c-quiz', '--c-infografia', '--c-tabela'];
  const node = (n, depth, color, path) => {
    const kids = n.filhos || [];
    const el = h('div', { class: 'st-node' + (depth >= 2 && kids.length ? ' closed' : ''), style: `--c:var(${color})` });
    const lab = h('button', { class: 'lab', type: 'button', title: 'Perguntar ao Jarvis sobre isto' }, h('span', { text: n.rotulo }));
    if (kids.length) { const tg = h('span', { class: 'tg', text: depth >= 2 ? '+' : '−', title: 'Expandir ou recolher' });
      tg.onclick = (e) => { e.stopPropagation(); el.classList.toggle('closed'); tg.textContent = el.classList.contains('closed') ? '+' : '−'; }; lab.append(tg); }
    lab.onclick = () => askChat(`Explique "${n.rotulo}"${path.length ? ' no contexto de ' + path.join(' › ') : ''}, com base nas fontes.`);
    el.append(lab);
    if (kids.length) el.append(h('div', { class: 'st-kids' }, ...kids.map((k, i) => node(k, depth + 1, depth === 0 ? colors[i % colors.length] : color, [...path, n.rotulo]))));
    return el;
  };
  const root = d.raiz || { rotulo: d.titulo, filhos: [] };
  const map = h('div', { class: 'st-map' }, node(root, 0, '--c-mapa', []));
  const all = (open) => map.querySelectorAll('.st-node').forEach((n) => { if (n.querySelector(':scope > .st-kids')) { n.classList.toggle('closed', !open); const t = n.querySelector(':scope > .lab .tg'); if (t) t.textContent = open ? '−' : '+'; } });
  const ex = h('button', { class: 'st-chipbtn', type: 'button', text: 'Expandir tudo' }), co = h('button', { class: 'st-chipbtn', type: 'button', text: 'Recolher tudo' });
  ex.onclick = () => all(true); co.onclick = () => all(false);
  body.append(h('div', { class: 'st-vbar' }, ex, co, h('span', { class: 'st-muted', style: 'align-self:center;font-size:12px', text: 'Clique num tópico para perguntar ao Jarvis' })), map);
}
function viewReport(body, d) {
  body.append(h('div', { class: 'st-vbar' }, copyBtn(() => d.markdown || ''), (() => { const b = h('button', { class: 'st-chipbtn', type: 'button', html: IC.save + 'Guardar como nota' });
    b.onclick = async () => { nb.notes = await jpost(`/api/projects/${nb.pid}/notas`, { titulo: d.titulo, texto: d.markdown, origem: 'studio' }); toast('Guardado nas notas'); }; return b; })()), mdEl(d.markdown || ''));
}
function viewCards(body, d) {
  let cards = [...(d.cartoes || [])], i = 0; if (!cards.length) return;
  const card = h('div', { class: 'st-flash', role: 'button', tabindex: '0', 'aria-label': 'Virar cartão' }), count = h('span');
  const show = () => { card.classList.remove('flip'); const c = cards[i]; card.replaceChildren(h('div', { class: 'inner' }, h('div', { class: 'face' }, c.frente, h('small', { text: 'CLIQUE PARA VER A RESPOSTA' })), h('div', { class: 'face back' }, c.verso, h('small', { text: 'RESPOSTA' })))); count.textContent = `${i + 1} / ${cards.length}`; };
  card.onclick = () => card.classList.toggle('flip'); card.onkeydown = (e) => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); card.click(); } if (e.key === 'ArrowRight') nx.click(); if (e.key === 'ArrowLeft') pv.click(); };
  const pv = btn('ib', IC.prev, 'Anterior', () => { i = (i - 1 + cards.length) % cards.length; show(); }), nx = btn('ib', IC.next, 'Próximo', () => { i = (i + 1) % cards.length; show(); });
  const sh = btn('ib', IC.shuffle, 'Embaralhar', () => { cards.sort(() => Math.random() - .5); i = 0; show(); toast('Cartões embaralhados'); });
  const ex = h('button', { class: 'st-chipbtn', type: 'button', html: IC.spark + 'Explicar' }); ex.onclick = () => askChat(`Explique em detalhe: ${cards[i].frente} (resposta: ${cards[i].verso})`);
  body.append(card, h('div', { class: 'st-nav' }, pv, count, nx, sh), h('div', { class: 'st-vbar', style: 'justify-content:center' }, ex));
  show(); card.focus();
}
function viewQuiz(body, d) {
  const qs = d.perguntas || []; let i = 0, score = 0; const box = h('div', { class: 'st-q' }); body.append(box);
  const show = () => {
    if (i >= qs.length) { const again = h('button', { class: 'st-btn primary', type: 'button', text: 'Refazer' }); again.onclick = () => { i = 0; score = 0; show(); };
      box.replaceChildren(h('div', { class: 'st-score' }, h('b', { text: `${score}/${qs.length}` }), h('p', { text: score === qs.length ? 'Perfeito!' : score >= qs.length * .7 ? 'Muito bom.' : 'Vale revisar as fontes e tentar de novo.' }), again)); return; }
    const q = qs[i], next = h('button', { class: 'st-btn primary', type: 'button', text: i + 1 < qs.length ? 'Próxima' : 'Ver resultado', hidden: true }); next.onclick = () => { i++; show(); };
    const hint = h('p', { class: 'st-muted', hidden: true, text: 'Dica: ' + (q.dica || '') }), hb = h('button', { class: 'st-chipbtn', type: 'button', text: 'Dica' }); hb.onclick = () => { hint.hidden = false; hb.hidden = true; };
    const opts = (q.opcoes || []).map((o, k) => { const b = h('button', { class: 'st-opt', type: 'button' }, h('b', { text: 'ABCD'[k] }), h('span', {}, o.texto)); b._o = o; return b; });
    opts.forEach((b) => { b.onclick = () => { if (b._o.correta) score++; opts.forEach((x) => { x.disabled = true; if (x._o.correta) x.classList.add('ok'); x.querySelector('span').append(h('small', { class: 'ex', text: x._o.explicacao || '' })); });
      if (!b._o.correta) b.classList.add('bad'); next.hidden = false; hb.hidden = true; next.focus(); }; });
    box.replaceChildren(h('p', { class: 'vm', text: `Pergunta ${i + 1} de ${qs.length}` }), h('h4', { text: q.pergunta }), ...opts, hint, h('div', { class: 'st-vbar', style: 'justify-content:space-between' }, q.dica ? hb : h('span'), next));
  };
  show();
}
function viewInfo(body, d) {
  body.append(h('div', { class: 'st-info' }, h('header', {}, h('h2', { text: d.titulo || '' }), d.subtitulo ? h('p', { text: d.subtitulo }) : null),
    d.destaques?.length ? h('div', { class: 'nums' }, ...d.destaques.map((x) => h('div', {}, h('b', { text: x.valor }), h('span', { text: x.rotulo })))) : null,
    ...(d.secoes || []).map((s) => h('section', {}, h('div', { class: 'e', text: s.emoji || '📌' }), h('div', {}, h('h4', { text: s.titulo }), s.texto ? h('p', { text: s.texto }) : null,
      s.itens?.length ? h('ul', {}, ...s.itens.map((t) => h('li', { text: t }))) : null))),
    d.conclusao ? h('footer', { text: d.conclusao }) : null));
}
function viewTable(body, d) {
  const cols = d.colunas || [], rows = d.linhas || [];
  const csv = () => [cols, ...rows].map((r) => r.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
  const dl = h('a', { class: 'st-chipbtn', download: (d.titulo || 'tabela') + '.csv', html: IC.download + 'Baixar CSV' }); dl.href = URL.createObjectURL(new Blob(['﻿' + csv()], { type: 'text/csv' }));
  body.append(d.descricao ? h('p', { class: 'st-muted', style: 'margin:0 0 10px', text: d.descricao }) : '', h('div', { class: 'st-vbar' }, copyBtn(() => [cols, ...rows].map((r) => r.join('\t')).join('\n'), 'Copiar para planilha'), dl),
    h('div', { class: 'st-tbl' }, h('table', {}, h('tr', {}, ...cols.map((c) => h('th', { text: c }))), ...rows.map((r) => h('tr', {}, ...r.map((c) => h('td', { text: String(c ?? '') })))))));
}
function viewNote(body, d, a) {
  if (!a.edit) {
    const ed = h('button', { class: 'st-chipbtn', type: 'button', html: IC.pencil + 'Editar' }); ed.onclick = () => { nb.artView = { ...a, edit: true }; renderArt(); };
    const src = h('button', { class: 'st-chipbtn', type: 'button', html: IC.doc + 'Converter em fonte' });
    src.onclick = async () => { await jpost(`/api/projects/${nb.pid}/notas/${a.id}`, { virar_fonte: true }, 'PATCH'); toast('A nota virou fonte'); refresh(); };
    body.append(h('div', { class: 'st-vbar' }, ed, src, copyBtn(() => a.texto)), mdEl(a.texto, a.cit && Object.keys(a.cit).length ? a.cit : null)); return;
  }
  const t = h('input', { type: 'text', placeholder: 'Título da nota', value: a.titulo }), ta = h('textarea', { placeholder: 'Escreva sua nota (Markdown funciona: **negrito**, listas com -, ### títulos)' });
  t.value = a.titulo || ''; ta.value = a.texto || '';
  const save = h('button', { class: 'st-btn primary', type: 'button', text: 'Guardar' });
  save.onclick = async () => {
    const body = { titulo: t.value.trim() || 'Nota sem título', texto: ta.value };
    nb.notes = a.id ? await jpost(`/api/projects/${nb.pid}/notas/${a.id}`, body, 'PATCH') : await jpost(`/api/projects/${nb.pid}/notas`, body);
    const n = nb.notes.find((x) => x.id === a.id) || nb.notes[0]; nb.artView = { ...n, _k: 'nota' }; renderArt(); toast('Nota guardada');
  };
  body.append(h('div', { class: 'st-note' }, t, ta), h('div', { class: 'st-vbar', style: 'margin-top:12px;justify-content:flex-end' }, h('button', { class: 'st-btn ghost', type: 'button', text: 'Cancelar', onclick: null }), save));
  body.querySelector('.ghost').onclick = () => a.id ? (nb.artView = { ...a, edit: false }, renderArt()) : closeArt();
  (a.id ? ta : t).focus();
}
