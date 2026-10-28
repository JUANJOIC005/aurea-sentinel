"""Controladores del cliente, con un servidor de mentira para probar cada caso."""
from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtCore import QSettings

from cliente.controlador.acceso import REGISTRO_ENVIADO, ControladorAcceso
from cliente.controlador.aplicacion import Aplicacion
from cliente.controlador.sesion import ControladorSesion
from cliente.modelo.api import ErrorApi, ErrorConexion
from cliente.modelo.sesion import Sesion
from cliente.vista.ventana_acceso import VentanaAcceso
from cliente.vista.ventana_base import VentanaBase


def respuesta(rol="supervisor", minutos=15):
    expira = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    return {"token": "tok", "expira_en": expira.isoformat(),
            "usuario": {"id": 1, "nombre": "Laura Méndez Ortiz", "correo": "laura@cn.es", "rol": rol,
                        "area": {"codigo": "A1", "nombre": "Reactor y circuito primario"}, "supervisor": None}}


class FalsaApi:
    """Hace de servidor: devuelve lo que se le diga o lanza el error que se le pida."""
    servidor = "127.0.0.1:8000"

    def __init__(self):
        self.fallo = None
        self.llamadas = []
        self.token = None
        self.salud_ok = True

    def _llamar(self, nombre, resultado=None, *args):
        self.llamadas.append((nombre, *args))
        if self.fallo:
            raise self.fallo
        return resultado

    def login(self, correo, password):
        return self._llamar("login", respuesta(), correo, password)

    def registro(self, datos):
        return self._llamar("registro", {"mensaje": "ok"}, datos)

    def areas(self):
        return self._llamar("areas", [{"codigo": "A1", "nombre": "Reactor"}, {"codigo": "A3", "nombre": "Turbina"}])

    def supervisores(self, area):
        return self._llamar("supervisores", [{"id": 7, "nombre": "Marta Soler Vidal"}], area)

    def logout(self):
        return self._llamar("logout")

    def usar_token(self, token):
        self.token = token

    def salud(self):
        return self.salud_ok


@pytest.fixture(autouse=True)
def ajustes_limpios(qapp):
    QSettings("AUREA AUDIT", "AUREA Sentinel").clear()


@pytest.fixture
def acceso(qapp):
    api, ventana = FalsaApi(), VentanaAcceso("127.0.0.1:8000")
    control = ControladorAcceso(api, ventana)
    iniciadas = []
    control.sesion_iniciada.connect(iniciadas.append)
    return api, ventana, control, iniciadas


# ── Login ──
def test_login_correcto_emite_la_sesion_y_guarda_el_token(acceso):
    api, ventana, control, iniciadas = acceso
    control.iniciar_sesion("laura@cn.es", "clave", False)
    assert len(iniciadas) == 1 and isinstance(iniciadas[0], Sesion)
    assert iniciadas[0].usuario.nombre == "Laura Méndez Ortiz"
    assert api.token == "tok"
    assert ventana.login.boton.isEnabled()


def test_login_con_campos_vacios_o_correo_mal_escrito(acceso):
    api, ventana, control, iniciadas = acceso
    control.iniciar_sesion("", "", False)
    assert "Escribe tu correo" in ventana.login.aviso.text()
    control.iniciar_sesion("sin-arroba", "clave", False)
    assert "correo válido" in ventana.login.aviso.text()
    assert api.llamadas == [] and iniciadas == []


def test_login_rechazado_enseña_el_mensaje_del_servidor(acceso):
    api, ventana, control, iniciadas = acceso
    api.fallo = ErrorApi(401, "Correo o contraseña incorrectos")
    control.iniciar_sesion("laura@cn.es", "mala", False)
    assert ventana.login.aviso.text() == "Correo o contraseña incorrectos"
    assert ventana.login.aviso.objectName() == "AvisoError"
    assert iniciadas == [] and api.token is None
    assert ventana.login.boton.isEnabled() and ventana.login.boton.text() == "Iniciar sesión"


