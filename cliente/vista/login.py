"""Ventana 01 · Iniciar sesión (mockup 01)."""
from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QWidget)

from . import estilos, iconos
from .componentes import PanelMarca, etiqueta


class VistaLogin(QWidget):
    entrar = Signal(str, str, bool)      # correo, contraseña, equipo compartido
    solicitar_acceso = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        raiz.addWidget(PanelMarca(
            "AUREA Sentinel\nSupervisión y auditoría de la Central Nuclear Valdecierzo",
            "Una aplicación de AUREA AUDIT para consultar los datos de los sensores de la central "
            "y comprobar quién ha accedido a qué.",
            ["Cada persona ve solo los datos de su área",
             "Cuentas personales con permisos según el puesto",
             "Registro de actividad para las auditorías"],
            "© 2026 AUREA AUDIT · Auditoría tecnológica. Uso exclusivo de personal autorizado: "
            "los accesos quedan registrados.",
        ), 45)

        derecha = QWidget()
        derecha.setObjectName("PanelFormulario")
        derecha.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        centro = QVBoxLayout(derecha)
        centro.addStretch(1)
        formulario = QWidget()
        formulario.setFixedWidth(380)
        caja = QVBoxLayout(formulario)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(0)
        centro.addWidget(formulario, 0, Qt.AlignmentFlag.AlignHCenter)
        centro.addStretch(1)
        raiz.addWidget(derecha, 55)

        caja.addWidget(etiqueta("Iniciar sesión", "H1"))
        caja.addSpacing(16)

        self.aviso = QLabel()
        self.aviso.setWordWrap(True)
        self.aviso.hide()
        caja.addWidget(self.aviso)

        caja.addWidget(etiqueta("Correo", "Etiqueta"))
        caja.addSpacing(4)
        self.correo = QLineEdit()
        self.correo.setPlaceholderText("nombre.apellido@cn-valdecierzo.es")
        caja.addWidget(self.correo)
        caja.addSpacing(12)

        caja.addWidget(etiqueta("Contraseña", "Etiqueta"))
        caja.addSpacing(4)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self._ojo = QAction(iconos.icono("ojo", estilos.TEXTO_SUAVE, 16), "Mostrar la contraseña", self.password)
        self._ojo.triggered.connect(self._alternar_password)
        self.password.addAction(self._ojo, QLineEdit.ActionPosition.TrailingPosition)
        caja.addWidget(self.password)
        caja.addSpacing(10)

        self.compartido = QCheckBox("Equipo compartido")
        caja.addWidget(self.compartido)
        caja.addSpacing(16)

        self.boton = QPushButton("Iniciar sesión")
        self.boton.setObjectName("Primario")
        self.boton.setDefault(True)
        self.boton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton.clicked.connect(self._enviar)
        caja.addWidget(self.boton)
        caja.addSpacing(14)

        enlaces = QHBoxLayout()
        olvido = QPushButton("¿Has olvidado la contraseña?")
        olvido.setObjectName("Enlace")
        olvido.setCursor(Qt.CursorShape.PointingHandCursor)
        olvido.clicked.connect(self._olvido)
        registrar = QPushButton("Solicitar acceso")
        registrar.setObjectName("Enlace")
        registrar.setCursor(Qt.CursorShape.PointingHandCursor)
        registrar.clicked.connect(self.solicitar_acceso)
        enlaces.addWidget(olvido)
        enlaces.addStretch(1)
        enlaces.addWidget(registrar)
        caja.addLayout(enlaces)

        self.password.returnPressed.connect(self._enviar)
        self.correo.returnPressed.connect(self.password.setFocus)
        self._recordar_usuario()

    # ── Lo que la ventana ofrece al controlador ──
    def mostrar_error(self, mensaje: str) -> None:
        self._aviso("AvisoError", mensaje)

    def mostrar_info(self, mensaje: str) -> None:
        self._aviso("AvisoOk", mensaje)

    def ocultar_aviso(self) -> None:
        self.aviso.hide()

    def ocupado(self, ocupado: bool) -> None:
        self.boton.setEnabled(not ocupado)
        self.boton.setText("Comprobando…" if ocupado else "Iniciar sesión")

    def limpiar(self) -> None:
        self.password.clear()
        self.ocultar_aviso()
        self._recordar_usuario()
        (self.password if self.correo.text() else self.correo).setFocus()

    # ── Internos ──
    def _aviso(self, nombre: str, mensaje: str) -> None:
        self.aviso.setObjectName(nombre)
        self.aviso.setText(mensaje)
        self.aviso.style().unpolish(self.aviso)   # para que Qt relea el estilo del nuevo nombre
        self.aviso.style().polish(self.aviso)
        self.aviso.show()

    def _alternar_password(self) -> None:
        visible = self.password.echoMode() == QLineEdit.EchoMode.Password
        self.password.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)
        self._ojo.setIcon(iconos.icono("ojo_cerrado" if visible else "ojo", estilos.TEXTO_SUAVE, 16))

    def _olvido(self) -> None:
        self._aviso("AvisoInfo", "Pide a un administrador que restablezca tu contraseña. "
                                 "La recuperación automática no está disponible todavía.")

    def _enviar(self) -> None:
        self.entrar.emit(self.correo.text().strip(), self.password.text(), self.compartido.isChecked())

    def _recordar_usuario(self) -> None:
        recordado = QSettings("AUREA AUDIT", "AUREA Sentinel").value("ultimo_correo", "")
        if recordado and not self.compartido.isChecked():
            self.correo.setText(str(recordado))
