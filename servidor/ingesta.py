"""Ingesta de lecturas: firma HMAC, validación de cada lectura y apertura y cierre de alarmas.

El simulador firma cada envío con HMAC-SHA256 sobre «marca de tiempo + cuerpo». El servidor recalcula la firma con
la misma clave, y rechaza el envío entero si no coincide o si la marca de tiempo se aleja de la hora actual (para que
no se pueda repetir un envío antiguo). Después revisa cada lectura por separado: sensor conocido, valor dentro del
rango físico del sensor y fecha razonable. Lo que no cumple se rechaza y se anota en el registro de auditoría.
"""
import hashlib
import hmac
import math
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

from . import auditoria, estados

TOLERANCIA_RELOJ_S = 300       # diferencia máxima entre la marca del envío y la hora del servidor
MAX_FUTURO_S = 120             # una lectura no puede ser de «dentro de más de 2 minutos»
MAX_ANTIGUEDAD_DIAS = 31       # ni de hace más de un mes
MAX_LECTURAS = 500             # lecturas por envío

FORMATO = "%Y-%m-%d %H:%M:%S"  # como se guardan las fechas en la base de datos (UTC)


def firmar(clave: bytes, marca: int, cuerpo: bytes) -> str:
    return hmac.new(clave, str(marca).encode("ascii") + b"." + cuerpo, hashlib.sha256).hexdigest()


def firma_valida(clave: bytes, marca: str | None, firma: str | None, cuerpo: bytes,
                 ahora: float | None = None) -> bool:
    """Siempre contesta lo mismo, falle lo que falle: no se enseña qué parte de la firma está mal."""
    try:
        marca_n = int(marca or "")
    except ValueError:
        return False
    if not firma:
        return False
    ahora = time.time() if ahora is None else ahora
    if abs(ahora - marca_n) > TOLERANCIA_RELOJ_S:
        return False
    esperada = firmar(clave, marca_n, cuerpo)
    return hmac.compare_digest(firma.encode("utf-8", "replace"), esperada.encode("ascii"))


def _instante(texto: str) -> datetime | None:
    try:
        fecha = datetime.fromisoformat(texto.strip())
    except ValueError:
        return None
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc).replace(microsecond=0)


def transicion(nivel_abierto: str | None, estado: str) -> str:
    """Qué hay que hacer con la alarma de un sensor: 'nada', 'abrir', 'escalar' o 'cerrar'."""
    if estado == estados.NORMAL:
        return "cerrar" if nivel_abierto else "nada"
    if nivel_abierto is None:
        return "abrir"
    if nivel_abierto == estados.AVISO and estado == estados.ALARMA:
        return "escalar"
    return "nada"


def actualizar_alarma(conn, sensor: dict, instante: str, valor: float) -> None:
    """Abre la alarma si el valor pasa un umbral, la escala de aviso a alarma y la cierra al volver al rango."""
    actual = estados.estado(valor, sensor["aviso_bajo"], sensor["alarma_bajo"], sensor["aviso_alto"],
                            sensor["alarma_alto"])
    abierta = conn.execute(
        "SELECT id, nivel FROM alarma WHERE sensor_id = ? AND estado <> 'cerrada' ORDER BY id DESC LIMIT 1",
        (sensor["id"],)).fetchone()
    accion = transicion(abierta["nivel"] if abierta else None, actual)
    if accion == "abrir":
        conn.execute("INSERT INTO alarma (sensor_id, nivel, valor, abierta_en) VALUES (?, ?, ?, ?)",
                     (sensor["id"], actual, valor, instante))
    elif accion == "escalar":
        conn.execute("UPDATE alarma SET nivel = ?, valor = ? WHERE id = ?", (actual, valor, abierta["id"]))
    elif accion == "cerrar":
        conn.execute("UPDATE alarma SET estado = 'cerrada', cerrada_en = ? WHERE id = ?", (instante, abierta["id"]))


def _comprobar(lectura: dict, sensores: dict, ahora: datetime):
    """Devuelve (motivo del rechazo o None, sensor, instante como texto)."""
    sensor = sensores.get(lectura["tag"])
    if sensor is None:
        return "sensor_desconocido", None, None
    if not sensor["activo"]:
        return "sensor_inactivo", sensor, None
    valor = lectura["valor"]
    if not math.isfinite(valor):
        return "valor_no_numerico", sensor, None
    if valor < sensor["min_fisico"] or valor > sensor["max_fisico"]:
        return "fuera_de_rango_fisico", sensor, None
    instante = _instante(lectura["instante"])
    if instante is None:
        return "fecha_no_valida", sensor, None
    if instante > ahora + timedelta(seconds=MAX_FUTURO_S):
        return "fecha_en_el_futuro", sensor, None
    if instante < ahora - timedelta(days=MAX_ANTIGUEDAD_DIAS):
        return "fecha_demasiado_antigua", sensor, None
    return None, sensor, instante.strftime(FORMATO)


def ingestar(conn, lecturas: list[dict], ahora: datetime | None = None) -> dict:
    """Guarda las lecturas válidas. Devuelve cuántas se aceptaron, cuántas ya estaban y cuáles se rechazaron."""
    ahora = ahora or datetime.now(timezone.utc)
    sensores = {f["tag"]: f for f in conn.execute(
        "SELECT id, tag, activo, min_fisico, max_fisico, aviso_bajo, alarma_bajo, aviso_alto, alarma_alto"
        "  FROM sensor")}
    ultimo = {f["sensor_id"]: f["ultimo"] for f in conn.execute(
        "SELECT sensor_id, max(instante) AS ultimo FROM lectura GROUP BY sensor_id")}

    aceptadas, duplicadas, rechazadas, nuevas = 0, 0, [], []
    for lectura in lecturas:
        motivo, sensor, instante = _comprobar(lectura, sensores, ahora)
        if motivo:
            rechazadas.append({"tag": lectura["tag"], "motivo": motivo})
            continue
        cursor = conn.execute(
            "INSERT INTO lectura (sensor_id, instante, valor) VALUES (?, ?, ?)"
            " ON CONFLICT (sensor_id, instante) DO NOTHING",
            (sensor["id"], instante, lectura["valor"]))
        if cursor.rowcount:
            aceptadas += 1
            nuevas.append((sensor, instante, lectura["valor"]))
        else:
            duplicadas += 1

    # Las alarmas solo siguen a las lecturas más recientes: una lectura atrasada no abre ni cierra nada.
    for sensor, instante, valor in sorted(nuevas, key=lambda n: (n[0]["id"], n[1])):
        if instante >= ultimo.get(sensor["id"], ""):
            actualizar_alarma(conn, sensor, instante, valor)

    if rechazadas:
        motivos = Counter(r["motivo"] for r in rechazadas)
        auditoria.registrar(conn, "lectura_rechazada", "fallo", recurso="lectura",
                            detalle={"cantidad": len(rechazadas), "motivos": dict(motivos)})
    return {"aceptadas": aceptadas, "duplicadas": duplicadas, "rechazadas": rechazadas}
