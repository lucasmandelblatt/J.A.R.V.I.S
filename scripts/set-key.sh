#!/bin/bash
# Guarda a chave do Gemini no Keychain (serviço "jarvis-gemini", o que core.py lê).
# Com -w no fim e sem valor, o security pede a chave no terminal: ela não aparece em `ps` nem no histórico.
set -euo pipefail
echo "Crie a chave em https://aistudio.google.com/apikey e cole abaixo quando pedir."
security add-generic-password -U -s jarvis-gemini -a "$USER" -w
echo "Guardada no Keychain. Teste com: ./run.sh --check"
