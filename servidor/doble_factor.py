"""Consultas del segundo factor: secreto de cada persona y «desafíos» entre la contraseña y el código."""
from . import config, seguridad


def crear_desafio(conn, usuario_id: int) -> str:
    """Anula los desafíos abiertos de esa persona y crea uno nuevo. Devuelve el token (la base solo guarda su hash)."""
    conn.execute("UPDATE desafio_2fa SET usado = 1 WHERE usuario_id = ? AND usado = 0", (usuario_id,))
    token = seguridad.nuevo_token()
    conn.execute("INSERT INTO desafio_2fa (usuario_id, token_hash, expira_en) VALUES (?, ?, datetime('now', ?))",
                 (usuario_id, seguridad.hash_token(token), f"+{config.DESAFIO_MINUTOS} minutes"))
    return token


def desafio_abierto(conn, token: str) -> dict | None:
    return conn.execute(
        "SELECT id, usuario_id, intentos FROM desafio_2fa"
        " WHERE token_hash = ? AND usado = 0 AND expira_en > datetime('now')",
        (seguridad.hash_token(token or ""),)).fetchone()


def cerrar_desafio(conn, desafio_id: int) -> None:
    conn.execute("UPDATE desafio_2fa SET usado = 1 WHERE id = ?", (desafio_id,))


def anotar_error(conn, desafio_id: int) -> int:
    """Suma un código erróneo. Devuelve cuántos intentos quedan; al llegar a 0 el desafío se cierra."""
    fila = conn.execute("UPDATE desafio_2fa SET intentos = intentos + 1 WHERE id = ? RETURNING intentos",
                        (desafio_id,)).fetchone()
    restantes = max(0, config.CODIGOS_POR_DESAFIO - fila["intentos"])
    if restantes == 0:
        cerrar_desafio(conn, desafio_id)
    return restantes


def usuario(conn, usuario_id: int) -> dict | None:
    return conn.execute(
        "SELECT u.id, u.correo, u.estado, r.codigo AS rol,"
        "       (u.bloqueado_hasta IS NOT NULL AND u.bloqueado_hasta > datetime('now')) AS bloqueado"
        "  FROM usuario u JOIN rol r ON r.id = u.rol_id WHERE u.id = ?", (usuario_id,)).fetchone()


def estado(conn, usuario_id: int) -> dict | None:
    return conn.execute("SELECT secreto, activo, ultimo_paso FROM segundo_factor WHERE usuario_id = ?",
                        (usuario_id,)).fetchone()


def preparar_secreto(conn, usuario_id: int, secreto: str) -> None:
    """Guarda un secreto nuevo, todavía sin confirmar. Sustituye a otro sin confirmar de la misma persona."""
    conn.execute(
        "INSERT INTO segundo_factor (usuario_id, secreto) VALUES (?, ?)"
        " ON CONFLICT (usuario_id) DO UPDATE SET secreto = excluded.secreto, creado_en = datetime('now')"
        " WHERE activo = 0", (usuario_id, secreto))


def anotar_paso(conn, usuario_id: int, paso: int, activar: bool = False) -> None:
    conn.execute(
        "UPDATE segundo_factor SET ultimo_paso = ?,"
        "  activo = CASE WHEN ? THEN 1 ELSE activo END,"
        "  activado_en = CASE WHEN ? THEN datetime('now') ELSE activado_en END"
        " WHERE usuario_id = ?", (paso, int(activar), int(activar), usuario_id))
