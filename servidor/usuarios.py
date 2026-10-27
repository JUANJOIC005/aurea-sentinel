"""Consultas sobre usuarios, áreas y supervisores."""
import sqlite3

from . import config


def por_correo(conn, correo: str) -> dict | None:
    return conn.execute(
        "SELECT u.*, r.codigo AS rol,"
        "       (u.bloqueado_hasta IS NOT NULL AND u.bloqueado_hasta > datetime('now')) AS bloqueado"
        "  FROM usuario u JOIN rol r ON r.id = u.rol_id"
        " WHERE lower(u.correo) = lower(?)",
        (correo,),
    ).fetchone()


def perfil(conn, usuario_id: int) -> dict | None:
    """Datos que se envían al cliente: quién es, qué rol tiene y de qué área."""
    fila = conn.execute(
        "SELECT u.id, u.nombre, u.correo, r.codigo AS rol,"
        "       a.codigo AS area_codigo, a.nombre AS area_nombre,"
        "       s.id AS sup_id, s.nombre AS sup_nombre"
        "  FROM usuario u"
        "  JOIN rol r ON r.id = u.rol_id"
        "  LEFT JOIN area a ON a.id = u.area_id"
        "  LEFT JOIN usuario s ON s.id = u.supervisor_id"
        " WHERE u.id = ?",
        (usuario_id,),
    ).fetchone()
    if fila is None:
        return None
    return {
        "id": fila["id"],
        "nombre": fila["nombre"],
        "correo": fila["correo"],
        "rol": fila["rol"],
        "area": {"codigo": fila["area_codigo"], "nombre": fila["area_nombre"]} if fila["area_codigo"] else None,
        "supervisor": {"id": fila["sup_id"], "nombre": fila["sup_nombre"]} if fila["sup_id"] else None,
    }


def anotar_fallo(conn, usuario_id: int) -> bool:
    """Suma un intento fallido. Al llegar al máximo bloquea la cuenta y devuelve True."""
    fila = conn.execute(
        "UPDATE usuario SET"
        "  bloqueado_hasta = CASE WHEN intentos_fallidos + 1 >= :max"
        "                         THEN datetime('now', :espera) ELSE bloqueado_hasta END,"
        "  intentos_fallidos = CASE WHEN intentos_fallidos + 1 >= :max"
        "                           THEN 0 ELSE intentos_fallidos + 1 END"
        " WHERE id = :id"
        " RETURNING (bloqueado_hasta IS NOT NULL AND bloqueado_hasta > datetime('now')) AS bloqueada",
        {"max": config.INTENTOS_MAXIMOS, "espera": f"+{config.BLOQUEO_MINUTOS} minutes", "id": usuario_id},
    ).fetchone()
    return bool(fila and fila["bloqueada"])


def anotar_acceso(conn, usuario_id: int) -> None:
    conn.execute(
        "UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = NULL, ultimo_acceso = datetime('now')"
        " WHERE id = ?",
        (usuario_id,),
    )


def crear_pendiente(conn, nombre: str, correo: str, password_hash: str, rol: str,
                    area_codigo: str | None, supervisor_id: int | None, motivo: str | None) -> int | None:
    """Crea una cuenta en estado «pendiente». Devuelve su id, o None si el correo ya existe."""
    try:
        fila = conn.execute(
            "INSERT INTO usuario (nombre, correo, password_hash, rol_id, area_id, supervisor_id, motivo)"
            " VALUES (?, ?, ?,"
            "         (SELECT id FROM rol WHERE codigo = ?),"
            "         (SELECT id FROM area WHERE codigo = ?),"
            "         ?, ?)"
            " RETURNING id",
            (nombre.strip(), correo.strip(), password_hash, rol, area_codigo, supervisor_id, motivo),
        ).fetchone()
    except sqlite3.IntegrityError as error:
        if "UNIQUE" not in str(error):
            raise
        return None   # el correo ya existía
    return fila["id"]


def supervisor_activo(conn, usuario_id: int) -> dict | None:
    return conn.execute(
        "SELECT u.id, u.area_id FROM usuario u JOIN rol r ON r.id = u.rol_id"
        " WHERE u.id = ? AND r.codigo = 'supervisor' AND u.estado = 'activo'",
        (usuario_id,),
    ).fetchone()


def area_existe(conn, codigo: str) -> bool:
    return conn.execute("SELECT 1 FROM area WHERE codigo = ?", (codigo,)).fetchone() is not None


def areas(conn) -> list[dict]:
    return conn.execute("SELECT codigo, nombre FROM area ORDER BY id").fetchall()


def supervisores_de_area(conn, codigo: str) -> list[dict]:
    return conn.execute(
        "SELECT u.id, u.nombre FROM usuario u"
        "  JOIN rol r ON r.id = u.rol_id JOIN area a ON a.id = u.area_id"
        " WHERE r.codigo = 'supervisor' AND u.estado = 'activo' AND a.codigo = ?"
        " ORDER BY u.nombre",
        (codigo,),
    ).fetchall()
