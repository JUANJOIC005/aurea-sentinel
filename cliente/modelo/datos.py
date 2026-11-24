"""Cómo se muestran los datos de la central: cifras en español (coma decimal, punto de millar) y fechas locales."""
from datetime import datetime, timezone

ESTADOS = {"normal": "En rango", "aviso": "Aviso", "alarma": "Alarma", "sin_datos": "Sin datos"}
NIVELES = {"aviso": "Aviso", "alarma": "Alarma"}


def numero(valor: float | None, decimales: int | None = None) -> str:
    """325.6 → «325,6» · 22140 → «22.140» · 2.5 → «2,50». Sin dato: «—»."""
    if valor is None:
        return "—"
    if decimales is None:
        magnitud = abs(valor)
        decimales = 0 if magnitud >= 10_000 else 1 if magnitud >= 10 else 2
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ".")


def con_signo(valor: float | None, decimales: int | None = None) -> str:
    if valor is None:
        return "—"
    return ("+" if valor > 0 else "") + numero(valor, decimales)


def fecha(texto: str | None) -> datetime | None:
    """«2026-11-02T10:00:00Z» (UTC) → fecha con la zona horaria de este equipo."""
    if not texto:
        return None
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone()


def hora(texto: str | None) -> str:
    f = fecha(texto)
    return f"{f:%H:%M:%S}" if f else "—"


def fecha_hora(texto: str | None) -> str:
    f = fecha(texto)
    return f"{f:%d/%m/%Y %H:%M}" if f else "—"


def a_utc_iso(momento: datetime) -> str:
    """Una fecha local (o ya en UTC) → «2026-11-02T10:00:00Z», que es lo que entiende el servidor."""
    if momento.tzinfo is None:
        momento = momento.astimezone()
    return momento.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
