#!/bin/bash
# Uso: ./run.sh            inicia o servidor e abre no navegador
#      ./run.sh --check    conecta ao Gemini e pede uma frase falada
#      ./run.sh --test     roda os testes
set -euo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Rode ./install.sh primeiro." >&2; exit 1; }

case "${1:-}" in
  --check) exec .venv/bin/python server.py --check ;;
  --test)  exec .venv/bin/python testes.py ;;
esac

PORT="$(.venv/bin/python -c 'import core; print(core.settings()["port"])')"
echo "Jarvis em http://127.0.0.1:$PORT  (Ctrl+C para parar)"
( sleep 2; open "http://127.0.0.1:$PORT" ) &
exec .venv/bin/python server.py
