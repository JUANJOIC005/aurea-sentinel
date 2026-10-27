"""Controlador del acceso: conecta las ventanas de login y registro con el servidor."""
import re

from PySide6.QtCore import QObject, QSettings, Signal

from ..modelo.api import ClienteApi, ErrorApi, ErrorConexion
from ..modelo.sesion import Sesion
from ..vista.registro import LONGITUD_MINIMA
from ..vista.ventana_acceso import VentanaAcceso

CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SIN_CONEXION = "No se puede conectar con el servidor ({servidor}). Comprueba que está en marcha."
REGISTRO_ENVIADO = ("Solicitud enviada. Tu cuenta está pendiente de aprobación: "
                    "no podrás iniciar sesión hasta que un administrador la apruebe.")


class ControladorAcceso(QObject):
    sesion_iniciada = Signal(object)   # Sesion

    def __init__(self, api: ClienteApi, ventana: VentanaAcceso):
        super().__init__()
        self.api = api
        self.ventana = ventana
        ventana.login.entrar.connect(self.iniciar_sesion)
        ventana.login.solicitar_acceso.connect(self.abrir_registro)
        ventana.registro.enviar.connect(self.enviar_registro)
        ventana.registro.volver.connect(self.volver_al_login)
        ventana.registro.area_cambiada.connect(self.cargar_supervisores)

    # ── Login ──
    def iniciar_sesion(self, correo: str, password: str, equipo_compartido: bool) -> None:
        login = self.ventana.login
        if not correo or not password:
            login.mostrar_error("Escribe tu correo y tu contraseña.")
            return
        if not CORREO.match(correo):
            login.mostrar_error("Escribe un correo válido, por ejemplo nombre.apellido@cn-valdecierzo.es.")
            return
        login.ocultar_aviso()
        login.ocupado(True)
        try:
            sesion = Sesion.desde_respuesta(self.api.login(correo, password))
        except ErrorApi as error:
            login.mostrar_error(error.mensaje)
            return
        except ErrorConexion:
            login.mostrar_error(SIN_CONEXION.format(servidor=self.api.servidor))
            self.ventana.actualizar_conexion(False)
            return
        finally:
            login.ocupado(False)

        self.api.usar_token(sesion.token)
        ajustes = QSettings("AUREA AUDIT", "AUREA Sentinel")
        if equipo_compartido:
            ajustes.remove("ultimo_correo")
        else:
            ajustes.setValue("ultimo_correo", correo)
        self.sesion_iniciada.emit(sesion)

    # ── Registro ──
    def abrir_registro(self) -> None:
        self.ventana.registro.ocultar_aviso()
        try:
            self.ventana.registro.poner_areas(self.api.areas())
        except (ErrorApi, ErrorConexion):
            self.ventana.registro.mostrar_error(SIN_CONEXION.format(servidor=self.api.servidor))
        self.ventana.mostrar_registro()

    def volver_al_login(self) -> None:
        self.ventana.mostrar_login()

    def cargar_supervisores(self, area: str) -> None:
        try:
            self.ventana.registro.poner_supervisores(self.api.supervisores(area))
        except (ErrorApi, ErrorConexion):
            self.ventana.registro.poner_supervisores([])

    def enviar_registro(self, datos: dict) -> None:
        registro = self.ventana.registro
        error = self._validar_registro(datos)
        if error:
            registro.mostrar_error(error)
            return
        peticion = {k: v for k, v in datos.items() if k != "repetir"}
        registro.ocultar_aviso()
        registro.ocupado(True)
        try:
            self.api.registro(peticion)
        except ErrorApi as e:
            registro.mostrar_error(e.mensaje)
            return
        except ErrorConexion:
            registro.mostrar_error(SIN_CONEXION.format(servidor=self.api.servidor))
            return
        finally:
            registro.ocupado(False)
        registro.limpiar()
        self.ventana.mostrar_login()
        self.ventana.login.mostrar_info(REGISTRO_ENVIADO)

    @staticmethod
    def _validar_registro(d: dict) -> str | None:
        if len(d["nombre"]) < 3:
            return "Escribe tu nombre y apellidos."
        if not CORREO.match(d["correo"]):
            return "Escribe un correo corporativo válido."
        if d["rol"] == "supervisor" and not d["area"]:
            return "Elige el área del supervisor."
        if d["rol"] == "tecnico" and not d["supervisor_id"]:
            return "Un técnico debe elegir su supervisor responsable."
        if len(d["password"]) < LONGITUD_MINIMA:
            return f"La contraseña debe tener al menos {LONGITUD_MINIMA} caracteres."
        if d["password"] != d["repetir"]:
            return "Las contraseñas no coinciden."
        return None
