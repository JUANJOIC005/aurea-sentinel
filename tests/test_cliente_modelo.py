from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from cliente.modelo.api import ClienteApi, ErrorApi, ErrorConexion
from cliente.modelo.menus import MENUS
from cliente.modelo.sesion import Area, Sesion, Usuario
from servidor.api.main import app
from tests.conftest import CLAVE

RESPUESTA = {
    "token": "abc", "expira_en": "2026-11-01T10:15:00+00:00",
    "usuario": {"id": 1, "nombre": "Laura Méndez Ortiz", "correo": "laura@cn.es", "rol": "supervisor",
                "area": {"codigo": "A1", "nombre": "Reactor y circuito primario"}, "supervisor": None},
}


def test_sesion_desde_la_respuesta_del_servidor():
    sesion = Sesion.desde_respuesta(RESPUESTA)
    u = sesion.usuario
    assert (u.nombre, u.rol, u.rol_visible, u.iniciales) == ("Laura Méndez Ortiz", "supervisor", "Supervisor", "LM")
    assert u.area == Area("A1", "Reactor y circuito primario")
    assert u.area_visible == "A1 · Reactor y circuito primario"
    assert u.supervisor is None


def test_tecnico_con_supervisor_y_usuario_sin_area():
    datos = {**RESPUESTA, "usuario": {**RESPUESTA["usuario"], "rol": "tecnico", "supervisor": {"id": 2, "nombre": "Ana"}}}
    assert Sesion.desde_respuesta(datos).usuario.supervisor == "Ana"
    auditor = Usuario(5, "Beatriz Lara Quintana", "b@cn.es", "auditor")
    assert auditor.area_visible == "Todas las áreas" and auditor.rol_visible == "Auditor"


def test_minutos_restantes_redondea_hacia_arriba():
    ahora = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
    sesion = Sesion("t", Usuario(1, "A B", "a@b.c", "supervisor"), ahora + timedelta(minutes=14, seconds=30))
    assert sesion.minutos_restantes(ahora) == 15
    assert sesion.segundos_restantes(ahora) == 870
    assert sesion.segundos_restantes(ahora + timedelta(hours=1)) == 0
    assert sesion.minutos_restantes(ahora + timedelta(hours=1)) == 0


def test_cada_rol_tiene_menu_y_sus_secciones_son_unicas():
    assert set(MENUS) == {"supervisor", "tecnico", "auditor", "administrador"}
    for rol, secciones in MENUS.items():
        claves = [s.clave for s in secciones]
        assert claves and len(claves) == len(set(claves)), rol


@pytest.fixture
def cliente():
    return ClienteApi(url="http://testserver", http=TestClient(app))


def test_login_y_sesion(cliente, crear_usuario):
    crear_usuario()
    sesion = Sesion.desde_respuesta(cliente.login("laura.mendez@cn-valdecierzo.es", CLAVE))
    cliente.usar_token(sesion.token)
    assert cliente.yo()["usuario"]["nombre"] == "Laura Méndez Ortiz"
    cliente.logout()
    with pytest.raises(ErrorApi) as error:
        cliente.yo()
    assert error.value.estado == 401


def test_error_del_servidor_con_su_mensaje(cliente, crear_usuario):
    crear_usuario()
    with pytest.raises(ErrorApi) as error:
        cliente.login("laura.mendez@cn-valdecierzo.es", "mala-mala-mala")
    assert error.value.estado == 401 and "incorrectos" in error.value.mensaje


def test_registro_y_datos_publicos(cliente):
    assert len(cliente.areas()) == 9
    assert cliente.supervisores("A1") == []
    assert "pendiente" in cliente.registro({"nombre": "Marcos Gil Arroyo", "correo": "m@cn.es", "password": CLAVE,
                                            "rol": "auditor"})["mensaje"]


def test_salud(cliente):
    assert cliente.salud() is True


def test_sin_conexion():
    def caido(peticion):
        raise httpx.ConnectError("no hay nadie")
    cliente = ClienteApi(url="http://127.0.0.1:9", http=httpx.Client(base_url="http://127.0.0.1:9",
                                                                      transport=httpx.MockTransport(caido)))
    with pytest.raises(ErrorConexion):
        cliente.login("a@b.c", "x")
    assert cliente.salud() is False
    assert cliente.servidor == "127.0.0.1:9"


def test_respuesta_de_error_sin_json():
    cliente = ClienteApi(url="http://x", http=httpx.Client(
        base_url="http://x", transport=httpx.MockTransport(lambda r: httpx.Response(502, text="Bad gateway"))))
    with pytest.raises(ErrorApi) as error:
        cliente.yo()
    assert error.value.estado == 502 and error.value.mensaje == "Error del servidor."
