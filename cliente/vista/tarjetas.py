"""Indicadores (KPI) y tarjetas de sensor del panel del Supervisor (mockup SV-2 y ventana 04)."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..modelo import datos
from . import estilos
from .componentes import etiqueta
from .graficas import BarraUmbrales, Sparkline


class Indicador(QFrame):
    """Etiqueta, cifra grande y contexto, con una franja lateral del color de su significado."""

    def __init__(self, titulo: str, color: str = estilos.AZUL, parent=None):
        super().__init__(parent)
        self.setObjectName("Indicador")
        self._color = color
        self.setStyleSheet(
            f"#Indicador {{ background: {estilos.BLANCO}; border: 1px solid {estilos.PLATA};"
            f" border-left: 4px solid {color}; border-radius: 10px; }}")
        caja = QVBoxLayout(self)
        caja.setContentsMargins(16, 12, 14, 12)
        caja.setSpacing(2)
        caja.addWidget(etiqueta(titulo.upper(), "Mayusculas"))
        self.cifra = QLabel("—")
        self.cifra.setTextFormat(Qt.TextFormat.RichText)
        self.cifra.setStyleSheet(f"font-family: {estilos.FUENTE_TITULOS}; font-size: 28px; font-weight: 700;"
                                 f" color: {estilos.AZUL};")
        self.contexto = etiqueta("", "Suave")
        self.contexto.setWordWrap(True)
        caja.addWidget(self.cifra)
        caja.addWidget(self.contexto)

    def poner(self, cifra: str, contexto: str, color_contexto: str | None = None) -> None:
        self.cifra.setText(cifra)
        self.contexto.setText(contexto)
        self.contexto.setStyleSheet(f"font-size: 13px; color: {color_contexto or estilos.TEXTO_SUAVE};")


class TarjetaSensor(QFrame):
    """Tag, magnitud, valor, estado en texto, tendencia de 1 h, barra de umbrales y hora de la última lectura."""
    elegido = Signal(str)          # tag del sensor, para abrir su histórico

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TarjetaSensor")
        self.tag = ""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(210)
        caja = QVBoxLayout(self)
        caja.setContentsMargins(14, 12, 14, 12)
        caja.setSpacing(3)

        arriba = QHBoxLayout()
        self.etiqueta_tag = QLabel()
        self.etiqueta_tag.setStyleSheet(f"font-family: {estilos.FUENTE_MONO}; font-size: 11px; font-weight: 700;"
                                        f" color: {estilos.ACERO};")
        self.pildora = QLabel()
        arriba.addWidget(self.etiqueta_tag)
        arriba.addStretch(1)
        arriba.addWidget(self.pildora)
        caja.addLayout(arriba)

        self.nombre = etiqueta("", "Suave")
        self.nombre.setWordWrap(True)
        self.nombre.setMinimumHeight(32)
        self.nombre.setAlignment(Qt.AlignmentFlag.AlignTop)
        caja.addWidget(self.nombre)

        self.valor = QLabel("—")
        self.valor.setTextFormat(Qt.TextFormat.RichText)
        caja.addWidget(self.valor)
        self.grafica = Sparkline()
        caja.addWidget(self.grafica)
        self.barra = BarraUmbrales()
        caja.addWidget(self.barra)

        limites = QHBoxLayout()
        self.limite_bajo = etiqueta("", "Suave")
        self.limite_alto = etiqueta("", "Suave")
        for lbl in (self.limite_bajo, self.limite_alto):
            lbl.setStyleSheet("font-size: 10px; color: #7A889C;")
        limites.addWidget(self.limite_bajo)
        limites.addStretch(1)
        limites.addWidget(self.limite_alto)
        caja.addLayout(limites)

        self.pie = QLabel()
        self.pie.setTextFormat(Qt.TextFormat.RichText)
        self.pie.setWordWrap(True)
        self.pie.setStyleSheet("font-size: 10px; color: #7A889C;")
        caja.addWidget(self.pie)
        self._borde(estilos.PLATA)

    def _borde(self, color: str) -> None:
        self.setStyleSheet(f"#TarjetaSensor {{ background: {estilos.BLANCO}; border: 1px solid {color};"
                           f" border-radius: 10px; }}")

    def poner(self, t: dict) -> None:
        """`t` es una tarjeta de /lecturas/ultimas."""
        self.tag = t["tag"]
        estado = t["estado"]
        color = estilos.COLOR_ESTADO[estado]
        self.etiqueta_tag.setText(t["tag"])
        self.nombre.setText(t["nombre"])
        self.pildora.setText(f"● {datos.ESTADOS[estado]}")          # el color nunca va solo: siempre con texto
        self.pildora.setStyleSheet(f"background: {estilos.FONDO_ESTADO[estado]}; color: {color}; font-size: 11px;"
                                   f" font-weight: 700; border-radius: 9px; padding: 2px 9px;")
        self.valor.setText(f"<span style='font-family:{estilos.FUENTE_TITULOS}; font-size:28px; font-weight:700;"
                           f" color:{estilos.AZUL}'>{datos.numero(t['valor'])}</span>"
                           f" <span style='font-size:12px; color:{estilos.TEXTO_SUAVE}'>{t['unidad']}</span>")
        self.grafica.poner(t["serie"], color if estado in ("aviso", "alarma") else estilos.ACERO)
        self.barra.poner(t["umbrales"], t["valor"])
        u = t["umbrales"]
        self.limite_bajo.setText(f"aviso {datos.numero(u['aviso_bajo'])}" if u["aviso_bajo"] is not None else "")
        self.limite_alto.setText(f"alarma {datos.numero(u['alarma_alto'])} {t['unidad']}"
                                 if u["alarma_alto"] is not None else "")
        self.pie.setText(self._texto_pie(t))
        self._borde(color if estado in ("aviso", "alarma") else estilos.PLATA)
        self.setToolTip(f"{t['tag']} · {t['nombre']}\nPulsa para ver su histórico")

    @staticmethod
    def _texto_pie(t: dict) -> str:
        if t["instante"] is None:
            return "Sin lecturas todavía"
        texto = f"Última lectura {datos.hora(t['instante'])}"
        if t["tendencia_1h"] is not None:
            flecha = "▲" if t["tendencia_1h"] > 0 else "▼" if t["tendencia_1h"] < 0 else "▬"
            texto += f" · tendencia 1 h {flecha} {datos.con_signo(t['tendencia_1h'])}"
        if t["edad_s"] is not None and t["edad_s"] >= 120:
            texto += f" · <span style='color:{estilos.AVISO}'>hace {t['edad_s'] // 60} min</span>"
        return texto

    def mousePressEvent(self, evento):
        if evento.button() == Qt.MouseButton.LeftButton and self.tag:
            self.elegido.emit(self.tag)
        super().mousePressEvent(evento)
