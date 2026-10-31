import httpx

from cliente.modelo.api import ClienteApi
from servidor import config, datos_demo, db, local


def test_la_primera_vez_se_crea_la_base_y_las_cuentas_de_demostracion(conexion):
    conexion.execute("DELETE FROM usuario")
    conexion.commit()
    assert local.preparar_base_de_datos() is True
    assert conexion.execute("SELECT count(*) AS n FROM usuario").fetchone()["n"] == len(datos_demo.PERSONAS)


def test_si_ya_hay_cuentas_no_se_siembra_nada(crear_usuario, conexion):
    crear_usuario()
    assert local.preparar_base_de_datos() is False
    assert conexion.execute("SELECT count(*) AS n FROM usuario").fetchone()["n"] == 1


def test_la_base_de_datos_es_un_archivo_local():
    assert config.RUTA_BD.suffix == ".db"
    assert config.RUTA_BD.exists()


def test_el_servidor_local_responde_en_un_puerto_libre():
    servidor = local.iniciar()
    try:
        assert servidor.url.startswith("http://127.0.0.1:") and servidor.puerto > 0
        assert httpx.get(servidor.url + "/salud").json() == {"estado": "ok"}
        cliente = ClienteApi(servidor.url)
        sesion = cliente.login(datos_demo.correo_de(datos_demo.PERSONAS[0][0]), datos_demo.password_demo())
        assert sesion["usuario"]["rol"] == "supervisor"
    finally:
        servidor.parar()


def test_fechas_de_la_base_de_datos():
    assert db.a_fecha(None) is None
    fecha = db.a_fecha("2026-11-01 10:30:00")
    assert fecha.tzinfo is not None and fecha.hour == 10
