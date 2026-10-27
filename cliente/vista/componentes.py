"""Piezas visuales que se repiten en todas las ventanas."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget)

from . import estilos, iconos


class Avatar(QWidget):
    """Círculo con las iniciales, en el color del rol."""

    def __init__(self, iniciales: str, color: str, diametro: int = 34, parent=None):
        super().__init__(parent)
        self._iniciales, self._color = iniciales, QColor(color)
        self.setFixedSize(diametro, diametro)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(self.rect())
        fuente = QFont(self.font())
        fuente.setBold(True)
        fuente.setPixelSize(int(self.height() * 0.36))
        p.setFont(fuente)
        p.setPen(QColor(estilos.BLANCO))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._iniciales)


class InsigniaRol(QLabel):
    """Etiqueta con el nombre del rol, siempre del mismo color para ese rol."""

    def __init__(self, rol: str, texto: str, parent=None):
        super().__init__(texto, parent)
        self.setObjectName("InsigniaRol")
        self.setStyleSheet(
            f"background: {estilos.COLOR_ROL[rol]}; color: {estilos.BLANCO}; font-size: 11px;"
            f" font-weight: 700; border-radius: 9px; padding: 2px 9px;"
        )
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class PanelMarca(QWidget):
    """Panel azul de la izquierda del login y del registro (logo, mensaje y pie legal)."""

    def __init__(self, titulo: str, texto: str, puntos: list[str], pie: str, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(340)
        caja = QVBoxLayout(self)
        caja.setContentsMargins(42, 52, 42, 34)
        caja.setSpacing(0)

        logo = QLabel()
        logo.setFixedSize(112, 96)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(iconos.logo(100, 84))
        logo.setStyleSheet(f"background: {estilos.BLANCO}; border-radius: 12px;")
        caja.addWidget(logo, 0, Qt.AlignmentFlag.AlignLeft)
        caja.addStretch(2)

        self.titulo = QLabel(titulo)
        self.titulo.setWordWrap(True)
        self.titulo.setStyleSheet(
            f"color: {estilos.BLANCO}; font-family: {estilos.FUENTE_TITULOS}; font-size: 22px; font-weight: 700;")
        caja.addWidget(self.titulo)
        caja.addSpacing(10)
        descripcion = QLabel(texto)
        descripcion.setWordWrap(True)
        descripcion.setStyleSheet("color: #C9D6EA; font-size: 12px;")
        caja.addWidget(descripcion)
        caja.addSpacing(18)

        for punto in puntos:
            fila = QHBoxLayout()
            fila.setSpacing(8)
            marca = QLabel()
            marca.setPixmap(iconos.pixmap("check", estilos.CIAN, 14))
            marca.setFixedWidth(16)
            marca.setAlignment(Qt.AlignmentFlag.AlignTop)
            texto_punto = QLabel(punto)
            texto_punto.setWordWrap(True)
            texto_punto.setStyleSheet("color: #E3EAF5; font-size: 12px;")
            fila.addWidget(marca)
            fila.addWidget(texto_punto, 1)
            caja.addLayout(fila)
            caja.addSpacing(7)

        caja.addStretch(3)
        legal = QLabel(pie)
        legal.setWordWrap(True)
        legal.setStyleSheet("color: #9FB2D1; font-size: 10px;")
        caja.addWidget(legal)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(estilos.AZUL))
        # Círculos decorativos de la esquina inferior derecha
        lapiz = QPen(QColor(0, 194, 255, 70))
        lapiz.setWidthF(1.2)
        p.setPen(lapiz)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for radio in (150, 105):
            p.drawEllipse(QRectF(self.width() - radio, self.height() - radio * 1.1, radio * 2, radio * 2))


class IndicadorPasos(QWidget):
    """«1 Credenciales — 2 Código MFA». `actual` es 1 o 2; los pasos anteriores se marcan con ✓."""

    def __init__(self, pasos: list[str], actual: int = 1, parent=None):
        super().__init__(parent)
        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(6)
        for i, nombre in enumerate(pasos, start=1):
            circulo = QLabel("✓" if i < actual else str(i))
            circulo.setFixedSize(18, 18)
            circulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fondo = estilos.EN_RANGO if i < actual else (estilos.AZUL if i == actual else estilos.PLATA)
            color = estilos.BLANCO if i <= actual else estilos.TEXTO_SUAVE
            circulo.setStyleSheet(
                f"background: {fondo}; color: {color}; border-radius: 9px; font-size: 10px; font-weight: 700;")
            etiqueta = QLabel(nombre)
            etiqueta.setStyleSheet(f"font-size: 11px; color: {estilos.TEXTO_SUAVE};")
            fila.addWidget(circulo)
            fila.addWidget(etiqueta)
            if i < len(pasos):
                linea = QFrame()
                linea.setFixedSize(28, 1)
                linea.setStyleSheet(f"background: {estilos.PLATA};")
                fila.addWidget(linea)
        fila.addStretch(1)


class BarraEstado(QFrame):
    """Barra azul inferior: conexión a la izquierda, versión y caducidad a la derecha."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BarraEstado")
        self.setFixedHeight(22)
        fila = QHBoxLayout(self)
        fila.setContentsMargins(12, 0, 12, 0)
        self.izquierda = QLabel()
        self.derecha = QLabel()
        self.izquierda.setTextFormat(Qt.TextFormat.RichText)
        fila.addWidget(self.izquierda, 1)
        fila.addWidget(self.derecha, 0, Qt.AlignmentFlag.AlignRight)

    def poner(self, conectado: bool | None, izquierda_html: str, derecha: str) -> None:
        punto = {True: estilos.EN_RANGO, False: estilos.ALARMA, None: "#8A9BB5"}[conectado]
        self.izquierda.setText(f'<span style="color:{punto}">●</span>&nbsp;{izquierda_html}')
        self.derecha.setText(derecha)


def etiqueta(texto: str, nombre: str) -> QLabel:
    """QLabel con el estilo indicado (H1, H2, Suave, Etiqueta, Mayusculas…)."""
    lbl = QLabel(texto)
    lbl.setObjectName(nombre)
    return lbl
