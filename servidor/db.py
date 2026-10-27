"""Acceso a la base de datos SQLite (un único archivo local).

Una conexión por operación: confirma al salir y deshace si hay un error.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config


def _filas_como_diccionarios(cursor, fila):
    return {columna[0]: valor for columna, valor in zip(cursor.description, fila)}


@contextmanager
def conexion():
    config.RUTA_BD.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.RUTA_BD, timeout=10)
    conn.row_factory = _filas_como_diccionarios
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")   # el simulador puede escribir mientras la aplicación lee
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def a_fecha(texto: str | None) -> datetime | None:
    """Convierte «AAAA-MM-DD HH:MM:SS» (UTC, como se guarda) en un datetime con zona horaria."""
    return datetime.fromisoformat(texto).replace(tzinfo=timezone.utc) if texto else None
