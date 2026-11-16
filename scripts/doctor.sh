#!/bin/bash
# Diagnóstico rápido do ambiente. Só lê; não muda nada.
cd "$(dirname "$0")/.."
ok() { printf '  ok     %s\n' "$1"; }
no() { printf '  FALTA  %s\n' "$1"; }

[ "$(uname)" = "Darwin" ] && ok "macOS" || no "macOS (obrigatório)"
[ -x .venv/bin/python ] && ok ".venv ($(.venv/bin/python --version))" || no ".venv (rode ./install.sh)"
.venv/bin/python -c "import aiohttp" 2>/dev/null && ok "aiohttp" || no "aiohttp (rode ./install.sh)"
[ -f config.json ] && ok "config.json" || no "config.json (rode ./install.sh)"
{ [ -n "${GEMINI_API_KEY:-}" ] || security find-generic-password -s jarvis-gemini >/dev/null 2>&1; } \
  && ok "chave do Gemini" || no "chave do Gemini (./scripts/set-key.sh)"
for t in yt-dlp ffprobe claude; do
  command -v "$t" >/dev/null 2>&1 && ok "$t (opcional)" || no "$t (opcional)"
done
[ -d "$HOME/Applications/Jarvis.app" ] && ok "Jarvis.app" || no "Jarvis.app (opcional: ./install.sh --app)"
echo "Permissões do macOS (Microfone, Gravação de Tela, Automação) só se confirmam no app: Ajustes do Sistema > Privacidade."
