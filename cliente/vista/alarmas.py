"""Supervisor · Alarmas del área: lista con filtro y botón «Reconocer» en las que siguen abiertas (T15 y T17)."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QTableWidgetItem, QVBoxLayout, QWidget

from ..modelo import datos
from . import estilos
from .componentes import etiqueta
from .equipo import tabla, tarjeta_simple
from .panel import FILTROS

COLUMNAS = ["SENSOR", "NIVEL", "VALOR", "ABIERTA", "ESTADO", ""]


class VistaAlarmas(QWidget):
    filtro = Signal(str)
    reconocer = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filtro = "activas"
        caja = QVBoxLayout(self)
        caja.setContentsMargins(0, 0, 8, 8)
        caja.setSpacing(14)
        self.error = QLabel()
        self.error.setObjectName("AvisoError")
        self.error.setWordWrap(True)
        self.error.hide()
        caja.addWidget(self.error)
        marco, interior = tarjeta_simple()
        cab = QHBoxLayout()
        cab.addWidget(etiqueta("Alarmas y avisos del área", "H2"))
        cab.addStretch(1)
        grupo = QButtonGroup(self)
        self.botones_filtro = {}
        for clave, texto in FILTROS:
            b = QPushButton(texto)
            b.setObjectName("Secundario")
            b.setCheckable(True)
            b.setStyleSheet("QPushButton:checked { background: %s; color: white; }" % estilos.AZUL)
            b.clicked.connect(lambda _=False, c=clave: self._elegir(c))
            grupo.addButton(b)
            self.botones_filtro[clave] = b
            cab.addWidget(b)
        self.botones_filtro["activas"].setChecked(True)
        interior.addLayout(cab)
        self.tabla = tabla(COLUMNAS)
        self.tabla.setMinimumHeight(280)
        interior.addWidget(self.tabla)
        self.vacia = etiqueta("No hay alarmas activas en tu área.", "Suave")
        self.vacia.setAlignment(Qt.AlignmentFlag.AlignCenter)
        interior.addWidget(self.vacia)
        nota = QLabel("Reconocer una alarma indica que la has visto y la estás atendiendo. Se cierra sola cuando el "
                      "valor vuelve al rango. Puedes crear una tarea para tu equipo desde «Equipo y tareas».")
        nota.setObjectName("AvisoInfo")
        nota.setWordWrap(True)
        interior.addWidget(nota)
        caja.addWidget(marco)
        caja.addStretch(1)
        self.botones_reconocer: dict[int, QPushButton] = {}

    def filtro_actual(self) -> str:
        return self._filtro

    def mostrar_error(self, mensaje: str | None) -> None:
        self.error.setVisible(bool(mensaje))
        self.error.setText(mensaje or "")

    def poner(self, alarmas: list[dict]) -> None:
        self.tabla.setRowCount(len(alarmas))
        self.botones_reconocer = {}
        for fila, a in enumerate(alarmas):
            estado = {"abierta": "Abierta", "reconocida": f"Reconocida por {a['reconocida_por'] or '—'}"}.get(
                a["estado"], f"Cerrada {datos.fecha_hora(a['cerrada_en'])}")
            celdas = [f"{a['tag']} · {a['nombre']}", datos.NIVELES[a["nivel"]],
                      f"{datos.numero(a['valor'])} {a['unidad']}", datos.fecha_hora(a["abierta_en"]), estado]
            for col, texto in enumerate(celdas):
                celda = QTableWidgetItem(texto)
                if col == 1:
                    celda.setForeground(QBrush(QColor(estilos.AVISO if a["nivel"] == "aviso" else estilos.ALARMA)))
                self.tabla.setItem(fila, col, celda)
            if a["estado"] == "abierta":
                b = QPushButton("Reconocer")
                b.setObjectName("Secundario")
                b.clicked.connect(lambda _=False, i=a["id"]: self.reconocer.emit(i))
                self.botones_reconocer[a["id"]] = b
                self.tabla.setCellWidget(fila, 5, b)
            self.tabla.setRowHeight(fila, 44)
        self.tabla.setVisible(bool(alarmas))
        self.vacia.setVisible(not alarmas)
        self.vacia.setText({"activas": "No hay alarmas activas en tu área.",
                            "hoy": "Hoy no se ha abierto ninguna alarma en tu área.",
                            "7dias": "En los últimos 7 días no ha habido alarmas en tu área."}[self._filtro])

    def _elegir(self, clave: str) -> None:
        self._filtro = clave
        self.filtro.emit(clave)
