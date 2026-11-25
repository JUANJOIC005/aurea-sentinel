"""Registro de eventos de seguridad (accesos, fallos, denegaciones, exportaciones…) encadenado con hashes (T16).

Cada evento guarda la huella (SHA-256) del anterior y la suya propia, calculada sobre su contenido y esa huella
anterior. Si alguien cambia o borra un evento, la cadena deja de cuadrar a partir de ese punto y `verificar` lo dice.
La base de datos, además, no deja hacer UPDATE ni DELETE sobre la tabla (Sprint 1).

Los eventos anteriores a la cadena (bases de datos del Sprint 1 y 2) no tienen huella: se cuentan aparte y la cadena
empieza en el primer evento que sí la tiene.
"""
import hashlib
import json
from datetime import datetime, timezone

ORIGEN = "0" * 64                 # «huella anterior» del primer evento de la cadena
FORMATO = "%Y-%m-%d %H:%M:%S"


def huella(anterior: str, instante: str, actor_id: int | None, accion: str, recurso: str | None,
           resultado: str, detalle: str) -> str:
    contenido = json.dumps([anterior, instante, actor_id, accion, recurso, resultado, detalle],
                           ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def ultima_huella(conn) -> str:
    fila = conn.execute("SELECT hash FROM evento_auditoria WHERE hash IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
    return fila["hash"] if fila else ORIGEN


def registrar(conn, accion: str, resultado: str, actor_id: int | None = None,
              recurso: str | None = None, detalle: dict | None = None) -> None:
    # Si esta conexión aún no escribe nada, se reserva la escritura antes de leer la última huella: así dos
    # peticiones a la vez no pueden enlazar con el mismo evento anterior.
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    instante = datetime.now(timezone.utc).strftime(FORMATO)
    texto = json.dumps(detalle or {}, ensure_ascii=False)
    anterior = ultima_huella(conn)
    conn.execute(
        "INSERT INTO evento_auditoria (instante, actor_id, accion, recurso, resultado, detalle, hash_anterior, hash)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (instante, actor_id, accion, recurso, resultado, texto, anterior,
         huella(anterior, instante, actor_id, accion, recurso, resultado, texto)),
    )


def verificar(conn) -> dict:
    """Recorre el registro en orden y comprueba que cada evento enlaza con el anterior y que su contenido no ha
    cambiado. Devuelve el resumen y, si algo falla, el primer evento roto y por qué."""
    anterior, empezada = ORIGEN, False
    total = encadenados = sin_cadena = 0
    error = None
    for e in conn.execute("SELECT id, instante, actor_id, accion, recurso, resultado, detalle, hash_anterior, hash"
                          "  FROM evento_auditoria ORDER BY id"):
        total += 1
        if error:
            continue
        if e["hash"] is None:
            if empezada:
                error = {"id": e["id"], "motivo": "Evento sin huella dentro de la cadena."}
            else:
                sin_cadena += 1
            continue
        empezada = True
        if e["hash_anterior"] != anterior:
            error = {"id": e["id"], "motivo": "No enlaza con el evento anterior: falta un evento o se ha cambiado."}
            continue
        calculada = huella(anterior, e["instante"], e["actor_id"], e["accion"], e["recurso"], e["resultado"],
                           e["detalle"])
        if calculada != e["hash"]:
            error = {"id": e["id"], "motivo": "Su contenido no coincide con su huella: el evento se ha modificado."}
            continue
        encadenados += 1
        anterior = e["hash"]
    return {"integro": error is None, "eventos": total, "encadenados": encadenados, "sin_cadena": sin_cadena,
            "ultima_huella": anterior, "primer_error": error}
