"""Gráficas dibujadas a mano con QPainter (sin librerías extra): minigráfica, barra de umbrales y serie temporal."""
from dataclasses import dataclass, field
from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from ..modelo import datos
from . import estilos

COLOR_BARRA = "#DCE6F3"
COLOR_BARRA_AVISO = "#F1D58A"
COLOR_BARRA_ALARMA = "#E3A0A0"


class Sparkline(QWidget):
    """Tendencia de la última hora: una línea sin ejes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._valores: list[float] = []
        self._color = QColor(estilos.ACERO)
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def poner(self, valores: list[float], color: str = estilos.ACERO) -> None:
        self._valores, self._color = list(valores), QColor(color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 4, -1, -4)
        if len(self._valores) < 2:
            p.setPen(QPen(QColor(estilos.PLATA), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(r.left(), r.center().y()), QPointF(r.right(), r.center().y()))
            return
        bajo, alto = min(self._valores), max(self._valores)
        rango = (alto - bajo) or 1.0
        ruta = QPainterPath()
        for i, v in enumerate(self._valores):
            punto = QPointF(r.left() + r.width() * i / (len(self._valores) - 1),
                            r.bottom() - r.height() * (v - bajo) / rango if alto != bajo else r.center().y())
            ruta.moveTo(punto) if i == 0 else ruta.lineTo(punto)
        lapiz = QPen(self._color, 1.5)
        lapiz.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(lapiz)
        p.drawPath(ruta)


class BarraUmbrales(QWidget):
    """Barra con las zonas normal, aviso y alarma de un sensor y una marca en el valor actual."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._umbrales: dict = {}
        self._valor: float | None = None
        self.setFixedHeight(16)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def poner(self, umbrales: dict, valor: float | None) -> None:
        self._umbrales, self._valor = dict(umbrales), valor
        self.update()

    def extremos(self) -> tuple[float, float] | None:
        """Rango que cubre la barra: de los umbrales (y el valor) con un margen a cada lado."""
        puntos = [v for v in self._umbrales.values() if v is not None]
        if self._valor is not None:
            puntos.append(self._valor)
        if not puntos:
            return None
        bajo, alto = min(puntos), max(puntos)
        margen = ((alto - bajo) or abs(alto) or 1.0) * 0.15
        return bajo - margen, alto + margen

    def paintEvent(self, _):
        extremos = self.extremos()
        if extremos is None:
            return
        bajo, alto = extremos
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        barra = QRectF(0, 5, self.width(), 6)

        def x(v: float) -> float:
            return barra.left() + barra.width() * (min(max(v, bajo), alto) - bajo) / (alto - bajo)

        u = self._umbrales
        zonas = [(bajo, u.get("alarma_bajo"), COLOR_BARRA_ALARMA), (u.get("alarma_bajo"), u.get("aviso_bajo"),
                                                                    COLOR_BARRA_AVISO),
                 (u.get("aviso_bajo"), u.get("aviso_alto"), COLOR_BARRA),
                 (u.get("aviso_alto"), u.get("alarma_alto"), COLOR_BARRA_AVISO),
                 (u.get("alarma_alto"), alto, COLOR_BARRA_ALARMA)]
        # Un umbral que no existe se salta: la zona se une con la contigua.
        p.setPen(Qt.PenStyle.NoPen)
        p.setClipPath(self._redondeada(barra))
        p.fillRect(barra, QColor(COLOR_BARRA))
        izquierda = bajo
        for inicio, fin, color in zonas:
            if inicio is None and fin is None:
                continue
            a = x(izquierda if inicio is None else inicio)
            b = x(alto if fin is None else fin)
            if color != COLOR_BARRA and b > a:
                p.fillRect(QRectF(a, barra.top(), b - a, barra.height()), QColor(color))
        p.setClipping(False)
        if self._valor is not None:
            p.setPen(QPen(QColor(estilos.AZUL), 2.2))
            p.drawLine(QPointF(x(self._valor), 1), QPointF(x(self._valor), self.height() - 1))

    @staticmethod
    def _redondeada(r: QRectF) -> QPainterPath:
        ruta = QPainterPath()
        ruta.addRoundedRect(r, 3, 3)
        return ruta


