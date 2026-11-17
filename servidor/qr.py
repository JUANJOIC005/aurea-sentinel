"""Código QR como imagen SVG (con la librería `segno`, que es Python puro y no necesita nada más)."""
import io

import segno


def svg(texto: str, color: str = "#0B2D5B") -> str:
    qr = segno.make(texto, error="m")
    salida = io.BytesIO()
    qr.save(salida, kind="svg", xmldecl=False, nl=False, scale=5, border=2, dark=color, light="#FFFFFF")
    return salida.getvalue().decode("utf-8")
