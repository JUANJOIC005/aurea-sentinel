"""T13 · Acceso con segundo factor: el controlador del login, la ventana 03 y el servidor real, juntos."""
import pytest
from fastapi.testclient import TestClient
from PySide6.QtCore import QSettings

from cliente.controlador.acceso import ControladorAcceso
from cliente.modelo.api import ClienteApi, ErrorApi, ErrorConexion
from cliente.modelo.sesion import Sesion
from cliente.vista.ventana_acceso import VentanaAcceso
from servidor import config
from servidor.api.main import app
from tests.ayudas import activar_2fa, codigo_de
from tests.conftest import CLAVE, CORREOS


@pytest.fixture(autouse=True)
def preparar(monkeypatch, qapp):
    monkeypatch.setattr(config, "DOBLE_FACTOR_ACTIVO", True)
    QSettings("AUREA AUDIT", "AUREA Sentinel").clear()


@pytest.fixture
def acceso(qapp, central):
    api = ClienteApi(url="http://testserver", http=TestClient(app))
    ventana = VentanaAcceso("testserver")
    control = ControladorAcceso(api, ventana)
    iniciadas = []
    control.sesion_iniciada.connect(iniciadas.append)
    ventana.show()
    yield api, ventana, control, iniciadas
    ventana.close()


def entrar(control, nombre="laura", compartido=False):
    control.iniciar_sesion(CORREOS[nombre], CLAVE, compartido)


def secreto_guardado(conexion, usuario_id):
    return conexion.execute("SELECT secreto FROM segundo_factor WHERE usuario_id = ?", (usuario_id,)).fetchone()["secreto"]


def en_paso_2(ventana):
    return ventana.paginas.currentWidget() is ventana.verificacion


def en_login(ventana):
    return ventana.paginas.currentWidget() is ventana.login


def test_el_tecnico_entra_solo_con_la_contrasena(acceso):
    api, ventana, control, iniciadas = acceso
    entrar(control, "diego")
    assert len(iniciadas) == 1 and iniciadas[0].usuario.rol == "tecnico" and en_login(ventana)


def test_el_supervisor_llega_al_paso_2_y_todavia_no_tiene_sesion(acceso):
    api, ventana, control, iniciadas = acceso
    entrar(control)
    assert en_paso_2(ventana) and iniciadas == [] and api._token is None
    v = ventana.verificacion
    assert v.nombre.text() == "Laura Méndez Ortiz" and "A1 · Reactor y circuito primario" in v.area.text()


def test_la_primera_vez_enseña_el_qr_y_con_el_codigo_se_entra(acceso, conexion, central):
    api, ventana, control, iniciadas = acceso
    entrar(control)
    v = ventana.verificacion
    assert v.bloque_qr.isVisibleTo(v) and not v.imagen_qr.pixmap().isNull()
    secreto = secreto_guardado(conexion, central["laura"])
    assert v.clave.text().replace(" ", "") == secreto
    control.verificar_codigo(codigo_de(secreto))
    assert len(iniciadas) == 1 and isinstance(iniciadas[0], Sesion)
    assert iniciadas[0].usuario.nombre == "Laura Méndez Ortiz" and api._token == iniciadas[0].token
    assert v.boton.text() == "Verificar y entrar" and v.casillas.casillas[0].isEnabled()   # no queda bloqueada


def test_con_el_factor_ya_configurado_no_hay_qr(acceso, conexion, central):
    api, ventana, control, iniciadas = acceso
    secreto = activar_2fa(conexion, central["laura"])
    entrar(control)
    assert en_paso_2(ventana) and not ventana.verificacion.bloque_qr.isVisibleTo(ventana.verificacion)
    control.verificar_codigo(codigo_de(secreto))
    assert len(iniciadas) == 1


def test_el_auditor_y_el_administrador_tambien_pasan_por_el_segundo_paso(acceso, conexion, central):
    api, ventana, control, iniciadas = acceso
    for nombre in ("beatriz", "alvaro"):
        secreto = activar_2fa(conexion, central[nombre])
        entrar(control, nombre)
        assert en_paso_2(ventana) and ventana.verificacion.nombre.text()
        control.verificar_codigo(codigo_de(secreto))
        control.volver_al_paso_1()
    assert [s.usuario.rol for s in iniciadas] == ["auditor", "administrador"]


