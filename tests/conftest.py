import os
import tempfile

os.environ["AUREA_BD"] = os.path.join(tempfile.mkdtemp(prefix="aurea-bd-"), "pruebas.db")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="aurea-config-")

import pytest
from fastapi.testclient import TestClient

from servidor import db, migrate, seguridad
from servidor.api.main import app

CLAVE = "Valdecierzo-2026-ok!"
HASH_CLAVE = seguridad.hashear(CLAVE)


@pytest.fixture(autouse=True)
def base_de_datos():
    migrate.desde_cero()
    migrate.preparar()


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


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    from cliente.vista import estilos
    aplicacion = QApplication.instance() or QApplication([])
    aplicacion.setStyleSheet(estilos.HOJA)
    return aplicacion
