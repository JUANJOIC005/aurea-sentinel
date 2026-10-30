#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] && { set -a; . ./.env; set +a; }

orden="${1:-}"
[ $# -gt 0 ] && shift
case "$orden" in
  servidor)  python3 -m servidor.migrate >/dev/null; exec python3 -m uvicorn servidor.api.main:app --host "${AUREA_HOST:-127.0.0.1}" --port "${AUREA_PUERTO:-8000}" "$@" ;;
  cliente)   exec python3 -m cliente "$@" ;;
  simulador) exec python3 -m simulador "$@" ;;
  bd)        exec python3 -m servidor.migrate "$@" ;;
  demo)      exec python3 -m servidor.datos_demo "$@" ;;
  pruebas)   exec python3 -m pytest --cov=servidor --cov=cliente.modelo --cov=cliente.controlador --cov=simulador \
                                    --cov-report=term-missing "$@" ;;
  *) sed -n '2,8p' "$0"; exit 1 ;;
esac
