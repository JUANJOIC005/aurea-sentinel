"""Ventana de acceso: aloja el login y el registro, con la barra de estado de los mockups."""
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from ..modelo.sesion import ROLES
from . import iconos
from .componentes import BarraEstado
from .login import VistaLogin
from .registro import VistaRegistro
from .verificacion import CADUCIDAD_SESION, VistaVerificacion

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
        self.verificacion = VistaVerificacion()
        self.paginas = QStackedWidget()
        self.paginas.addWidget(self.login)
        self.paginas.addWidget(self.registro)
        self.paginas.addWidget(self.verificacion)
        self._conectado: bool | None = None
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
        self.actualizar_conexion(self._conectado)

    def mostrar_verificacion(self, usuario: dict) -> None:
        """Paso 2 del acceso. Desde aquí ya hay una persona identificada: su nombre y rol salen en la barra."""
        self.setWindowTitle("AUREA Sentinel — Verificación MFA · Central Nuclear Valdecierzo")
        self.verificacion.limpiar()
        self.verificacion.poner_identidad(usuario)
        self.paginas.setCurrentWidget(self.verificacion)
        area, rol = usuario.get("area"), usuario["rol"]
        zona = f"{area['codigo']} · {area['nombre']}" if area else "Todas las áreas"
        self.barra.poner(self._conectado,
                         f"Conectado a <b>{self._servidor}</b> &nbsp;·&nbsp; Usuario: <b>{usuario['nombre']}</b> · "
                         f"{ROLES[rol]} · {zona}",
                         f"{VERSION} · sesión caduca en {CADUCIDAD_SESION.get(rol, 15)} min")

    def mostrar_registro(self) -> None:
        self.setWindowTitle("AUREA Sentinel — Solicitar acceso · Central Nuclear Valdecierzo")
        self.paginas.setCurrentWidget(self.registro)

    def actualizar_conexion(self, conectado: bool | None) -> None:
        self._conectado = conectado
        if self.paginas.currentWidget() is self.verificacion:
            return                       # en el paso 2 la barra ya enseña quién es la persona
        self.barra.poner(conectado, "Sin sesión iniciada", VERSION)
