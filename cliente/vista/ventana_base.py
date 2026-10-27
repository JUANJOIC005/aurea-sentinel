"""VentanaBase: estructura común de las 11 ventanas con sesión (mockups SV-2 y 04).

    barra de título · menú lateral (con pie de usuario) · cabecera (título, «Datos en vivo», campana,
    avatar con nombre y rol) · contenido · barra de estado

Todas las vistas del producto se colocan dentro del contenedor central.
"""
from datetime import datetime

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from ..modelo.menus import MENUS, Seccion
from ..modelo.sesion import Sesion
from . import estilos, iconos
from .componentes import Avatar, BarraEstado, InsigniaRol, etiqueta

VERSION = "AUREA Sentinel 0.1"


class VistaPendiente(QWidget):
    """Marcador de una ventana que se construye en un sprint posterior."""

    def __init__(self, seccion: Seccion, sesion: Sesion):
        super().__init__()
        caja = QVBoxLayout(self)
        caja.setContentsMargins(0, 0, 0, 0)
        tarjeta = QFrame()
        tarjeta.setObjectName("Tarjeta")
        interior = QVBoxLayout(tarjeta)
        interior.setContentsMargins(26, 22, 26, 22)
        interior.setSpacing(8)
        interior.addWidget(etiqueta(f"Ventana {seccion.ventana} · {seccion.texto}", "H2"))
        interior.addWidget(etiqueta(f"Esta ventana se construye en el {seccion.sprint} (ver backlog).", "Suave"))
        interior.addSpacing(10)
        interior.addWidget(etiqueta("SESIÓN INICIADA", "Mayusculas"))
        u = sesion.usuario
        datos = [("Nombre", u.nombre), ("Rol", u.rol_visible), ("Área", u.area_visible)]
        if u.supervisor:
            datos.append(("Supervisor", u.supervisor))
        for clave, valor in datos:
            fila = QLabel(f"<span style='color:{estilos.TEXTO_SUAVE}'>{clave}:</span>&nbsp; <b>{valor}</b>")
            interior.addWidget(fila)
        caja.addWidget(tarjeta)
        caja.addStretch(1)


class MenuLateral(QFrame):
    seleccionada = Signal(str)
    cerrar_sesion = Signal()

    def __init__(self, sesion: Sesion):
        super().__init__()
        self.setObjectName("MenuLateral")
        self._sesion = sesion
        self._botones: dict[str, QPushButton] = {}
        self._textos: dict[QPushButton, str] = {}
        self._reducido = False

        caja = QVBoxLayout(self)
        caja.setContentsMargins(12, 16, 12, 14)
        caja.setSpacing(2)

        # Logo
        fila_logo = QHBoxLayout()
        fila_logo.setContentsMargins(4, 0, 0, 0)
        logo = QLabel()
        logo.setPixmap(iconos.isotipo(30))
        self.nombre_app = QLabel("<b style='font-size:14px; color:%s'>AUREA Sentinel</b><br>"
                                 "<span style='font-size:9px; letter-spacing:1px; color:%s'>CENTRAL VALDECIERZO</span>"
                                 % (estilos.AZUL, estilos.TEXTO_SUAVE))
        fila_logo.addWidget(logo)
        fila_logo.addWidget(self.nombre_app, 1)
        caja.addLayout(fila_logo)
        caja.addSpacing(18)

        # Secciones
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        self._rotulos: list[QLabel] = []
        grupo_actual = None
        for seccion in MENUS[sesion.usuario.rol]:
            if seccion.grupo != grupo_actual:
                grupo_actual = seccion.grupo
                rotulo = etiqueta(seccion.grupo, "Mayusculas")
                rotulo.setContentsMargins(6, 8, 0, 4)
                self._rotulos.append(rotulo)
                caja.addWidget(rotulo)
            boton = QPushButton(f"  {seccion.texto}")
            boton.setObjectName("ItemMenu")
            boton.setCheckable(True)
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.setToolTip(seccion.texto)
            boton.setIconSize(QSize(18, 18))
            self._icono(boton, seccion.icono, False)
            boton.toggled.connect(lambda marcado, b=boton, i=seccion.icono: self._icono(b, i, marcado))
            boton.clicked.connect(lambda _=False, clave=seccion.clave: self.seleccionada.emit(clave))
            self._grupo.addButton(boton)
            self._botones[seccion.clave] = boton
            self._textos[boton] = f"  {seccion.texto}"
            caja.addWidget(boton)
        caja.addStretch(1)

        # Pie: quién está conectado
        self.pie = QWidget()
        pie = QVBoxLayout(self.pie)
        pie.setContentsMargins(4, 0, 0, 0)
        pie.setSpacing(4)
        u = sesion.usuario
        pie.addWidget(etiqueta(f"Conectado como <b>{u.nombre}</b>", "Suave"))
        pie.itemAt(0).widget().setWordWrap(True)
        pie.addWidget(InsigniaRol(u.rol, u.rol_visible))
        pie.addWidget(etiqueta(u.area_visible, "Suave"))
        self.caduca = etiqueta("", "Suave")
        pie.addWidget(self.caduca)
        salir = QPushButton("  Cerrar sesión")
        salir.setObjectName("CerrarSesion")
        salir.setIcon(iconos.icono("salir", estilos.TEXTO, 16))
        salir.setCursor(Qt.CursorShape.PointingHandCursor)
        salir.clicked.connect(self.cerrar_sesion)
        pie.addWidget(salir)
        self.boton_salir = salir
        caja.addWidget(self.pie)
        self.fijar_ancho(False)

    def _icono(self, boton: QPushButton, nombre: str, marcado: bool) -> None:
        boton.setIcon(iconos.icono(nombre, estilos.BLANCO if marcado else estilos.ACERO, 18))

    def marcar(self, clave: str) -> None:
        self._botones[clave].setChecked(True)

    def poner_caducidad(self, texto: str) -> None:
        self.caduca.setText(texto)

    def fijar_ancho(self, reducido: bool) -> None:
        """Menú completo (224 px) o solo iconos (68 px, ventanas pequeñas)."""
        self._reducido = reducido
        self.setFixedWidth(estilos.ANCHO_MENU_REDUCIDO if reducido else estilos.ANCHO_MENU)
        self.nombre_app.setVisible(not reducido)
        self.pie.setVisible(not reducido)
        for rotulo in self._rotulos:
            rotulo.setVisible(not reducido)
        for boton, texto in self._textos.items():
            boton.setText("" if reducido else texto)


