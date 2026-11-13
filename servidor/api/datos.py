"""Datos de la central para las ventanas: lecturas en directo, histórico, alarmas, equipo e inventario.

Cada ruta pide permiso con `requiere(recurso, acción)` (tabla de permisos de T09) y, después, filtra por área o por
vínculo: la ventana nunca decide qué datos ve la persona, lo decide el servidor.
"""
import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from .. import auditoria, config, db, estados
from .errores import ErrorNegocio
from .permisos import Acceso, denegar, requiere

router = APIRouter()

FORMATO = "%Y-%m-%d %H:%M:%S"
COLUMNAS_SENSOR = ("s.id, s.tag, s.nombre, s.magnitud, s.unidad, s.valor_nominal, s.min_fisico, s.max_fisico,"
                   " s.aviso_bajo, s.alarma_bajo, s.aviso_alto, s.alarma_alto, s.activo,"
                   " a.codigo AS area_codigo, a.nombre AS area_nombre")


# ── Utilidades ──
def _iso(texto: str | None) -> str | None:
    """«2026-11-02 10:00:00» (UTC, como se guarda) → «2026-11-02T10:00:00Z»."""
    return texto.replace(" ", "T") + "Z" if texto else None


def _fecha(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        fecha = datetime.fromisoformat(texto.strip().replace("Z", "+00:00"))
    except ValueError:
        raise ErrorNegocio(422, "La fecha no es válida: usa el formato AAAA-MM-DD o AAAA-MM-DDTHH:MM.") from None
    return (fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _umbrales(s: dict) -> dict:
    return {"aviso_bajo": s["aviso_bajo"], "alarma_bajo": s["alarma_bajo"],
            "aviso_alto": s["aviso_alto"], "alarma_alto": s["alarma_alto"]}


def _ficha(s: dict) -> dict:
    return {"tag": s["tag"], "nombre": s["nombre"], "magnitud": s["magnitud"], "unidad": s["unidad"],
            "area": {"codigo": s["area_codigo"], "nombre": s["area_nombre"]},
            "min_fisico": s["min_fisico"], "max_fisico": s["max_fisico"], "valor_nominal": s["valor_nominal"],
            "umbrales": _umbrales(s)}


def _estado(s: dict, valor: float) -> str:
    return estados.estado(valor, s["aviso_bajo"], s["alarma_bajo"], s["aviso_alto"], s["alarma_alto"])


def _sensores(conn, acceso: Acceso, tag: str | None = None) -> list[dict]:
    """Los sensores que esta persona puede ver, según su ámbito (su área o los que le han asignado)."""
    sql, params = f"SELECT {COLUMNAS_SENSOR} FROM sensor s JOIN area a ON a.id = s.area_id", []
    if acceso.ambito == "asignados":
        sql += " JOIN asignacion_sensor x ON x.sensor_id = s.id AND x.tecnico_id = ?"
        params.append(acceso.usuario["id"])
    sql += " WHERE s.activo = 1"
    if acceso.ambito == "area":
        sql += " AND a.codigo = ?"
        params.append((acceso.usuario.get("area") or {}).get("codigo"))
    if tag:
        sql += " AND s.tag = ?"
        params.append(tag)
    return conn.execute(sql + " ORDER BY s.id", params).fetchall()


def _sensor_o_prohibido(conn, acceso: Acceso, tag: str, recurso: str, accion: str) -> dict:
    permitido = _sensores(conn, acceso, tag)
    if permitido:
        return permitido[0]
    if conn.execute("SELECT 1 FROM sensor WHERE tag = ? AND activo = 1", (tag,)).fetchone() is None:
        raise ErrorNegocio(404, "Sensor no encontrado.")
    denegar(acceso.usuario, recurso, accion, "area_o_asignacion", tag=tag)


# ── Lecturas en directo ──
def _tarjeta(conn, s: dict, ahora: datetime) -> dict:
    ultima = conn.execute("SELECT instante, valor FROM lectura WHERE sensor_id = ? ORDER BY instante DESC LIMIT 1",
                          (s["id"],)).fetchone()
    abierta = conn.execute("SELECT nivel FROM alarma WHERE sensor_id = ? AND estado <> 'cerrada' "
                           "ORDER BY id DESC LIMIT 1", (s["id"],)).fetchone()
    ficha = _ficha(s) | {"valor": None, "instante": None, "estado": "sin_datos", "edad_s": None,
                         "tendencia_1h": None, "serie": [], "alarma": abierta["nivel"] if abierta else None}
    if ultima is None:
        return ficha
    # Serie de la última hora (un punto por minuto) respecto a la última lectura, para la gráfica pequeña.
    serie = conn.execute(
        "SELECT substr(instante, 1, 16) AS minuto, avg(valor) AS valor FROM lectura"
        " WHERE sensor_id = ? AND instante > datetime(?, '-60 minutes') AND instante <= ?"
        " GROUP BY minuto ORDER BY minuto", (s["id"], ultima["instante"], ultima["instante"])).fetchall()
    fecha = datetime.strptime(ultima["instante"], FORMATO).replace(tzinfo=timezone.utc)
    return ficha | {
        "valor": ultima["valor"], "instante": _iso(ultima["instante"]), "estado": _estado(s, ultima["valor"]),
        "edad_s": max(0, int((ahora - fecha).total_seconds())),
        "serie": [round(f["valor"], 4) for f in serie],
        "tendencia_1h": round(ultima["valor"] - serie[0]["valor"], 4) if len(serie) > 1 else None,
    }


def _resumen(conn, tarjetas: list[dict], sensores: list[dict]) -> dict:
    cuenta = {e: sum(1 for t in tarjetas if t["estado"] == e) for e in ("normal", "aviso", "alarma")}
    ids = [s["id"] for s in sensores]
    lecturas = validas = alarmas = 0
    if ids:
        marcas = ",".join("?" * len(ids))
        fila = conn.execute(f"SELECT count(*) AS n, coalesce(sum(valida), 0) AS validas FROM lectura"
                            f" WHERE sensor_id IN ({marcas}) AND instante >= datetime('now', '-24 hours')",
                            ids).fetchone()
        lecturas, validas = fila["n"], fila["validas"]
        alarmas = conn.execute(f"SELECT count(*) AS n FROM alarma WHERE sensor_id IN ({marcas})"
                               f" AND estado <> 'cerrada'", ids).fetchone()["n"]
    return {"sensores": len(sensores), "en_rango": cuenta["normal"], "en_aviso": cuenta["aviso"],
            "en_alarma": cuenta["alarma"], "alarmas_activas": alarmas, "tareas_abiertas": None,
            "lecturas_24h": lecturas, "validas_24h": validas,
            "pct_validas": round(100 * validas / lecturas, 1) if lecturas else None}


def _agregado_por_area(conn, ahora: datetime) -> dict:
    """Para el Auditor: cuántos sensores de cada área están en rango, en aviso o en alarma. Sin valores sueltos."""
    areas = {}
    for s in conn.execute(f"SELECT {COLUMNAS_SENSOR} FROM sensor s JOIN area a ON a.id = s.area_id"
                          f" WHERE s.activo = 1 ORDER BY s.id").fetchall():
        estado = _tarjeta(conn, s, ahora)["estado"]
        fila = areas.setdefault(s["area_codigo"], {"area": {"codigo": s["area_codigo"], "nombre": s["area_nombre"]},
                                                   "sensores": 0, "normal": 0, "aviso": 0, "alarma": 0,
                                                   "sin_datos": 0})
        fila["sensores"] += 1
        fila[estado] += 1
    return {"agregado": True, "areas": list(areas.values())}


@router.get("/lecturas/ultimas")
def ultimas(acceso: Acceso = Depends(requiere("lecturas", "ver"))):
    ahora = datetime.now(timezone.utc)
    with db.conexion() as conn:
        if acceso.ambito == "agregados":
            return _agregado_por_area(conn, ahora)
        sensores = _sensores(conn, acceso)
        tarjetas = [_tarjeta(conn, s, ahora) for s in sensores]
        return {"sensores": tarjetas, "resumen": _resumen(conn, tarjetas, sensores)}


# ── Histórico ──
def _historico(conn, acceso: Acceso, tag: str, horas: int, desde: str | None, hasta: str | None) -> dict:
    s = _sensor_o_prohibido(conn, acceso, tag, "historico", "ver")
    limite = config.HISTORICO_DIAS[acceso.usuario["rol"]]
    ultimo = conn.execute("SELECT max(instante) AS u FROM lectura WHERE sensor_id = ?", (s["id"],)).fetchone()["u"]
    fin = _fecha(hasta) or (datetime.strptime(ultimo, FORMATO).replace(tzinfo=timezone.utc) if ultimo
                            else datetime.now(timezone.utc))
    inicio = _fecha(desde) or fin - timedelta(hours=horas)
    if inicio >= fin:
        raise ErrorNegocio(422, "La fecha de inicio debe ser anterior a la de fin.")
    if fin - inicio > timedelta(days=limite):
        raise ErrorNegocio(422, f"Puedes consultar como máximo {limite} días de una vez.")
    ini_txt, fin_txt = inicio.strftime(FORMATO), fin.strftime(FORMATO)

    horas_filas = conn.execute(
        "SELECT strftime('%Y-%m-%d %H:00:00', instante) AS hora, min(valor) AS minimo, max(valor) AS maximo,"
        "       avg(valor) AS media, count(*) AS n, coalesce(sum(valida), 0) AS validas"
        "  FROM lectura WHERE sensor_id = ? AND instante BETWEEN ? AND ? GROUP BY hora ORDER BY hora",
        (s["id"], ini_txt, fin_txt)).fetchall()
    puntos = []
    for f in horas_filas:
        peor = max((_estado(s, f["minimo"]), _estado(s, f["maximo"])), key=("normal", "aviso", "alarma").index)
        puntos.append({"hora": _iso(f["hora"]), "minimo": round(f["minimo"], 4), "maximo": round(f["maximo"], 4),
                       "media": round(f["media"], 4), "lecturas": f["n"], "validas": f["validas"], "estado": peor})
    total = sum(p["lecturas"] for p in puntos)
    en_rango = conn.execute(
        "SELECT count(*) AS n FROM lectura WHERE sensor_id = ? AND instante BETWEEN ? AND ?"
        " AND valor < coalesce(?, 1e308) AND valor > coalesce(?, -1e308)",
        (s["id"], ini_txt, fin_txt, s["aviso_alto"], s["aviso_bajo"])).fetchone()["n"]
    resumen = {"minimo": min((p["minimo"] for p in puntos), default=None),
               "maximo": max((p["maximo"] for p in puntos), default=None),
               "media": round(sum(p["media"] * p["lecturas"] for p in puntos) / total, 4) if total else None,
               "lecturas": total, "validas": sum(p["validas"] for p in puntos),
               "pct_en_rango": round(100 * en_rango / total, 1) if total else None}
    return {"sensor": _ficha(s), "agregado": True, "desde": _iso(ini_txt), "hasta": _iso(fin_txt),
            "resumen": resumen, "puntos": puntos}


@router.get("/lecturas/historico")
def historico(tag: str = Query(min_length=1, max_length=20), horas: int = Query(default=24, ge=1, le=24 * 30),
              desde: str | None = None, hasta: str | None = None,
              acceso: Acceso = Depends(requiere("historico", "ver"))):
    with db.conexion() as conn:
        return _historico(conn, acceso, tag, horas, desde, hasta)


@router.get("/lecturas/historico/csv")
def historico_csv(tag: str = Query(min_length=1, max_length=20), horas: int = Query(default=24, ge=1, le=24 * 30),
                  desde: str | None = None, hasta: str | None = None,
                  acceso: Acceso = Depends(requiere("historico", "exportar"))):
    with db.conexion() as conn:
        datos = _historico(conn, acceso, tag, horas, desde, hasta)
        salida = io.StringIO()
        escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
        escritor.writerow(["hora_utc", "minimo", "maximo", "media", "lecturas", "estado"])
        for p in datos["puntos"]:
            escritor.writerow([p["hora"], p["minimo"], p["maximo"], p["media"], p["lecturas"], p["estado"]])
        auditoria.registrar(conn, "exportacion_csv", "ok", actor_id=acceso.usuario["id"], recurso=f"historico:{tag}",
                            detalle={"desde": datos["desde"], "hasta": datos["hasta"], "filas": len(datos["puntos"])})
    nombre = f"historico_{tag}_{datos['desde'][:10]}_{datos['hasta'][:10]}.csv"
    return Response("﻿" + salida.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


# ── Alarmas, equipo e inventario ──
FILTROS_ALARMA = {"activas": "a.estado <> 'cerrada'", "hoy": "a.abierta_en >= date('now')",
                  "7dias": "a.abierta_en >= datetime('now', '-7 days')"}


@router.get("/alarmas")
def alarmas(filtro: Literal["activas", "hoy", "7dias"] = "activas",
            acceso: Acceso = Depends(requiere("alarmas", "ver"))):
    with db.conexion() as conn:
        ids = [s["id"] for s in _sensores(conn, acceso)]
        if not ids:
            return {"alarmas": []}
        filas = conn.execute(
            "SELECT a.id, s.tag, s.nombre, s.unidad, a.nivel, a.valor, a.abierta_en, a.cerrada_en, a.estado,"
            "       u.nombre AS reconocida_por"
            "  FROM alarma a JOIN sensor s ON s.id = a.sensor_id LEFT JOIN usuario u ON u.id = a.reconocida_por"
            f" WHERE a.sensor_id IN ({','.join('?' * len(ids))}) AND {FILTROS_ALARMA[filtro]}"
            " ORDER BY a.abierta_en DESC LIMIT 200", ids).fetchall()
    return {"alarmas": [f | {"abierta_en": _iso(f["abierta_en"]), "cerrada_en": _iso(f["cerrada_en"])}
                        for f in filas]}


@router.get("/equipo")
def equipo(acceso: Acceso = Depends(requiere("equipo", "ver"))):
    """Los técnicos vinculados al Supervisor y los sensores que tiene asignados cada uno."""
    with db.conexion() as conn:
        tecnicos = conn.execute(
            "SELECT id, nombre, correo, ultimo_acceso FROM usuario WHERE supervisor_id = ? AND estado = 'activo'"
            " ORDER BY nombre", (acceso.usuario["id"],)).fetchall()
        for t in tecnicos:
            t["sensores"] = [f["tag"] for f in conn.execute(
                "SELECT s.tag FROM asignacion_sensor x JOIN sensor s ON s.id = x.sensor_id"
                " WHERE x.tecnico_id = ? ORDER BY s.id", (t["id"],))]
            t["ultimo_acceso"] = _iso(t["ultimo_acceso"])
    return {"tecnicos": tecnicos}


@router.get("/sensores")
def inventario(acceso: Acceso = Depends(requiere("sensores", "ver"))):
    """Inventario completo, solo lectura (Auditor y Administrador)."""
    with db.conexion() as conn:
        filas = conn.execute(f"SELECT {COLUMNAS_SENSOR} FROM sensor s JOIN area a ON a.id = s.area_id"
                             f" ORDER BY s.id").fetchall()
    return {"sensores": [_ficha(s) | {"activo": bool(s["activo"])} for s in filas]}
