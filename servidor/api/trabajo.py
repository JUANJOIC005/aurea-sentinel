"""Trabajo entre el Supervisor y sus técnicos: tareas, incidencias y lecturas manuales, y reconocer alarmas.

Igual que en el resto del servidor, cada ruta pide permiso con `requiere(recurso, acción)` y después comprueba el
vínculo: un Supervisor solo asigna tareas a sus técnicos y sobre sensores de su área; un Técnico solo cambia sus
tareas y solo registra incidencias de los sensores que tiene asignados. Lo que no cuadra se deniega con el mismo 403.
"""
import math
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator

from .. import auditoria, db
from .errores import ErrorNegocio
from .permisos import Acceso, denegar, requiere

router = APIRouter()

FORMATO = "%Y-%m-%d %H:%M:%S"
Prioridad = Literal["baja", "media", "alta"]
EstadoTarea = Literal["pendiente", "en_curso", "hecha"]
TipoIncidencia = Literal["inspeccion", "lectura_manual", "anomalia"]


def _iso(texto: str | None) -> str | None:
    return texto.replace(" ", "T") + "Z" if texto else None


def _ahora() -> str:
    return datetime.now(timezone.utc).strftime(FORMATO)


def _sensor(conn, tag: str) -> dict:
    fila = conn.execute("SELECT s.id, s.tag, s.nombre, s.unidad, s.min_fisico, s.max_fisico, s.area_id, s.activo,"
                        "       a.codigo AS area_codigo FROM sensor s JOIN area a ON a.id = s.area_id WHERE s.tag = ?",
                        (tag,)).fetchone()
    if fila is None or not fila["activo"]:
        raise ErrorNegocio(404, "Sensor no encontrado.")
    return fila


def _area_id(conn, usuario: dict) -> int | None:
    area = (usuario.get("area") or {}).get("codigo")
    fila = conn.execute("SELECT id FROM area WHERE codigo = ?", (area,)).fetchone() if area else None
    return fila["id"] if fila else None


# ── Tareas ──
class NuevaTarea(BaseModel):
    titulo: str = Field(min_length=3, max_length=120)
    descripcion: str | None = Field(default=None, max_length=1000)
    tecnico_id: int
    sensor_tag: str | None = Field(default=None, max_length=20)
    alarma_id: int | None = None
    prioridad: Prioridad = "media"
    fecha_limite: date | None = None

    @field_validator("titulo")
    @classmethod
    def _sin_espacios_sobrantes(cls, valor: str) -> str:
        valor = valor.strip()
        if len(valor) < 3:
            raise ValueError("título demasiado corto")
        return valor


class CambioEstado(BaseModel):
    estado: EstadoTarea


SQL_TAREAS = (
    "SELECT t.id, t.titulo, t.descripcion, t.prioridad, t.estado, t.fecha_limite, t.creada_en, t.cerrada_en,"
    "       t.alarma_id, tec.id AS tecnico_id, tec.nombre AS tecnico_nombre, sup.id AS creada_por_id,"
    "       sup.nombre AS creada_por_nombre, s.tag AS sensor_tag, s.nombre AS sensor_nombre,"
    "       (SELECT count(*) FROM incidencia i WHERE i.tarea_id = t.id) AS incidencias,"
    "       (SELECT max(i.id) FROM incidencia i WHERE i.tarea_id = t.id) AS ultima_incidencia"
    "  FROM tarea t JOIN usuario tec ON tec.id = t.asignada_a JOIN usuario sup ON sup.id = t.creada_por"
    "  LEFT JOIN sensor s ON s.id = t.sensor_id")


def _tarea(f: dict) -> dict:
    return {"id": f["id"], "titulo": f["titulo"], "descripcion": f["descripcion"], "prioridad": f["prioridad"],
            "estado": f["estado"], "fecha_limite": f["fecha_limite"], "creada_en": _iso(f["creada_en"]),
            "cerrada_en": _iso(f["cerrada_en"]), "alarma_id": f["alarma_id"],
            "tecnico": {"id": f["tecnico_id"], "nombre": f["tecnico_nombre"]},
            "creada_por": {"id": f["creada_por_id"], "nombre": f["creada_por_nombre"]},
            "sensor": {"tag": f["sensor_tag"], "nombre": f["sensor_nombre"]} if f["sensor_tag"] else None,
            "incidencias": f["incidencias"], "ultima_incidencia": f["ultima_incidencia"]}


