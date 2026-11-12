"""T14 · Lecturas falsas: firmas incorrectas y lecturas manipuladas contra la ingesta de T12.

Primero se ataca la firma (sin conocer la clave del simulador) y después se envían lecturas manipuladas con una firma
válida, como haría un simulador averiado o comprometido. Los resultados están en el capítulo 7.2 de DOCUMENTACION.md.
"""
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

import pytest

from servidor import claves, ingesta
from servidor.api.ingesta import MENSAJE_FIRMA

URL = "/ingesta/lecturas"


def iso(desplazamiento_s: float = -1) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=desplazamiento_s)).strftime("%Y-%m-%dT%H:%M:%SZ")


def cuerpo_de(lecturas) -> bytes:
    return json.dumps({"lecturas": lecturas}, separators=(",", ":")).encode()


def lectura(tag="TE-101", valor=325.6, desplazamiento_s=-1) -> dict:
    return {"tag": tag, "instante": iso(desplazamiento_s), "valor": valor}


def post(api, cuerpo: bytes, marca, firma):
    cabeceras = {"Content-Type": "application/json"}
    if marca is not None:
        cabeceras["X-Aurea-Marca"] = str(marca)
    if firma is not None:
        cabeceras["X-Aurea-Firma"] = firma
    return api.post(URL, content=cuerpo, headers=cabeceras)


def firmado(api, lecturas=None, cuerpo: bytes | None = None):
    """Envío con la firma buena, como el simulador."""
    cuerpo = cuerpo if cuerpo is not None else cuerpo_de(lecturas)
    marca = int(time.time())
    return post(api, cuerpo, marca, ingesta.firmar(claves.clave_ingesta(), marca, cuerpo))


def guardadas(conexion) -> int:
    return conexion.execute("SELECT count(*) AS n FROM lectura").fetchone()["n"]


def firmas_rechazadas(conexion) -> int:
    return conexion.execute("SELECT count(*) AS n FROM evento_auditoria"
                            " WHERE accion = 'ingesta_firma_invalida'").fetchone()["n"]


def rechazado_por_firma(r, conexion) -> bool:
    return (r.status_code == 401 and r.json() == {"detalle": MENSAJE_FIRMA}
            and guardadas(conexion) == 0 and firmas_rechazadas(conexion) == 1)


# ── Firmas incorrectas ──
@pytest.mark.parametrize("clave", [b"", b"aurea", b"Valdecierzo-2026!", b"0" * 64])
def test_una_clave_adivinada_no_sirve(api, conexion, clave):
    cuerpo, marca = cuerpo_de([lectura()]), int(time.time())
    assert rechazado_por_firma(post(api, cuerpo, marca, ingesta.firmar(clave, marca, cuerpo)), conexion)


@pytest.mark.parametrize("algoritmo", [hashlib.md5, hashlib.sha1, hashlib.sha512])
def test_una_firma_con_otro_algoritmo_se_rechaza(api, conexion, algoritmo):
    cuerpo, marca = cuerpo_de([lectura()]), int(time.time())
    firma = hmac.new(claves.clave_ingesta(), f"{marca}.".encode() + cuerpo, algoritmo).hexdigest()
    assert rechazado_por_firma(post(api, cuerpo, marca, firma), conexion)


@pytest.mark.parametrize("retoque", ["truncada", "mayusculas", "un_caracter", "repetida", "vacia"])
def test_una_firma_retocada_se_rechaza(api, conexion, retoque):
    cuerpo, marca = cuerpo_de([lectura()]), int(time.time())
    buena = ingesta.firmar(claves.clave_ingesta(), marca, cuerpo)
    firma = {"truncada": buena[:32], "mayusculas": buena.upper(),
             "un_caracter": buena[:-1] + ("0" if buena[-1] != "0" else "1"),
             "repetida": buena + buena, "vacia": ""}[retoque]
    assert rechazado_por_firma(post(api, cuerpo, marca, firma), conexion)


def test_firmar_solo_el_cuerpo_sin_la_marca_no_sirve(api, conexion):
    cuerpo, marca = cuerpo_de([lectura()]), int(time.time())
    firma = hmac.new(claves.clave_ingesta(), cuerpo, hashlib.sha256).hexdigest()
    assert rechazado_por_firma(post(api, cuerpo, marca, firma), conexion)


