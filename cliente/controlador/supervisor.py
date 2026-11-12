"""Controlador del Supervisor: conecta el panel (ventana 04) y el histórico (ventana 05) con el servidor."""
from pathlib import Path

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QFileDialog

from ..modelo.api import ClienteApi, ErrorApi, ErrorConexion
from ..modelo.sesion import Sesion
from ..vista.historico import VistaHistorico
from ..vista.panel import VistaPanel
from ..vista.ventana_base import VentanaBase

PERIODO_REFRESCO_MS = 5_000        # los datos del panel se refrescan cada 5 s
SIN_CONEXION = "No se puede conectar con el servidor ({servidor}). Se volverá a intentar solo."


def elegir_archivo_csv(nombre: str) -> str:
    ruta, _ = QFileDialog.getSaveFileName(None, "Exportar histórico", nombre, "CSV (*.csv)")
    return ruta


class ControladorSupervisor(QObject):
    def __init__(self, api: ClienteApi, sesion: Sesion, ventana: VentanaBase, elegir_archivo=elegir_archivo_csv,
                 periodo_ms: int = PERIODO_REFRESCO_MS):
        super().__init__()
        self.api, self.sesion, self.ventana = api, sesion, ventana
        self.elegir_archivo = elegir_archivo
        area = sesion.usuario.area
        self.panel = VistaPanel(area.codigo if area else "")
        self.historico = VistaHistorico()
        ventana.registrar_vista("panel", self.panel)
        ventana.registrar_vista("historico", self.historico)
        ventana.mostrar("panel")

        self.panel.abrir_historico.connect(self.abrir_historico)
        self.panel.filtro_alarmas.connect(self.cambiar_filtro)
        self.historico.consultar.connect(self.consultar)
        self.historico.exportar.connect(self.exportar)
        ventana.seccion_elegida.connect(self._al_cambiar_de_seccion)

        self._etiquetas: list[str] = []
        self.refrescar()
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._al_tic)
        self._reloj.start(periodo_ms)

    def detener(self) -> None:
        self._reloj.stop()

    # ── Panel ──
    def refrescar(self) -> None:
        try:
            ultimas = self.api.lecturas_ultimas()
            alarmas = self.api.alarmas(self.panel.filtro_actual())
            equipo = self.api.equipo()
        except ErrorApi as error:
            self.panel.mostrar_error(error.mensaje)
            return
        except ErrorConexion:
            self.panel.mostrar_error(SIN_CONEXION.format(servidor=self.api.servidor))
            return
        self.panel.mostrar_error(None)
        self.panel.poner_datos(ultimas)
        self.panel.poner_alarmas(alarmas)
        self.panel.poner_equipo(equipo)
        etiquetas = [s["tag"] for s in ultimas["sensores"]]
        if etiquetas != self._etiquetas:             # el histórico ofrece los mismos sensores que el panel
            self._etiquetas = etiquetas
            self.historico.poner_sensores(ultimas["sensores"])

    def cambiar_filtro(self, _filtro: str) -> None:
        try:
            self.panel.poner_alarmas(self.api.alarmas(self.panel.filtro_actual()))
        except ErrorApi as error:
            self.panel.mostrar_error(error.mensaje)
        except ErrorConexion:
            self.panel.mostrar_error(SIN_CONEXION.format(servidor=self.api.servidor))

    def _al_tic(self) -> None:
        if self.panel.isVisible():
            self.refrescar()

    def _al_cambiar_de_seccion(self, clave: str) -> None:
        if clave == "panel":
            self.refrescar()

    # ── Histórico ──
    def abrir_historico(self, tag: str) -> None:
        """Se pulsa un sensor del panel: se abre su histórico (últimos 7 días, o el periodo que esté elegido)."""
        self.ventana.mostrar("historico")
        self.historico.elegir_sensor(tag)
        self.historico.aplicar()

    def consultar(self, parametros: dict) -> None:
        vista = self.historico
        vista.ocupado(True)
        try:
            principal = self._pedir(parametros["tag"], parametros)
            comparado = self._pedir(parametros["comparar"], parametros) if parametros["comparar"] else None
        except ErrorApi as error:
            vista.mostrar_error(error.mensaje)
            return
        except ErrorConexion:
            vista.mostrar_error(SIN_CONEXION.format(servidor=self.api.servidor))
            return
        finally:
            vista.ocupado(False)
        vista.poner_resultado(principal, comparado)

    def _pedir(self, tag: str, p: dict) -> dict:
        return self.api.historico(tag, p["horas"] or 24, p["desde"], p["hasta"])

    def exportar(self, parametros: dict) -> None:
        vista = self.historico
        try:
            contenido = self.api.historico_csv(parametros["tag"], parametros["horas"] or 24,
                                               parametros["desde"], parametros["hasta"])
        except ErrorApi as error:
            vista.mostrar_error(error.mensaje)
            return
        except ErrorConexion:
            vista.mostrar_error(SIN_CONEXION.format(servidor=self.api.servidor))
            return
        ruta = self.elegir_archivo(f"historico_{parametros['tag']}.csv")
        if not ruta:
            return                                  # la persona canceló
        Path(ruta).write_bytes(contenido)
        filas = max(0, contenido.decode("utf-8-sig").count("\n") - 1)
        vista.mostrar_info(f"Exportado {filas} filas a {ruta}. La exportación queda en el registro de auditoría.")
