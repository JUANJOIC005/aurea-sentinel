"""Ventana 03 · Verificación en dos pasos (mockup 03): seis casillas para el código de la aplicación autenticadora."""
import time

from PySide6.QtCore import QByteArray, QTimer, Qt, Signal
from PySide6.QtGui import QClipboard, QGuiApplication, QKeySequence, QPainter, QPixmap, QRegularExpressionValidator
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget)

from ..modelo.sesion import ROLES
from . import estilos, iconos
from .componentes import Avatar, IndicadorPasos, InsigniaRol, PanelMarca, etiqueta

PERIODO_CODIGO = 30           # el código cambia cada 30 s (igual que en el servidor)
CADUCIDAD_SESION = {"supervisor": 15, "auditor": 15, "administrador": 10}   # minutos, como en el servidor
DIGITOS = 6


class Casilla(QLineEdit):
    """Una casilla de un dígito. Avisa si se pulsa «borrar» estando vacía o si se pega un código."""
    retroceso = Signal()
    pegado = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaxLength(1)
        self.setFixedSize(46, 52)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setValidator(QRegularExpressionValidator(r"[0-9]", self))
        self.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {estilos.AZUL}; padding: 0;")

    def keyPressEvent(self, evento):
        if evento.matches(QKeySequence.StandardKey.Paste):
            self.pegado.emit(QGuiApplication.clipboard().text(QClipboard.Mode.Clipboard))
            return
        if evento.key() == Qt.Key.Key_Backspace and not self.text():
            self.retroceso.emit()
            return
        super().keyPressEvent(evento)


class CasillasCodigo(QWidget):
    """Seis casillas que se rellenan solas una tras otra. Admite pegar el código entero."""
    cambiado = Signal(str)
    entrar = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(8)
        self.casillas = [Casilla() for _ in range(DIGITOS)]
        for i, c in enumerate(self.casillas):
            c.textEdited.connect(lambda texto, i=i: self._escrito(i, texto))
            c.retroceso.connect(lambda i=i: self._retroceso(i))
            c.pegado.connect(self.poner)
            c.returnPressed.connect(self.entrar)
            fila.addWidget(c)
        fila.addStretch(1)

    def codigo(self) -> str:
        return "".join(c.text() for c in self.casillas)

    def completo(self) -> bool:
        return len(self.codigo()) == DIGITOS

    def poner(self, texto: str) -> None:
        """Rellena desde el principio con los dígitos de `texto` (ignora lo demás)."""
        digitos = "".join(ch for ch in texto if ch.isdigit())[:DIGITOS]
        for i, c in enumerate(self.casillas):
            c.setText(digitos[i] if i < len(digitos) else "")
        self.casillas[min(len(digitos), DIGITOS - 1)].setFocus()
        self.cambiado.emit(self.codigo())

    def limpiar(self) -> None:
        for c in self.casillas:
            c.clear()
        self.casillas[0].setFocus()
        self.cambiado.emit("")

    def bloquear(self, bloqueado: bool) -> None:
        for c in self.casillas:
            c.setEnabled(not bloqueado)

    def _escrito(self, i: int, texto: str) -> None:
        if texto and i < DIGITOS - 1:
            self.casillas[i + 1].setFocus()
            self.casillas[i + 1].selectAll()
        self.cambiado.emit(self.codigo())

    def _retroceso(self, i: int) -> None:
        if i > 0:
            self.casillas[i - 1].setFocus()
            self.casillas[i - 1].clear()
            self.cambiado.emit(self.codigo())


def pixmap_desde_svg(svg: str, lado: int, escala: float = 2.0) -> QPixmap:
    px = QPixmap(int(lado * escala), int(lado * escala))
    px.fill(Qt.GlobalColor.white)
    pintor = QPainter(px)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(pintor)
    pintor.end()
    px.setDevicePixelRatio(escala)
    return px