def _una_tarea(conn, tarea_id: int) -> dict:
    return _tarea(conn.execute(SQL_TAREAS + " WHERE t.id = ?", (tarea_id,)).fetchone())


@router.get("/tareas")
def ver_tareas(estado: EstadoTarea | None = None, acceso: Acceso = Depends(requiere("tareas", "ver"))):
    """El Supervisor ve las tareas de los técnicos de su equipo; el Técnico, las que tiene asignadas."""
    yo = acceso.usuario["id"]
    filtro = "tec.supervisor_id = ?" if acceso.ambito == "equipo" else "t.asignada_a = ?"
    sql, params = SQL_TAREAS + f" WHERE {filtro}", [yo]
    if estado:
        sql += " AND t.estado = ?"
        params.append(estado)
    sql += (" ORDER BY CASE t.estado WHEN 'hecha' THEN 1 ELSE 0 END,"
            " CASE t.prioridad WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END, t.fecha_limite IS NULL,"
            " t.fecha_limite, t.id DESC")
    with db.conexion() as conn:
        return {"tareas": [_tarea(f) for f in conn.execute(sql, params).fetchall()]}


@router.post("/tareas", status_code=201)
def crear_tarea(datos: NuevaTarea, acceso: Acceso = Depends(requiere("tareas", "crear"))):
    yo = acceso.usuario
    if datos.fecha_limite and datos.fecha_limite < date.today():
        raise ErrorNegocio(422, "La fecha límite no puede ser anterior a hoy.")
    with db.conexion() as conn:
        tecnico = conn.execute("SELECT id FROM usuario WHERE id = ? AND supervisor_id = ? AND estado = 'activo'",
                               (datos.tecnico_id, yo["id"])).fetchone()
        if tecnico is None:
            denegar(yo, "tareas", "crear", "tecnico_ajeno", tecnico_id=datos.tecnico_id)
        mi_area = _area_id(conn, yo)
        sensor_id = None
        if datos.alarma_id is not None:
            alarma = conn.execute("SELECT a.id, s.tag, s.area_id FROM alarma a JOIN sensor s ON s.id = a.sensor_id"
                                  " WHERE a.id = ?", (datos.alarma_id,)).fetchone()
            if alarma is None:
                raise ErrorNegocio(404, "Alarma no encontrada.")
            if alarma["area_id"] != mi_area:
                denegar(yo, "tareas", "crear", "area", alarma_id=datos.alarma_id)
            if datos.sensor_tag and datos.sensor_tag != alarma["tag"]:
                raise ErrorNegocio(422, "La alarma es de otro sensor.")
            datos.sensor_tag = alarma["tag"]
        if datos.sensor_tag:
            sensor = _sensor(conn, datos.sensor_tag)
            if sensor["area_id"] != mi_area:
                denegar(yo, "tareas", "crear", "area", tag=datos.sensor_tag)
            sensor_id = sensor["id"]
        fila = conn.execute(
            "INSERT INTO tarea (titulo, descripcion, creada_por, asignada_a, sensor_id, alarma_id, prioridad,"
            " fecha_limite) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (datos.titulo, (datos.descripcion or "").strip() or None, yo["id"], datos.tecnico_id, sensor_id,
             datos.alarma_id, datos.prioridad, datos.fecha_limite.isoformat() if datos.fecha_limite else None),
        ).fetchone()
        auditoria.registrar(conn, "tarea_creada", "ok", actor_id=yo["id"], recurso=f"tarea:{fila['id']}",
                            detalle={"tecnico_id": datos.tecnico_id, "sensor": datos.sensor_tag,
                                     "prioridad": datos.prioridad})
        return _una_tarea(conn, fila["id"])