@dataclass
class Serie:
    nombre: str
    puntos: list[tuple[float, float]]            # (segundos desde 1970, valor)
    color: str = estilos.AZUL
    marcar_maximo: bool = False
    extra: dict = field(default_factory=dict)


class GraficaTemporal(QWidget):
    """Una o dos series en el tiempo, con las bandas de aviso y alarma de un sensor."""

    MARGEN = (58, 12, 16, 28)                    # izquierda, arriba, derecha, abajo

    def __init__(self, parent=None):
        super().__init__(parent)
        self._series: list[Serie] = []
        self._umbrales: dict = {}
        self._unidad = ""
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

    def poner(self, series: list[Serie], umbrales: dict | None = None, unidad: str = "") -> None:
        self._series = [s for s in series if s.puntos]
        self._umbrales, self._unidad = dict(umbrales or {}), unidad
        self.update()

    # ── Geometría ──
    def _zona(self) -> QRectF:
        i, a, d, b = self.MARGEN
        return QRectF(i, a, max(10, self.width() - i - d), max(10, self.height() - a - b))

    def _rangos(self) -> tuple[float, float, float, float] | None:
        if not self._series:
            return None
        xs = [x for s in self._series for x, _ in s.puntos]
        ys = [y for s in self._series for _, y in s.puntos]
        ys += [s.extra["maximo"][1] for s in self._series if "maximo" in s.extra]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        extension = (y1 - y0) or abs(y1) or 1.0
        for t in self._umbrales.values():                    # solo los umbrales cercanos a los datos
            if t is not None and y0 - 0.6 * extension <= t <= y1 + 0.6 * extension:
                y0, y1 = min(y0, t), max(y1, t)
        margen = ((y1 - y0) or 1.0) * 0.08
        return x0, (x1 if x1 > x0 else x0 + 1), y0 - margen, y1 + margen

    def _punto(self, zona: QRectF, rangos, x: float, y: float) -> QPointF:
        x0, x1, y0, y1 = rangos
        return QPointF(zona.left() + zona.width() * (x - x0) / (x1 - x0),
                       zona.bottom() - zona.height() * (y - y0) / (y1 - y0))

    # ── Dibujo ──
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        zona, rangos = self._zona(), self._rangos()
        fuente = QFont(self.font())
        fuente.setPixelSize(11)
        p.setFont(fuente)
        if rangos is None:
            p.setPen(QColor(estilos.TEXTO_SUAVE))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No hay lecturas en el periodo elegido")
            return
        x0, x1, y0, y1 = rangos
        self._bandas(p, zona, rangos)
        self._ejes(p, zona, rangos)
        for serie in self._series:
            ruta = QPainterPath()
            for i, (x, y) in enumerate(serie.puntos):
                punto = self._punto(zona, rangos, x, y)
                ruta.moveTo(punto) if i == 0 else ruta.lineTo(punto)
            lapiz = QPen(QColor(serie.color), 1.6)
            lapiz.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(lapiz)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(ruta)
        principal = self._series[0]
        if principal.marcar_maximo:
            x, y = principal.extra.get("maximo") or max(principal.puntos, key=lambda punto: punto[1])
            self._marca_maximo(p, zona, rangos, x, y)

    def _bandas(self, p: QPainter, zona: QRectF, rangos) -> None:
        _, _, y0, y1 = rangos
        u = self._umbrales

        def y_de(valor: float) -> float:
            return zona.bottom() - zona.height() * (min(max(valor, y0), y1) - y0) / (y1 - y0)

        p.setPen(Qt.PenStyle.NoPen)
        fondos = [(u.get("aviso_alto"), u.get("alarma_alto"), estilos.BANDA_AVISO),
                  (u.get("alarma_alto"), None, estilos.BANDA_ALARMA),
                  (u.get("alarma_bajo"), u.get("aviso_bajo"), estilos.BANDA_AVISO),
                  (None, u.get("alarma_bajo"), estilos.BANDA_ALARMA)]
        for bajo, alto, color in fondos:
            limite_inferior = y0 if bajo is None else bajo
            limite_superior = y1 if alto is None else alto
            if (bajo is None and alto is None) or limite_superior <= y0 or limite_inferior >= y1:
                continue
            arriba, abajo = y_de(limite_superior), y_de(limite_inferior)
            p.fillRect(QRectF(zona.left(), arriba, zona.width(), abajo - arriba), QColor(color))
        for etiqueta, clave, color in (("aviso", "aviso_alto", estilos.AVISO), ("alarma", "alarma_alto", estilos.ALARMA),
                                       ("aviso", "aviso_bajo", estilos.AVISO), ("alarma", "alarma_bajo", estilos.ALARMA)):
            valor = u.get(clave)
            if valor is None or not (y0 <= valor <= y1):
                continue
            p.setPen(QPen(QColor(color), 1, Qt.PenStyle.DashLine))
            y = y_de(valor)
            p.drawLine(QPointF(zona.left(), y), QPointF(zona.right(), y))
            p.setPen(QColor(color))
            p.drawText(QRectF(zona.right() - 150, y - 14, 146, 13), Qt.AlignmentFlag.AlignRight,
                       f"{etiqueta} {datos.numero(valor)} {self._unidad}")

    def _ejes(self, p: QPainter, zona: QRectF, rangos) -> None:
        x0, x1, y0, y1 = rangos
        p.setPen(QPen(QColor(estilos.PLATA), 1))
        p.drawRect(zona)
        p.setPen(QColor(estilos.TEXTO_SUAVE))
        for i in range(5):
            valor = y0 + (y1 - y0) * i / 4
            y = zona.bottom() - zona.height() * i / 4
            p.drawText(QRectF(0, y - 7, zona.left() - 6, 14), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       datos.numero(valor))
        dias = (x1 - x0) >= 36 * 3600
        marcas = 6
        for i in range(marcas):
            x = x0 + (x1 - x0) * i / (marcas - 1)
            posicion = zona.left() + zona.width() * i / (marcas - 1)
            texto = datetime.fromtimestamp(x).strftime("%d/%m" if dias else "%H:%M")
            alineacion = (Qt.AlignmentFlag.AlignLeft if i == 0 else
                          Qt.AlignmentFlag.AlignRight if i == marcas - 1 else Qt.AlignmentFlag.AlignHCenter)
            ancho = 60
            inicio = posicion if i == 0 else posicion - ancho if i == marcas - 1 else posicion - ancho / 2
            p.drawText(QRectF(inicio, zona.bottom() + 5, ancho, 14), alineacion, texto)

    def _marca_maximo(self, p: QPainter, zona: QRectF, rangos, x: float, y: float) -> None:
        punto = self._punto(zona, rangos, x, y)
        p.setPen(QPen(QColor(estilos.AVISO), 1.6))
        p.setBrush(QColor(estilos.BLANCO))
        p.drawEllipse(punto, 4, 4)
        texto = f"máx {datos.numero(y)} {self._unidad} · {datetime.fromtimestamp(x):%d/%m %H:%M}"
        ancho = p.fontMetrics().horizontalAdvance(texto) + 8
        izquierda = min(max(punto.x() - ancho / 2, zona.left()), zona.right() - ancho)
        p.setPen(QColor(estilos.AVISO))
        p.drawText(QRectF(izquierda, max(zona.top(), punto.y() - 22), ancho, 14), Qt.AlignmentFlag.AlignCenter, texto)

    # ── Ratón: valor más cercano ──
    def mouseMoveEvent(self, evento):
        rangos, zona = self._rangos(), self._zona()
        if rangos is None or not zona.contains(evento.position()):
            QToolTip.hideText()
            return
        x0, x1, _, _ = rangos
        x = x0 + (x1 - x0) * (evento.position().x() - zona.left()) / zona.width()
        lineas = []
        for serie in self._series:
            cercano = min(serie.puntos, key=lambda punto: abs(punto[0] - x))
            lineas.append(f"{serie.nombre}: {datos.numero(cercano[1])} {self._unidad} · "
                          f"{datetime.fromtimestamp(cercano[0]):%d/%m/%Y %H:%M}")
        QToolTip.showText(evento.globalPosition().toPoint(), "\n".join(lineas), self)