def test_cambiar_la_marca_despues_de_firmar_se_detecta(api, conexion):
    cuerpo, marca = cuerpo_de([lectura()]), int(time.time())
    firma = ingesta.firmar(claves.clave_ingesta(), marca, cuerpo)
    assert rechazado_por_firma(post(api, cuerpo, marca + 1, firma), conexion)


@pytest.mark.parametrize("marca", ["", "abc", "12.5", "-1", "1e10", str(2 ** 63)])
def test_una_marca_de_tiempo_falsa_se_rechaza(api, conexion, marca):
    cuerpo = cuerpo_de([lectura()])
    firma = ingesta.firmar(claves.clave_ingesta(), 0, cuerpo)
    assert rechazado_por_firma(post(api, cuerpo, marca, firma), conexion)


def test_un_envio_firmado_con_la_hora_del_futuro_se_rechaza(api, conexion):
    cuerpo = cuerpo_de([lectura()])
    marca = int(time.time()) + ingesta.TOLERANCIA_RELOJ_S + 60
    assert rechazado_por_firma(post(api, cuerpo, marca, ingesta.firmar(claves.clave_ingesta(), marca, cuerpo)),
                               conexion)


@pytest.mark.parametrize("cambio", ["valor", "tag", "instante", "lectura_de_mas"])
def test_reutilizar_la_firma_de_un_envio_bueno_con_otros_datos_no_cuela(api, conexion, cambio):
    original = [lectura()]
    cuerpo, marca = cuerpo_de(original), int(time.time())
    firma = ingesta.firmar(claves.clave_ingesta(), marca, cuerpo)
    falso = [dict(original[0])]
    if cambio == "valor":
        falso[0]["valor"] = 300.0
    elif cambio == "tag":
        falso[0]["tag"] = "PT-102"
    elif cambio == "instante":
        falso[0]["instante"] = iso(-120)
    else:
        falso.append(lectura("PT-102", 15.5))
    assert rechazado_por_firma(post(api, cuerpo_de(falso), marca, firma), conexion)


