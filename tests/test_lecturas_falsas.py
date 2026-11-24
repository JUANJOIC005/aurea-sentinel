"""T14 · Lecturas manipuladas y firmas incorrectas: 30 intentos de colar datos falsos (F01 a F30).

Un envío falso debe responder 401 (firma) o 422 (datos), no guardar nada y, si lo que falla son los datos,
dejar anotado el rechazo en el registro de auditoría.
"""
import json
import time

import pytest

from servidor import claves, ingesta
from tests.test_ingesta import URL, alarmas, enviar, eventos, guardadas, iso, lectura


def enviar_bruto(api, cuerpo: bytes, clave: bytes | None = None, marca: int | None = None):
    """Firma exactamente estos bytes y los envía: sirve para cuerpos que `enviar` no sabría construir."""
    marca = int(time.time()) if marca is None else marca
    return api.post(URL, content=cuerpo, headers={
        "Content-Type": "application/json", "X-Aurea-Marca": str(marca),
        "X-Aurea-Firma": ingesta.firmar(clave or claves.clave_ingesta(), marca, cuerpo)})


def cuerpo_de(*lecturas) -> bytes:
    return json.dumps({"lecturas": list(lecturas)}, separators=(",", ":")).encode()


def nada_guardado(conexion):
    assert guardadas(conexion) == 0


# ── Firmas incorrectas (F01 a F10) ──
def test_f01_envio_sin_firma(api, conexion):
    assert enviar(api, [lectura()], con_firma=False).status_code == 401
    nada_guardado(conexion)


def test_f02_firma_hecha_con_otra_clave(api, conexion):
    assert enviar(api, [lectura()], clave=b"clave-de-un-atacante").status_code == 401
    nada_guardado(conexion)


def test_f03_valor_alterado_despues_de_firmar(api, conexion):
    firmado = cuerpo_de(lectura(valor=325.6))
    manipulado = cuerpo_de(lectura(valor=399.0))
    assert enviar(api, [lectura(valor=325.6)], cuerpo=manipulado).status_code == 401
    assert firmado != manipulado
    nada_guardado(conexion)


def test_f04_lectura_anadida_despues_de_firmar(api, conexion):
    con_extra = cuerpo_de(lectura(), lectura("PT-102", 155.0, -2))
    assert enviar(api, [lectura()], cuerpo=con_extra).status_code == 401
    nada_guardado(conexion)


def test_f05_reenvio_de_un_envio_antiguo(api, conexion):
    hace_10_minutos = int(time.time()) - 600
    assert enviar(api, [lectura()], marca=hace_10_minutos).status_code == 401
    nada_guardado(conexion)


def test_f06_marca_de_tiempo_del_futuro(api, conexion):
    assert enviar(api, [lectura()], marca=int(time.time()) + 600).status_code == 401
    nada_guardado(conexion)


def test_f07_firma_en_mayusculas(api, conexion):
    cuerpo = cuerpo_de(lectura())
    marca = int(time.time())
    firma = ingesta.firmar(claves.clave_ingesta(), marca, cuerpo)
    r = api.post(URL, content=cuerpo, headers={"X-Aurea-Marca": str(marca), "X-Aurea-Firma": firma.upper()})
    assert r.status_code == 401
    nada_guardado(conexion)


def test_f08_firma_cortada(api, conexion):
    cuerpo = cuerpo_de(lectura())
    marca = int(time.time())
    firma = ingesta.firmar(claves.clave_ingesta(), marca, cuerpo)
    r = api.post(URL, content=cuerpo, headers={"X-Aurea-Marca": str(marca), "X-Aurea-Firma": firma[:32]})
    assert r.status_code == 401
    nada_guardado(conexion)


def test_f09_marca_que_no_es_un_numero(api, conexion):
    cuerpo = cuerpo_de(lectura())
    r = api.post(URL, content=cuerpo, headers={"X-Aurea-Marca": "manana", "X-Aurea-Firma": "0" * 64})
    assert r.status_code == 401
    nada_guardado(conexion)


