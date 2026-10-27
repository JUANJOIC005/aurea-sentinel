"""Arranque de la aplicación y paso entre ventanas (acceso ↔ ventana con sesión)."""
import os
import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from ..modelo.api import ClienteApi
from ..modelo.sesion import Sesion
from ..vista import estilos
from ..vista.ventana_acceso import VentanaAcceso
from ..vista.ventana_base import VentanaBase
from .acceso import ControladorAcceso
from .sesion import ControladorSesion


class Aplicacion:
    def __init__(self, api: ClienteApi | None = None):
        self.api = api or ClienteApi()
        self.acceso = VentanaAcceso(self.api.servidor)
        self.control_acceso = ControladorAcceso(self.api, self.acceso)
        self.control_acceso.sesion_iniciada.connect(self.abrir_sesion)
        self.base: VentanaBase | None = None
        self.control_sesion: ControladorSesion | None = None
        self._tic = QTimer()
        self._tic.timeout.connect(self._comprobar_servidor_en_acceso)

    def iniciar(self) -> None:
        self.acceso.show()
        self._comprobar_servidor_en_acceso()
        self._tic.start(15_000)

    def _comprobar_servidor_en_acceso(self) -> None:
        if self.acceso.isVisible():
            self.acceso.actualizar_conexion(self.api.salud())

    def abrir_sesion(self, sesion: Sesion) -> None:
        self._tic.stop()
        self.base = VentanaBase(sesion, self.api.servidor)
        self.control_sesion = ControladorSesion(self.api, sesion, self.base)
        self.control_sesion.sesion_cerrada.connect(self.cerrar_sesion)
        self.acceso.hide()
        self.base.show()

    def cerrar_sesion(self, motivo: str) -> None:
        # Primero se enseña el acceso: si se cerrara antes la ventana base, Qt cerraría la aplicación.
        self.acceso.mostrar_login()
        self.acceso.login.limpiar()
        if motivo:
            self.acceso.login.mostrar_error(motivo)
        self.acceso.show()
        if self.base is not None:
            self.base.close()
            self.base.deleteLater()
            self.base = None
        self.control_sesion = None
        self._comprobar_servidor_en_acceso()
        self._tic.start(15_000)


    def al_salir(self) -> None:
        """Si se cierra la aplicación con la sesión abierta, se cierra también en el servidor."""
        if self.control_sesion is not None:
            self.control_sesion.cerrar()


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("AUREA Sentinel")
    app.setOrganizationName("AUREA AUDIT")
    app.setStyleSheet(estilos.HOJA)
    servidor = None
    if not os.environ.get("AUREA_API_URL"):    # sin servidor indicado, la aplicación lleva el suyo (local)
        try:
            from servidor.local import iniciar
            servidor = iniciar()
        except Exception as error:
            QMessageBox.critical(None, "AUREA Sentinel", f"No se ha podido preparar la aplicación:\n{error}")
            return 1
    aplicacion = Aplicacion(ClienteApi(servidor.url) if servidor else None)
    app.aboutToQuit.connect(aplicacion.al_salir)
    aplicacion.iniciar()
    codigo = app.exec()
    if servidor:
        servidor.parar()
    return codigo