def test_una_sesion_de_usuario_no_sustituye_a_la_firma(api, central, entrar, conexion):
    token, _ = entrar()
    antes = guardadas(conexion)
    r = api.post(URL, content=cuerpo_de([lectura(desplazamiento_s=60)]),
                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    assert r.status_code == 401 and r.json() == {"detalle": MENSAJE_FIRMA}
    assert guardadas(conexion) == antes and firmas_rechazadas(conexion) == 1


def test_repetir_un_envio_bueno_dentro_del_margen_no_guarda_nada_nuevo(api, conexion):
    cuerpo, marca = cuerpo_de([lectura()]), int(time.time())
    firma = ingesta.firmar(claves.clave_ingesta(), marca, cuerpo)
    assert post(api, cuerpo, marca, firma).json()["aceptadas"] == 1
    otra_vez = post(api, cuerpo, marca, firma)
    assert otra_vez.status_code == 200 and otra_vez.json() == {"aceptadas": 0, "duplicadas": 1, "rechazadas": []}
    assert guardadas(conexion) == 1


# ── Lecturas manipuladas con firma válida ──
def test_ningun_sensor_acepta_valores_fuera_de_su_rango_fisico(api, conexion):
    sensores = conexion.execute("SELECT tag, min_fisico, max_fisico FROM sensor WHERE activo = 1").fetchall()
    assert len(sensores) == 36
    fuera = []
    for s in sensores:
        margen = (s["max_fisico"] - s["min_fisico"]) * 0.001
        fuera += [lectura(s["tag"], s["min_fisico"] - margen, -5), lectura(s["tag"], s["max_fisico"] + margen, -6)]
    r = firmado(api, fuera)
    assert r.status_code == 422
    assert len(r.json()["rechazadas"]) == 72
    assert {x["motivo"] for x in r.json()["rechazadas"]} == {"fuera_de_rango_fisico"}
    assert guardadas(conexion) == 0


def test_los_limites_fisicos_exactos_si_se_aceptan(api, conexion):
    sensores = conexion.execute("SELECT tag, min_fisico, max_fisico FROM sensor WHERE activo = 1").fetchall()
    limites = []
    for s in sensores:
        limites += [lectura(s["tag"], s["min_fisico"], -5), lectura(s["tag"], s["max_fisico"], -6)]
    r = firmado(api, limites)
    assert r.status_code == 200 and r.json()["aceptadas"] == 72


@pytest.mark.parametrize("valor", [b"NaN", b"Infinity", b"-Infinity", b"1e309", b"null", b"[1]", b'{"v":1}', b'""'])
def test_un_valor_que_no_es_un_numero_no_se_guarda(api, conexion, valor):
    cuerpo = b'{"lecturas":[{"tag":"TE-101","instante":"' + iso().encode() + b'","valor":' + valor + b"}]}"
    r = firmado(api, cuerpo=cuerpo)
    assert r.status_code == 422
    assert guardadas(conexion) == 0


@pytest.mark.xfail(strict=True, reason="Hallazgo de T14: con firma válida se acepta true/false y el número en texto "
                                       "(Pydantic los convierte a float). Pendiente de T12.")
@pytest.mark.parametrize("valor", [True, "325.6"])
def test_un_valor_booleano_o_en_texto_no_se_guarda(api, conexion, valor):
    r = firmado(api, [lectura(valor=valor)])
    assert r.status_code == 422
    assert guardadas(conexion) == 0


@pytest.mark.parametrize("tag", ["te-101", "TE-101 ", " TE-101", "TE‑101", "TE-101' OR '1'='1", "TE-1O1"])
def test_un_tag_parecido_al_de_un_sensor_real_se_rechaza(api, conexion, tag):
    r = firmado(api, [lectura(tag)])
    assert r.status_code == 422
    assert r.json()["rechazadas"] == [{"tag": tag, "motivo": "sensor_desconocido"}]
    assert guardadas(conexion) == 0


@pytest.mark.parametrize("instante, motivo", [
    ("1970-01-01T00:00:00Z", "fecha_demasiado_antigua"),
    ("9999-12-31T23:59:59Z", "fecha_en_el_futuro"),
    ("ahora", "fecha_no_valida"),
    ("2026-02-30T10:00:00Z", "fecha_no_valida"),
    ("2026-11-02T25:00:00Z", "fecha_no_valida"),
])
def test_una_fecha_falsa_se_rechaza(api, conexion, instante, motivo):
    r = firmado(api, [{"tag": "TE-101", "instante": instante, "valor": 325.6}])
    assert r.status_code == 422
    assert r.json()["rechazadas"] == [{"tag": "TE-101", "motivo": motivo}]


def test_una_hora_con_otra_zona_horaria_que_cae_en_el_futuro_se_rechaza(api, conexion):
    futuro = datetime.now(timezone(timedelta(hours=-5))) + timedelta(hours=1)
    r = firmado(api, [{"tag": "TE-101", "instante": futuro.isoformat(timespec="seconds"), "valor": 325.6}])
    assert r.status_code == 422
    assert r.json()["rechazadas"][0]["motivo"] == "fecha_en_el_futuro"


def test_no_se_puede_reescribir_una_lectura_ya_guardada(api, conexion):
    original = lectura(valor=325.6, desplazamiento_s=-30)
    assert firmado(api, [original]).json()["aceptadas"] == 1
    r = firmado(api, [original | {"valor": 300.0}])
    assert r.json() == {"aceptadas": 0, "duplicadas": 1, "rechazadas": []}
    assert conexion.execute("SELECT valor FROM lectura").fetchone()["valor"] == 325.6


def test_los_campos_de_mas_se_ignoran(api, conexion):
    falsa = lectura() | {"valida": 0, "sensor_id": 36, "area": "A9", "firma": "x"}
    assert firmado(api, [falsa]).json()["aceptadas"] == 1
    fila = conexion.execute("SELECT s.tag, l.valida FROM lectura l JOIN sensor s ON s.id = l.sensor_id").fetchone()
    assert (fila["tag"], fila["valida"]) == ("TE-101", 1)


def test_cada_lectura_manipulada_queda_en_el_registro(api, conexion):
    firmado(api, [lectura("XX-999"), lectura(valor=-1e6), {"tag": "TE-101", "instante": "ahora", "valor": 1.0},
                  lectura("PT-102", 15.5)])
    fila = conexion.execute("SELECT resultado, detalle FROM evento_auditoria"
                            " WHERE accion = 'lectura_rechazada'").fetchone()
    assert fila["resultado"] == "fallo"
    assert json.loads(fila["detalle"]) == {"cantidad": 3, "motivos": {
        "sensor_desconocido": 1, "fuera_de_rango_fisico": 1, "fecha_no_valida": 1}}
    assert guardadas(conexion) == 1