def test_f10_una_sesion_de_supervisor_no_sirve_para_mandar_lecturas(api, central, entrar, conexion):
    from tests.conftest import CORREOS
    token, _ = entrar(CORREOS["laura"])
    antes = guardadas(conexion)                  # la central de pruebas ya trae lecturas
    r = api.post(URL, content=cuerpo_de(lectura()),
                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    assert r.status_code == 401
    assert guardadas(conexion) == antes


# ── Valores imposibles o con otra forma (F11 a F18) ──
def test_f11_valor_por_encima_del_maximo_fisico(api, conexion):
    r = enviar(api, [lectura("TE-101", 450.0)])
    assert r.status_code == 422 and r.json()["rechazadas"][0]["motivo"] == "fuera_de_rango_fisico"
    nada_guardado(conexion)


def test_f12_valor_por_debajo_del_minimo_fisico(api, conexion):
    assert enviar(api, [lectura("PT-102", -10.0)]).status_code == 422
    nada_guardado(conexion)


def test_f13_valor_nan(api, conexion):
    cuerpo = b'{"lecturas":[{"tag":"TE-101","instante":"%s","valor":NaN}]}' % iso(-1).encode()
    assert enviar_bruto(api, cuerpo).status_code == 422
    nada_guardado(conexion)


def test_f14_valor_infinito(api, conexion):
    cuerpo = b'{"lecturas":[{"tag":"TE-101","instante":"%s","valor":Infinity}]}' % iso(-1).encode()
    assert enviar_bruto(api, cuerpo).status_code == 422
    nada_guardado(conexion)


def test_f15_valor_escrito_como_texto_con_coma(api, conexion):
    cuerpo = cuerpo_de({"tag": "TE-101", "instante": iso(-1), "valor": "325,6"})
    assert enviar_bruto(api, cuerpo).status_code == 422
    nada_guardado(conexion)


def test_f16_valor_nulo(api, conexion):
    cuerpo = cuerpo_de({"tag": "TE-101", "instante": iso(-1), "valor": None})
    assert enviar_bruto(api, cuerpo).status_code == 422
    nada_guardado(conexion)


def test_f17_sensor_que_no_existe(api, conexion):
    r = enviar(api, [lectura("ZZ-999")])
    assert r.status_code == 422 and r.json()["rechazadas"][0]["motivo"] == "sensor_desconocido"
    nada_guardado(conexion)


def test_f18_inyeccion_sql_en_el_tag(api, conexion):
    r = enviar(api, [lectura("TE-101'; DROP TABLE lectura;--")])
    assert r.status_code == 422
    assert conexion.execute("SELECT count(*) AS n FROM sensor").fetchone()["n"] == 36
    nada_guardado(conexion)                      # la tabla sigue existiendo y vacía


# ── Fechas falsas (F19 a F21) ──
def test_f19_fecha_en_el_futuro(api, conexion):
    r = enviar(api, [{"tag": "TE-101", "instante": iso(+7200), "valor": 325.6}])
    assert r.json()["rechazadas"][0]["motivo"] == "fecha_en_el_futuro"
    nada_guardado(conexion)


def test_f20_fecha_de_hace_mas_de_un_mes(api, conexion):
    r = enviar(api, [{"tag": "TE-101", "instante": iso(-45 * 86400), "valor": 325.6}])
    assert r.json()["rechazadas"][0]["motivo"] == "fecha_demasiado_antigua"
    nada_guardado(conexion)


def test_f21_fecha_mal_formada(api, conexion):
    r = enviar(api, [{"tag": "TE-101", "instante": "32/13/2026", "valor": 325.6}])
    assert r.json()["rechazadas"][0]["motivo"] == "fecha_no_valida"
    nada_guardado(conexion)


# ── Manipular lo que ya está guardado o saturar (F22 a F26) ──
def test_f22_repetir_un_instante_con_otro_valor_no_pisa_el_original(api, conexion):
    instante = iso(-30)
    enviar(api, [{"tag": "TE-101", "instante": instante, "valor": 325.6}])
    r = enviar(api, [{"tag": "TE-101", "instante": instante, "valor": 399.0}])
    assert r.json()["duplicadas"] == 1 and r.json()["aceptadas"] == 0
    assert conexion.execute("SELECT valor FROM lectura").fetchone()["valor"] == 325.6


def test_f23_envio_de_501_lecturas(api, conexion):
    muchas = [lectura(desplazamiento_s=-i - 1) for i in range(ingesta.MAX_LECTURAS + 1)]
    assert enviar(api, muchas).status_code == 422
    nada_guardado(conexion)


def test_f24_envio_vacio(api, conexion):
    assert enviar(api, []).status_code == 422
    nada_guardado(conexion)


def test_f25_cuerpo_que_no_es_json(api, conexion):
    assert enviar_bruto(api, b"<script>alert(1)</script>").status_code == 422
    nada_guardado(conexion)


def test_f26_sensor_desactivado(api, conexion):
    conexion.execute("UPDATE sensor SET activo = 0 WHERE tag = 'FT-103'")
    conexion.commit()
    assert enviar(api, [lectura("FT-103", 22140.0)]).json()["rechazadas"][0]["motivo"] == "sensor_inactivo"
    nada_guardado(conexion)


# ── Mezclas, fronteras y efectos secundarios (F27 a F30) ──
def test_f27_en_un_envio_mezclado_solo_se_guarda_lo_valido_y_se_anota_lo_demas(api, conexion):
    r = enviar(api, [lectura("TE-101", 325.6), lectura("PT-102", 9999.0), lectura("XX-000"), lectura("FT-103", 22140.0)])
    assert r.status_code == 200 and r.json()["aceptadas"] == 2 and len(r.json()["rechazadas"]) == 2
    assert guardadas(conexion) == 2
    detalle = json.loads(eventos(conexion, "lectura_rechazada")[0]["detalle"])
    assert detalle["cantidad"] == 2 and detalle["motivos"] == {"fuera_de_rango_fisico": 1, "sensor_desconocido": 1}


def test_f28_una_lectura_falsa_no_abre_alarmas(api, conexion):
    enviar(api, [lectura("PT-102", 999.0)])
    assert alarmas(conexion) == [] and guardadas(conexion) == 0


def test_f29_el_limite_justo_del_sensor_se_acepta_y_un_poco_mas_no(api, conexion):
    assert enviar(api, [lectura("TE-101", 400.0, -3)]).status_code == 200          # máximo físico de TE-101
    assert enviar(api, [lectura("TE-101", 400.01, -2)]).status_code == 422
    assert guardadas(conexion) == 1


def test_f30_una_firma_buena_no_vale_para_el_mismo_cuerpo_con_un_espacio_de_mas(api, conexion):
    limpio = cuerpo_de(lectura())
    marca = int(time.time())
    firma = ingesta.firmar(claves.clave_ingesta(), marca, limpio)
    r = api.post(URL, content=limpio + b" ", headers={"X-Aurea-Marca": str(marca), "X-Aurea-Firma": firma})
    assert r.status_code == 401
    nada_guardado(conexion)


def test_hay_exactamente_30_casos_con_su_numero():
    numeros = sorted(n for n in globals() if n.startswith("test_f") and n[6:8].isdigit() or
                     n.startswith("test_f") and n[6].isdigit())
    assert [n[5:8] for n in numeros] == [f"f{i:02d}" for i in range(1, 31)]