def test_login_sin_servidor(acceso):
    api, ventana, control, iniciadas = acceso
    api.fallo = ErrorConexion("caído")
    control.iniciar_sesion("laura@cn.es", "clave", False)
    assert "No se puede conectar" in ventana.login.aviso.text() and iniciadas == []
    assert "Servidor" not in ventana.barra.izquierda.text()


def test_equipo_compartido_no_recuerda_el_usuario(acceso):
    _, _, control, _ = acceso
    ajustes = QSettings("AUREA AUDIT", "AUREA Sentinel")
    control.iniciar_sesion("laura@cn.es", "clave", False)
    assert ajustes.value("ultimo_correo") == "laura@cn.es"
    control.iniciar_sesion("laura@cn.es", "clave", True)
    assert ajustes.value("ultimo_correo") is None


# ── Registro ──
def datos_registro(**cambios):
    base = {"nombre": "Marcos Gil Arroyo", "correo": "marcos@cn.es", "password": "Valdecierzo-2026-ok!",
            "repetir": "Valdecierzo-2026-ok!", "rol": "auditor", "area": None, "supervisor_id": None,
            "motivo": None}
    return {**base, **cambios}


def test_abrir_registro_carga_las_areas(acceso):
    _, ventana, control, _ = acceso
    control.abrir_registro()
    assert ventana.paginas.currentWidget() is ventana.registro
    assert ventana.registro.area.count() == 2


def test_abrir_registro_sin_servidor_avisa(acceso):
    api, ventana, control, _ = acceso
    api.fallo = ErrorConexion("caído")
    control.abrir_registro()
    assert "No se puede conectar" in ventana.registro.aviso.text()


@pytest.mark.parametrize("cambios, texto", [
    ({"nombre": "ab"}, "nombre"),
    ({"correo": "malo"}, "correo"),
    ({"rol": "supervisor"}, "área"),
    ({"rol": "tecnico"}, "supervisor"),
    ({"password": "corta", "repetir": "corta"}, "12 caracteres"),
    ({"repetir": "otra-cosa-distinta"}, "no coinciden"),
])
def test_registro_validado_antes_de_enviarlo(acceso, cambios, texto):
    api, ventana, control, _ = acceso
    control.enviar_registro(datos_registro(**cambios))
    assert texto in ventana.registro.aviso.text() and api.llamadas == []


def test_registro_correcto_vuelve_al_login_con_aviso_de_pendiente(acceso):
    api, ventana, control, _ = acceso
    ventana.mostrar_registro()
    control.enviar_registro(datos_registro())
    nombre, enviado = api.llamadas[-1]
    assert nombre == "registro" and "repetir" not in enviado and enviado["rol"] == "auditor"
    assert ventana.paginas.currentWidget() is ventana.login
    assert ventana.login.aviso.text() == REGISTRO_ENVIADO and ventana.login.aviso.objectName() == "AvisoOk"


def test_registro_rechazado_o_sin_servidor(acceso):
    api, ventana, control, _ = acceso
    api.fallo = ErrorApi(422, "La contraseña aparece en las listas de contraseñas filtradas.")
    control.enviar_registro(datos_registro())
    assert "filtradas" in ventana.registro.aviso.text()
    api.fallo = ErrorConexion("caído")
    control.enviar_registro(datos_registro())
    assert "No se puede conectar" in ventana.registro.aviso.text()


def test_un_tecnico_elige_area_y_despues_supervisor(acceso):
    api, ventana, control, _ = acceso
    control.abrir_registro()
    ventana.registro.rol.setCurrentIndex(1)           # Técnico de campo
    assert ventana.registro.supervisor.isEnabled()
    assert api.llamadas[-1] == ("supervisores", "A1")
    assert ventana.registro.supervisor.currentText() == "Marta Soler Vidal"
    assert ventana.registro.datos()["supervisor_id"] == 7


def test_supervisores_sin_servidor_deja_la_lista_vacia(acceso):
    api, ventana, control, _ = acceso
    api.fallo = ErrorConexion("caído")
    control.cargar_supervisores("A1")
    assert ventana.registro.supervisor.count() == 0


def test_volver_al_login(acceso):
    _, ventana, control, _ = acceso
    ventana.mostrar_registro()
    control.volver_al_login()
    assert ventana.paginas.currentWidget() is ventana.login