def test_un_codigo_erroneo_se_queda_en_el_paso_2_y_deja_probar_otro(acceso, conexion, central):
    api, ventana, control, iniciadas = acceso
    secreto = activar_2fa(conexion, central["laura"])
    entrar(control)
    v = ventana.verificacion
    v.casillas.poner("000000")
    control.verificar_codigo("000000")
    assert en_paso_2(ventana) and iniciadas == []
    assert v.aviso.isVisibleTo(v) and v.aviso.text().startswith("Código incorrecto") and "2 intentos" in v.aviso.text()
    assert v.casillas.codigo() == "" and v.boton.text() == "Verificar y entrar"
    control.verificar_codigo(codigo_de(secreto))
    assert len(iniciadas) == 1


def test_tres_codigos_erroneos_devuelven_al_paso_1_con_un_mensaje(acceso, conexion, central):
    api, ventana, control, iniciadas = acceso
    secreto = activar_2fa(conexion, central["laura"])
    entrar(control)
    for _ in range(3):
        control.verificar_codigo("111111")
    assert en_login(ventana) and iniciadas == [] and control._paso2 is None
    assert "Demasiados intentos" in ventana.login.aviso.text() and ventana.login.aviso.objectName() == "AvisoError"
    control.verificar_codigo(codigo_de(secreto))                # sin desafío no pasa nada
    assert iniciadas == []


def test_cambiar_de_usuario_vuelve_al_paso_1_y_borra_la_contrasena(acceso):
    api, ventana, control, iniciadas = acceso
    ventana.login.password.setText(CLAVE)
    entrar(control)
    ventana.verificacion.cambiar.click()
    assert en_login(ventana) and ventana.login.password.text() == "" and control._paso2 is None
    assert not ventana.login.aviso.isVisibleTo(ventana.login)


def test_si_el_desafio_caduca_se_vuelve_al_paso_1(acceso, conexion, central):
    api, ventana, control, iniciadas = acceso
    secreto = activar_2fa(conexion, central["laura"])
    entrar(control)
    conexion.execute("UPDATE desafio_2fa SET expira_en = datetime('now', '-1 minute')")
    conexion.commit()
    control.verificar_codigo(codigo_de(secreto))
    assert en_login(ventana) and "caducado" in ventana.login.aviso.text() and iniciadas == []


def test_si_se_pierde_la_conexion_en_el_paso_2_se_queda_y_avisa(acceso, conexion, central, monkeypatch):
    api, ventana, control, iniciadas = acceso
    activar_2fa(conexion, central["laura"])
    entrar(control)
    monkeypatch.setattr(api, "verificar_2fa", lambda *a: (_ for _ in ()).throw(ErrorConexion("caído")))
    control.verificar_codigo("123456")
    v = ventana.verificacion
    assert en_paso_2(ventana) and "No se puede conectar" in v.aviso.text() and v.boton.text() == "Verificar y entrar"


def test_si_el_servidor_falla_al_pedir_el_qr_se_vuelve_al_login(acceso, monkeypatch):
    api, ventana, control, iniciadas = acceso
    monkeypatch.setattr(api, "configurar_2fa", lambda d: (_ for _ in ()).throw(ErrorApi(500, "Error del servidor.")))
    entrar(control)
    assert en_login(ventana) and "Error del servidor." in ventana.login.aviso.text()


def test_el_correo_se_recuerda_solo_si_no_es_un_equipo_compartido(acceso, conexion, central):
    api, ventana, control, iniciadas = acceso
    ajustes = QSettings("AUREA AUDIT", "AUREA Sentinel")
    secreto = activar_2fa(conexion, central["laura"])
    entrar(control, compartido=False)
    control.verificar_codigo(codigo_de(secreto))
    assert ajustes.value("ultimo_correo") == CORREOS["laura"]
    entrar(control, compartido=True)
    control.verificar_codigo(codigo_de(secreto, +1))
    assert ajustes.value("ultimo_correo") is None


def test_una_contrasena_mala_no_llega_al_paso_2(acceso):
    api, ventana, control, iniciadas = acceso
    control.iniciar_sesion(CORREOS["laura"], "otra-contraseña-larga", False)
    assert en_login(ventana) and ventana.login.aviso.isVisibleTo(ventana.login) and iniciadas == []
