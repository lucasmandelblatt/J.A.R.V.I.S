#!/bin/bash
# Instala o Jarvis: ambiente Python, dependências e config.json. Uso: ./install.sh [--app]
set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '\n==> %s\n' "$1"; }
warn() { printf 'AVISO: %s\n' "$1" >&2; }
fail() { printf 'ERRO: %s\n' "$1" >&2; exit 1; }

[ "$(uname)" = "Darwin" ] || fail "O Jarvis só roda no macOS (Keychain, osascript, screencapture, app Swift)."

say "Procurando o Python"
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for c in python3.15 python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
      PY="$c"; break
    fi
  done
fi
[ -n "$PY" ] || fail "Python 3.11 ou mais novo não encontrado. Instale com: brew install python"
echo "Usando $("$PY" --version) em $(command -v "$PY")"

say "Criando o ambiente (.venv) e instalando as dependências"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt

say "Configuração"
if [ ! -f config.json ]; then
  cp config.example.json config.json
  echo "config.json criado a partir do exemplo (edite à vontade; ele fica fora do git)."
  if [ -t 0 ]; then
    read -r -p "Como o Jarvis deve te chamar? " NOME
    [ -n "$NOME" ] && NOME="$NOME" .venv/bin/python -c 'import os, config; config.save_setting("user_name", os.environ["NOME"])'
  fi
else
  echo "config.json já existe; não mexi."
fi

say "Ferramentas opcionais"
command -v yt-dlp  >/dev/null 2>&1 || warn "yt-dlp não encontrado (brew install yt-dlp); só é preciso para assistir vídeos."
command -v ffprobe >/dev/null 2>&1 || warn "ffprobe não encontrado (brew install ffmpeg); só é preciso para assistir vídeos."
command -v claude  >/dev/null 2>&1 || warn "Claude Code não encontrado; pesquisa profunda e trabalho longo ficam indisponíveis."

say "Chave do Gemini"
if [ -n "${GEMINI_API_KEY:-}" ] || security find-generic-password -s jarvis-gemini >/dev/null 2>&1; then
  echo "Chave encontrada."
else
  warn "Chave do Gemini não encontrada. Rode ./scripts/set-key.sh (ou exporte GEMINI_API_KEY)."
fi

if [ "${1:-}" = "--app" ]; then
  say "Compilando o app (precisa das Ferramentas de Linha de Comando do Xcode)"
  xcode-select -p >/dev/null 2>&1 || fail "Rode: xcode-select --install"
  app/build.sh
fi

say "Pronto. Próximo passo: ./run.sh --check (testa a conexão) e depois ./run.sh"
