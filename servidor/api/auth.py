"""Login, registro y sesión."""
from fastapi import APIRouter, Depends, Header, Request

from .. import auditoria, config, db, seguridad, sesiones, usuarios
from .errores import ErrorNegocio
from .esquemas import PeticionLogin, PeticionRegistro

router = APIRouter()

# Siempre el mismo mensaje: no revela si el correo existe, si la contraseña falló o si la cuenta está bloqueada.
MENSAJE_LOGIN = (
    f"Correo o contraseña incorrectos, o cuenta no disponible. "
    f"Tras {config.INTENTOS_MAXIMOS} intentos fallidos la cuenta se bloquea {config.BLOQUEO_MINUTOS} minutos."
)
MENSAJE_REGISTRO = "Solicitud recibida. Tu cuenta queda pendiente hasta que un administrador la apruebe."


def sesion_actual(authorization: str | None = Header(default=None)) -> dict:
    """Comprueba el token de la cabecera Authorization: Bearer <token>."""
    esquema, _, token = (authorization or "").partition(" ")
    if esquema.lower() != "bearer" or not token:
        raise ErrorNegocio(401, "Sesión no válida o caducada.")
    with db.conexion() as conn:
        datos = sesiones.validar(conn, token.strip())
    if datos is None:
        raise ErrorNegocio(401, "Sesión no válida o caducada.")
    datos["token"] = token.strip()
    return datos


def _fallo_login(conn, motivo: str, usuario_id: int | None, ip: str, resultado: str = "fallo"):
    auditoria.registrar(conn, "login", resultado, actor_id=usuario_id, recurso="sesion",
                        detalle={"motivo": motivo, "ip": ip})


@router.post("/auth/login")
def login(datos: PeticionLogin, request: Request):
    ip = request.client.host if request.client else "desconocida"
    with db.conexion() as conn:
        usuario = usuarios.por_correo(conn, datos.correo)

        if usuario is None:
            seguridad.verificar_ficticio(datos.password)
            _fallo_login(conn, "usuario_desconocido", None, ip)
            conn.commit()
            raise ErrorNegocio(401, MENSAJE_LOGIN)

        correcta = seguridad.verificar(usuario["password_hash"], datos.password)

        if usuario["bloqueado"]:
            _fallo_login(conn, "cuenta_bloqueada", usuario["id"], ip, "denegado")
            conn.commit()
            raise ErrorNegocio(401, MENSAJE_LOGIN)

        if not correcta:
            bloqueada = usuarios.anotar_fallo(conn, usuario["id"])
            _fallo_login(conn, "cuenta_bloqueada_por_intentos" if bloqueada else "contrasena_incorrecta",
                         usuario["id"], ip)
            conn.commit()
            raise ErrorNegocio(401, MENSAJE_LOGIN)

        if usuario["estado"] != "activo":
            _fallo_login(conn, f"cuenta_{usuario['estado']}", usuario["id"], ip, "denegado")
            conn.commit()
            raise ErrorNegocio(401, MENSAJE_LOGIN)

        usuarios.anotar_acceso(conn, usuario["id"])
        token, expira_en = sesiones.crear(conn, usuario["id"], usuario["rol"])
        auditoria.registrar(conn, "login", "ok", actor_id=usuario["id"], recurso="sesion", detalle={"ip": ip})
        perfil = usuarios.perfil(conn, usuario["id"])

    return {"token": token, "expira_en": expira_en.isoformat(), "usuario": perfil}


@router.post("/auth/registro", status_code=201)
def registro(datos: PeticionRegistro, request: Request):
    ip = request.client.host if request.client else "desconocida"
    problemas = seguridad.comprobar_politica(datos.password)
    if problemas:
        raise ErrorNegocio(422, "La contraseña " + " y ".join(problemas) + ".")

    with db.conexion() as conn:
        supervisor_id = None
        area = datos.area
        if datos.rol == "supervisor":
            if not area or not usuarios.area_existe(conn, area):
                raise ErrorNegocio(422, "Indica el área del supervisor.")
        elif datos.rol == "tecnico":
            supervisor = usuarios.supervisor_activo(conn, datos.supervisor_id) if datos.supervisor_id else None
            if supervisor is None:
                raise ErrorNegocio(422, "Un técnico debe indicar su supervisor responsable.")
            supervisor_id = supervisor["id"]
            area = None  # el técnico hereda el área de su supervisor
        else:
            area = None

        nuevo_id = usuarios.crear_pendiente(
            conn, datos.nombre, datos.correo, seguridad.hashear(datos.password),
            datos.rol, area, supervisor_id, datos.motivo,
        )
        # Si el correo ya existía se responde igual, para no revelarlo.
        auditoria.registrar(
            conn, "registro_solicitado" if nuevo_id else "registro_duplicado", "ok" if nuevo_id else "fallo",
            actor_id=nuevo_id, recurso="usuario", detalle={"rol": datos.rol, "ip": ip},
        )
    return {"mensaje": MENSAJE_REGISTRO}


@router.get("/auth/yo")
def yo(sesion: dict = Depends(sesion_actual)):
    return {"usuario": sesion["usuario"], "expira_en": sesion["expira_en"].isoformat()}


@router.post("/auth/logout", status_code=204)
def logout(sesion: dict = Depends(sesion_actual)):
    with db.conexion() as conn:
        sesiones.cerrar(conn, sesion["token"])
        auditoria.registrar(conn, "logout", "ok", actor_id=sesion["usuario"]["id"], recurso="sesion")