@router.patch("/tareas/{tarea_id}/estado")
def cambiar_estado(tarea_id: int, datos: CambioEstado,
                   acceso: Acceso = Depends(requiere("tareas", "cambiar_estado"))):
    """Solo el Técnico al que está asignada la mueve entre Pendiente, En curso y Hecha."""
    yo = acceso.usuario
    with db.conexion() as conn:
        tarea = conn.execute("SELECT id, asignada_a, estado FROM tarea WHERE id = ?", (tarea_id,)).fetchone()
        if tarea is None:
            raise ErrorNegocio(404, "Tarea no encontrada.")
        if tarea["asignada_a"] != yo["id"]:
            denegar(yo, "tareas", "cambiar_estado", "tarea_ajena", tarea_id=tarea_id)
        cerrada = _ahora() if datos.estado == "hecha" else None
        conn.execute("UPDATE tarea SET estado = ?, cerrada_en = ? WHERE id = ?", (datos.estado, cerrada, tarea_id))
        auditoria.registrar(conn, "tarea_estado", "ok", actor_id=yo["id"], recurso=f"tarea:{tarea_id}",
                            detalle={"antes": tarea["estado"], "despues": datos.estado})
        return _una_tarea(conn, tarea_id)


# ── Incidencias y lecturas manuales ──
class NuevaIncidencia(BaseModel):
    sensor_tag: str = Field(min_length=1, max_length=20)
    tipo: TipoIncidencia
    valor_medido: float | None = Field(default=None, strict=True)
    observaciones: str | None = Field(default=None, max_length=1000)
    tarea_id: int | None = None


SQL_INCIDENCIAS = (
    "SELECT i.id, i.tipo, i.valor_medido, i.observaciones, i.creada_en, i.tarea_id, t.titulo AS tarea_titulo,"
    "       s.tag, s.nombre AS sensor_nombre, s.unidad, tec.id AS tecnico_id, tec.nombre AS tecnico_nombre,"
    "       sup.id AS supervisor_id, sup.nombre AS supervisor_nombre"
    "  FROM incidencia i JOIN sensor s ON s.id = i.sensor_id JOIN usuario tec ON tec.id = i.tecnico_id"
    "  LEFT JOIN usuario sup ON sup.id = tec.supervisor_id LEFT JOIN tarea t ON t.id = i.tarea_id")


def _incidencia(f: dict, ocultar_nombres: bool = False) -> dict:
    tecnico = f"Técnico n.º {f['tecnico_id']}" if ocultar_nombres else f["tecnico_nombre"]
    supervisor = f"Supervisor n.º {f['supervisor_id']}" if ocultar_nombres else f["supervisor_nombre"]
    return {"id": f["id"], "tipo": f["tipo"], "valor_medido": f["valor_medido"], "observaciones": f["observaciones"],
            "creada_en": _iso(f["creada_en"]),
            "sensor": {"tag": f["tag"], "nombre": f["sensor_nombre"], "unidad": f["unidad"]},
            "tarea": {"id": f["tarea_id"], "titulo": f["tarea_titulo"]} if f["tarea_id"] else None,
            "tecnico": {"id": f["tecnico_id"], "nombre": tecnico},
            "supervisor": {"id": f["supervisor_id"], "nombre": supervisor}}


@router.get("/incidencias")
def ver_incidencias(tag: str | None = Query(default=None, max_length=20), limite: int = Query(default=100, ge=1, le=500),
                    acceso: Acceso = Depends(requiere("incidencias", "ver"))):
    """Supervisor: las de su equipo. Técnico: las suyas. Auditor: todas, en solo lectura y sin nombres."""
    sql, params, condiciones = SQL_INCIDENCIAS, [], []
    if acceso.ambito == "equipo":
        condiciones.append("tec.supervisor_id = ?")
        params.append(acceso.usuario["id"])
    elif acceso.ambito == "propias":
        condiciones.append("i.tecnico_id = ?")
        params.append(acceso.usuario["id"])
    if tag:
        condiciones.append("s.tag = ?")
        params.append(tag)
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY i.creada_en DESC, i.id DESC LIMIT ?"
    params.append(limite)
    with db.conexion() as conn:
        filas = conn.execute(sql, params).fetchall()
    return {"incidencias": [_incidencia(f, ocultar_nombres=acceso.ambito == "todo") for f in filas]}


