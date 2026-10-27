"""Registro de eventos de seguridad (accesos, fallos, registros). La cadena de hashes llega en el Sprint 3."""
import json


def registrar(conn, accion: str, resultado: str, actor_id: int | None = None,
              recurso: str | None = None, detalle: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO evento_auditoria (actor_id, accion, recurso, resultado, detalle)"
        " VALUES (?, ?, ?, ?, ?)",
        (actor_id, accion, recurso, resultado, json.dumps(detalle or {}, ensure_ascii=False)),
    )