class Cabecera(QWidget):
    def __init__(self, sesion: Sesion):
        super().__init__()
        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(12)
        textos = QVBoxLayout()
        textos.setSpacing(1)
        self.titulo = etiqueta("", "H1")
        self.contexto = etiqueta("", "Suave")
        textos.addWidget(self.titulo)
        textos.addWidget(self.contexto)
        fila.addLayout(textos, 1)

        self.chip = QFrame()
        self.chip.setObjectName("Chip")
        chip = QHBoxLayout(self.chip)
        chip.setContentsMargins(10, 4, 12, 4)
        self.texto_chip = QLabel()
        self.texto_chip.setStyleSheet("font-size: 11px;")
        self.texto_chip.setTextFormat(Qt.TextFormat.RichText)
        chip.addWidget(self.texto_chip)
        fila.addWidget(self.chip, 0, Qt.AlignmentFlag.AlignVCenter)

        self.campana = QPushButton()
        self.campana.setFlat(True)
        self.campana.setIcon(iconos.icono("campana", estilos.TEXTO, 20))
        self.campana.setIconSize(QSize(20, 20))
        self.campana.setFixedSize(34, 34)
        self.campana.setToolTip("Notificaciones")
        fila.addWidget(self.campana, 0, Qt.AlignmentFlag.AlignVCenter)

        u = sesion.usuario
        pildora = QFrame()
        pildora.setObjectName("PildoraUsuario")
        p = QHBoxLayout(pildora)
        p.setContentsMargins(6, 5, 16, 5)
        p.setSpacing(9)
        p.addWidget(Avatar(u.iniciales, estilos.COLOR_ROL[u.rol], 38))
        datos = QVBoxLayout()
        datos.setSpacing(2)
        nombre = QLabel(u.nombre)
        nombre.setStyleSheet(f"font-family: {estilos.FUENTE_TITULOS}; font-size: 14px; font-weight: 700;")
        datos.addWidget(nombre)
        datos.addWidget(InsigniaRol(u.rol, u.rol_visible))
        p.addLayout(datos)
        self.pildora = pildora
        fila.addWidget(pildora, 0, Qt.AlignmentFlag.AlignVCenter)

    def poner_conexion(self, conectado: bool, ahora: datetime) -> None:
        color = estilos.EN_RANGO if conectado else estilos.ALARMA
        texto = "Servidor conectado" if conectado else "Sin conexión"
        self.texto_chip.setText(f'<span style="color:{color}">●</span> {texto} · {ahora:%d/%m/%Y · %H:%M}')


