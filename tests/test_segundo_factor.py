"""T11 · Segundo factor: sin el código de 6 dígitos no se entra."""
import pytest

from servidor import config
from servidor.api.auth import MENSAJE_LOGIN
from tests.ayudas import activar_2fa, codigo_de
from tests.conftest import CLAVE, CORREOS


@pytest.fixture(autouse=True)
def con_doble_factor(monkeypatch):
    monkeypatch.setattr(config, "DOBLE_FACTOR_ACTIVO", True)


def login(api, nombre="laura"):
    return api.post("/auth/login", json={"correo": CORREOS[nombre], "password": CLAVE})


def desafio(api, nombre="laura"):
    return login(api, nombre).json()["desafio"]


def verificar(api, token, codigo):
    return api.post("/auth/2fa/verificar", json={"desafio": token, "codigo": codigo})


def eventos(conexion, accion):
    return conexion.execute("SELECT * FROM evento_auditoria WHERE accion = ?", (accion,)).fetchall()


# ── Quién necesita el código ──
@pytest.mark.parametrize("nombre", ["laura", "beatriz", "alvaro"])
def test_supervisor_auditor_y_administrador_no_reciben_sesion_con_solo_la_contrasena(api, central, nombre):
    datos = login(api, nombre).json()
    assert datos["requiere_2fa"] is True and "token" not in datos
    assert datos["configurado"] is False and datos["desafio"]
    assert datos["usuario"]["nombre"]            # el paso 2 enseña quién eres: nombre, rol y área
    assert api.get("/auth/yo").status_code == 401


def test_el_tecnico_entra_solo_con_contrasena(api, central):
    r = login(api, "diego")
    assert r.status_code == 200 and r.json()["token"] and "requiere_2fa" not in r.json()


def test_con_el_doble_factor_desactivado_se_entra_como_antes(api, central, monkeypatch):
    monkeypatch.setattr(config, "DOBLE_FACTOR_ACTIVO", False)
    assert login(api).json()["token"]


def test_una_contrasena_mala_sigue_dando_el_mismo_mensaje_sin_desafio(api, central):
    r = api.post("/auth/login", json={"correo": CORREOS["laura"], "password": "otra-contraseña-larga"})
    assert r.status_code == 401 and r.json()["detalle"] == MENSAJE_LOGIN


# ── Primera vez: configurar con QR ──
def test_la_primera_vez_se_configura_con_qr_y_se_entra(api, central, conexion):
    token = desafio(api)
    c = api.post("/auth/2fa/configurar", json={"desafio": token}).json()
    assert c["uri"].startswith("otpauth://totp/AUREA%20Sentinel:") and c["qr_svg"].startswith("<svg")
    assert len(c["secreto"]) == 32
    r = api.post("/auth/2fa/activar", json={"desafio": token, "codigo": codigo_de(c["secreto"])})
    assert r.status_code == 200
    sesion = r.json()
    assert sesion["usuario"]["rol"] == "supervisor" and sesion["token"]
    yo = api.get("/auth/yo", headers={"Authorization": f"Bearer {sesion['token']}"})
    assert yo.status_code == 200 and yo.json()["usuario"]["nombre"] == "Laura Méndez Ortiz"
    activo = conexion.execute("SELECT activo FROM segundo_factor WHERE usuario_id = ?", (central["laura"],)).fetchone()
    assert activo["activo"] == 1


def test_el_secreto_no_confirmado_no_sirve_para_entrar(api, central):
    token = desafio(api)
    c = api.post("/auth/2fa/configurar", json={"desafio": token}).json()
    # «verificar» es para quien ya tiene el factor activo: antes hay que confirmarlo con «activar»
    assert verificar(api, token, codigo_de(c["secreto"])).status_code == 409


def test_el_secreto_se_guarda_en_la_base_pero_la_respuesta_de_login_no_lo_lleva(api, central, conexion):
    datos = login(api).json()
    assert "secreto" not in str(datos).lower()
    assert conexion.execute("SELECT count(*) AS n FROM segundo_factor").fetchone()["n"] == 0


def test_no_se_puede_volver_a_configurar_un_factor_ya_activo(api, central, conexion):
    activar_2fa(conexion, central["laura"])
    r = api.post("/auth/2fa/configurar", json={"desafio": desafio(api)})
    assert r.status_code == 409


def test_el_qr_de_dos_intentos_de_configuracion_es_el_mismo_secreto_hasta_confirmar(api, central):
    primero = api.post("/auth/2fa/configurar", json={"desafio": desafio(api)}).json()["secreto"]
    segundo = api.post("/auth/2fa/configurar", json={"desafio": desafio(api)}).json()["secreto"]
    assert primero == segundo


# ── Cada día: escribir el código ──
def test_con_el_factor_activo_el_codigo_correcto_abre_la_sesion(api, central, conexion):
    secreto = activar_2fa(conexion, central["laura"])
    datos = login(api).json()
    assert datos["configurado"] is True
    r = verificar(api, datos["desafio"], codigo_de(secreto))
    assert r.status_code == 200 and r.json()["token"]


