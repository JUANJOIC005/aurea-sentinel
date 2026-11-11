import os
import tempfile

os.environ["AUREA_BD"] = os.path.join(tempfile.mkdtemp(prefix="aurea-bd-"), "pruebas.db")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="aurea-config-")

import pytest
from fastapi.testclient import TestClient

from servidor import config, db, migrate, seguridad
from servidor.api.main import app

CLAVE = "Valdecierzo-2026-ok!"
HASH_CLAVE = seguridad.hashear(CLAVE)


@pytest.fixture(autouse=True)
def base_de_datos():
    migrate.desde_cero()
    migrate.preparar()


@pytest.fixture(autouse=True)
def sin_doble_factor(monkeypatch):
    """Las pruebas de acceso y de datos entran solo con contraseña; las del segundo factor lo activan a propósito."""
    monkeypatch.setattr(config, "DOBLE_FACTOR_ACTIVO", False)


@pytest.fixture
def api():
    return TestClient(app)


@pytest.fixture
def conexion():
    with db.conexion() as conn:
        yield conn


@pytest.fixture
def crear_usuario(conexion):
    def _crear(nombre="Laura Méndez Ortiz", correo="laura.mendez@cn-valdecierzo.es", rol="supervisor",
               area="A1", supervisor_id=None, estado="activo", password_hash=HASH_CLAVE) -> int:
        fila = conexion.execute(
            "INSERT INTO usuario (nombre, correo, password_hash, rol_id, area_id, supervisor_id, estado)"
            " VALUES (?, ?, ?, (SELECT id FROM rol WHERE codigo = ?),"
            "         (SELECT id FROM area WHERE codigo = ?), ?, ?) RETURNING id",
            (nombre, correo, password_hash, rol, area, supervisor_id, estado),
        ).fetchone()
        conexion.commit()
        return fila["id"]
    return _crear


@pytest.fixture
def entrar(api):
    def _entrar(correo="laura.mendez@cn-valdecierzo.es", password=CLAVE):
        r = api.post("/auth/login", json={"correo": correo, "password": password})
        assert r.status_code == 200, r.text
        return r.json()["token"], r.json()
    return _entrar


CORREOS = {
    "laura": "laura.mendez@cn-valdecierzo.es", "javier": "javier.ruiz@cn-valdecierzo.es",
    "diego": "diego.paredes@cn-valdecierzo.es", "nuria": "nuria.vega@cn-valdecierzo.es",
    "ivan": "ivan.cano@cn-valdecierzo.es", "beatriz": "beatriz.lara@cn-valdecierzo.es",
    "alvaro": "alvaro.campos@cn-valdecierzo.es",
}


@pytest.fixture
def central(crear_usuario, conexion):
    """Una central pequeña con sus lecturas: Laura (A1) y Javier (A2) con sus técnicos, un auditor y un administrador.
    Diego tiene TE-101 y PT-102; Nuria, FT-103 y LT-104; Iván, PT-201 y LT-202. Devuelve los id por nombre."""
    from tests import ayudas
    ids = {"laura": crear_usuario("Laura Méndez Ortiz", CORREOS["laura"], "supervisor", "A1"),
           "javier": crear_usuario("Javier Ruiz Pastor", CORREOS["javier"], "supervisor", "A2")}
    ids["diego"] = crear_usuario("Diego Paredes Luna", CORREOS["diego"], "tecnico", None, ids["laura"])
    ids["nuria"] = crear_usuario("Nuria Vega Santos", CORREOS["nuria"], "tecnico", None, ids["laura"])
    ids["ivan"] = crear_usuario("Iván Cano Rubio", CORREOS["ivan"], "tecnico", None, ids["javier"])
    ids["beatriz"] = crear_usuario("Beatriz Lara Quintana", CORREOS["beatriz"], "auditor", None)
    ids["alvaro"] = crear_usuario("Álvaro Campos Ibarra", CORREOS["alvaro"], "administrador", None)
    for tecnico, supervisor, etiquetas in (("diego", "laura", ("TE-101", "PT-102")),
                                           ("nuria", "laura", ("FT-103", "LT-104")),
                                           ("ivan", "javier", ("PT-201", "LT-202"))):
        for etiqueta in etiquetas:
            ayudas.asignar(conexion, ids[tecnico], etiqueta, ids[supervisor])
    ayudas.sembrar_nominal(conexion)
    return ids


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    from cliente.vista import estilos
    aplicacion = QApplication.instance() or QApplication([])
    aplicacion.setStyleSheet(estilos.HOJA)
    return aplicacion
