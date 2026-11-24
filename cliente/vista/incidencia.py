"""Ventana 08 · Técnico · Registrar incidencia (diálogo sobre «Mi turno») y la lista de incidencias del técnico."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QTableWidgetItem, QVBoxLayout, QWidget)

from ..modelo import datos
from ..modelo.sesion import Usuario
from . import estilos
from .componentes import InsigniaRol, etiqueta
from .equipo import tabla, tarjeta_simple

TOLERANCIA = 0.01           # 1 % del rango físico: diferencia aceptable entre la lectura manual y la del sistema
COLUMNAS = ["FECHA", "SENSOR", "TIPO", "VALOR", "TAREA", "OBSERVACIONES"]


def a_numero(texto: str) -> float | None:
    """«325,4» o «325.4» → 325.4. Si no es un número, None."""
    texto = texto.strip().replace(" ", "")
    if texto.count(",") == 1 and "." not in texto:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


class DialogoIncidencia(QDialog):
    """Modal: sensor y tarea precargados, tipo, valor medido comparado con el del sistema y observaciones.
    La validación se repite en el servidor antes de guardar."""
    guardar = Signal(dict)

    def __init__(self, usuario: Usuario, sensores: list[dict], tareas: list[dict], tag: str | None = None,
                 tarea_id: int | None = None, tipo: str = "inspeccion", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar incidencia")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(f"QDialog {{ background: {estilos.BLANCO}; }}")
        self._sensores = {s["tag"]: s for s in sensores}
        self._tareas = [t for t in tareas if t["estado"] != "hecha"]
        caja = QVBoxLayout(self)
        caja.setContentsMargins(22, 18, 22, 18)
        caja.setSpacing(10)

        cab = QHBoxLayout()
        cab.addWidget(etiqueta("Registrar incidencia", "H2"))
        cab.addStretch(1)
        cab.addWidget(etiqueta(usuario.nombre, "Suave"))
        cab.addWidget(InsigniaRol(usuario.rol, usuario.rol_visible))
        caja.addLayout(cab)

        fila = QHBoxLayout()
        izq, der = QVBoxLayout(), QVBoxLayout()
        izq.addWidget(etiqueta("Sensor", "Etiqueta"))
        self.sensor = QComboBox()
        for s in sensores:
            self.sensor.addItem(f"{s['tag']} · {s['nombre']}", s["tag"])
        izq.addWidget(self.sensor)
        der.addWidget(etiqueta("Tarea relacionada", "Etiqueta"))
        self.tarea = QComboBox()
        der.addWidget(self.tarea)
        fila.addLayout(izq, 1)
        fila.addLayout(der, 1)
        caja.addLayout(fila)

        caja.addWidget(etiqueta("Tipo", "Etiqueta"))
        tipos = QHBoxLayout()
        tipos.setSpacing(0)
        self._grupo = QButtonGroup(self)
        self.botones_tipo: dict[str, QPushButton] = {}
        for clave, texto in datos.TIPOS_INCIDENCIA.items():
            b = QPushButton(texto)
            b.setCheckable(True)
            b.setObjectName("Secundario")
            b.setStyleSheet("QPushButton:checked { background: %s; color: white; border-color: %s; }"
                            % (estilos.AZUL, estilos.AZUL))
            b.clicked.connect(self._actualizar)
            self._grupo.addButton(b)
            self.botones_tipo[clave] = b
            tipos.addWidget(b, 1)
        caja.addLayout(tipos)

        self.etiqueta_valor = etiqueta("Valor medido", "Etiqueta")
        caja.addWidget(self.etiqueta_valor)
        self.valor = QLineEdit()
        self.valor.setPlaceholderText("Ej.: 325,4")
        self.valor.textChanged.connect(self._actualizar)
        caja.addWidget(self.valor)
        self.comparacion = etiqueta("", "Suave")
        self.comparacion.setWordWrap(True)
        caja.addWidget(self.comparacion)

        caja.addWidget(etiqueta("Observaciones", "Etiqueta"))
        self.observaciones = QPlainTextEdit()
        self.observaciones.setPlaceholderText("Qué has visto o hecho, con qué instrumento…")
        self.observaciones.setFixedHeight(90)
        caja.addWidget(self.observaciones)

        self.error = QLabel()
        self.error.setObjectName("AvisoError")
        self.error.setWordWrap(True)
        self.error.hide()
        caja.addWidget(self.error)

        pie = QHBoxLayout()
        sup = usuario.supervisor or "tu supervisor"
        nota = etiqueta(f"Se guarda con tu usuario, hora y sensor. {sup} la verá en su equipo.", "Suave")
        nota.setWordWrap(True)
        pie.addWidget(nota, 1)
        self.cancelar = QPushButton("Cancelar")
        self.cancelar.setObjectName("Secundario")
        self.cancelar.clicked.connect(self.reject)
        self.boton = QPushButton("Guardar incidencia")
        self.boton.setObjectName("Primario")
        self.boton.clicked.connect(self._enviar)
        pie.addWidget(self.cancelar)
        pie.addWidget(self.boton)
        caja.addLayout(pie)

        self.sensor.currentIndexChanged.connect(self._poner_tareas)
        if tarea_id is not None:
            t = next((t for t in self._tareas if t["id"] == tarea_id), None)
            if t and t["sensor"]:
                tag = tag or t["sensor"]["tag"]
        if tag and self.sensor.findData(tag) >= 0:
            self.sensor.setCurrentIndex(self.sensor.findData(tag))
        self._poner_tareas()
        if tarea_id is not None and self.tarea.findData(tarea_id) >= 0:
            self.tarea.setCurrentIndex(self.tarea.findData(tarea_id))
        self.botones_tipo[tipo].setChecked(True)
        self._actualizar()

    # ── Lo que el diálogo ofrece al controlador ──
    def tipo(self) -> str:
        return next(c for c, b in self.botones_tipo.items() if b.isChecked())

    def mostrar_error(self, mensaje: str) -> None:
        self.error.setText(mensaje)
        self.error.show()
        self.boton.setEnabled(True)

    # ── Internos ──
    def _poner_tareas(self) -> None:
        tag = self.sensor.currentData()
        self.tarea.clear()
        self.tarea.addItem("Sin tarea relacionada", None)
        for t in self._tareas:
            if t["sensor"] is None or t["sensor"]["tag"] == tag:
                self.tarea.addItem(t["titulo"], t["id"])
        self._actualizar()

    def _actualizar(self) -> None:
        lectura = self.botones_tipo["lectura_manual"].isChecked()
        s = self._sensores.get(self.sensor.currentData())
        unidad = f" ({s['unidad']})" if s else ""
        self.etiqueta_valor.setText(("Valor medido" if lectura else "Valor medido (opcional)") + unidad)
        valor = a_numero(self.valor.text()) if self.valor.text().strip() else None
        if not s or valor is None or s.get("valor") is None:
            self.comparacion.setText("")
            return
        dif = valor - s["valor"]
        rango = s["max_fisico"] - s["min_fisico"]
        dentro = abs(dif) <= TOLERANCIA * rango
        self.comparacion.setText(
            f"Valor del sistema a las {datos.hora(s['instante'])[:5]}: {datos.numero(s['valor'])} {s['unidad']}"
            f" · diferencia {datos.con_signo(dif)} · tolerancia ±{datos.numero(TOLERANCIA * rango)} "
            + ("(dentro)" if dentro else "(fuera: revisa el sensor)"))
        self.comparacion.setStyleSheet(f"color: {estilos.EN_RANGO if dentro else estilos.AVISO};")

    def _enviar(self) -> None:
        s = self._sensores.get(self.sensor.currentData())
        if s is None:
            self.mostrar_error("No tienes sensores asignados.")
            return
        tipo = self.tipo()
        texto = self.valor.text().strip()
        valor = a_numero(texto) if texto else None
        if texto and valor is None:
            self.mostrar_error("El valor medido tiene que ser un número (por ejemplo 325,4).")
            return
        if tipo == "lectura_manual" and valor is None:
            self.mostrar_error("Una lectura manual necesita el valor medido.")
            return
        if valor is not None and not s["min_fisico"] <= valor <= s["max_fisico"]:
            self.mostrar_error(f"El valor está fuera del rango físico del sensor "
                               f"({datos.numero(s['min_fisico'])} – {datos.numero(s['max_fisico'])} {s['unidad']}).")
            return
        self.error.hide()
        self.boton.setEnabled(False)
        self.guardar.emit({"sensor_tag": s["tag"], "tipo": tipo, "valor_medido": valor,
                           "observaciones": self.observaciones.toPlainText().strip() or None,
                           "tarea_id": self.tarea.currentData()})


class VistaIncidencias(QWidget):
    """Lo que el técnico ha registrado (las más recientes primero) y el botón para registrar otra."""
    nueva = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
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
        cab.addWidget(etiqueta("Mis incidencias y lecturas manuales", "H2"))
        cab.addStretch(1)
        boton = QPushButton("Registrar incidencia")
        boton.setObjectName("Primario")
        boton.clicked.connect(self.nueva)
        cab.addWidget(boton)
        interior.addLayout(cab)
        self.tabla = tabla(COLUMNAS)
        self.tabla.setMinimumHeight(320)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        interior.addWidget(self.tabla)
        self.vacia = etiqueta("Todavía no has registrado ninguna incidencia.", "Suave")
        self.vacia.setAlignment(Qt.AlignmentFlag.AlignCenter)
        interior.addWidget(self.vacia)
        caja.addWidget(marco)
        caja.addStretch(1)

    def mostrar_error(self, mensaje: str | None) -> None:
        self.error.setVisible(bool(mensaje))
        self.error.setText(mensaje or "")

    def poner(self, incidencias: list[dict]) -> None:
        self.tabla.setRowCount(len(incidencias))
        for fila, i in enumerate(incidencias):
            valor = f"{datos.numero(i['valor_medido'])} {i['sensor']['unidad']}" if i["valor_medido"] is not None else "—"
            celdas = [datos.fecha_hora(i["creada_en"]), i["sensor"]["tag"], datos.TIPOS_INCIDENCIA[i["tipo"]], valor,
                      i["tarea"]["titulo"] if i["tarea"] else "—", i["observaciones"] or ""]
            for col, texto in enumerate(celdas):
                self.tabla.setItem(fila, col, QTableWidgetItem(texto))
            self.tabla.setRowHeight(fila, 36)
        self.tabla.setVisible(bool(incidencias))
        self.vacia.setVisible(not incidencias)
