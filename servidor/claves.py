"""Claves del sistema. Nunca están en el repositorio.

La clave con la que el simulador firma las lecturas (HMAC) se toma de la variable AUREA_CLAVE_INGESTA; si no está
definida se crea una al azar la primera vez y se guarda junto a la base de datos, en un archivo que solo lee su dueño.
El servidor y el simulador corren en el mismo equipo y comparten esa carpeta, así que no hay que copiar nada.

Igual se guarda la clave con la que se firman los CSV del registro de auditoría (T16): variable
AUREA_CLAVE_EXPORTACION o archivo clave_exportacion.key junto a la base de datos.
"""
import os
import secrets

from . import config

NOMBRE_ARCHIVO = "clave_ingesta.key"
NOMBRE_ARCHIVO_EXPORTACION = "clave_exportacion.key"


def clave_ingesta() -> bytes:
    return _clave("AUREA_CLAVE_INGESTA", NOMBRE_ARCHIVO)


def clave_exportacion() -> bytes:
    return _clave("AUREA_CLAVE_EXPORTACION", NOMBRE_ARCHIVO_EXPORTACION)


def _clave(variable: str, archivo: str) -> bytes:
    del_entorno = os.environ.get(variable)
    if del_entorno:
        return del_entorno.encode("utf-8")
    ruta = config.RUTA_BD.parent / archivo
    if ruta.is_file():
        return ruta.read_text(encoding="ascii").strip().encode("ascii")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    clave = secrets.token_hex(32)
    ruta.write_text(clave, encoding="ascii")
    try:
        ruta.chmod(0o600)        # en Windows no hace nada: ahí protege la carpeta del usuario
    except OSError:
        pass
    return clave.encode("ascii")
