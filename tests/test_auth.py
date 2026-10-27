"""T04 y T10 · Login, bloqueo, sesión y caducidad."""
import json

from servidor import config
from servidor.api.auth import MENSAJE_LOGIN
from tests.conftest import CLAVE

CORREO = "laura.mendez@cn-valdecierzo.es"


def login(api, correo=CORREO, password=CLAVE):
    return api.post("/auth/login", json={"correo": correo, "password": password})


# ── Login correcto e incorrecto ──
def test_login_correcto_devuelve_token_nombre_rol_y_area(api, crear_usuario):
    crear_usuario()
    r = login(api)
    assert r.status_code == 200
    datos = r.json()
    assert len(datos["token"]) >= 40
    assert datos["usuario"]["nombre"] == "Laura Méndez Ortiz"
    assert datos["usuario"]["rol"] == "supervisor"
    assert datos["usuario"]["area"] == {"codigo": "A1", "nombre": "Reactor y circuito primario"}
    assert "password" not in str(datos).lower().replace("password_hash", "")


def test_el_correo_no_distingue_mayusculas(api, crear_usuario):
    crear_usuario()
    assert login(api, correo=CORREO.upper()).status_code == 200


def test_login_de_un_tecnico_incluye_a_su_supervisor(api, crear_usuario):
    sup = crear_usuario()
    crear_usuario(nombre="Diego Paredes Luna", correo="diego.paredes@cn-valdecierzo.es", rol="tecnico",
                  area=None, supervisor_id=sup)
    datos = login(api, "diego.paredes@cn-valdecierzo.es").json()
    assert datos["usuario"]["supervisor"]["nombre"] == "Laura Méndez Ortiz"
    assert datos["usuario"]["area"]["codigo"] == "A1"


def test_contrasena_incorrecta(api, crear_usuario):
    crear_usuario()
    r = login(api, password="otra-contraseña-larga")
    assert r.status_code == 401
    assert r.json()["detalle"] == MENSAJE_LOGIN


def test_el_error_es_identico_si_el_correo_no_existe(api, crear_usuario):
    crear_usuario()
    existente = login(api, password="mal-mal-mal-mal")
    inexistente = login(api, correo="nadie@cn-valdecierzo.es", password="mal-mal-mal-mal")
    assert existente.status_code == inexistente.status_code == 401
    assert existente.json() == inexistente.json()


def test_campos_vacios_no_son_validos(api):
    assert api.post("/auth/login", json={"correo": "", "password": ""}).status_code == 422


# ── Bloqueo tras cinco intentos ──
def test_bloqueo_tras_cinco_intentos_fallidos(api, crear_usuario, conexion):
    crear_usuario()
    for _ in range(config.INTENTOS_MAXIMOS):
        assert login(api, password="incorrecta-incorrecta").status_code == 401
    # Con la contraseña buena ya no entra: la cuenta está bloqueada
    r = login(api)
    assert r.status_code == 401 and r.json()["detalle"] == MENSAJE_LOGIN
    fila = conexion.execute("SELECT bloqueado_hasta > datetime('now', '+14 minutes') AS bloqueada FROM usuario").fetchone()
    assert fila["bloqueada"]


def test_cuatro_fallos_no_bloquean(api, crear_usuario):
    crear_usuario()
    for _ in range(config.INTENTOS_MAXIMOS - 1):
        login(api, password="incorrecta-incorrecta")
    assert login(api).status_code == 200


def test_un_acierto_reinicia_el_contador(api, crear_usuario, conexion):
    crear_usuario()
    for _ in range(3):
        login(api, password="incorrecta-incorrecta")
    assert login(api).status_code == 200
    assert conexion.execute("SELECT intentos_fallidos FROM usuario").fetchone()["intentos_fallidos"] == 0


def test_el_bloqueo_termina_a_los_15_minutos(api, crear_usuario, conexion):
    crear_usuario()
    for _ in range(config.INTENTOS_MAXIMOS):
        login(api, password="incorrecta-incorrecta")
    conexion.execute("UPDATE usuario SET bloqueado_hasta = datetime('now', '-1 minute')")
    conexion.commit()
    assert login(api).status_code == 200


# ── Cuentas que no pueden entrar ──
def test_una_cuenta_pendiente_no_puede_iniciar_sesion(api, crear_usuario):
    crear_usuario(estado="pendiente")
    r = login(api)
    assert r.status_code == 401 and r.json()["detalle"] == MENSAJE_LOGIN