class VentanaBase(QMainWindow):
    seccion_elegida = Signal(str)
    cierre_pedido = Signal()

    def __init__(self, sesion: Sesion, servidor: str):
        super().__init__()
        self.sesion = sesion
        self._servidor = servidor
        self._conectado: bool | None = None
        self.setWindowIcon(QIcon(iconos.isotipo(64)))
        self.setMinimumSize(1024, 640)
        self.resize(1440, 900)

        self.menu = MenuLateral(sesion)
        self.cabecera = Cabecera(sesion)
        self.contenido = QStackedWidget()
        self.barra = BarraEstado()
        self._paginas: dict[str, QWidget] = {}
        self._secciones = {s.clave: s for s in MENUS[sesion.usuario.rol]}

        zona = QWidget()
        zona.setObjectName("Fondo")
        derecha = QVBoxLayout(zona)
        derecha.setContentsMargins(24, 18, 24, 16)
        derecha.setSpacing(16)
        derecha.addWidget(self.cabecera)
        derecha.addWidget(self.contenido, 1)

        cuerpo = QWidget()
        fila = QHBoxLayout(cuerpo)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(0)
        fila.addWidget(self.menu)
        fila.addWidget(zona, 1)

        central = QWidget()
        columna = QVBoxLayout(central)
        columna.setContentsMargins(0, 0, 0, 0)
        columna.setSpacing(0)
        columna.addWidget(cuerpo, 1)
        columna.addWidget(self.barra)
        self.setCentralWidget(central)

        self.menu.seleccionada.connect(self.mostrar)
        self.menu.cerrar_sesion.connect(self.cierre_pedido)
        self.mostrar(MENUS[sesion.usuario.rol][0].clave)
        self.actualizar_estado()
        self._ajustar_a_ancho()

    # ── Navegación ──
    def registrar_vista(self, clave: str, vista: QWidget) -> None:
        """Sustituye el marcador de una sección por su ventana real (la usarán los sprints siguientes)."""
        antigua = self._paginas.get(clave)
        if antigua is not None:
            self.contenido.removeWidget(antigua)
            antigua.deleteLater()
        self._paginas[clave] = vista
        self.contenido.addWidget(vista)

    def mostrar(self, clave: str) -> None:
        seccion = self._secciones[clave]
        if clave not in self._paginas:
            self.registrar_vista(clave, VistaPendiente(seccion, self.sesion))
        self.contenido.setCurrentWidget(self._paginas[clave])
        self.menu.marcar(clave)
        u = self.sesion.usuario
        self.setWindowTitle(f"AUREA Sentinel — {seccion.texto} · Central Nuclear Valdecierzo")
        self.cabecera.titulo.setText(seccion.texto + (f" {u.area.codigo}" if u.rol == "supervisor" and u.area
                                                      and seccion.clave == "panel" else ""))
        self.cabecera.contexto.setText(f"Central Nuclear Valdecierzo · {u.area_visible}")
        self.seccion_elegida.emit(clave)

    # ── Estado ──
    def poner_conexion(self, conectado: bool, ahora: datetime | None = None) -> None:
        self._conectado = conectado
        self.cabecera.poner_conexion(conectado, ahora or datetime.now())
        self.actualizar_estado()

    def poner_caducidad(self, minutos: int) -> None:
        self.menu.poner_caducidad(f"Sesión caduca en {minutos} min")
        self.actualizar_estado(minutos)

    def actualizar_estado(self, minutos: int | None = None) -> None:
        u = self.sesion.usuario
        if minutos is None:
            minutos = self.sesion.minutos_restantes()
        self.barra.poner(
            self._conectado,
            f"Conectado a <b>{self._servidor}</b> &nbsp;·&nbsp; Usuario: <b>{u.nombre}</b> · {u.rol_visible} · "
            f"{u.area_visible}",
            f"{VERSION} · sesión caduca en {minutos} min",
        )

    # ── Adaptación a la pantalla ──
    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._ajustar_a_ancho()

    def _ajustar_a_ancho(self) -> None:
        """Por debajo de 1366 px: menú de iconos y se oculta «Datos en vivo» (sigue en la barra de estado)."""
        pequena = self.width() < estilos.ANCHO_MINIMO_COMPLETO
        self.menu.fijar_ancho(pequena)
        self.cabecera.chip.setVisible(not pequena)
