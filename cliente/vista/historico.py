"""Ventana 05 · Supervisor · Histórico de sensores (mockup 05): periodo, estadísticas, gráfica, tabla y CSV."""
from datetime import datetime, time, timedelta

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QDateEdit, QFrame, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..modelo import datos
from . import estilos
from .componentes import etiqueta
from .graficas import GraficaTemporal, Serie
from .tarjetas import Indicador

PERIODOS = [("24h", "24 h", 24), ("7d", "7 días", 168), ("30d", "30 días", 720), ("personalizado", "Personalizado", None)]
FILAS_POR_PAGINA = 10
COLUMNAS = ["FECHA Y HORA", "MÍN", "MEDIA", "MÁX", "LECTURAS", "ESTADO"]


class VistaHistorico(QWidget):
    consultar = Signal(dict)     # {tag, horas, desde, hasta, comparar}
    exportar = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sensores: list[dict] = []
        self._puntos: list[dict] = []
        self._pagina = 0
        self._periodo = "7d"
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
        caja = QVBoxLayout(contenido)
        caja.setContentsMargins(0, 0, 8, 8)
        caja.setSpacing(14)

        self.error = QLabel()
        self.error.setObjectName("AvisoError")
        self.error.setWordWrap(True)
        self.error.hide()
        caja.addWidget(self.error)
        caja.addWidget(self._controles())

        fila = QHBoxLayout()
        fila.setSpacing(14)
        self.kpi_min = Indicador("Mínimo", estilos.ACERO)
        self.kpi_max = Indicador("Máximo", estilos.AVISO)
        self.kpi_media = Indicador("Media", estilos.ACERO)
        self.kpi_rango = Indicador("Tiempo en rango", estilos.EN_RANGO)
        self.kpi_validas = Indicador("Lecturas válidas", estilos.CIAN)
        for kpi in (self.kpi_min, self.kpi_max, self.kpi_media, self.kpi_rango, self.kpi_validas):
            fila.addWidget(kpi, 1)
        caja.addLayout(fila)

        tarjeta = QFrame()
        tarjeta.setObjectName("Tarjeta")
        interior = QVBoxLayout(tarjeta)
        interior.setContentsMargins(16, 14, 16, 14)
        cabecera = QHBoxLayout()
        self.titulo_grafica = etiqueta("", "H2")
        cabecera.addWidget(self.titulo_grafica, 1)
        self.leyenda = etiqueta("", "Suave")
        cabecera.addWidget(self.leyenda)
        interior.addLayout(cabecera)
        self.grafica = GraficaTemporal()
        interior.addWidget(self.grafica)
        caja.addWidget(tarjeta)
        caja.addWidget(self._tabla())
        caja.addStretch(1)

    # ── Construcción ──
    def _controles(self) -> QFrame:
        tarjeta = QFrame()
        tarjeta.setObjectName("Tarjeta")
        caja = QHBoxLayout(tarjeta)
        caja.setContentsMargins(16, 12, 16, 12)
        caja.setSpacing(16)

        def columna(titulo: str, *widgets) -> QVBoxLayout:
            v = QVBoxLayout()
            v.setSpacing(4)
            v.addWidget(etiqueta(titulo, "Etiqueta"))
            for w in widgets:
                v.addWidget(w) if not isinstance(w, QHBoxLayout) else v.addLayout(w)
            return v

        self.sensor = QComboBox()
        self.sensor.setMinimumWidth(190)
        self.sensor.currentIndexChanged.connect(self._sensor_cambiado)
        caja.addLayout(columna("Sensor", self.sensor))

        botones = QHBoxLayout()
        botones.setSpacing(0)
        grupo = QButtonGroup(self)
        self._botones_periodo = {}
        for clave, texto, _ in PERIODOS:
            b = QPushButton(texto)
            b.setObjectName("Secundario")
            b.setCheckable(True)
            b.setStyleSheet("QPushButton { padding: 0 11px; } QPushButton:checked { background: %s; color: white; }"
                            % estilos.AZUL)
            b.clicked.connect(lambda _=False, c=clave: self._elegir_periodo(c))
            grupo.addButton(b)
            self._botones_periodo[clave] = b
            botones.addWidget(b)
        self._botones_periodo[self._periodo].setChecked(True)
        caja.addLayout(columna("Periodo", botones))

        hoy = QDate.currentDate()
        self.desde = QDateEdit(hoy.addDays(-7))
        self.hasta = QDateEdit(hoy)
        for campo in (self.desde, self.hasta):
            campo.setCalendarPopup(True)
            campo.setDisplayFormat("dd/MM/yyyy")
            campo.setMinimumWidth(110)
        rango = QHBoxLayout()
        rango.addWidget(self.desde)
        rango.addWidget(etiqueta("–", "Suave"))
        rango.addWidget(self.hasta)
        self.rango = QWidget()
        self.rango.setLayout(rango)
        rango.setContentsMargins(0, 0, 0, 0)
        self.bloque_rango = columna("Desde – hasta", self.rango)
        self.titulo_rango = self.bloque_rango.itemAt(0).widget()
        caja.addLayout(self.bloque_rango)
        self._mostrar_rango(False)

        self.comparar = QComboBox()
        self.comparar.setMinimumWidth(140)
        caja.addLayout(columna("Comparar con", self.comparar))
        caja.addStretch(1)

        self.boton_csv = QPushButton("Exportar CSV")
        self.boton_csv.setObjectName("Secundario")
        self.boton_csv.clicked.connect(lambda: self.exportar.emit(self.parametros()))
        self.boton_aplicar = QPushButton("Aplicar")
        self.boton_aplicar.setObjectName("Primario")
        self.boton_aplicar.clicked.connect(self.aplicar)
        caja.addWidget(self.boton_csv, 0, Qt.AlignmentFlag.AlignBottom)
        caja.addWidget(self.boton_aplicar, 0, Qt.AlignmentFlag.AlignBottom)
        return tarjeta

    def _tabla(self) -> QFrame:
        tarjeta = QFrame()
        tarjeta.setObjectName("Tarjeta")
        caja = QVBoxLayout(tarjeta)
        caja.setContentsMargins(16, 14, 16, 14)
        cabecera = QHBoxLayout()
        cabecera.addWidget(etiqueta("Lecturas agregadas por hora", "H2"))
        self.cuenta = etiqueta("", "Suave")
        cabecera.addWidget(self.cuenta)
        cabecera.addStretch(1)
        self.anterior = QPushButton("Anterior")
        self.siguiente = QPushButton("Siguiente")
        for b, paso in ((self.anterior, -1), (self.siguiente, +1)):
            b.setObjectName("Secundario")
            b.setMinimumHeight(30)
            b.clicked.connect(lambda _=False, p=paso: self._mover(p))
            cabecera.addWidget(b)
        caja.addLayout(cabecera)
        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.verticalHeader().hide()
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tabla.setShowGrid(False)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setMinimumHeight(40 * FILAS_POR_PAGINA + 36)
        self.tabla.horizontalHeader().setStyleSheet(
            f"QHeaderView::section {{ background: {estilos.BLANCO}; color: {estilos.TEXTO_SUAVE}; border: none;"
            f" border-bottom: 1px solid {estilos.PLATA}; font-size: 11px; font-weight: 700; padding: 6px; }}")
        self.tabla.setStyleSheet(f"QTableWidget {{ border: none; background: {estilos.BLANCO}; font-size: 13px; }}"
                                 f" QTableWidget::item {{ border-bottom: 1px solid #EEF1F6; padding: 4px; }}")
        caja.addWidget(self.tabla)
        return tarjeta

    # ── Lo que la ventana ofrece al controlador ──
    def poner_sensores(self, sensores: list[dict]) -> None:
        """`sensores`: las tarjetas de /lecturas/ultimas (tag, nombre, unidad…)."""
        actual = self.sensor.currentData()
        self._sensores = sensores
        self.sensor.blockSignals(True)
        self.sensor.clear()
        for s in sensores:
            self.sensor.addItem(f"{s['tag']}  {s['nombre']}", s["tag"])
        self.sensor.blockSignals(False)
        self.elegir_sensor(actual or (sensores[0]["tag"] if sensores else None))

    def elegir_sensor(self, tag: str | None) -> None:
        indice = self.sensor.findData(tag) if tag else -1
        if indice >= 0:
            self.sensor.setCurrentIndex(indice)
        self._sensor_cambiado()

    def parametros(self) -> dict:
        """Lo que se pregunta al servidor según lo elegido en pantalla."""
        horas = next(h for clave, _, h in PERIODOS if clave == self._periodo)
        desde = hasta = None
        if self._periodo == "personalizado":
            inicio = datetime.combine(self.desde.date().toPython(), time.min)
            fin = datetime.combine(self.hasta.date().toPython(), time.max).replace(microsecond=0)
            desde, hasta = datos.a_utc_iso(inicio), datos.a_utc_iso(fin)
            horas = None
        return {"tag": self.sensor.currentData(), "horas": horas, "desde": desde, "hasta": hasta,
                "comparar": self.comparar.currentData()}

    def aplicar(self) -> None:
        if self.sensor.currentData():
            self.ocultar_error()
            self.consultar.emit(self.parametros())

    def mostrar_error(self, mensaje: str) -> None:
        self._aviso("AvisoError", mensaje)

    def mostrar_info(self, mensaje: str) -> None:
        self._aviso("AvisoOk", mensaje)

    def ocultar_error(self) -> None:
        self.error.hide()

    def _aviso(self, nombre: str, mensaje: str) -> None:
        self.error.setObjectName(nombre)
        self.error.setText(mensaje)
        self.error.style().unpolish(self.error)
        self.error.style().polish(self.error)
        self.error.show()

    def ocupado(self, ocupado: bool) -> None:
        self.boton_aplicar.setEnabled(not ocupado)
        self.boton_aplicar.setText("Consultando…" if ocupado else "Aplicar")

    def poner_resultado(self, resultado: dict, comparado: dict | None = None) -> None:
        s, r = resultado["sensor"], resultado["resumen"]
        unidad = s["unidad"]
        self.kpi_min.poner(f"{datos.numero(r['minimo'])}<span style='font-size:13px'> {unidad}</span>", "mínimo del periodo")
        self.kpi_max.poner(f"{datos.numero(r['maximo'])}<span style='font-size:13px'> {unidad}</span>", "máximo del periodo")
        self.kpi_media.poner(f"{datos.numero(r['media'])}<span style='font-size:13px'> {unidad}</span>", "media del periodo")
        self.kpi_rango.poner(f"{datos.numero(r['pct_en_rango'], 1)}<span style='font-size:13px'> %</span>"
                             if r["pct_en_rango"] is not None else "—", "por debajo del aviso")
        self.kpi_validas.poner(datos.numero(r["validas"], 0), f"de {datos.numero(r['lecturas'], 0)} lecturas")

        series = [self._serie(resultado, estilos.AZUL, marcar=True)]
        if comparado:
            series.append(self._serie(comparado, estilos.CIAN))
        self.grafica.poner(series, s["umbrales"], unidad)
        periodo = f"{datos.fecha_hora(resultado['desde'])} – {datos.fecha_hora(resultado['hasta'])}"
        self.titulo_grafica.setText(f"{s['tag']} · {s['nombre']} ({unidad})")
        self.leyenda.setText(f"media horaria · {periodo}" + (f" · comparado con {comparado['sensor']['tag']}"
                                                              if comparado else ""))
        self._puntos = list(reversed(resultado["puntos"]))
        self._pagina = 0
        self._pintar_tabla(unidad)
        self._unidad = unidad

    # ── Internos ──
    @staticmethod
    def _serie(resultado: dict, color: str, marcar: bool = False) -> Serie:
        puntos = [(datos.fecha(p["hora"]).timestamp(), p["media"]) for p in resultado["puntos"]]
        extra = {}
        if resultado["puntos"]:
            mejor = max(resultado["puntos"], key=lambda p: p["maximo"])
            extra["maximo"] = (datos.fecha(mejor["hora"]).timestamp(), mejor["maximo"])
        return Serie(resultado["sensor"]["tag"], puntos, color, marcar_maximo=marcar, extra=extra)

    def _pintar_tabla(self, unidad: str) -> None:
        inicio = self._pagina * FILAS_POR_PAGINA
        filas = self._puntos[inicio:inicio + FILAS_POR_PAGINA]
        self.tabla.setRowCount(len(filas))
        for i, p in enumerate(filas):
            celdas = [datos.fecha_hora(p["hora"]), datos.numero(p["minimo"]), datos.numero(p["media"]),
                      datos.numero(p["maximo"]), f"{p['validas']} / {p['lecturas']}", datos.ESTADOS[p["estado"]]]
            for c, texto in enumerate(celdas):
                celda = QTableWidgetItem(texto)
                if p["estado"] in ("aviso", "alarma"):
                    celda.setBackground(QBrush(QColor(estilos.FONDO_ESTADO[p["estado"]])))
                if c == 5:
                    celda.setForeground(QBrush(QColor(estilos.COLOR_ESTADO[p["estado"]])))
                self.tabla.setItem(i, c, celda)
            self.tabla.setRowHeight(i, 40)
        total = len(self._puntos)
        self.cuenta.setText(f"{inicio + 1 if total else 0}–{inicio + len(filas)} de {total} filas ({unidad})")
        self.anterior.setEnabled(self._pagina > 0)
        self.siguiente.setEnabled(inicio + FILAS_POR_PAGINA < total)

    def _mover(self, paso: int) -> None:
        self._pagina = max(0, self._pagina + paso)
        self._pintar_tabla(getattr(self, "_unidad", ""))

    def _elegir_periodo(self, clave: str) -> None:
        self._periodo = clave
        self._mostrar_rango(clave == "personalizado")

    def _mostrar_rango(self, visible: bool) -> None:
        self.rango.setVisible(visible)
        self.titulo_rango.setVisible(visible)

    def _sensor_cambiado(self) -> None:
        """Solo se pueden comparar sensores con la misma unidad."""
        tag = self.sensor.currentData()
        actual = next((s for s in self._sensores if s["tag"] == tag), None)
        self.comparar.clear()
        self.comparar.addItem("Ninguno", None)
        if actual:
            for s in self._sensores:
                if s["tag"] != tag and s["unidad"] == actual["unidad"]:
                    self.comparar.addItem(f"{s['tag']}  {s['nombre']}", s["tag"])