# ── Sesión abierta ──
@pytest.fixture
def sesion_abierta(qapp):
    api = FalsaApi()
    sesion = Sesion.desde_respuesta(respuesta())
    ventana = VentanaBase(sesion, api.servidor)
    control = ControladorSesion(api, sesion, ventana)
    cierres = []
    control.sesion_cerrada.connect(cierres.append)
    yield api, sesion, ventana, control, cierres
    control._reloj.stop()
    control._conexion.stop()


def test_al_abrir_se_comprueba_la_conexion_y_se_enseña_la_caducidad(sesion_abierta):
    _, _, ventana, _, _ = sesion_abierta
    assert "Servidor conectado" in ventana.cabecera.texto_chip.text()
    assert "Sesión caduca en 15 min" == ventana.menu.caduca.text()
    assert "sesión caduca en 15 min" in ventana.barra.derecha.text()


def test_si_el_servidor_se_cae_se_avisa(sesion_abierta):
    api, _, ventana, control, _ = sesion_abierta
    api.salud_ok = False
    control.comprobar_conexion()
    assert "Sin conexión" in ventana.cabecera.texto_chip.text()


def test_la_caducidad_baja_con_el_tiempo(sesion_abierta):
    _, sesion, ventana, control, cierres = sesion_abierta
    control.refrescar_caducidad(datetime.now(timezone.utc) + timedelta(minutes=10))
    assert ventana.menu.caduca.text() == "Sesión caduca en 5 min" and cierres == []


def test_al_caducar_se_vuelve_al_login_con_un_aviso(sesion_abierta):
    api, _, _, control, cierres = sesion_abierta
    control.refrescar_caducidad(datetime.now(timezone.utc) + timedelta(minutes=16))
    assert cierres == ["Tu sesión ha caducado. Vuelve a iniciar sesión."]
    assert api.token is None
    control.refrescar_caducidad(datetime.now(timezone.utc) + timedelta(minutes=17))
    assert len(cierres) == 1                           # solo se cierra una vez


def test_cerrar_sesion_avisa_al_servidor(sesion_abierta):
    api, _, ventana, _, cierres = sesion_abierta
    ventana.menu.boton_salir.click()
    assert ("logout",) in api.llamadas and cierres == [""] and api.token is None


def test_cerrar_sesion_funciona_aunque_el_servidor_no_conteste(sesion_abierta):
    api, _, _, control, cierres = sesion_abierta
    api.fallo = ErrorConexion("caído")
    control.cerrar()
    assert cierres == [""]


# ── La aplicación entera ──
def test_flujo_completo_login_ventana_y_cierre(qapp):
    api = FalsaApi()
    app = Aplicacion(api)
    app.iniciar()
    assert app.acceso.isVisible() and app.base is None
    app.control_acceso.iniciar_sesion("laura@cn.es", "clave", False)
    assert app.base is not None and app.base.isVisible() and not app.acceso.isVisible()
    assert app.base.sesion.usuario.nombre == "Laura Méndez Ortiz"
    app.base.menu.boton_salir.click()
    assert app.base is None and app.acceso.isVisible()
    assert app.acceso.login.password.text() == ""
    app.al_salir()                                     # sin sesión abierta no hace nada
    app.acceso.close()


def test_al_caducar_la_sesion_el_login_lo_cuenta(qapp):
    app = Aplicacion(FalsaApi())
    app.iniciar()
    app.control_acceso.iniciar_sesion("laura@cn.es", "clave", False)
    app.control_sesion.refrescar_caducidad(datetime.now(timezone.utc) + timedelta(hours=1))
    assert "caducado" in app.acceso.login.aviso.text()
    app.acceso.close()


def test_cerrar_la_aplicacion_con_sesion_abierta_cierra_la_sesion(qapp):
    api = FalsaApi()
    app = Aplicacion(api)
    app.iniciar()
    app.control_acceso.iniciar_sesion("laura@cn.es", "clave", False)
    app.al_salir()
    assert ("logout",) in api.llamadas
    app.acceso.close()
