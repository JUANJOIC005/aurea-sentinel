"""Registro de auditoría para el Auditor (T16): consulta, verificación de la cadena y exportación a CSV firmado.

El Auditor ve todo el registro con los nombres ocultos («Usuario n.º 12 · Supervisor»). El Administrador solo ve
sus propios eventos. Nadie más tiene acceso. Cada exportación queda, a su vez, en el registro.
"""
import csv
import hashlib
import hmac
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from .. import auditoria, claves, db
from .datos import _fecha, _iso
from .errores import ErrorNegocio
from .permisos import Acceso, requiere

router = APIRouter()

FORMATO = "%Y-%m-%d %H:%M:%S"
PREFIJO_FIRMA = "# firma HMAC-SHA256: "
ROLES = {"supervisor": "Supervisor", "tecnico": "Técnico", "auditor": "Auditor", "administrador": "Administrador"}
COLUMNAS = ["id", "instante_utc", "actor", "rol", "accion", "recurso", "resultado", "detalle", "huella"]


def _consulta(acceso: Acceso, desde: str | None, hasta: str | None, accion: str | None, resultado: str | None):
    sql = ("SELECT e.id, e.instante, e.actor_id, u.nombre AS actor_nombre, r.codigo AS rol, e.accion, e.recurso,"
           "       e.resultado, e.detalle, e.hash"
           "  FROM evento_auditoria e LEFT JOIN usuario u ON u.id = e.actor_id LEFT JOIN rol r ON r.id = u.rol_id")
    condiciones, params = [], []
    if acceso.ambito == "propias":
        condiciones.append("e.actor_id = ?")
        params.append(acceso.usuario["id"])
    for valor, condicion in ((_fecha(desde), "e.instante >= ?"), (_fecha(hasta), "e.instante <= ?")):
        if valor:
            condiciones.append(condicion)
            params.append(valor.strftime(FORMATO))
    if accion:
        condiciones.append("e.accion = ?")
        params.append(accion)
    if resultado:
        condiciones.append("e.resultado = ?")
        params.append(resultado)
    return sql + (" WHERE " + " AND ".join(condiciones) if condiciones else ""), params


def _actor(e: dict, ocultar: bool) -> str:
    if e["actor_id"] is None:
        return "Sistema o sin identificar"
    return f"Usuario n.º {e['actor_id']}" if ocultar else e["actor_nombre"]


def _evento(e: dict, ocultar: bool) -> dict:
    return {"id": e["id"], "instante": _iso(e["instante"]), "actor": _actor(e, ocultar),
            "rol": ROLES.get(e["rol"]), "accion": e["accion"], "recurso": e["recurso"], "resultado": e["resultado"],
            "detalle": e["detalle"], "huella": e["hash"]}


@router.get("/auditoria/eventos")
def eventos(desde: str | None = None, hasta: str | None = None, accion: str | None = Query(default=None, max_length=40),
            resultado: str | None = Query(default=None, pattern="^(ok|fallo|denegado)$"),
            limite: int = Query(default=200, ge=1, le=1000), acceso: Acceso = Depends(requiere("auditoria", "ver"))):
    sql, params = _consulta(acceso, desde, hasta, accion, resultado)
    with db.conexion() as conn:
        filas = conn.execute(sql + " ORDER BY e.id DESC LIMIT ?", params + [limite]).fetchall()
    return {"eventos": [_evento(e, ocultar=acceso.ambito == "todo") for e in filas]}


@router.get("/auditoria/verificar")
def verificar(acceso: Acceso = Depends(requiere("auditoria", "verificar"))):
    with db.conexion() as conn:
        resultado = auditoria.verificar(conn)
        auditoria.registrar(conn, "verificacion_auditoria", "ok" if resultado["integro"] else "fallo",
                            actor_id=acceso.usuario["id"], recurso="auditoria",
                            detalle={"eventos": resultado["eventos"], "integro": resultado["integro"]})
    return resultado


def firmar(contenido: bytes) -> str:
    return hmac.new(claves.clave_exportacion(), contenido, hashlib.sha256).hexdigest()


def comprobar_firma(csv_firmado: bytes) -> bool:
    """El CSV termina en «# firma HMAC-SHA256: …», calculada sobre todo lo anterior."""
    texto = csv_firmado.decode("utf-8-sig", errors="replace")
    cuerpo, _, ultima = texto.rstrip("\r\n").rpartition("\r\n")
    if not ultima.startswith(PREFIJO_FIRMA) or not cuerpo:
        return False
    esperada = firmar(("﻿" + cuerpo + "\r\n").encode("utf-8"))
    return hmac.compare_digest(ultima[len(PREFIJO_FIRMA):].strip(), esperada)


@router.get("/auditoria/exportar")
def exportar(desde: str | None = None, hasta: str | None = None, accion: str | None = Query(default=None, max_length=40),
             acceso: Acceso = Depends(requiere("auditoria", "exportar"))):
    sql, params = _consulta(acceso, desde, hasta, accion, None)
    ahora = datetime.now(timezone.utc)
    with db.conexion() as conn:
        filas = conn.execute(sql + " ORDER BY e.id", params).fetchall()
        estado = auditoria.verificar(conn)
        salida = io.StringIO()
        salida.write(f"# AUREA Sentinel · registro de auditoría · exportado {ahora:%Y-%m-%dT%H:%M:%SZ} · "
                     f"{len(filas)} eventos · cadena {'íntegra' if estado['integro'] else 'ROTA'} · "
                     f"última huella {estado['ultima_huella']}\r\n")
        escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
        escritor.writerow(COLUMNAS)
        for e in filas:
            ev = _evento(e, ocultar=True)
            escritor.writerow([ev[c] if c != "instante_utc" else ev["instante"] for c in
                               ["id", "instante_utc", "actor", "rol", "accion", "recurso", "resultado", "detalle",
                                "huella"]])
        cuerpo = ("﻿" + salida.getvalue()).encode("utf-8")
        firma = firmar(cuerpo)
        auditoria.registrar(conn, "exportacion_auditoria", "ok", actor_id=acceso.usuario["id"], recurso="auditoria",
                            detalle={"eventos": len(filas), "desde": desde, "hasta": hasta, "accion": accion,
                                     "firma": firma[:16]})
    contenido = cuerpo + f"{PREFIJO_FIRMA}{firma}\r\n".encode("utf-8")
    nombre = f"registro_auditoria_{ahora:%Y%m%d_%H%M}.csv"
    return Response(contenido, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"', "X-Aurea-Firma": firma})


@router.post("/auditoria/comprobar-firma")
async def comprobar(request: Request, acceso: Acceso = Depends(requiere("auditoria", "exportar"))):
    """El Auditor comprueba que un CSV exportado no se ha tocado después."""
    contenido = await request.body()
    if not contenido or len(contenido) > 20_000_000:
        raise ErrorNegocio(422, "Envía el CSV exportado (como mucho 20 MB).")
    return {"valida": comprobar_firma(contenido)}
