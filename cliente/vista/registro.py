"""Ventana 02 · Solicitar acceso (mockup 02)."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QVBoxLayout, QWidget)

from . import estilos
from .componentes import PanelMarca, etiqueta

ROLES_SOLICITABLES = [("Supervisor de área", "supervisor"), ("Técnico de campo", "tecnico"),
                      ("Auditor AUREA", "auditor")]
LONGITUD_MINIMA = 12


class VistaRegistro(QWidget):
    enviar = Signal(dict)                # datos del formulario
    volver = Signal()
    area_cambiada = Signal(str)          # código de área, para cargar sus supervisores

    def __init__(self, parent=None):
        super().__init__(parent)
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(PanelMarca(
            "Solicitud de acceso\nAUREA Sentinel",
            "Las cuentas las crea cada persona, pero un administrador las revisa antes de activarlas. "
            "Así nadie accede a datos de la central sin estar autorizado.",
            ["Rellenas la solicitud con tus datos y tu puesto",
             "Un administrador la revisa y te asigna rol y área",
             "Cuando te aprueban, ya puedes iniciar sesión"],
            "© 2026 AUREA AUDIT · Auditoría tecnológica. Tratamiento de datos conforme al RGPD: "
            "solo se recogen los necesarios para gestionar tu acceso.",
        ), 45)

        derecha = QWidget()
        derecha.setObjectName("PanelFormulario")
        derecha.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        centro = QVBoxLayout(derecha)
        centro.addStretch(1)
        formulario = QWidget()
        formulario.setFixedWidth(440)
        caja = QVBoxLayout(formulario)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(0)
        centro.addWidget(formulario, 0, Qt.AlignmentFlag.AlignHCenter)
        centro.addStretch(1)
        raiz.addWidget(derecha, 55)

        caja.addWidget(etiqueta("Solicitar acceso", "H1"))
        caja.addSpacing(4)
        caja.addWidget(etiqueta("Tu cuenta quedará pendiente hasta que un administrador la apruebe.", "Suave"))
        caja.addSpacing(14)

        self.aviso = QLabel()
        self.aviso.setWordWrap(True)
        self.aviso.hide()
        caja.addWidget(self.aviso)

        rejilla = QGridLayout()
        rejilla.setHorizontalSpacing(12)
        rejilla.setVerticalSpacing(4)
        self.nombre = QLineEdit()
        self.correo = QLineEdit()
        self.correo.setPlaceholderText("nombre@cn-valdecierzo.es")
        self.rol = QComboBox()
        for texto, valor in ROLES_SOLICITABLES:
            self.rol.addItem(texto, valor)
        self.area = QComboBox()
        self.supervisor = QComboBox()
        self.motivo = QPlainTextEdit()
        self.motivo.setFixedHeight(64)
        self.motivo.setPlaceholderText("Cuéntanos brevemente por qué necesitas acceso.")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.repetir = QLineEdit()
        self.repetir.setEchoMode(QLineEdit.EchoMode.Password)

        def campo(fila: int, columna: int, texto: str, widget: QWidget, ancho: int = 1):
            rotulo = etiqueta(texto, "Etiqueta")
            rotulo.setContentsMargins(0, 14 if fila else 0, 0, 0)
            rejilla.addWidget(rotulo, fila * 2, columna, 1, ancho)
            rejilla.addWidget(widget, fila * 2 + 1, columna, 1, ancho)

        campo(0, 0, "Nombre y apellidos", self.nombre)
        campo(0, 1, "Correo corporativo", self.correo)
        campo(1, 0, "Rol solicitado", self.rol)
        campo(1, 1, "Área", self.area)
        self.etiqueta_supervisor = etiqueta("Supervisor responsable (solo técnicos)", "Etiqueta")
        self.etiqueta_supervisor.setContentsMargins(0, 14, 0, 0)
        rejilla.addWidget(self.etiqueta_supervisor, 4, 0, 1, 2)
        rejilla.addWidget(self.supervisor, 5, 0, 1, 2)
        campo(3, 0, "Motivo de la solicitud", self.motivo, 2)
        campo(4, 0, "Contraseña", self.password)
        campo(4, 1, "Repetir contraseña", self.repetir)
        caja.addLayout(rejilla)
        caja.addSpacing(10)

        self.politica = QLabel()
        self.politica.setTextFormat(Qt.TextFormat.RichText)
        self.politica.setStyleSheet("font-size: 11px;")
        self.politica.setWordWrap(True)
        caja.addWidget(self.politica)
        caja.addSpacing(18)

        botones = QHBoxLayout()
        self.boton = QPushButton("Enviar solicitud")
        self.boton.setObjectName("Primario")
        self.boton.setCursor(Qt.CursorShape.PointingHandCursor)
        atras = QPushButton("Volver al acceso")
        atras.setObjectName("Secundario")
        atras.setCursor(Qt.CursorShape.PointingHandCursor)
        botones.addWidget(self.boton, 3)
        botones.addWidget(atras, 2)
        caja.addLayout(botones)

        self.boton.clicked.connect(self._enviar)
        atras.clicked.connect(self.volver)
        self.rol.currentIndexChanged.connect(self._rol_cambiado)
        self.area.currentIndexChanged.connect(self._area_cambiada)
        self.password.textChanged.connect(self._actualizar_politica)
        self.repetir.textChanged.connect(self._actualizar_politica)
        self._rol_cambiado()
        self._actualizar_politica()

    # ── Lo que la ventana ofrece al controlador ──
    def poner_areas(self, areas: list[dict]) -> None:
        self.area.blockSignals(True)
        self.area.clear()
        for a in areas:
            self.area.addItem(f"{a['codigo']} · {a['nombre']}", a["codigo"])
        self.area.blockSignals(False)
        self._area_cambiada()

    def poner_supervisores(self, supervisores: list[dict]) -> None:
        self.supervisor.clear()
        for s in supervisores:
            self.supervisor.addItem(s["nombre"], s["id"])

    def mostrar_error(self, mensaje: str) -> None:
        self._aviso("AvisoError", mensaje)

    def ocultar_aviso(self) -> None:
        self.aviso.hide()

    def ocupado(self, ocupado: bool) -> None:
        self.boton.setEnabled(not ocupado)
        self.boton.setText("Enviando…" if ocupado else "Enviar solicitud")

    def limpiar(self) -> None:
        for campo in (self.nombre, self.correo, self.password, self.repetir):
            campo.clear()
        self.motivo.clear()
        self.rol.setCurrentIndex(0)
        self.ocultar_aviso()

    def datos(self) -> dict:
        rol = self.rol.currentData()
        return {
            "nombre": self.nombre.text().strip(),
            "correo": self.correo.text().strip(),
            "password": self.password.text(),
            "repetir": self.repetir.text(),
            "rol": rol,
            "area": self.area.currentData() if rol == "supervisor" else None,
            "supervisor_id": self.supervisor.currentData() if rol == "tecnico" else None,
            "motivo": self.motivo.toPlainText().strip() or None,
        }

    # ── Internos ──
    def _aviso(self, nombre: str, mensaje: str) -> None:
        self.aviso.setObjectName(nombre)
        self.aviso.setText(mensaje)
        self.aviso.style().unpolish(self.aviso)
        self.aviso.style().polish(self.aviso)
        self.aviso.show()

    def _enviar(self) -> None:
        self.enviar.emit(self.datos())

    def _rol_cambiado(self) -> None:
        rol = self.rol.currentData()
        self.area.setEnabled(rol in ("supervisor", "tecnico"))
        # Un técnico elige el área de su supervisor y luego al supervisor
        self.supervisor.setEnabled(rol == "tecnico")
        self.etiqueta_supervisor.setEnabled(rol == "tecnico")
        if rol == "tecnico":
            self._area_cambiada()

    def _area_cambiada(self) -> None:
        if self.rol.currentData() == "tecnico" and self.area.currentData():
            self.area_cambiada.emit(self.area.currentData())

    def _actualizar_politica(self) -> None:
        def estado(cumple: bool, texto: str) -> str:
            color = estilos.EN_RANGO if cumple else estilos.TEXTO_SUAVE
            return f'<span style="color:{color}">{"✓" if cumple else "○"} {texto}</span>'

        largo = len(self.password.text()) >= LONGITUD_MINIMA
        iguales = bool(self.password.text()) and self.password.text() == self.repetir.text()
        self.politica.setText(" &nbsp;·&nbsp; ".join([
            estado(largo, f"Mínimo {LONGITUD_MINIMA} caracteres"),
            estado(False, "no habitual"),
            estado(iguales, "coinciden"),
        ]))
