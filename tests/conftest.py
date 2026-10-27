"""Preparación común de las pruebas.

Las pruebas usan una base de datos temporal propia (AUREA_BD apunta a una carpeta temporal):
se recrea desde cero antes de cada prueba, así que nunca tocan los datos del usuario.
"""
import os
import tempfile

os.environ["AUREA_BD"] = os.path.join(tempfile.mkdtemp(prefix="aurea-bd-"), "pruebas.db")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="aurea-config-")  # QSettings no toca los del usuario

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from servidor import db, migrate, seguridad  # noqa: E402
from servidor.api.main import app  # noqa: E402

CLAVE = "Valdecierzo-2026-ok!"
HASH_CLAVE = seguridad.hashear(CLAVE)   # se calcula una vez: Argon2 es lento a propósito


@pytest.fixture(autouse=True)
def base_de_datos():
    """Cada prueba empieza con la base recién creada: catálogo de áreas y sensores, sin usuarios ni lecturas."""
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
    """Inicia sesión por la API y devuelve (token, respuesta)."""
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