def test_cuentas_bloqueadas_o_rechazadas_no_entran(api, crear_usuario):
    crear_usuario(estado="bloqueado")
    crear_usuario(nombre="Javier Ruiz Pastor", correo="javier@cn.es", area="A2", estado="rechazado")
    assert login(api).status_code == 401
    assert login(api, "javier@cn.es").status_code == 401


# ── Sesión y caducidad ──
def test_la_sesion_identifica_al_usuario(api, crear_usuario, entrar):
    crear_usuario()
    token, _ = entrar()
    r = api.get("/auth/yo", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["usuario"]["nombre"] == "Laura Méndez Ortiz"


def test_sin_token_o_con_token_falso_no_hay_sesion(api):
    assert api.get("/auth/yo").status_code == 401
    assert api.get("/auth/yo", headers={"Authorization": "Bearer inventado"}).status_code == 401
    assert api.get("/auth/yo", headers={"Authorization": "Basic abc"}).status_code == 401


def test_la_caducidad_depende_del_rol(api, crear_usuario, entrar, conexion):
    crear_usuario()
    crear_usuario(nombre="Álvaro Campos Ibarra", correo="alvaro@cn.es", rol="administrador", area=None)
    crear_usuario(nombre="Beatriz Lara Quintana", correo="beatriz@cn.es", rol="auditor", area=None)
    esperado = {"laura.mendez@cn-valdecierzo.es": 15, "alvaro@cn.es": 10, "beatriz@cn.es": 15}
    for correo, minutos in esperado.items():
        entrar(correo)
    filas = conexion.execute(
        "SELECT u.correo, round((julianday(s.expira_en) - julianday(s.creada_en)) * 1440) AS minutos"
        " FROM sesion s JOIN usuario u ON u.id = s.usuario_id").fetchall()
    assert {f["correo"]: int(f["minutos"]) for f in filas} == esperado


def test_una_sesion_caducada_deja_de_valer(api, crear_usuario, entrar, conexion):
    crear_usuario()
    token, _ = entrar()
    conexion.execute("UPDATE sesion SET creada_en = datetime('now', '-2 hours'),"
                     " expira_en = datetime('now', '-1 hour')")
    conexion.commit()
    assert api.get("/auth/yo", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_cerrar_sesion_invalida_el_token(api, crear_usuario, entrar):
    crear_usuario()
    token, _ = entrar()
    cabeceras = {"Authorization": f"Bearer {token}"}
    assert api.post("/auth/logout", headers=cabeceras).status_code == 204
    assert api.get("/auth/yo", headers=cabeceras).status_code == 401


def test_si_se_bloquea_la_cuenta_la_sesion_deja_de_valer(api, crear_usuario, entrar, conexion):
    crear_usuario()
    token, _ = entrar()
    conexion.execute("UPDATE usuario SET estado = 'bloqueado'")
    conexion.commit()
    assert api.get("/auth/yo", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_el_token_no_se_guarda_en_la_base_de_datos(api, crear_usuario, entrar, conexion):
    crear_usuario()
    token, _ = entrar()
    guardado = conexion.execute("SELECT token_hash FROM sesion").fetchone()["token_hash"]
    assert token != guardado and token not in guardado


def test_la_contrasena_se_guarda_con_argon2id(crear_usuario, conexion):
    from servidor import seguridad
    crear_usuario(password_hash=seguridad.hashear(CLAVE))
    assert conexion.execute("SELECT password_hash FROM usuario").fetchone()["password_hash"].startswith("$argon2id$")


# ── Registro de eventos ──
def test_los_accesos_quedan_en_el_registro_de_auditoria(api, crear_usuario, conexion):
    crear_usuario()
    login(api, password="incorrecta-incorrecta")
    login(api)
    eventos = conexion.execute("SELECT accion, resultado, detalle FROM evento_auditoria ORDER BY id").fetchall()
    assert [(e["accion"], e["resultado"]) for e in eventos] == [("login", "fallo"), ("login", "ok")]
    assert json.loads(eventos[0]["detalle"])["motivo"] == "contrasena_incorrecta"


def test_el_bloqueo_queda_registrado(api, crear_usuario, conexion):
    crear_usuario()
    for _ in range(config.INTENTOS_MAXIMOS):
        login(api, password="incorrecta-incorrecta")
    motivos = [json.loads(e["detalle"])["motivo"] for e in conexion.execute("SELECT detalle FROM evento_auditoria ORDER BY id")]
    assert motivos[-1] == "cuenta_bloqueada_por_intentos"
