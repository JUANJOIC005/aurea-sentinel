"""Ventana 06 · Supervisor · Equipo y tareas (mockup 06): técnicos vinculados, tablero de tareas y «Nueva tarea»."""
from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ..modelo import datos
from . import estilos
from .componentes import etiqueta

COLUMNAS_EQUIPO = ["TÉCNICO", "SENSORES ASIGNADOS", "TAREAS ABIERTAS", "ÚLTIMA ACTIVIDAD", "ESTADO"]
COLOR_PRIORIDAD = {"alta": estilos.ALARMA, "media": estilos.AVISO, "baja": estilos.ACERO}
FONDO_PRIORIDAD = {"alta": "#FBECEC", "media": "#FFF3D6", "baja": "#EEF3FA"}
COLUMNAS_TABLERO = ["pendiente", "en_curso", "hecha"]


def tabla(columnas: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(columnas))
    t.setHorizontalHeaderLabels(columnas)
    t.verticalHeader().hide()
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    t.setShowGrid(False)
    cab = t.horizontalHeader()
    cab.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    cab.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    cab.setStyleSheet(f"QHeaderView::section {{ background: {estilos.BLANCO}; color: {estilos.TEXTO_SUAVE}; border: none;"
                      f" border-bottom: 1px solid {estilos.PLATA}; font-size: 11px; font-weight: 700; padding: 6px 12px; }}")
    t.setStyleSheet(f"QTableWidget {{ border: none; background: {estilos.BLANCO}; font-size: 13px; }}"
                    f" QTableWidget::item {{ border-bottom: 1px solid #EEF1F6; padding: 4px 12px; }}")
    return t


def pildora(texto: str, color: str, fondo: str) -> QLabel:
    p = QLabel(texto)
    p.setStyleSheet(f"background: {fondo}; color: {color}; border-radius: 9px; padding: 2px 9px; font-size: 11px;"
                    f" font-weight: 700;")
    return p


def tarjeta_simple() -> tuple[QFrame, QVBoxLayout]:
    marco = QFrame()
    marco.setObjectName("Tarjeta")
    caja = QVBoxLayout(marco)
    caja.setContentsMargins(16, 14, 16, 14)
    caja.setSpacing(10)
    return marco, caja


class TarjetaTarea(QFrame):
    """Una tarea en el tablero: prioridad por el color del borde y por texto (no solo por color)."""

    def __init__(self, t: dict, parent=None):
        super().__init__(parent)
        self.tarea_id = t["id"]
        color = COLOR_PRIORIDAD[t["prioridad"]]
        self.setStyleSheet(f"TarjetaTarea {{ background: {estilos.BLANCO}; border: 1px solid {estilos.PLATA};"
                           f" border-left: 4px solid {color}; border-radius: 6px; }}")
        caja = QVBoxLayout(self)
        caja.setContentsMargins(12, 9, 12, 9)
        caja.setSpacing(4)
        titulo = QLabel(t["titulo"])
        titulo.setWordWrap(True)
        titulo.setStyleSheet("font-weight: 700; font-size: 13px; border: none;")
        caja.addWidget(titulo)
        sensor = f"{t['sensor']['tag']} · " if t["sensor"] else ""
        if t["estado"] == "hecha":
            texto = f"{t['tecnico']['nombre']} · cerrada {datos.fecha_hora(t['cerrada_en'])}"
            if t["ultima_incidencia"]:
                texto += f" · incidencia n.º {t['ultima_incidencia']}"
        else:
            texto = f"{sensor}{t['tecnico']['nombre']} · límite {datos.dia(t['fecha_limite'])}"
        detalle = etiqueta(texto, "Suave")
        detalle.setWordWrap(True)
        detalle.setStyleSheet("border: none;")
        caja.addWidget(detalle)
        fila = QHBoxLayout()
        fila.addWidget(pildora(datos.PRIORIDADES[t["prioridad"]], color, FONDO_PRIORIDAD[t["prioridad"]]))
        fila.addStretch(1)
        caja.addLayout(fila)


