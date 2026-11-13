"""Segundo paso del acceso: código de 6 dígitos (TOTP) para Supervisor, Auditor y Administrador.

    POST /auth/login           → {"requiere_2fa": true, "configurado": …, "desafio": …, "usuario": …}
    POST /auth/2fa/configurar  → secreto, enlace y QR para la aplicación autenticadora (solo la primera vez)
    POST /auth/2fa/activar     → confirma el primer código y abre la sesión
    POST /auth/2fa/verificar   → código de cada día; abre la sesión
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from .. import auditoria, db, doble_factor, qr, sesiones, totp, usuarios
from .errores import ErrorNegocio

router = APIRouter()

MENSAJE_CADUCADO = "La verificación ha caducado. Vuelve a iniciar sesión."
MENSAJE_BLOQUEO = "Demasiados intentos fallidos. Vuelve a iniciar sesión más tarde."


class PeticionDesafio(BaseModel):
    desafio: str = Field(min_length=1, max_length=200)


class PeticionCodigo(PeticionDesafio):
    codigo: str = Field(min_length=1, max_length=12)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


def _desafio(conn, token: str) -> dict:
    desafio = doble_factor.desafio_abierto(conn, token)
    if desafio is None:
        raise ErrorNegocio(401, MENSAJE_CADUCADO)
    persona = doble_factor.usuario(conn, desafio["usuario_id"])
    if persona is None or persona["estado"] != "activo" or persona["bloqueado"]:
        raise ErrorNegocio(423, MENSAJE_BLOQUEO)
    desafio["correo"], desafio["rol"] = persona["correo"], persona["rol"]
    return desafio


@router.post("/auth/2fa/configurar")
def configurar(datos: PeticionDesafio, request: Request):
    with db.conexion() as conn:
        desafio = _desafio(conn, datos.desafio)
        segundo = doble_factor.estado(conn, desafio["usuario_id"])
        if segundo and segundo["activo"]:
            raise ErrorNegocio(409, "El segundo factor ya está configurado: escribe el código de tu aplicación.")
        secreto = segundo["secreto"] if segundo else totp.nuevo_secreto()
        doble_factor.preparar_secreto(conn, desafio["usuario_id"], secreto)
        enlace = totp.uri(secreto, desafio["correo"])
        auditoria.registrar(conn, "2fa_configuracion_iniciada", "ok", actor_id=desafio["usuario_id"],
                            recurso="sesion", detalle={"ip": _ip(request)})
    return {"secreto": secreto, "uri": enlace, "qr_svg": qr.svg(enlace)}


def _comprobar(conn, desafio: dict, codigo: str, request: Request, activando: bool) -> dict:
    """Si el código es bueno abre la sesión; si no, cuenta el fallo (y a los 3 cierra el desafío)."""
    uid = desafio["usuario_id"]
    segundo = doble_factor.estado(conn, uid)
    if segundo is None or bool(segundo["activo"]) == activando:
        raise ErrorNegocio(409, "El segundo factor no está en el estado esperado. Vuelve a iniciar sesión.")

    paso = totp.verificar(segundo["secreto"], codigo, segundo["ultimo_paso"])
    if paso is None:
        bloqueada = usuarios.anotar_fallo(conn, uid)
        restantes = doble_factor.anotar_error(conn, desafio["id"])
        auditoria.registrar(conn, "2fa_fallido", "fallo", actor_id=uid, recurso="sesion",
                            detalle={"ip": _ip(request), "restantes": restantes})
        if restantes == 0:
            auditoria.registrar(conn, "2fa_desafio_agotado", "denegado", actor_id=uid, recurso="sesion",
                                detalle={"ip": _ip(request)})
        conn.commit()          # se guarda el fallo aunque se responda con error
        if bloqueada or restantes == 0:
            raise ErrorNegocio(423, MENSAJE_BLOQUEO)
        raise ErrorNegocio(401, f"Código incorrecto. Te quedan {restantes} "
                                f"{'intento' if restantes == 1 else 'intentos'}.")

    doble_factor.cerrar_desafio(conn, desafio["id"])
    doble_factor.anotar_paso(conn, uid, paso, activar=activando)
    usuarios.anotar_acceso(conn, uid)
    token, expira_en = sesiones.crear(conn, uid, desafio["rol"])
    auditoria.registrar(conn, "login", "ok", actor_id=uid, recurso="sesion",
                        detalle={"ip": _ip(request), "segundo_factor": True})
    return {"token": token, "expira_en": expira_en.isoformat(), "usuario": usuarios.perfil(conn, uid)}


@router.post("/auth/2fa/verificar")
def verificar(datos: PeticionCodigo, request: Request):
    with db.conexion() as conn:
        return _comprobar(conn, _desafio(conn, datos.desafio), datos.codigo, request, activando=False)


@router.post("/auth/2fa/activar")
def activar(datos: PeticionCodigo, request: Request):
    with db.conexion() as conn:
        return _comprobar(conn, _desafio(conn, datos.desafio), datos.codigo, request, activando=True)
