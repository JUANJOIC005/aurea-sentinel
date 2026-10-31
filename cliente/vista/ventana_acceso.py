"""Ventana de acceso: aloja el login y el registro, con la barra de estado de los mockups."""
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from . import iconos
from .componentes import BarraEstado
from .login import VistaLogin
from .registro import VistaRegistro

VERSION = "AUREA Sentinel 0.1"


class VentanaAcceso(QMainWindow):
    def __init__(self, servidor: str):
        super().__init__()
        self.setWindowTitle("AUREA Sentinel — Acceso · Central Nuclear Valdecierzo")
        self.setWindowIcon(QIcon(iconos.isotipo(64)))
        self.setMinimumSize(1024, 640)
        self.resize(1100, 700)
        self._servidor = servidor

        self.login = VistaLogin()
        self.registro = VistaRegistro()
        self.paginas = QStackedWidget()
        self.paginas.addWidget(self.login)
        self.paginas.addWidget(self.registro)
        self.barra = BarraEstado()

        central = QWidget()
        caja = QVBoxLayout(central)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(0)
        caja.addWidget(self.paginas, 1)
        caja.addWidget(self.barra)
        self.setCentralWidget(central)
        self.actualizar_conexion(None)

    def mostrar_login(self) -> None:
        self.setWindowTitle("AUREA Sentinel — Acceso · Central Nuclear Valdecierzo")
        self.paginas.setCurrentWidget(self.login)

    def mostrar_registro(self) -> None:
        self.setWindowTitle("AUREA Sentinel — Solicitar acceso · Central Nuclear Valdecierzo")
        self.paginas.setCurrentWidget(self.registro)

    def actualizar_conexion(self, conectado: bool | None) -> None:
        self.barra.poner(conectado, "Sin sesión iniciada", VERSION)