class VistaEquipo(QWidget):
    crear = Signal(dict)            # datos de la nueva tarea, tal como los pide el servidor

    def __init__(self, supervisor: str, area: str, parent=None):
        super().__init__(parent)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setFrameShape(QFrame.Shape.NoFrame)
        desplazable.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget"
                                  " { background: transparent; }")
        raiz.addWidget(desplazable)
        contenido = QWidget()
        contenido.setObjectName("Fondo")
        desplazable.setWidget(contenido)
        fila = QHBoxLayout(contenido)
        fila.setContentsMargins(0, 0, 8, 8)
        fila.setSpacing(14)

        izquierda = QVBoxLayout()
        izquierda.setSpacing(14)
        self.error = QLabel()
        self.error.setObjectName("AvisoError")
        self.error.setWordWrap(True)
        self.error.hide()
        izquierda.addWidget(self.error)
        self.subtitulo = etiqueta(f"Técnicos vinculados a {supervisor} · área {area}", "Suave")
        izquierda.addWidget(self.subtitulo)
        izquierda.addWidget(self._tarjeta_equipo())
        izquierda.addWidget(self._tarjeta_tablero())
        izquierda.addStretch(1)
        fila.addLayout(izquierda, 3)
        fila.addWidget(self._formulario(), 1, Qt.AlignmentFlag.AlignTop)
        self.poner_equipo([])
        self.poner_tareas([])

    # ── Construcción ──
    def _tarjeta_equipo(self) -> QFrame:
        marco, caja = tarjeta_simple()
        cab = QHBoxLayout()
        cab.addWidget(etiqueta("Técnicos de mi equipo", "H2"))
        cab.addWidget(etiqueta("Relación Supervisor → Técnico definida por el administrador", "Suave"))
        cab.addStretch(1)
        caja.addLayout(cab)
        self.tabla_equipo = tabla(COLUMNAS_EQUIPO)
        self.tabla_equipo.setMinimumHeight(120)
        self.tabla_equipo.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.tabla_equipo.setColumnWidth(4, 130)          # la pastilla de estado es un widget: no cuenta para el ajuste
        caja.addWidget(self.tabla_equipo)
        self.sin_equipo = etiqueta("Todavía no tienes técnicos vinculados.", "Suave")
        caja.addWidget(self.sin_equipo)
        return marco

    def _tarjeta_tablero(self) -> QFrame:
        marco, caja = tarjeta_simple()
        caja.addWidget(etiqueta("Tablero de tareas", "H2"))
        columnas = QHBoxLayout()
        columnas.setSpacing(12)
        self._columnas: dict[str, QVBoxLayout] = {}
        self._contadores: dict[str, QLabel] = {}
        for estado in COLUMNAS_TABLERO:
            fondo = QFrame()
            fondo.setStyleSheet(f"QFrame#Columna {{ background: {estilos.FONDO}; border-radius: 8px; }}")
            fondo.setObjectName("Columna")
            col = QVBoxLayout(fondo)
            col.setContentsMargins(10, 10, 10, 10)
            col.setSpacing(8)
            cab = QHBoxLayout()
            cab.addWidget(etiqueta(datos.ESTADOS_TAREA[estado].upper(), "Mayusculas"))
            contador = etiqueta("0", "Mayusculas")
            cab.addWidget(contador)
            cab.addStretch(1)
            col.addLayout(cab)
            lista = QVBoxLayout()
            lista.setSpacing(8)
            col.addLayout(lista)
            col.addStretch(1)
            self._columnas[estado], self._contadores[estado] = lista, contador
            columnas.addWidget(fondo, 1)
        caja.addLayout(columnas)
        return marco

    def _formulario(self) -> QFrame:
        marco, caja = tarjeta_simple()
        marco.setMinimumWidth(300)
        marco.setMaximumWidth(380)
        caja.addWidget(etiqueta("Nueva tarea", "H2"))

        def campo(texto: str, widget: QWidget) -> QWidget:
            caja.addWidget(etiqueta(texto, "Etiqueta"))
            caja.addWidget(widget)
            return widget

        self.tecnico = campo("Técnico", QComboBox())
        self.sensor = campo("Sensor relacionado", QComboBox())
        self.titulo = campo("Título", QLineEdit())
        self.titulo.setPlaceholderText("Ej.: calibración mensual de TE-101")
        self.titulo.setMaxLength(120)
        self.descripcion = campo("Descripción", QPlainTextEdit())
        self.descripcion.setPlaceholderText("Qué hay que hacer y qué registrar al terminar")
        self.descripcion.setFixedHeight(84)
        fila = QHBoxLayout()
        izq, der = QVBoxLayout(), QVBoxLayout()
        izq.addWidget(etiqueta("Prioridad", "Etiqueta"))
        self.prioridad = QComboBox()
        for clave, texto in datos.PRIORIDADES.items():
            self.prioridad.addItem(texto, clave)
        self.prioridad.setCurrentIndex(1)
        izq.addWidget(self.prioridad)
        der.addWidget(etiqueta("Fecha límite", "Etiqueta"))
        self.fecha = QDateEdit(QDate.currentDate().addDays(3))
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat("dd/MM/yyyy")
        self.fecha.setMinimumDate(QDate.currentDate())
        self.fecha.setMinimumHeight(38)
        der.addWidget(self.fecha)
        fila.addLayout(izq)
        fila.addLayout(der)
        caja.addLayout(fila)
        self.boton = QPushButton("Asignar tarea")
        self.boton.setObjectName("Primario")
        self.boton.clicked.connect(self._enviar)
        caja.addWidget(self.boton)
        self.mensaje = QLabel()
        self.mensaje.setWordWrap(True)
        self.mensaje.hide()
        caja.addWidget(self.mensaje)
        nota = QLabel("Solo puedes asignar tareas a técnicos vinculados contigo y sobre sensores de tu área. "
                      "La asignación queda registrada.")
        nota.setObjectName("AvisoInfo")
        nota.setWordWrap(True)
        caja.addWidget(nota)
        return marco

    # ── Lo que la ventana ofrece al controlador ──
    def mostrar_error(self, mensaje: str | None) -> None:
        self.error.setVisible(bool(mensaje))
        self.error.setText(mensaje or "")

    def mostrar_resultado(self, correcto: bool, texto: str) -> None:
        self.mensaje.setObjectName("AvisoOk" if correcto else "AvisoError")
        self.mensaje.style().unpolish(self.mensaje)                  # vuelve a aplicar el estilo del nuevo nombre
        self.mensaje.style().polish(self.mensaje)
        self.mensaje.setText(texto)
        self.mensaje.show()
        self.boton.setEnabled(True)

    def poner_equipo(self, tecnicos: list[dict]) -> None:
        elegido = self.tecnico.currentData()
        self.tecnico.blockSignals(True)
        self.tecnico.clear()
        for t in tecnicos:
            self.tecnico.addItem(t["nombre"], t["id"])
        if elegido is not None and self.tecnico.findData(elegido) >= 0:
            self.tecnico.setCurrentIndex(self.tecnico.findData(elegido))
        self.tecnico.blockSignals(False)
        self.boton.setEnabled(bool(tecnicos))

        self.tabla_equipo.setRowCount(len(tecnicos))
        for fila, t in enumerate(tecnicos):
            act = t.get("ultima_actividad")
            ultima = (f"{datos.hora(act['instante'])[:5]} · {datos.TIPOS_INCIDENCIA[act['tipo']].lower()} {act['sensor']}"
                      if act else "sin actividad registrada")
            celdas = [t["nombre"], " · ".join(t["sensores"]) or "—", str(t.get("tareas_abiertas", 0)), ultima]
            for col, texto in enumerate(celdas):
                self.tabla_equipo.setItem(fila, col, QTableWidgetItem(texto))
            ocupado = t.get("estado") == "ocupado"
            self.tabla_equipo.setCellWidget(fila, 4, pildora("● Ocupado" if ocupado else "● Disponible",
                                                             estilos.AVISO if ocupado else estilos.EN_RANGO,
                                                             "#FFF3D6" if ocupado else "#E8F5EE"))
            self.tabla_equipo.setRowHeight(fila, 40)
        self.tabla_equipo.setVisible(bool(tecnicos))
        self.sin_equipo.setVisible(not tecnicos)

    def poner_sensores(self, sensores: list[dict]) -> None:
        """Los sensores del área (los mismos que el panel): el servidor no manda los de otras áreas."""
        elegido = self.sensor.currentData()
        self.sensor.clear()
        self.sensor.addItem("Sin sensor concreto", None)
        for s in sensores:
            self.sensor.addItem(f"{s['tag']} · {s['nombre']}", s["tag"])
        if elegido and self.sensor.findData(elegido) >= 0:
            self.sensor.setCurrentIndex(self.sensor.findData(elegido))

    def poner_tareas(self, tareas: list[dict]) -> None:
        for estado, lista in self._columnas.items():
            while lista.count():
                viejo = lista.takeAt(0).widget()
                if viejo:
                    viejo.setParent(None)
                    viejo.deleteLater()
            delestado = [t for t in tareas if t["estado"] == estado]
            self._contadores[estado].setText(str(len(delestado)))
            for t in delestado:
                tarjeta = TarjetaTarea(t)
                lista.addWidget(tarjeta)
                tarjeta.show()
            if not delestado:
                lista.addWidget(etiqueta("Ninguna", "Suave"))

    def tarjetas(self, estado: str) -> list[TarjetaTarea]:
        lista = self._columnas[estado]
        return [lista.itemAt(i).widget() for i in range(lista.count())
                if isinstance(lista.itemAt(i).widget(), TarjetaTarea)]

    def limpiar_formulario(self) -> None:
        self.titulo.clear()
        self.descripcion.clear()
        self.prioridad.setCurrentIndex(1)
        self.fecha.setDate(QDate.currentDate().addDays(3))

    # ── Internos ──
    def _enviar(self) -> None:
        titulo = self.titulo.text().strip()
        if self.tecnico.currentData() is None:
            self.mostrar_resultado(False, "Elige el técnico al que asignas la tarea.")
            return
        if len(titulo) < 3:
            self.mostrar_resultado(False, "Escribe un título de al menos 3 letras.")
            self.titulo.setFocus()
            return
        self.boton.setEnabled(False)
        self.crear.emit({"titulo": titulo, "descripcion": self.descripcion.toPlainText().strip() or None,
                         "tecnico_id": self.tecnico.currentData(), "sensor_tag": self.sensor.currentData(),
                         "prioridad": self.prioridad.currentData(),
                         "fecha_limite": self.fecha.date().toString("yyyy-MM-dd")})
