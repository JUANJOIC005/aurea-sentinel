"""A dónde van las lecturas.

- `DestinoApi` (lo normal desde el Sprint 2): las manda firmadas (HMAC) a la API de ingesta del servidor, que
  rechaza las firmas falsas y los valores imposibles.
- `DestinoBaseDeDatos`: las escribe directamente en la base de datos SQLite local, sin firma. Es solo para
  desarrollar sin tener la aplicación abierta (`--destino bd`).
El simulador no cambia: solo el destino.
"""
import json
import time
from datetime import timezone
from typing import Protocol

import sqlite3
from pathlib import Path

import httpx

from servidor.ingesta import firmar

from .modelo import Lectura, Sensor


class ErrorDestino(Exception):
    """El destino no ha aceptado las lecturas (servidor caído, firma rechazada…)."""


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


class DestinoApi(DestinoBaseDeDatos):
    """Lee el catálogo de sensores de la base de datos (es configuración) y envía las lecturas firmadas."""

    def __init__(self, ruta_bd: Path | str, url: str, clave: bytes,
                 http: httpx.Client | None = None, reloj=time.time):
        super().__init__(ruta_bd)
        self._http = http or httpx.Client(base_url=url.rstrip("/"), timeout=10.0)
        self._clave = clave
        self._reloj = reloj

    def cuerpo(self, lecturas: list[Lectura]) -> bytes:
        return json.dumps(
            {"lecturas": [{"tag": l.tag,
                           "instante": l.instante.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "valor": l.valor} for l in lecturas]},
            separators=(",", ":")).encode("utf-8")

    def enviar(self, lecturas: list[Lectura]) -> None:
        cuerpo = self.cuerpo(lecturas)
        marca = int(self._reloj())
        cabeceras = {"Content-Type": "application/json", "X-Aurea-Marca": str(marca),
                     "X-Aurea-Firma": firmar(self._clave, marca, cuerpo)}
        try:
            respuesta = self._http.post("/ingesta/lecturas", content=cuerpo, headers=cabeceras)
        except httpx.HTTPError as error:
            raise ErrorDestino(f"No se ha podido hablar con el servidor: {error}") from error
        if respuesta.status_code >= 400:
            try:
                detalle = respuesta.json().get("detalle", "sin detalle")
            except ValueError:
                detalle = "sin detalle"
            raise ErrorDestino(f"El servidor ha rechazado las lecturas ({respuesta.status_code}): {detalle}")

    def cerrar(self) -> None:
        self._http.close()
        super().cerrar()
