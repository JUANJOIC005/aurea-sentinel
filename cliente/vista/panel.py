"""Ventana 04 · Supervisor · Panel del área (mockup 04): indicadores, 4 sensores, alarmas y equipo."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..modelo import datos
from . import estilos
from .componentes import Avatar, etiqueta
from .tarjetas import Indicador, TarjetaSensor

FILTROS = [("activas", "Activas"), ("hoy", "Hoy"), ("7dias", "7 días")]
COLUMNAS_ALARMAS = ["SENSOR", "NIVEL", "VALOR", "ABIERTA", "ESTADO"]
ANCHO_DOS_COLUMNAS = 1000       # por debajo, las tarjetas de sensor pasan a dos por fila


class VistaPanel(QWidget):
    abrir_historico = Signal(str)       # tag
    filtro_alarmas = Signal(str)        # activas | hoy | 7dias

    def __init__(self, area_texto: str, parent=None):
        super().__init__(parent)
        self._tarjetas: list[TarjetaSensor] = []
        self._filtro = "activas"
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

        fila_kpi = QHBoxLayout()
        fila_kpi.setSpacing(14)
        self.kpi_rango = Indicador("Sensores en rango", estilos.AZUL)
        self.kpi_alarmas = Indicador("Alarmas activas", estilos.AVISO)
        self.kpi_tareas = Indicador("Tareas abiertas del equipo", estilos.ACERO)
        self.kpi_validas = Indicador("Lecturas válidas (24 h)", estilos.CIAN)
        for kpi in (self.kpi_rango, self.kpi_alarmas, self.kpi_tareas, self.kpi_validas):
            fila_kpi.addWidget(kpi, 1)
        caja.addLayout(fila_kpi)

        self.rejilla = QGridLayout()
        self.rejilla.setSpacing(14)
        caja.addLayout(self.rejilla)

        inferior = QHBoxLayout()
        inferior.setSpacing(14)
        inferior.addWidget(self._tarjeta_alarmas(), 3)
        inferior.addWidget(self._tarjeta_equipo(area_texto), 2)
        caja.addLayout(inferior)
        caja.addStretch(1)
        self.poner_alarmas([])
        self.poner_equipo([])

    # ── Construcción ──
    def _tarjeta_alarmas(self) -> QFrame:
        tarjeta = QFrame()
        tarjeta.setObjectName("Tarjeta")
        caja = QVBoxLayout(tarjeta)
        caja.setContentsMargins(16, 14, 16, 14)
        caja.setSpacing(10)
        cabecera = QHBoxLayout()
        cabecera.addWidget(etiqueta("Alarmas y avisos del área", "H2"))
        cabecera.addStretch(1)
        grupo = QButtonGroup(self)
        self._botones_filtro = {}
        for clave, texto in FILTROS:
            boton = QPushButton(texto)
            boton.setObjectName("Secundario")
            boton.setCheckable(True)
            boton.setMinimumHeight(30)
            boton.setStyleSheet("QPushButton:checked { background: %s; color: white; }" % estilos.AZUL)
            boton.clicked.connect(lambda _=False, c=clave: self._elegir_filtro(c))
            grupo.addButton(boton)
            self._botones_filtro[clave] = boton
            cabecera.addWidget(boton)
        self._botones_filtro["activas"].setChecked(True)
        caja.addLayout(cabecera)

        self.tabla = QTableWidget(0, len(COLUMNAS_ALARMAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS_ALARMAS)
        self.tabla.verticalHeader().hide()
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tabla.setShowGrid(False)
        self.tabla.setMinimumHeight(170)
        cabecera_tabla = self.tabla.horizontalHeader()
        cabecera_tabla.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        cabecera_tabla.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)     # el nombre del sensor es lo largo
        cabecera_tabla.setStretchLastSection(False)
        cabecera_tabla.setStyleSheet(
            f"QHeaderView::section {{ background: {estilos.BLANCO}; color: {estilos.TEXTO_SUAVE}; border: none;"
            f" border-bottom: 1px solid {estilos.PLATA}; font-size: 11px; font-weight: 700; padding: 6px 12px;"
            f" text-align: left; }}")
        self.tabla.setStyleSheet(f"QTableWidget {{ border: none; background: {estilos.BLANCO}; font-size: 13px; }}"
                                 f" QTableWidget::item {{ border-bottom: 1px solid #EEF1F6; padding: 4px 12px; }}")
        caja.addWidget(self.tabla)
        self.sin_alarmas = etiqueta("", "Suave")
        self.sin_alarmas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caja.addWidget(self.sin_alarmas)
        caja.addWidget(etiqueta("Reconocer una alarma se podrá hacer desde el Sprint 3 (T15).", "Suave"))
        return tarjeta

    def _tarjeta_equipo(self, area_texto: str) -> QFrame:
        tarjeta = QFrame()
        tarjeta.setObjectName("Tarjeta")
        self.caja_equipo = QVBoxLayout(tarjeta)
        self.caja_equipo.setContentsMargins(16, 14, 16, 14)
        self.caja_equipo.setSpacing(10)
        cabecera = QHBoxLayout()
        cabecera.addWidget(etiqueta("Mi equipo", "H2"))
        cabecera.addStretch(1)
        asignar = QPushButton("+ Asignar tarea")
        asignar.setObjectName("Primario")
        asignar.setEnabled(False)
        asignar.setToolTip("Asignar tareas llega en el Sprint 3 (T15 y T17).")
        cabecera.addWidget(asignar)
        self.caja_equipo.addLayout(cabecera)
        self.lista_equipo = QVBoxLayout()
        self.lista_equipo.setSpacing(8)
        self.caja_equipo.addLayout(self.lista_equipo)
        self.caja_equipo.addStretch(1)
        aviso = QLabel(f"Solo ves los sensores del área {area_texto} y los técnicos vinculados a ti. "
                       f"El servidor no envía a tu equipo datos de otras áreas.")
        aviso.setObjectName("AvisoInfo")
        aviso.setWordWrap(True)
        self.caja_equipo.addWidget(aviso)
        return tarjeta

    # ── Lo que la ventana ofrece al controlador ──
    def mostrar_error(self, mensaje: str | None) -> None:
        self.error.setVisible(bool(mensaje))
        self.error.setText(mensaje or "")

    def poner_datos(self, ultimas: dict) -> None:
        """`ultimas` es la respuesta de /lecturas/ultimas: las tarjetas de sensor y el resumen."""
        sensores, resumen = ultimas["sensores"], ultimas["resumen"]
        while len(self._tarjetas) < len(sensores):
            tarjeta = TarjetaSensor()
            tarjeta.elegido.connect(self.abrir_historico)
            self._tarjetas.append(tarjeta)
        for tarjeta, sensor in zip(self._tarjetas, sensores):
            tarjeta.poner(sensor)
        for tarjeta in self._tarjetas[len(sensores):]:
            tarjeta.hide()
        self._colocar_tarjetas(len(sensores))

        self.kpi_rango.poner(
            f"{resumen['en_rango']}<span style='font-size:14px; color:{estilos.TEXTO_SUAVE}'> / {resumen['sensores']}</span>",
            f"{resumen['en_aviso']} en aviso · {resumen['en_alarma']} en alarma")
        activas = [s for s in sensores if s["alarma"]]
        self.kpi_alarmas.poner(
            str(resumen["alarmas_activas"]),
            ", ".join(f"{s['tag']} · {s['alarma']}" for s in activas[:2]) if resumen["alarmas_activas"] else
            "Ninguna activa",
            estilos.AVISO if resumen["alarmas_activas"] else None)
        self.kpi_tareas.poner("—", "Las tareas llegan en el Sprint 3 (T15)")
        pct = resumen["pct_validas"]
        self.kpi_validas.poner(f"{datos.numero(pct, 1)}<span style='font-size:14px'> %</span>" if pct is not None else "—",
                               f"{datos.numero(resumen['lecturas_24h'], 0)} medidas en 24 h")

    def poner_alarmas(self, alarmas: list[dict]) -> None:
        self.tabla.setRowCount(len(alarmas))
        for fila, a in enumerate(alarmas):
            color = estilos.AVISO if a["nivel"] == "aviso" else estilos.ALARMA
            celdas = [f"{a['tag']} · {a['nombre']}", datos.NIVELES[a["nivel"]], f"{datos.numero(a['valor'])} {a['unidad']}",
                      datos.fecha_hora(a["abierta_en"]),
                      "Abierta" if a["estado"] == "abierta" else
                      "Reconocida" if a["estado"] == "reconocida" else f"Cerrada {datos.fecha_hora(a['cerrada_en'])}"]
            fondo = QBrush(QColor(estilos.FONDO_ESTADO[a["nivel"]])) if a["estado"] != "cerrada" else None
            for columna, texto in enumerate(celdas):
                celda = QTableWidgetItem(texto)
                if columna == 1:
                    celda.setForeground(QBrush(QColor(color)))
                    fuente = celda.font()
                    fuente.setBold(True)
                    celda.setFont(fuente)
                if fondo:
                    celda.setBackground(fondo)
                self.tabla.setItem(fila, columna, celda)
            self.tabla.setRowHeight(fila, 38)
        vacia = not alarmas
        self.tabla.setVisible(not vacia)
        self.sin_alarmas.setVisible(vacia)
        self.sin_alarmas.setText({"activas": "No hay alarmas activas en tu área.",
                                  "hoy": "Hoy no se ha abierto ninguna alarma en tu área.",
                                  "7dias": "En los últimos 7 días no ha habido alarmas en tu área."}[self._filtro])

    def poner_equipo(self, tecnicos: list[dict]) -> None:
        while self.lista_equipo.count():
            elemento = self.lista_equipo.takeAt(0)
            viejo = elemento.widget()
            if viejo:
                viejo.setParent(None)                   # sale ya de la pantalla (deleteLater tarda en actuar)
                viejo.deleteLater()
        if not tecnicos:
            self.lista_equipo.addWidget(etiqueta("Todavía no tienes técnicos vinculados.", "Suave"))
        for t in tecnicos:
            fila = QWidget()
            caja = QHBoxLayout(fila)
            caja.setContentsMargins(0, 0, 0, 0)
            caja.setSpacing(10)
            caja.addWidget(Avatar("".join(p[0] for p in t["nombre"].split()[:2]).upper(), estilos.ACERO, 34))
            textos = QVBoxLayout()
            textos.setSpacing(1)
            nombre = QLabel(t["nombre"])
            nombre.setStyleSheet("font-weight: 700; font-size: 13px;")
            sensores = " · ".join(t["sensores"]) or "sin sensores asignados"
            ultimo = f"último acceso {datos.fecha_hora(t['ultimo_acceso'])}" if t["ultimo_acceso"] else "aún no ha entrado"
            detalle = etiqueta(f"Técnico de campo · {sensores} · {ultimo}", "Suave")
            detalle.setWordWrap(True)
            textos.addWidget(nombre)
            textos.addWidget(detalle)
            caja.addLayout(textos, 1)
            self.lista_equipo.addWidget(fila)

    # ── Internos ──
    def _elegir_filtro(self, clave: str) -> None:
        self._filtro = clave
        self.filtro_alarmas.emit(clave)

    def filtro_actual(self) -> str:
        return self._filtro

    def _colocar_tarjetas(self, cuantas: int) -> None:
        for i in reversed(range(self.rejilla.count())):
            self.rejilla.takeAt(i)
        columnas = 4 if self.width() >= ANCHO_DOS_COLUMNAS else 2
        for i, tarjeta in enumerate(self._tarjetas[:cuantas]):
            self.rejilla.addWidget(tarjeta, i // columnas, i % columnas)
            tarjeta.show()
        for c in range(4):
            self.rejilla.setColumnStretch(c, 1 if c < columnas else 0)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        visibles = sum(1 for t in self._tarjetas if not t.isHidden())
        if self._tarjetas:
            self._colocar_tarjetas(visibles)
