"""Jarvis's fast hands on the Mac: everyday actions done directly in Python and AppleScript, in under a second,
without waking Claude. Anything that needs judgment (writing, e-mail, multi-step jobs) still goes to executar_no_mac.

Nothing here deletes for good: "lixeira" moves to the Trash, and every move refuses to overwrite a file.
"""
import datetime
import pathlib
import re
import shutil
import subprocess
from config import USER

HOME = pathlib.Path.home()
PLACES = {
    "mesa": HOME / "Desktop", "área de trabalho": HOME / "Desktop", "area de trabalho": HOME / "Desktop",
    "desktop": HOME / "Desktop", "downloads": HOME / "Downloads", "transferências": HOME / "Downloads",
    "documentos": HOME / "Documents", "documents": HOME / "Documents", "imagens": HOME / "Pictures",
    "fotos": HOME / "Pictures", "pictures": HOME / "Pictures", "aplicativos": HOME / "Applications",
    "home": HOME, "inicio": HOME, "início": HOME,
}
PRINTS = HOME / "Pictures" / "Prints"             # where loose screenshots from the Desktop go
LOOSE_IMAGES = HOME / "Pictures" / "Imagens da Mesa"
SCREENSHOT = re.compile(r"^(Screenshot|Screen Shot|Captura de Tela|Captura de ecrã|Screen Recording|Gravação de Tela)\b", re.I)
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif", ".tiff", ".mov"}

ACTIONS = ["organizar_mesa", "abrir_app", "abrir", "listar_pasta", "criar_pasta", "mover", "lixeira",
           "volume", "mudo", "modo_escuro"]


def osa(script):
    r = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "o AppleScript falhou")
    return r.stdout.strip()


def resolve(name, must_exist=True):
    """A path from what the user said: a known place (mesa, downloads...), ~/..., an absolute path, or a file or folder
    name looked up on the Desktop, Downloads and Documents."""
    raw = (name or "").strip().strip('"')
    if not raw:
        raise ValueError("Faltou dizer qual pasta ou arquivo.")
    if raw.lower() in PLACES:
        return PLACES[raw.lower()]
    p = pathlib.Path(raw).expanduser()
    if p.is_absolute():
        if must_exist and not p.exists():
            raise FileNotFoundError(f"Não existe: {p}")
        return p
    for base in (HOME / "Desktop", HOME / "Downloads", HOME / "Documents", HOME):
        cand = base / raw
        if cand.exists():
            return cand
        hits = [c for c in base.iterdir() if c.name.lower() == raw.lower()] if base.is_dir() else []
        if hits:
            return hits[0]
    if must_exist:
        raise FileNotFoundError(f"Não achei '{raw}' na Mesa, em Downloads nem em Documentos.")
    return HOME / "Desktop" / raw


def free_name(dest):
    """dest, or 'name 2.ext', 'name 3.ext'... so a move never overwrites anything."""
    if not dest.exists():
        return dest
    n = 2
    while (dest.parent / f"{dest.stem} {n}{dest.suffix}").exists():
        n += 1
    return dest.parent / f"{dest.stem} {n}{dest.suffix}"


def organize_desktop(include_images):
    desk = HOME / "Desktop"
    month = datetime.date.today().strftime("%Y-%m")
    moved_prints = moved_images = 0
    for f in sorted(desk.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        if SCREENSHOT.match(f.name):
            target = PRINTS / month
            moved_prints += 1
        elif include_images and f.suffix.lower() in IMAGE_EXT:
            target = LOOSE_IMAGES
            moved_images += 1
        else:
            continue
        target.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), str(free_name(target / f.name)))
    parts = []
    if moved_prints:
        parts.append(f"{moved_prints} prints foram para Imagens > Prints > {month}")
    if moved_images:
        parts.append(f"{moved_images} imagens soltas foram para Imagens > Imagens da Mesa")
    if not parts:
        return "A Mesa já estava sem prints soltos." + ("" if include_images else
               " (Imagens que não são print ficaram; posso mover também se você quiser.)")
    left = [f for f in desk.iterdir() if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in IMAGE_EXT]
    tail = f" Ainda ficaram {len(left)} imagens que não são print na Mesa." if left and not include_images else ""
    return "Pronto: " + "; ".join(parts) + ". Nada foi apagado." + tail


def run(args):
    """Runs one fast action and returns a short sentence for Jarvis to say."""
    action = args.get("acao")
    alvo, destino, valor = args.get("alvo", ""), args.get("destino", ""), args.get("valor")
    if action == "organizar_mesa":
        return organize_desktop(bool(args.get("incluir_imagens")))
    if action == "abrir_app":
        r = subprocess.run(["/usr/bin/open", "-a", alvo], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            raise RuntimeError(f"Não achei o app '{alvo}'.")
        return f"{alvo} aberto."
    if action == "abrir":
        target = alvo if re.match(r"^[a-z]+://", alvo or "") else str(resolve(alvo))
        subprocess.run(["/usr/bin/open", target], check=True, timeout=15)
        return f"Aberto: {pathlib.Path(target).name or target}."
    if action == "listar_pasta":
        folder = resolve(alvo)
        items = sorted((c for c in folder.iterdir() if not c.name.startswith(".")), key=lambda c: c.stat().st_mtime, reverse=True)
        dirs = [c.name + "/" for c in items if c.is_dir()]
        files = [c.name for c in items if c.is_file()]
        return (f"{folder} tem {len(dirs)} pastas e {len(files)} arquivos. Mais recentes primeiro. "
                f"Pastas: {', '.join(dirs[:30]) or 'nenhuma'}. Arquivos: {', '.join(files[:40]) or 'nenhum'}.")
    if action == "criar_pasta":
        folder = resolve(alvo, must_exist=False)
        folder.mkdir(parents=True, exist_ok=True)
        return f"Pasta pronta: {folder}."
    if action == "mover":
        src, dest = resolve(alvo), resolve(destino, must_exist=False)
        if not dest.exists():
            dest.mkdir(parents=True)
        if not dest.is_dir():
            raise ValueError("O destino precisa ser uma pasta.")
        final = free_name(dest / src.name)
        shutil.move(str(src), str(final))
        return f"Movi {src.name} para {dest}."
    if action == "lixeira":
        if not args.get("confirmado"):
            return f"Preciso do sim de {USER} antes de mandar '{alvo}' para a Lixeira. Pergunte e chame de novo com confirmado=true."
        src = resolve(alvo)
        osa(f'tell application "Finder" to delete (POSIX file "{src}" as alias)')
        return f"{src.name} foi para a Lixeira (dá para recuperar de lá)."
    if action == "volume":
        level = max(0, min(100, int(valor if valor is not None else 50)))
        osa(f"set volume output volume {level} without output muted")
        return f"Volume em {level}%."
    if action == "mudo":
        on = args.get("ligar", True) is not False
        osa(f"set volume {'with' if on else 'without'} output muted")
        return "Som no mudo." if on else "Som de volta."
    if action == "modo_escuro":
        script = 'tell application "System Events" to tell appearance preferences to set dark mode to '
        on = args.get("ligar")
        osa(script + ("not dark mode" if on is None else "true" if on else "false"))
        dark = osa('tell application "System Events" to tell appearance preferences to get dark mode') == "true"
        return f"Modo {'escuro' if dark else 'claro'} ligado."
    raise ValueError(f"Ação desconhecida: {action}")
