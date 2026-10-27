"""Iconos de línea (estilo de los mockups), dibujados como SVG y teñidos del color que se pida."""
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

RECURSOS = Path(__file__).resolve().parent.parent / "recursos"

_TRAZOS = {
    "panel": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/>'
             '<rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "grafica": '<path d="M3 3v18h18"/><path d="M7 15l4-5 3 3 5-7"/>',
    "equipo": '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/>'
              '<circle cx="17" cy="9" r="2.4"/><path d="M16.5 14.2c2.6.3 4.5 2.5 4.5 5.3"/>',
    "campana": '<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 21a2 2 0 0 0 4 0"/>',
    "informe": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/><path d="M9 12h6M9 16h6"/>',
    "sensor": '<circle cx="12" cy="12" r="3"/><path d="M5.6 5.6a9 9 0 0 0 0 12.8M18.4 5.6a9 9 0 0 1 0 12.8"/>',
    "escudo": '<path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    "candado": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "salir": '<path d="M10 4H5v16h5"/><path d="M15 8l4 4-4 4M19 12H9"/>',
    "ojo": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "ojo_cerrado": '<path d="M3 3l18 18"/><path d="M10.6 5.1A10 10 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3.2 4"/>'
                   '<path d="M6.5 6.6C3.8 8.4 2 12 2 12s3.6 7 10 7a10 10 0 0 0 4.2-.9"/>',
    "aviso": '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "reloj": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
}


def pixmap(nombre: str, color: str, tam: int = 18, escala: float = 2.0) -> QPixmap:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{_TRAZOS[nombre]}</svg>'
    )
    px = QPixmap(int(tam * escala), int(tam * escala))
    px.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(px)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(pintor)
    pintor.end()
    px.setDevicePixelRatio(escala)
    return px


def icono(nombre: str, color: str, tam: int = 18) -> QIcon:
    return QIcon(pixmap(nombre, color, tam))


def _imagen(nombre: str, ancho: int, alto: int, escala: float = 2.0) -> QPixmap:
    """Imagen de marca escalada a caber en ancho×alto (px lógicos) con buena nitidez."""
    original = QPixmap(str(RECURSOS / nombre))
    px = original.scaled(int(ancho * escala), int(alto * escala), Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    px.setDevicePixelRatio(escala)
    return px


def isotipo(alto: int) -> QPixmap:
    """Solo la «A» del logotipo de AUREA AUDIT (icono de ventana y menú lateral)."""
    return _imagen("aurea_isotipo.png", alto * 2, alto)


def logo(ancho: int, alto: int) -> QPixmap:
    """Logotipo completo de AUREA AUDIT con su nombre y lema (paneles azules de acceso)."""
    return _imagen("aurea_logo.png", ancho, alto)