def test_un_codigo_erroneo_no_abre_la_sesion_y_dice_cuantos_intentos_quedan(api, central, conexion):
    activar_2fa(conexion, central["laura"], "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP")
    token = desafio(api)
    r = verificar(api, token, "000000")
    assert r.status_code == 401 and "Te quedan 2 intentos" in r.json()["detalle"]
    assert "Te quedan 1 intento." in verificar(api, token, "000001").json()["detalle"]


def test_tres_codigos_erroneos_devuelven_al_paso_1_y_dejan_rastro(api, central, conexion):
    secreto = activar_2fa(conexion, central["laura"])
    token = desafio(api)
    for _ in range(2):
        assert verificar(api, token, "111111").status_code == 401
    assert verificar(api, token, "111111").status_code == 423
    # El desafío queda cerrado: ni siquiera el código bueno vale ya.
    assert verificar(api, token, codigo_de(secreto)).status_code == 401
    assert len(eventos(conexion, "2fa_fallido")) == 3
    assert len(eventos(conexion, "2fa_desafio_agotado")) == 1


def test_cinco_fallos_seguidos_bloquean_la_cuenta_15_minutos(api, central, conexion):
    activar_2fa(conexion, central["laura"])
    for _ in range(3):
        verificar(api, desafio(api), "222222")
    verificar(api, desafio(api), "222222")
    ultimo = verificar(api, desafio(api), "222222")
    assert ultimo.status_code == 423
    # Ya bloqueada: con la contraseña correcta no se obtiene ni desafío.
    r = login(api)
    assert r.status_code == 401 and r.json()["detalle"] == MENSAJE_LOGIN and "desafio" not in r.text


def test_acertar_el_codigo_pone_a_cero_los_fallos(api, central, conexion):
    secreto = activar_2fa(conexion, central["laura"])
    token = desafio(api)
    verificar(api, token, "333333")
    assert verificar(api, token, codigo_de(secreto)).status_code == 200
    fallos = conexion.execute("SELECT intentos_fallidos FROM usuario WHERE id = ?", (central["laura"],)).fetchone()
    assert fallos["intentos_fallidos"] == 0


def test_el_mismo_codigo_no_se_puede_usar_dos_veces(api, central, conexion):
    secreto = activar_2fa(conexion, central["laura"])
    codigo = codigo_de(secreto)
    assert verificar(api, desafio(api), codigo).status_code == 200
    assert verificar(api, desafio(api), codigo).status_code == 401
    assert verificar(api, desafio(api), codigo_de(secreto, +1)).status_code == 200   # el siguiente sí


def test_un_desafio_solo_vale_una_vez(api, central, conexion):
    secreto = activar_2fa(conexion, central["laura"])
    token = desafio(api)
    assert verificar(api, token, codigo_de(secreto)).status_code == 200
    assert verificar(api, token, codigo_de(secreto, +1)).status_code == 401


def test_un_desafio_nuevo_anula_el_anterior(api, central, conexion):
    secreto = activar_2fa(conexion, central["laura"])
    viejo, nuevo = desafio(api), desafio(api)
    assert verificar(api, viejo, codigo_de(secreto)).status_code == 401
    assert verificar(api, nuevo, codigo_de(secreto)).status_code == 200


def test_un_desafio_caducado_no_vale(api, central, conexion):
    secreto = activar_2fa(conexion, central["laura"])
    token = desafio(api)
    conexion.execute("UPDATE desafio_2fa SET expira_en = datetime('now', '-1 minute')")
    conexion.commit()
    r = verificar(api, token, codigo_de(secreto))
    assert r.status_code == 401 and "caducado" in r.json()["detalle"]


def test_el_codigo_de_otra_persona_no_sirve(api, central, conexion):
    activar_2fa(conexion, central["laura"])
    otro = activar_2fa(conexion, central["javier"])
    assert verificar(api, desafio(api, "laura"), codigo_de(otro)).status_code == 401


def test_un_desafio_inventado_se_rechaza(api, central):
    assert verificar(api, "no-existe", "123456").status_code == 401
    assert api.post("/auth/2fa/configurar", json={"desafio": "no-existe"}).status_code == 401


def test_si_se_bloquea_la_cuenta_entre_los_dos_pasos_el_desafio_no_vale(api, central, conexion):
    secreto = activar_2fa(conexion, central["laura"])
    token = desafio(api)
    conexion.execute("UPDATE usuario SET bloqueado_hasta = datetime('now', '+10 minutes') WHERE id = ?",
                     (central["laura"],))
    conexion.commit()
    assert verificar(api, token, codigo_de(secreto)).status_code == 423


def test_cada_paso_queda_en_el_registro_de_auditoria(api, central, conexion):
    secreto = activar_2fa(conexion, central["laura"])
    token = desafio(api)
    verificar(api, token, "444444")
    verificar(api, token, codigo_de(secreto))
    acciones = [e["accion"] for e in conexion.execute("SELECT accion FROM evento_auditoria ORDER BY id").fetchall()]
    assert acciones == ["login_primer_paso", "2fa_fallido", "login"]
    assert '"segundo_factor": true' in eventos(conexion, "login")[0]["detalle"]


def test_los_mensajes_de_error_del_codigo_no_revelan_el_secreto(api, central, conexion):
    secreto = activar_2fa(conexion, central["laura"])
    r = verificar(api, desafio(api), "555555")
    assert secreto not in r.text