@router.post("/incidencias", status_code=201)
def crear_incidencia(datos: NuevaIncidencia, acceso: Acceso = Depends(requiere("incidencias", "crear"))):
    """Queda ligada a sensor, tarea, técnico y supervisor. Devuelve también el último valor del sistema."""
    yo = acceso.usuario
    with db.conexion() as conn:
        sensor = _sensor(conn, datos.sensor_tag)
        asignado = conn.execute("SELECT 1 FROM asignacion_sensor WHERE tecnico_id = ? AND sensor_id = ?",
                                (yo["id"], sensor["id"])).fetchone()
        if asignado is None:
            denegar(yo, "incidencias", "crear", "area_o_asignacion", tag=datos.sensor_tag)
        if datos.tarea_id is not None:
            tarea = conn.execute("SELECT asignada_a, sensor_id FROM tarea WHERE id = ?", (datos.tarea_id,)).fetchone()
            if tarea is None:
                raise ErrorNegocio(404, "Tarea no encontrada.")
            if tarea["asignada_a"] != yo["id"]:
                denegar(yo, "incidencias", "crear", "tarea_ajena", tarea_id=datos.tarea_id)
            if tarea["sensor_id"] is not None and tarea["sensor_id"] != sensor["id"]:
                raise ErrorNegocio(422, "La tarea es de otro sensor.")
        valor = datos.valor_medido
        if datos.tipo == "lectura_manual" and valor is None:
            raise ErrorNegocio(422, "Una lectura manual necesita el valor medido.")
        if valor is not None and (not math.isfinite(valor) or not sensor["min_fisico"] <= valor <= sensor["max_fisico"]):
            raise ErrorNegocio(422, f"El valor medido está fuera del rango físico del sensor "
                                    f"({sensor['min_fisico']:g} – {sensor['max_fisico']:g} {sensor['unidad']}).")
        fila = conn.execute(
            "INSERT INTO incidencia (tecnico_id, tarea_id, sensor_id, tipo, valor_medido, observaciones)"
            " VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
            (yo["id"], datos.tarea_id, sensor["id"], datos.tipo, valor, (datos.observaciones or "").strip() or None),
        ).fetchone()
        auditoria.registrar(conn, "incidencia_registrada", "ok", actor_id=yo["id"], recurso=f"incidencia:{fila['id']}",
                            detalle={"sensor": datos.sensor_tag, "tipo": datos.tipo, "tarea_id": datos.tarea_id})
        ultima = conn.execute("SELECT valor FROM lectura WHERE sensor_id = ? ORDER BY instante DESC LIMIT 1",
                              (sensor["id"],)).fetchone()
        respuesta = _incidencia(conn.execute(SQL_INCIDENCIAS + " WHERE i.id = ?", (fila["id"],)).fetchone())
    sistema = ultima["valor"] if ultima else None
    respuesta["valor_sistema"] = sistema
    respuesta["diferencia"] = round(valor - sistema, 4) if valor is not None and sistema is not None else None
    return respuesta


# ── Alarmas ──
@router.post("/alarmas/{alarma_id}/reconocer")
def reconocer_alarma(alarma_id: int, acceso: Acceso = Depends(requiere("alarmas", "reconocer"))):
    """El Supervisor del área marca que ha visto la alarma. Se cierra sola cuando el valor vuelve al rango."""
    yo = acceso.usuario
    with db.conexion() as conn:
        alarma = conn.execute("SELECT a.id, a.estado, s.tag, s.area_id FROM alarma a JOIN sensor s"
                              " ON s.id = a.sensor_id WHERE a.id = ?", (alarma_id,)).fetchone()
        if alarma is None:
            raise ErrorNegocio(404, "Alarma no encontrada.")
        if alarma["area_id"] != _area_id(conn, yo):
            denegar(yo, "alarmas", "reconocer", "area", alarma_id=alarma_id)
        if alarma["estado"] != "abierta":
            raise ErrorNegocio(409, "Esta alarma ya está " + ("reconocida." if alarma["estado"] == "reconocida"
                                                               else "cerrada."))
        ahora = _ahora()
        conn.execute("UPDATE alarma SET estado = 'reconocida', reconocida_por = ?, reconocida_en = ? WHERE id = ?",
                     (yo["id"], ahora, alarma_id))
        auditoria.registrar(conn, "alarma_reconocida", "ok", actor_id=yo["id"], recurso=f"alarma:{alarma_id}",
                            detalle={"sensor": alarma["tag"]})
    return {"id": alarma_id, "estado": "reconocida", "reconocida_por": yo["nombre"], "reconocida_en": _iso(ahora)}