class VistaVerificacion(QWidget):
    verificar = Signal(str)           # código de 6 dígitos
    cambiar_usuario = Signal()        # «¿No eres tú? Cambiar»: vuelve al paso 1

    def __init__(self, parent=None):
        super().__init__(parent)
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(PanelMarca(
            "Verificación en dos pasos",
            "La contraseña es correcta. Falta confirmar que eres tú con el código de 6 dígitos de tu aplicación "
            "autenticadora (TOTP).",
            ["El código cambia cada 30 segundos",
             "Tres códigos erróneos te devuelven al paso 1 y quedan anotados",
             "Solo Supervisor, Auditor y Administrador usan este segundo paso"],
            "El código cambia cada 30 segundos. Tres códigos erróneos devuelven al paso 1 y generan un evento "
            "de seguridad.",
        ), 45)

        derecha = QWidget()
        derecha.setObjectName("PanelFormulario")
        derecha.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        centro = QVBoxLayout(derecha)
        centro.addStretch(1)
        formulario = QWidget()
        formulario.setFixedWidth(400)
        self.caja = QVBoxLayout(formulario)
        self.caja.setContentsMargins(0, 0, 0, 0)
        self.caja.setSpacing(0)
        centro.addWidget(formulario, 0, Qt.AlignmentFlag.AlignHCenter)
        centro.addStretch(1)
        raiz.addWidget(derecha, 55)

        self.caja.addWidget(IndicadorPasos(["Credenciales", "Código MFA"], actual=2))
        self.caja.addSpacing(16)

        # Tarjeta con quién es la persona (nombre, rol y área) antes de pedir el código
        self.tarjeta = QFrame()
        self.tarjeta.setObjectName("Tarjeta")
        fila = QHBoxLayout(self.tarjeta)
        fila.setContentsMargins(12, 10, 14, 10)
        fila.setSpacing(10)
        self.avatar_sitio = QVBoxLayout()
        fila.addLayout(self.avatar_sitio)
        datos = QVBoxLayout()
        datos.setSpacing(3)
        self.nombre = QLabel()
        self.nombre.setStyleSheet(f"font-family: {estilos.FUENTE_TITULOS}; font-size: 14px; font-weight: 700;")
        self.insignia_sitio = QHBoxLayout()
        self.insignia_sitio.setSpacing(6)
        self.area = etiqueta("", "Suave")
        self.area.setWordWrap(True)
        self.insignia_sitio.addWidget(self.area, 1)
        self.insignia_sitio.addStretch(1)
        datos.addWidget(self.nombre)
        datos.addLayout(self.insignia_sitio)
        fila.addLayout(datos, 1)
        cambio = QVBoxLayout()
        cambio.setSpacing(0)
        cambio.addWidget(etiqueta("¿No eres tú?", "Suave"))
        self.cambiar = QPushButton("Cambiar")
        self.cambiar.setObjectName("Enlace")
        self.cambiar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cambiar.clicked.connect(self.cambiar_usuario)
        cambio.addWidget(self.cambiar)
        fila.addLayout(cambio)
        self.caja.addWidget(self.tarjeta)
        self.caja.addSpacing(18)

        self.titulo = etiqueta("Introduce el código", "H1")
        self.caja.addWidget(self.titulo)
        self.caja.addSpacing(10)

        # Solo la primera vez: QR para la aplicación autenticadora
        self.bloque_qr = QFrame()
        self.bloque_qr.setObjectName("Tarjeta")
        qr = QHBoxLayout(self.bloque_qr)
        qr.setContentsMargins(12, 12, 12, 12)
        qr.setSpacing(14)
        self.imagen_qr = QLabel()
        self.imagen_qr.setFixedSize(150, 150)
        self.imagen_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr.addWidget(self.imagen_qr)
        pasos = QVBoxLayout()
        pasos.setSpacing(6)
        instrucciones = QLabel("1. Abre Google Authenticator, Microsoft Authenticator u otra aplicación TOTP.<br>"
                               "2. Escanea este código QR.<br>3. Escribe abajo el código de 6 dígitos que muestra.")
        instrucciones.setWordWrap(True)
        instrucciones.setStyleSheet("font-size: 12px;")
        self.clave = QLabel()
        self.clave.setWordWrap(True)
        self.clave.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.clave.setStyleSheet(f"font-family: {estilos.FUENTE_MONO}; font-size: 11px; color: {estilos.TEXTO_SUAVE};")
        pasos.addWidget(instrucciones)
        sin_camara = etiqueta("¿No puedes escanearlo? Escribe esta clave:", "Suave")
        sin_camara.setWordWrap(True)
        pasos.addWidget(sin_camara)
        pasos.addWidget(self.clave)
        pasos.addStretch(1)
        qr.addLayout(pasos, 1)
        self.caja.addWidget(self.bloque_qr)
        self.caja.addSpacing(10)

        self.aviso = QLabel()
        self.aviso.setWordWrap(True)
        self.aviso.hide()
        self.caja.addWidget(self.aviso)

        self.casillas = CasillasCodigo()
        self.caja.addWidget(self.casillas)
        self.caja.addSpacing(8)
        reloj = QHBoxLayout()
        reloj.setSpacing(6)
        icono = QLabel()
        icono.setPixmap(iconos.pixmap("reloj", estilos.TEXTO_SUAVE, 14))
        self.cuenta_atras = etiqueta("", "Suave")
        reloj.addWidget(icono)
        reloj.addWidget(self.cuenta_atras)
        reloj.addStretch(1)
        self.caja.addLayout(reloj)
        self.caja.addSpacing(14)

        self.boton = QPushButton("Verificar y entrar")
        self.boton.setObjectName("Primario")
        self.boton.setDefault(True)
        self.boton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton.setEnabled(False)
        self.boton.clicked.connect(self._enviar)
        self.caja.addWidget(self.boton)
        self.caja.addSpacing(14)

        self.caducidad = QLabel()
        self.caducidad.setObjectName("AvisoInfo")
        self.caducidad.setWordWrap(True)
        self.caja.addWidget(self.caducidad)

        self.casillas.cambiado.connect(lambda codigo: self.boton.setEnabled(len(codigo) == DIGITOS))
        self.casillas.entrar.connect(self._enviar)
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self.actualizar_cuenta_atras)
        self.modo_codigo()
        self.actualizar_cuenta_atras()

    # ── Lo que la ventana ofrece al controlador ──
    def poner_identidad(self, usuario: dict) -> None:
        """`usuario` es el perfil que devuelve el servidor tras acertar la contraseña (nombre, rol y área)."""
        rol = usuario["rol"]
        while self.avatar_sitio.count():
            viejo = self.avatar_sitio.takeAt(0).widget()
            viejo.setParent(None)                      # sale ya de la pantalla (deleteLater tarda en actuar)
            viejo.deleteLater()
        iniciales = "".join(p[0] for p in usuario["nombre"].split()[:2]).upper()
        self.avatar_sitio.addWidget(Avatar(iniciales, estilos.COLOR_ROL[rol], 40))
        for i in range(self.insignia_sitio.count() - 1, -1, -1):
            elemento = self.insignia_sitio.itemAt(i).widget()
            if isinstance(elemento, InsigniaRol):
                viejo = self.insignia_sitio.takeAt(i).widget()
                viejo.setParent(None)
                viejo.deleteLater()
        self.insignia_sitio.insertWidget(0, InsigniaRol(rol, ROLES[rol]))
        self.nombre.setText(usuario["nombre"])
        area = usuario.get("area")
        self.area.setText(f"{area['codigo']} · {area['nombre']}" if area else "Todas las áreas")
        minutos = CADUCIDAD_SESION.get(rol, 15)
        self.caducidad.setText(f"Tu sesión caducará tras {minutos} min (valor fijado para el rol {ROLES[rol]}).")

    def modo_codigo(self) -> None:
        self.titulo.setText("Introduce el código")
        self.bloque_qr.hide()

    def modo_configuracion(self, secreto: str, qr_svg: str) -> None:
        """Primera vez: se enseña el QR y la clave para dar de alta la aplicación autenticadora."""
        self.titulo.setText("Configura tu aplicación autenticadora")
        self.imagen_qr.setPixmap(pixmap_desde_svg(qr_svg, 150))
        self.clave.setText(" ".join(secreto[i:i + 4] for i in range(0, len(secreto), 4)))
        self.bloque_qr.show()

    def mostrar_error(self, mensaje: str) -> None:
        self._aviso("AvisoError", mensaje)

    def ocultar_aviso(self) -> None:
        self.aviso.hide()

    def ocupado(self, ocupado: bool) -> None:
        self.boton.setText("Comprobando…" if ocupado else "Verificar y entrar")
        self.casillas.bloquear(ocupado)
        self.boton.setEnabled(not ocupado and self.casillas.completo())
        self.cambiar.setEnabled(not ocupado)

    def limpiar(self) -> None:
        self.casillas.limpiar()
        self.ocultar_aviso()
        self.modo_codigo()

    def actualizar_cuenta_atras(self) -> None:
        self.cuenta_atras.setText(f"Código válido durante {PERIODO_CODIGO - int(time.time() % PERIODO_CODIGO)} s")

    # ── Internos ──
    def _aviso(self, nombre: str, mensaje: str) -> None:
        self.aviso.setObjectName(nombre)
        self.aviso.setText(mensaje)
        self.aviso.style().unpolish(self.aviso)
        self.aviso.style().polish(self.aviso)
        self.aviso.show()

    def _enviar(self) -> None:
        if self.casillas.completo():
            self.verificar.emit(self.casillas.codigo())

    def showEvent(self, evento):
        super().showEvent(evento)
        self._reloj.start(1000)
        self.actualizar_cuenta_atras()
        self.casillas.casillas[0].setFocus()

    def hideEvent(self, evento):
        super().hideEvent(evento)
        self._reloj.stop()
