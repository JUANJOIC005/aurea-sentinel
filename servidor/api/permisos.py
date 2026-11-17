"""Permisos por rol (tabla de T09, apartado 6.2 de la documentación) y comprobación en cada petición.

Regla general: en cada petición se comprueba primero el **rol**, después el **área o el vínculo**, y solo entonces
se consultan datos. Todo lo que no está en la tabla está prohibido. Si algo no coincide la respuesta es siempre la
misma («prohibido») y queda anotada en el registro de auditoría.

Ámbitos:
  area       los sensores del área del Supervisor
  asignados  los sensores que el Supervisor ha asignado al Técnico
  agregados  solo estadísticas (mínimo, máximo, media), nunca lecturas sueltas
  todo       el inventario completo, en solo lectura
"""
from dataclasses import dataclass

from fastapi import Depends, Request

from .. import auditoria, db
from .auth import sesion_actual
from .errores import ErrorNegocio

MENSAJE_PROHIBIDO = "No tienes permiso para esta operación."

PERMISOS: dict[tuple[str, str], dict[str, str]] = {
    ("lecturas", "ver"): {"supervisor": "area", "tecnico": "asignados", "auditor": "agregados"},
    ("historico", "ver"): {"supervisor": "area", "tecnico": "asignados", "auditor": "agregados"},
    ("historico", "exportar"): {"supervisor": "area"},
    ("alarmas", "ver"): {"supervisor": "area", "tecnico": "asignados"},
    ("equipo", "ver"): {"supervisor": "area"},
    ("sensores", "ver"): {"auditor": "todo", "administrador": "todo"},
}


@dataclass(frozen=True)
class Acceso:
    usuario: dict
    ambito: str


def denegar(usuario: dict, recurso: str, accion: str, motivo: str, **detalle) -> None:
    """Anota el intento y responde 403. Usa su propia conexión: la de la petición se deshace con el error."""
    with db.conexion() as conn:
        auditoria.registrar(conn, "acceso_denegado", "denegado", actor_id=usuario["id"],
                            recurso=f"{recurso}:{accion}", detalle={"motivo": motivo, **detalle})
    raise ErrorNegocio(403, MENSAJE_PROHIBIDO)


def requiere(recurso: str, accion: str):
    """Dependencia de FastAPI: deja pasar solo a los roles de la tabla y entrega el ámbito de cada uno."""
    def dependencia(request: Request, sesion: dict = Depends(sesion_actual)) -> Acceso:
        usuario = sesion["usuario"]
        ambito = PERMISOS.get((recurso, accion), {}).get(usuario["rol"])
        if ambito is None:
            denegar(usuario, recurso, accion, "rol", ruta=request.url.path)
        return Acceso(usuario, ambito)
    return dependencia
