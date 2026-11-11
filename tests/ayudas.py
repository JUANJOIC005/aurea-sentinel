"""Piezas comunes de las pruebas de permisos, datos y doble factor (Sprint 2)."""
from datetime import datetime, timedelta, timezone

from servidor import totp

FORMATO = "%Y-%m-%d %H:%M:%S"


def ahora() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def sembrar(conexion, tag: str, valores: list[float], paso_s: int = 300, fin: datetime | None = None) -> None:
    """Guarda las lecturas de un sensor: la última en `fin` (ahora, por defecto) y una cada `paso_s` hacia atrás."""
    fin = fin or ahora()
    sensor = conexion.execute("SELECT id FROM sensor WHERE tag = ?", (tag,)).fetchone()["id"]
    n = len(valores)
    conexion.executemany(
        "INSERT INTO lectura (sensor_id, instante, valor) VALUES (?, ?, ?)",
        [(sensor, (fin - timedelta(seconds=paso_s * (n - 1 - i))).strftime(FORMATO), v)
         for i, v in enumerate(valores)])
    conexion.commit()


def sembrar_nominal(conexion, lecturas: int = 24, paso_s: int = 300) -> None:
    """Lecturas en el valor nominal de los 36 sensores (dos horas con el paso por defecto)."""
    for s in conexion.execute("SELECT tag, valor_nominal FROM sensor").fetchall():
        sembrar(conexion, s["tag"], [s["valor_nominal"]] * lecturas, paso_s)


def asignar(conexion, tecnico_id: int, tag: str, por: int | None = None) -> None:
    conexion.execute("INSERT OR IGNORE INTO asignacion_sensor (tecnico_id, sensor_id, asignado_por)"
                     " VALUES (?, (SELECT id FROM sensor WHERE tag = ?), ?)", (tecnico_id, tag, por))
    conexion.commit()


def abrir_alarma(conexion, tag: str, nivel: str = "aviso", valor: float = 0.0, estado: str = "abierta",
                 hace_minutos: int = 10) -> None:
    abierta = (ahora() - timedelta(minutes=hace_minutos)).strftime(FORMATO)
    cerrada = None if estado != "cerrada" else ahora().strftime(FORMATO)
    conexion.execute("INSERT INTO alarma (sensor_id, nivel, valor, abierta_en, estado, cerrada_en)"
                     " VALUES ((SELECT id FROM sensor WHERE tag = ?), ?, ?, ?, ?, ?)",
                     (tag, nivel, valor, abierta, estado, cerrada))
    conexion.commit()


def activar_2fa(conexion, usuario_id: int, secreto: str | None = None) -> str:
    """Deja el segundo factor de una persona ya configurado y devuelve su secreto."""
    secreto = secreto or totp.nuevo_secreto()
    conexion.execute("INSERT OR REPLACE INTO segundo_factor (usuario_id, secreto, activo) VALUES (?, ?, 1)",
                     (usuario_id, secreto))
    conexion.commit()
    return secreto


def codigo_de(secreto: str, desplazamiento: int = 0) -> str:
    return totp.codigo(secreto, totp.paso_actual() + desplazamiento)
