"""Sesiones: el cliente recibe un token; en la base de datos solo se guarda su hash."""
from . import config, db, seguridad, usuarios


def crear(conn, usuario_id: int, rol: str):
    """Crea una sesión con la caducidad del rol. Devuelve (token, expira_en)."""
    token = seguridad.nuevo_token()
    fila = conn.execute(
        "INSERT INTO sesion (usuario_id, token_hash, expira_en)"
        " VALUES (?, ?, datetime('now', ?)) RETURNING expira_en",
        (usuario_id, seguridad.hash_token(token), f"+{config.SESION_MINUTOS[rol]} minutes"),
    ).fetchone()
    return token, db.a_fecha(fila["expira_en"])


def validar(conn, token: str) -> dict | None:
    """Devuelve el perfil del usuario y la caducidad si el token es válido, o None."""
    fila = conn.execute(
        "SELECT s.usuario_id, s.expira_en FROM sesion s JOIN usuario u ON u.id = s.usuario_id"
        " WHERE s.token_hash = ? AND s.cerrada_en IS NULL AND s.expira_en > datetime('now')"
        "   AND u.estado = 'activo'",
        (seguridad.hash_token(token),),
    ).fetchone()
    if fila is None:
        return None
    perfil = usuarios.perfil(conn, fila["usuario_id"])
    return {"usuario": perfil, "expira_en": db.a_fecha(fila["expira_en"])}


def cerrar(conn, token: str) -> None:
    conn.execute(
        "UPDATE sesion SET cerrada_en = datetime('now') WHERE token_hash = ? AND cerrada_en IS NULL",
        (seguridad.hash_token(token),),
    )
