"""Configuración del servidor. Todo viene de variables de entorno (o del fichero .env)."""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _cargar_env() -> None:
    """Lee .env sin pisar las variables que ya estén definidas en el entorno."""
    fichero = RAIZ / ".env"
    if not fichero.is_file():
        return
    for linea in fichero.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip())


_cargar_env()

def _carpeta_de_datos() -> Path:
    """Dónde guarda la aplicación sus datos: la carpeta de datos del usuario, sin permisos de administrador."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "AUREA Sentinel"


RUTA_BD = Path(os.environ.get("AUREA_BD") or _carpeta_de_datos() / "aurea sentinel.db")
HOST = os.environ.get("AUREA_HOST", "127.0.0.1")
PUERTO = int(os.environ.get("AUREA_PUERTO", "8000"))   # solo para ./run.sh servidor; la aplicación elige un puerto libre

INTENTOS_MAXIMOS = 5          # fallos seguidos antes de bloquear la cuenta
BLOQUEO_MINUTOS = 15          # duración del bloqueo
PASSWORD_MINIMO = 12          # longitud mínima de contraseña

# Caducidad de la sesión según el rol (minutos)
SESION_MINUTOS = {"supervisor": 15, "tecnico": 30, "auditor": 15, "administrador": 10}

# Segundo factor (código de 6 dígitos). Obligatorio para estos roles; AUREA_DOBLE_FACTOR=no lo desactiva
# (solo para desarrollar o para una demostración sin móvil: por defecto está activado).
DOBLE_FACTOR_ACTIVO = os.environ.get("AUREA_DOBLE_FACTOR", "si").strip().lower() not in ("no", "0", "false", "off")
DOBLE_FACTOR_ROLES = frozenset({"supervisor", "auditor", "administrador"})
DESAFIO_MINUTOS = 5           # tiempo para escribir el código tras acertar la contraseña
CODIGOS_POR_DESAFIO = 3       # tres códigos erróneos devuelven al paso 1

# Cuántos días de histórico puede consultar cada rol de una vez
HISTORICO_DIAS = {"supervisor": 30, "tecnico": 7, "auditor": 30}
