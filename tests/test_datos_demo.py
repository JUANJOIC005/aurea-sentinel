"""Cuentas de demostración: cumplen lo que pide el enunciado y se pueden usar para entrar."""
from servidor import datos_demo

CLAVE_DEMO = "Demo-Valdecierzo-2026!"


def test_correo_sin_tildes_ni_espacios():
    assert datos_demo.correo_de("Laura Méndez Ortiz") == "laura.mendez@cn-valdecierzo.es"
    assert datos_demo.correo_de("Óscar Medina Torres") == "oscar.medina@cn-valdecierzo.es"
    assert datos_demo.correo_de("Iván Cano Rubio") == "ivan.cano@cn-valdecierzo.es"


def test_los_correos_son_todos_distintos():
    correos = [datos_demo.correo_de(p[0]) for p in datos_demo.PERSONAS]
    assert len(correos) == len(set(correos)) == 18


def test_cumple_los_requisitos_de_datos_del_profesor(conexion):
    assert datos_demo.crear_cuentas(conexion, CLAVE_DEMO) == 18
    por_rol = {f["rol"]: f["n"] for f in conexion.execute(
        "SELECT r.codigo AS rol, count(*) AS n FROM usuario u JOIN rol r ON r.id = u.rol_id GROUP BY 1")}
    assert por_rol == {"supervisor": 9, "tecnico": 6, "auditor": 2, "administrador": 1}      # ≥ 9 principales, ≥ 4 relacionados
    con_varios = conexion.execute(
        "SELECT count(*) AS n FROM (SELECT supervisor_id FROM usuario WHERE supervisor_id IS NOT NULL"
        " GROUP BY 1 HAVING count(*) > 1) t").fetchone()["n"]
    assert con_varios >= 1                                                                    # alguno con varios técnicos
    assert conexion.execute("SELECT count(DISTINCT area_id) AS n FROM usuario WHERE rol_id = 1").fetchone()["n"] == 9


def test_repetirlo_no_duplica_nada(conexion):
    datos_demo.crear_cuentas(conexion, CLAVE_DEMO)
    assert datos_demo.crear_cuentas(conexion, CLAVE_DEMO) == 0
    assert conexion.execute("SELECT count(*) AS n FROM usuario").fetchone()["n"] == 18


def test_cada_tecnico_esta_en_el_area_de_su_supervisor(conexion):
    datos_demo.crear_cuentas(conexion, CLAVE_DEMO)
    mal = conexion.execute("SELECT count(*) AS n FROM usuario t JOIN usuario s ON s.id = t.supervisor_id"
                           " WHERE t.area_id <> s.area_id").fetchone()["n"]
    assert mal == 0


def test_se_puede_entrar_con_una_cuenta_de_demo(api, conexion):
    datos_demo.crear_cuentas(conexion, CLAVE_DEMO)
    conexion.commit()
    r = api.post("/auth/login", json={"correo": "diego.paredes@cn-valdecierzo.es", "password": CLAVE_DEMO})
    assert r.status_code == 200
    usuario = r.json()["usuario"]
    assert usuario["rol"] == "tecnico" and usuario["supervisor"]["nombre"] == "Laura Méndez Ortiz"
