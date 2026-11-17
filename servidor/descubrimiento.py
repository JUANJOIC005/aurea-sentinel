"""Cómo encuentra el simulador al servidor: la aplicación anota su dirección en un archivo junto a la base de datos.

El servidor local elige un puerto libre cada vez que arranca, así que el simulador (otro proceso) no puede
saberlo de antemano. Mientras la aplicación está abierta existe `servidor.json`; al cerrarla se borra.
"""
import json
import os

from . import config

NOMBRE_ARCHIVO = "servidor.json"


def _ruta():
    return config.RUTA_BD.parent / NOMBRE_ARCHIVO


def publicar(url: str) -> None:
    ruta = _ruta()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps({"url": url, "pid": os.getpid()}), encoding="utf-8")


def retirar() -> None:
    _ruta().unlink(missing_ok=True)


def leer() -> str | None:
    """La dirección anotada por la aplicación, o None si no hay ninguna abierta (o el archivo está roto)."""
    try:
        return json.loads(_ruta().read_text(encoding="utf-8"))["url"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
