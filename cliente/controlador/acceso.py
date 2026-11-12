"""Controlador del acceso: conecta las ventanas de login y registro con el servidor."""
import re

from PySide6.QtCore import QObject, QSettings, Signal

from ..modelo.api import ClienteApi, ErrorApi, ErrorConexion
from ..modelo.sesion import Sesion
from ..vista.registro import LONGITUD_MINIMA
from ..vista.ventana_acceso import VentanaAcceso

CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SIN_CONEXION = "No se puede conectar con el servidor ({servidor}). Comprueba que está en marcha."
CODIGO_ERRONEO = "Código incorrecto"       # así empieza el mensaje del servidor cuando aún quedan intentos
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
        ventana.verificacion.verificar.connect(self.verificar_codigo)
        ventana.verificacion.cambiar_usuario.connect(self.volver_al_paso_1)
        self._paso2: dict | None = None        # desafío del servidor mientras se espera el código

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
            datos = self.api.login(correo, password)
        except ErrorApi as error:
            login.mostrar_error(error.mensaje)
            return
        except ErrorConexion:
            login.mostrar_error(SIN_CONEXION.format(servidor=self.api.servidor))
            self.ventana.actualizar_conexion(False)
            return
        finally:
            login.ocupado(False)

        if datos.get("requiere_2fa"):
            self._empezar_verificacion(datos, correo, equipo_compartido)
        else:
            self._abrir_sesion(datos, correo, equipo_compartido)

    def _abrir_sesion(self, datos: dict, correo: str, equipo_compartido: bool) -> None:
        sesion = Sesion.desde_respuesta(datos)
        self.api.usar_token(sesion.token)
        ajustes = QSettings("AUREA AUDIT", "AUREA Sentinel")
        if equipo_compartido:
            ajustes.remove("ultimo_correo")
        else:
            ajustes.setValue("ultimo_correo", correo)
        self._paso2 = None
        self.sesion_iniciada.emit(sesion)

    # ── Segundo paso: código de 6 dígitos ──
    def _empezar_verificacion(self, datos: dict, correo: str, equipo_compartido: bool) -> None:
        self._paso2 = {"desafio": datos["desafio"], "configurado": datos["configurado"], "correo": correo,
                       "compartido": equipo_compartido}
        self.ventana.mostrar_verificacion(datos["usuario"])
        if datos["configurado"]:
            return
        try:                                  # primera vez: el servidor da el QR para la aplicación autenticadora
            qr = self.api.configurar_2fa(datos["desafio"])
        except ErrorApi as error:
            self._volver_al_login(error.mensaje)
        except ErrorConexion:
            self._volver_al_login(SIN_CONEXION.format(servidor=self.api.servidor))
        else:
            self.ventana.verificacion.modo_configuracion(qr["secreto"], qr["qr_svg"])

    def verificar_codigo(self, codigo: str) -> None:
        if self._paso2 is None:
            return
        paso = self._paso2
        vista = self.ventana.verificacion
        vista.ocultar_aviso()
        vista.ocupado(True)
        enviar = self.api.verificar_2fa if paso["configurado"] else self.api.activar_2fa
        try:
            datos = enviar(paso["desafio"], codigo)
        except ErrorApi as error:
            if error.estado == 401 and error.mensaje.startswith(CODIGO_ERRONEO):
                vista.ocupado(False)           # se queda en el paso 2 para escribir otro código
                vista.mostrar_error(error.mensaje)
                vista.casillas.limpiar()
            else:                              # desafío caducado, 3 códigos erróneos o cuenta bloqueada
                vista.ocupado(False)
                self._volver_al_login(error.mensaje)
            return
        except ErrorConexion:
            vista.ocupado(False)
            vista.mostrar_error(SIN_CONEXION.format(servidor=self.api.servidor))
            return
        vista.ocupado(False)
        self._abrir_sesion(datos, paso["correo"], paso["compartido"])

    def volver_al_paso_1(self) -> None:
        """«¿No eres tú? Cambiar»: se descarta el desafío y se vuelve a pedir correo y contraseña."""
        self._volver_al_login("")

    def _volver_al_login(self, mensaje: str) -> None:
        self._paso2 = None
        self.ventana.mostrar_login()
        self.ventana.login.limpiar()
        if mensaje:
            self.ventana.login.mostrar_error(mensaje)

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
