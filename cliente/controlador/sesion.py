"""Controlador de la sesión abierta: caducidad, estado de la conexión y cierre de sesión."""
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from ..modelo.api import ClienteApi, ErrorApi, ErrorConexion
from ..modelo.sesion import Sesion
from ..vista.ventana_base import VentanaBase

PERIODO_CADUCIDAD_MS = 15_000     # cada cuánto se refresca «sesión caduca en…»
PERIODO_CONEXION_MS = 15_000      # cada cuánto se comprueba que el servidor responde


class ControladorSesion(QObject):
    sesion_cerrada = Signal(str)   # motivo para enseñar en el login ("" si se cerró a propósito)

    def __init__(self, api: ClienteApi, sesion: Sesion, ventana: VentanaBase):
        super().__init__()
        self.api, self.sesion, self.ventana = api, sesion, ventana
        ventana.cierre_pedido.connect(self.cerrar)
        self._cerrada = False

        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self.refrescar_caducidad)
        self._reloj.start(PERIODO_CADUCIDAD_MS)
        self._conexion = QTimer(self)
        self._conexion.timeout.connect(self.comprobar_conexion)
        self._conexion.start(PERIODO_CONEXION_MS)
        self.comprobar_conexion()
        self.refrescar_caducidad()

    def comprobar_conexion(self) -> None:
        self.ventana.poner_conexion(self.api.salud(), datetime.now())

    def refrescar_caducidad(self, ahora: datetime | None = None) -> None:
        if self.sesion.segundos_restantes(ahora) <= 0:
            self._terminar("Tu sesión ha caducado. Vuelve a iniciar sesión.")
            return
        self.ventana.poner_caducidad(self.sesion.minutos_restantes(ahora))

    def cerrar(self) -> None:
        """El usuario pulsa «Cerrar sesión»: se avisa al servidor y se vuelve al login."""
        try:
            self.api.logout()
        except (ErrorApi, ErrorConexion):
            pass  # aunque el servidor no conteste, en este equipo la sesión se cierra igual
        self._terminar("")

    def _terminar(self, motivo: str) -> None:
        if self._cerrada:
            return
        self._cerrada = True
        self._reloj.stop()
        self._conexion.stop()
        self.api.usar_token(None)
        self.sesion_cerrada.emit(motivo)
