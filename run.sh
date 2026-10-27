#!/usr/bin/env bash
# Comandos del proyecto:  ./run.sh <servidor|cliente|simulador|bd|demo|pruebas> [opciones]
#   bd [--desde-cero]   crea o actualiza la base de datos local (SQLite) con las migraciones
#   demo                crea las cuentas de demostración (18 usuarios)
#   servidor            arranca la API suelta (la aplicación ya lleva la suya)
#   simulador           genera lecturas de los 36 sensores
#   cliente             abre la aplicación de escritorio (con su servidor y su base de datos locales)
#   pruebas             pruebas con informe de cobertura
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
