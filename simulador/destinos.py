"""A dónde van las lecturas.

Hoy (Sprint 1) se guardan directamente en la base de datos SQLite local. En el Sprint 2 se añadirá un destino que las
envíe firmadas (HMAC) a la API de ingesta; el simulador no cambia, solo el destino.
"""
from datetime import timezone
from typing import Protocol

import sqlite3
from pathlib import Path

from .modelo import Lectura, Sensor


class Destino(Protocol):
    def enviar(self, lecturas: list[Lectura]) -> None: ...
    def cerrar(self) -> None: ...


class DestinoBaseDeDatos:
    def __init__(self, ruta: Path | str):
        self._conn = sqlite3.connect(ruta, timeout=10)
        self._conn.execute("PRAGMA foreign_keys = ON")

    def sensores(self) -> list[Sensor]:
        filas = self._conn.execute(
            "SELECT id, tag, valor_nominal, min_fisico, max_fisico,"
            "       aviso_bajo, alarma_bajo, aviso_alto, alarma_alto"
            "  FROM sensor WHERE activo ORDER BY id"
        ).fetchall()
        return [Sensor(*fila) for fila in filas]

    def enviar(self, lecturas: list[Lectura]) -> None:
        self._conn.executemany(
            "INSERT INTO lectura (sensor_id, instante, valor) VALUES (?, ?, ?)"
            " ON CONFLICT (sensor_id, instante) DO NOTHING",
            [(l.sensor_id, l.instante.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), l.valor)
             for l in lecturas],
        )
        self._conn.commit()

    def cerrar(self) -> None:
        self._conn.close()
