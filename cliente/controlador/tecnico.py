"""Controlador del Técnico: Mi turno (ventana 07), Registrar incidencia (08), sus incidencias y su histórico de 7 días."""
from datetime import datetime

from PySide6.QtCore import QObject, QTimer

from ..modelo import datos
from ..modelo.api import ClienteApi, ErrorApi, ErrorConexion
from ..modelo.sesion import Sesion
from ..vista.historico import VistaHistorico
from ..vista.incidencia import DialogoIncidencia, VistaIncidencias
from ..vista.turno import VistaTurno
from ..vista.ventana_base import VentanaBase
from .supervisor import PERIODO_REFRESCO_MS, SIN_CONEXION

HORAS_GRAFICA = 7 * 24                 # el Técnico consulta como mucho 7 días


class ControladorTecnico(QObject):
    def __init__(self, api: ClienteApi, sesion: Sesion, ventana: VentanaBase, periodo_ms: int = PERIODO_REFRESCO_MS,
                 abrir_dialogo=None):
        super().__init__()
        self.api, self.sesion, self.ventana = api, sesion, ventana
        self.turno = VistaTurno()
        self.incidencias = VistaIncidencias()
        self.historico = VistaHistorico()
        ventana.registrar_vista("turno", self.turno)
        ventana.registrar_vista("incidencias", self.incidencias)
        ventana.registrar_vista("historico", self.historico)
        ventana.mostrar("turno")
        self.abrir_dialogo = abrir_dialogo or (lambda dialogo: dialogo.exec())
        self.dialogo: DialogoIncidencia | None = None

        self.turno.registrar.connect(self.registrar)
        self.turno.cambiar_estado.connect(self.cambiar_estado)
        self.turno.ver_sensor.connect(self.ver_sensor)
        self.incidencias.nueva.connect(lambda: self.registrar({"tipo": "inspeccion"}))
        self.historico.consultar.connect(self.consultar)
        self.historico.exportar.connect(lambda _p: self.historico.mostrar_error("Exportar a CSV es solo del Supervisor."))
        ventana.seccion_elegida.connect(self._al_cambiar_de_seccion)

        self._sensores: list[dict] = []
        self._tareas: list[dict] = []
        self.refrescar()
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._al_tic)
        self._reloj.start(periodo_ms)

    def detener(self) -> None:
        self._reloj.stop()

    def _mensaje(self, error: Exception) -> str:
        return error.mensaje if isinstance(error, ErrorApi) else SIN_CONEXION.format(servidor=self.api.servidor)

    # ── Mi turno ──
    def refrescar(self) -> None:
        try:
            ultimas = self.api.lecturas_ultimas()
            tareas = self.api.tareas()
            incidencias = self.api.incidencias()
        except (ErrorApi, ErrorConexion) as error:
            self.turno.mostrar_error(self._mensaje(error))
            return
        self.turno.mostrar_error(None)
        sensores = ultimas["sensores"]
        cambio = [s["tag"] for s in sensores] != [s["tag"] for s in self._sensores]
        self._sensores, self._tareas = sensores, tareas
        self.turno.poner_datos(ultimas)
        self.turno.poner_tareas(tareas)
        hoy = datetime.now().date()
        de_hoy = [i for i in incidencias if datos.fecha(i["creada_en"]).date() == hoy]
        self.turno.poner_resumen(sum(i["tipo"] != "lectura_manual" for i in de_hoy),
                                 sum(i["tipo"] == "lectura_manual" for i in de_hoy),
                                 sum(1 for t in tareas if t["cerrada_en"] and datos.fecha(t["cerrada_en"]).date() == hoy))
        self.incidencias.poner(incidencias)
        if cambio:
            self.historico.poner_sensores(sensores)
            self._grafica(sensores[-1]["tag"] if sensores else None)

    def _grafica(self, tag: str | None) -> None:
        if not tag:
            self.turno.poner_grafica(None)
            return
        try:
            self.turno.poner_grafica(self.api.historico(tag, HORAS_GRAFICA))
        except (ErrorApi, ErrorConexion):
            self.turno.poner_grafica(None)

    def cambiar_estado(self, tarea_id: int, estado: str) -> None:
        try:
            self.api.cambiar_estado_tarea(tarea_id, estado)
        except (ErrorApi, ErrorConexion) as error:
            self.turno.mostrar_error(self._mensaje(error))
            return
        self.refrescar()

    def ver_sensor(self, tag: str) -> None:
        self.ventana.mostrar("historico")
        self.historico.elegir_sensor(tag)
        self.historico.aplicar()

    # ── Registrar incidencia (ventana 08) ──
    def registrar(self, preset: dict) -> None:
        if not self._sensores:
            self.turno.mostrar_error("Tu supervisor todavía no te ha asignado sensores.")
            return
        self.dialogo = DialogoIncidencia(self.sesion.usuario, self._sensores, self._tareas, tag=preset.get("tag"),
                                         tarea_id=preset.get("tarea_id"), tipo=preset.get("tipo", "inspeccion"),
                                         parent=self.ventana)
        self.dialogo.guardar.connect(self.guardar)
        self.abrir_dialogo(self.dialogo)

    def guardar(self, datos_incidencia: dict) -> None:
        try:
            self.api.crear_incidencia(datos_incidencia)
        except (ErrorApi, ErrorConexion) as error:
            if self.dialogo:
                self.dialogo.mostrar_error(self._mensaje(error))
            return
        if self.dialogo:
            self.dialogo.accept()
        self.refrescar()

    # ── Histórico (7 días) ──
    def consultar(self, parametros: dict) -> None:
        vista = self.historico
        vista.ocupado(True)
        try:
            principal = self.api.historico(parametros["tag"], parametros["horas"] or 24, parametros["desde"],
                                           parametros["hasta"])
            comparado = (self.api.historico(parametros["comparar"], parametros["horas"] or 24, parametros["desde"],
                                            parametros["hasta"]) if parametros["comparar"] else None)
        except (ErrorApi, ErrorConexion) as error:
            vista.mostrar_error(self._mensaje(error))
            return
        finally:
            vista.ocupado(False)
        vista.poner_resultado(principal, comparado)

    # ── Refresco ──
    def _al_tic(self) -> None:
        if self.turno.isVisible() and not (self.dialogo and self.dialogo.isVisible()):
            self.refrescar()

    def _al_cambiar_de_seccion(self, clave: str) -> None:
        if clave in ("turno", "incidencias"):
            self.refrescar()
