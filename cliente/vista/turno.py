"""Ventana 07 · Técnico · Mi turno (mockup 07): aviso, sus sensores, sus tareas, gráfica de 7 días y acciones."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from ..modelo import datos
from . import estilos
from .componentes import etiqueta
from .equipo import COLOR_PRIORIDAD, FONDO_PRIORIDAD, pildora, tarjeta_simple
from .graficas import GraficaTemporal, Serie
from .tarjetas import TarjetaSensor

SIGUIENTE = {"pendiente": ("en_curso", "Empezar"), "en_curso": ("hecha", "Terminar")}


class FilaTarea(QFrame):
    cambiar = Signal(int, str)        # id, nuevo estado
    registrar = Signal(int)           # id: abrir la incidencia con esta tarea

    def __init__(self, t: dict, parent=None):
        super().__init__(parent)
        self.tarea_id = t["id"]
        self.setStyleSheet(f"FilaTarea {{ border: 1px solid {estilos.PLATA}; border-radius: 6px;"
                           f" background: {estilos.BLANCO}; }}")
        fila = QHBoxLayout(self)
        fila.setContentsMargins(10, 8, 10, 8)
        fila.setSpacing(10)
        fila.addWidget(pildora(datos.PRIORIDADES[t["prioridad"]], COLOR_PRIORIDAD[t["prioridad"]],
                               FONDO_PRIORIDAD[t["prioridad"]]), 0, Qt.AlignmentFlag.AlignTop)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        titulo = QLabel(t["titulo"])
        titulo.setWordWrap(True)
        titulo.setStyleSheet("font-weight: 700; font-size: 13px; border: none;")
        textos.addWidget(titulo)
        if t["estado"] == "hecha":
            detalle = f"Cerrada {datos.fecha_hora(t['cerrada_en'])}"
        else:
            detalle = (f"{datos.ESTADOS_TAREA[t['estado']]} · límite {datos.dia(t['fecha_limite'])}"
                       f" · asignada por {t['creada_por']['nombre']}")
        d = etiqueta(detalle, "Suave")
        d.setWordWrap(True)
        d.setStyleSheet("border: none;")
        textos.addWidget(d)
        fila.addLayout(textos, 1)
        self.botones: dict[str, QPushButton] = {}
        if t["estado"] in SIGUIENTE:
            nuevo, texto = SIGUIENTE[t["estado"]]
            b = QPushButton(texto)
            b.setObjectName("Secundario")
            b.clicked.connect(lambda _=False: self.cambiar.emit(self.tarea_id, nuevo))
            self.botones["estado"] = b
            fila.addWidget(b)
            r = QPushButton("Registrar")
            r.setObjectName("Secundario")
            r.setToolTip("Registrar una incidencia o lectura ligada a esta tarea")
            r.clicked.connect(lambda _=False: self.registrar.emit(self.tarea_id))
            self.botones["registrar"] = r
            fila.addWidget(r)


class VistaTurno(QWidget):
    registrar = Signal(dict)          # {"tipo": …, "tag": …, "tarea_id": …} para abrir el diálogo ya relleno
    cambiar_estado = Signal(int, str)
    ver_sensor = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tarjetas: list[TarjetaSensor] = []
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

        self.banner = QFrame()
        self.banner.setObjectName("Banner")
        self.banner.setStyleSheet("QFrame#Banner { background: #FFF6DD; border: 1px solid #F1DFA6; border-radius: 8px; }")
        fila_banner = QHBoxLayout(self.banner)
        fila_banner.setContentsMargins(14, 8, 10, 8)
        self.texto_banner = QLabel()
        self.texto_banner.setWordWrap(True)
        self.texto_banner.setStyleSheet("color: #7A5A00; font-size: 13px; border: none;")
        fila_banner.addWidget(self.texto_banner, 1)
        self.boton_banner = QPushButton("Ver sensor")
        self.boton_banner.setObjectName("Secundario")
        self.boton_banner.clicked.connect(lambda: self.ver_sensor.emit(self._tag_banner))
        fila_banner.addWidget(self.boton_banner)
        self._tag_banner = ""
        self.banner.hide()
        caja.addWidget(self.banner)

        arriba = QHBoxLayout()
        arriba.setSpacing(14)
        self.rejilla = QGridLayout()
        self.rejilla.setSpacing(14)
        arriba.addLayout(self.rejilla, 3)
        marco, self.caja_tareas = tarjeta_simple()
        cab = QHBoxLayout()
        cab.addWidget(etiqueta("Mis tareas", "H2"))
        self.contador_tareas = etiqueta("0", "Mayusculas")
        cab.addWidget(self.contador_tareas)
        cab.addStretch(1)
        self.caja_tareas.addLayout(cab)
        self.lista_tareas = QVBoxLayout()
        self.lista_tareas.setSpacing(8)
        self.caja_tareas.addLayout(self.lista_tareas)
        self.caja_tareas.addStretch(1)
        arriba.addWidget(marco, 2)
        caja.addLayout(arriba)

        abajo = QHBoxLayout()
        abajo.setSpacing(14)
        marco_g, caja_g = tarjeta_simple()
        self.titulo_grafica = etiqueta("Últimos 7 días", "H2")
        caja_g.addWidget(self.titulo_grafica)
        caja_g.addWidget(etiqueta("Un técnico solo consulta 7 días de histórico.", "Suave"))
        self.grafica = GraficaTemporal()
        self.grafica.setMinimumHeight(220)
        caja_g.addWidget(self.grafica)
        abajo.addWidget(marco_g, 3)

        marco_a, caja_a = tarjeta_simple()
        caja_a.addWidget(etiqueta("Acciones rápidas", "H2"))
        self.boton_incidencia = QPushButton("Registrar incidencia")
        self.boton_incidencia.setObjectName("Primario")
        self.boton_incidencia.clicked.connect(lambda: self.registrar.emit({"tipo": "inspeccion"}))
        self.boton_lectura = QPushButton("Registrar lectura manual")
        self.boton_lectura.setObjectName("Secundario")
        self.boton_lectura.clicked.connect(lambda: self.registrar.emit({"tipo": "lectura_manual"}))
        caja_a.addWidget(self.boton_incidencia)
        caja_a.addWidget(self.boton_lectura)
        nota = QLabel("Ves únicamente los sensores que te ha asignado tu supervisor. Si necesitas otro, pídelo "
                      "desde una tarea.")
        nota.setObjectName("AvisoInfo")
        nota.setWordWrap(True)
        caja_a.addWidget(nota)
        self.resumen = etiqueta("", "Suave")
        self.resumen.setWordWrap(True)
        caja_a.addWidget(self.resumen)
        caja_a.addStretch(1)
        abajo.addWidget(marco_a, 2)
        caja.addLayout(abajo)
        caja.addStretch(1)
        self.poner_tareas([])

    # ── Lo que la ventana ofrece al controlador ──
    def mostrar_error(self, mensaje: str | None) -> None:
        self.error.setVisible(bool(mensaje))
        self.error.setText(mensaje or "")

    def poner_datos(self, ultimas: dict) -> None:
        sensores = ultimas["sensores"]
        while len(self._tarjetas) < len(sensores):
            t = TarjetaSensor()
            t.elegido.connect(self.ver_sensor)
            self._tarjetas.append(t)
        for i, (tarjeta, s) in enumerate(zip(self._tarjetas, sensores)):
            tarjeta.poner(s)
            self.rejilla.addWidget(tarjeta, i // 2, i % 2)
            tarjeta.show()
        for tarjeta in self._tarjetas[len(sensores):]:
            tarjeta.hide()
        alerta = next((s for s in sensores if s["estado"] in ("aviso", "alarma")), None)
        self.banner.setVisible(alerta is not None)
        if alerta:
            self._tag_banner = alerta["tag"]
            self.texto_banner.setText(
                f"<b>{datos.ESTADOS[alerta['estado']]} en {alerta['tag']}</b> · {alerta['nombre']}: "
                f"{datos.numero(alerta['valor'])} {alerta['unidad']}. Revisa el sensor y registra lo que veas.")
        self.boton_lectura.setEnabled(bool(sensores))
        self.boton_incidencia.setEnabled(bool(sensores))
        if not sensores:
            self.resumen.setText("Tu supervisor todavía no te ha asignado sensores.")

    def poner_tareas(self, tareas: list[dict]) -> None:
        while self.lista_tareas.count():
            viejo = self.lista_tareas.takeAt(0).widget()
            if viejo:
                viejo.setParent(None)
                viejo.deleteLater()
        abiertas = [t for t in tareas if t["estado"] != "hecha"]
        hechas = [t for t in tareas if t["estado"] == "hecha"][:3]
        self.contador_tareas.setText(str(len(abiertas)))
        for t in abiertas + hechas:
            fila = FilaTarea(t)
            fila.cambiar.connect(self.cambiar_estado)
            fila.registrar.connect(lambda tid: self.registrar.emit({"tipo": "inspeccion", "tarea_id": tid}))
            self.lista_tareas.addWidget(fila)
            fila.show()
        if not tareas:
            self.lista_tareas.addWidget(etiqueta("No tienes tareas asignadas.", "Suave"))

    def filas_tarea(self) -> list[FilaTarea]:
        return [self.lista_tareas.itemAt(i).widget() for i in range(self.lista_tareas.count())
                if isinstance(self.lista_tareas.itemAt(i).widget(), FilaTarea)]

    def poner_grafica(self, resultado: dict | None) -> None:
        if not resultado:
            self.titulo_grafica.setText("Últimos 7 días")
            self.grafica.poner([])
            return
        s = resultado["sensor"]
        self.titulo_grafica.setText(f"{s['tag']} · últimos 7 días")
        puntos = [(datos.fecha(p["hora"]).timestamp(), p["media"]) for p in resultado["puntos"]]
        self.grafica.poner([Serie(s["tag"], puntos, estilos.AZUL)], s["umbrales"], s["unidad"])

    def poner_resumen(self, incidencias_hoy: int, lecturas_hoy: int, hechas_hoy: int) -> None:
        self.resumen.setText(f"Tu actividad de hoy: {lecturas_hoy} lecturas manuales · {incidencias_hoy} incidencias"
                             f" · {hechas_hoy} tareas cerradas")
