"""T12 · Ingesta de lecturas firmadas: firma HMAC, lecturas falsas rechazadas y alarmas."""
import json
import time
from datetime import datetime, timedelta, timezone

import pytest

from servidor import claves, config, ingesta

URL = "/ingesta/lecturas"


def iso(desplazamiento_s: float = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=desplazamiento_s)).strftime("%Y-%m-%dT%H:%M:%SZ")


def lectura(tag="TE-101", valor=325.6, desplazamiento_s=-1):
    return {"tag": tag, "instante": iso(desplazamiento_s), "valor": valor}


def enviar(api, lecturas, clave=None, marca=None, cuerpo=None, con_firma=True):
    """Envía lecturas firmadas como lo hace el simulador. `cuerpo` permite mandar bytes distintos de los firmados."""
    clave = clave or claves.clave_ingesta()
    marca = int(time.time()) if marca is None else marca
    firmado = json.dumps({"lecturas": lecturas}, separators=(",", ":")).encode()
    cabeceras = {"Content-Type": "application/json"}
    if con_firma:
        cabeceras |= {"X-Aurea-Marca": str(marca), "X-Aurea-Firma": ingesta.firmar(clave, marca, firmado)}
    return api.post(URL, content=cuerpo if cuerpo is not None else firmado, headers=cabeceras)


def guardadas(conexion) -> int:
    return conexion.execute("SELECT count(*) AS n FROM lectura").fetchone()["n"]


def eventos(conexion, accion):
    return conexion.execute("SELECT * FROM evento_auditoria WHERE accion = ?", (accion,)).fetchall()


# ── La clave ──
def test_la_clave_se_crea_una_vez_fuera_del_repositorio(monkeypatch):
    monkeypatch.delenv("AUREA_CLAVE_INGESTA", raising=False)
    archivo = config.RUTA_BD.parent / claves.NOMBRE_ARCHIVO
    archivo.unlink(missing_ok=True)
    primera = claves.clave_ingesta()
    assert archivo.is_file() and len(primera) == 64
    assert claves.clave_ingesta() == primera
    assert config.RAIZ not in archivo.parents                      # nunca dentro del repositorio


def test_la_variable_de_entorno_manda_sobre_el_archivo(monkeypatch):
    monkeypatch.setenv("AUREA_CLAVE_INGESTA", "otra-clave")
    assert claves.clave_ingesta() == b"otra-clave"


# ── La firma ──
def test_un_envio_firmado_se_acepta_y_se_guarda(api, conexion):
    r = enviar(api, [lectura()])
    assert r.status_code == 200
    assert r.json() == {"aceptadas": 1, "duplicadas": 0, "rechazadas": []}
    assert guardadas(conexion) == 1


def test_sin_firma_se_rechaza_y_no_se_guarda_nada(api, conexion):
    r = enviar(api, [lectura()], con_firma=False)
    assert r.status_code == 401 and r.json()["detalle"] == "Firma no válida."
    assert guardadas(conexion) == 0
    assert len(eventos(conexion, "ingesta_firma_invalida")) == 1


def test_una_firma_hecha_con_otra_clave_se_rechaza(api, conexion):
    assert enviar(api, [lectura()], clave=b"clave-falsa").status_code == 401
    assert guardadas(conexion) == 0


def test_si_se_cambia_el_cuerpo_despues_de_firmar_se_rechaza(api, conexion):
    manipulado = json.dumps({"lecturas": [lectura(valor=399.0)]}, separators=(",", ":")).encode()
    assert enviar(api, [lectura()], cuerpo=manipulado).status_code == 401
    assert guardadas(conexion) == 0


def test_un_envio_antiguo_repetido_se_rechaza(api, conexion):
    vieja = int(time.time()) - ingesta.TOLERANCIA_RELOJ_S - 5
    assert enviar(api, [lectura()], marca=vieja).status_code == 401
    assert enviar(api, [lectura()], marca=int(time.time()) + ingesta.TOLERANCIA_RELOJ_S + 5).status_code == 401
    assert guardadas(conexion) == 0


def test_todos_los_fallos_de_firma_dan_la_misma_respuesta(api):
    respuestas = [
        enviar(api, [lectura()], con_firma=False).json(),
        enviar(api, [lectura()], clave=b"x").json(),
        enviar(api, [lectura()], marca=1).json(),
        api.post(URL, content=b"{}", headers={"X-Aurea-Marca": "no-es-un-numero", "X-Aurea-Firma": "zzzz"}).json(),
    ]
    assert all(r == respuestas[0] for r in respuestas)


def test_firma_valida_solo_con_clave_cuerpo_y_marca_correctos():
    marca, cuerpo = int(time.time()), b'{"lecturas":[]}'
    firma = ingesta.firmar(b"k", marca, cuerpo)
    assert ingesta.firma_valida(b"k", str(marca), firma, cuerpo)
    assert not ingesta.firma_valida(b"k", str(marca + 1), firma, cuerpo)
    assert not ingesta.firma_valida(b"otra", str(marca), firma, cuerpo)
    assert not ingesta.firma_valida(b"k", str(marca), firma, cuerpo + b" ")
    assert not ingesta.firma_valida(b"k", None, firma, cuerpo)
    assert not ingesta.firma_valida(b"k", str(marca), None, cuerpo)


# ── Lecturas falsas o imposibles ──
@pytest.mark.parametrize("tag, valor", [
    ("TE-101", 400.1),          # por encima del máximo físico del sensor (400 °C)
    ("TE-101", -0.5),           # por debajo del mínimo físico
    ("PT-102", 1e9),
])
def test_un_valor_imposible_se_rechaza(api, conexion, tag, valor):
    r = enviar(api, [lectura(tag, valor)])
    assert r.status_code == 422
    assert r.json()["rechazadas"] == [{"tag": tag, "motivo": "fuera_de_rango_fisico"}]
    assert guardadas(conexion) == 0
    assert len(eventos(conexion, "lectura_rechazada")) == 1


def test_un_valor_no_numerico_no_se_guarda(api, conexion):
    cuerpo = b'{"lecturas":[{"tag":"TE-101","instante":"2026-11-02T10:00:00Z","valor":NaN}]}'
    marca = int(time.time())
    r = api.post(URL, content=cuerpo, headers={"X-Aurea-Marca": str(marca),
                                               "X-Aurea-Firma": ingesta.firmar(claves.clave_ingesta(), marca, cuerpo)})
    assert r.status_code == 422
    assert guardadas(conexion) == 0


def test_un_sensor_que_no_existe_se_rechaza(api, conexion):
    r = enviar(api, [lectura("XX-999")])
    assert r.status_code == 422 and r.json()["rechazadas"][0]["motivo"] == "sensor_desconocido"


def test_un_sensor_desactivado_se_rechaza(api, conexion):
    conexion.execute("UPDATE sensor SET activo = 0 WHERE tag = 'TE-101'")
    conexion.commit()
    assert enviar(api, [lectura()]).json()["rechazadas"][0]["motivo"] == "sensor_inactivo"


@pytest.mark.parametrize("instante, motivo", [
    (iso(+3600), "fecha_en_el_futuro"),
    (iso(-40 * 86400), "fecha_demasiado_antigua"),
    ("ayer por la tarde", "fecha_no_valida"),
])
def test_las_fechas_imposibles_se_rechazan(api, instante, motivo):
    r = enviar(api, [{"tag": "TE-101", "instante": instante, "valor": 325.0}])
    assert r.json()["rechazadas"][0]["motivo"] == motivo


def test_un_envio_mezclado_guarda_lo_bueno_y_rechaza_lo_malo(api, conexion):
    r = enviar(api, [lectura("TE-101", 325.6), lectura("PT-102", 9999.0), lectura("FT-103", 22140.0)])
    assert r.status_code == 200
    assert r.json()["aceptadas"] == 2 and r.json()["rechazadas"] == [{"tag": "PT-102", "motivo": "fuera_de_rango_fisico"}]
    assert guardadas(conexion) == 2
    detalle = json.loads(eventos(conexion, "lectura_rechazada")[0]["detalle"])
    assert detalle == {"cantidad": 1, "motivos": {"fuera_de_rango_fisico": 1}}


def test_repetir_una_lectura_no_la_duplica(api, conexion):
    una = [lectura(desplazamiento_s=-5)]
    assert enviar(api, una).json()["aceptadas"] == 1
    segunda = enviar(api, una).json()
    assert segunda["aceptadas"] == 0 and segunda["duplicadas"] == 1
    assert guardadas(conexion) == 1


def test_no_se_aceptan_mas_de_500_lecturas_por_envio(api):
    muchas = [lectura(desplazamiento_s=-i) for i in range(ingesta.MAX_LECTURAS + 1)]
    assert enviar(api, muchas).status_code == 422
    assert enviar(api, []).status_code == 422


def test_un_cuerpo_que_no_es_json_se_rechaza_aunque_este_firmado(api):
    cuerpo = b"esto no es json"
    marca = int(time.time())
    r = api.post(URL, content=cuerpo, headers={"X-Aurea-Marca": str(marca),
                                               "X-Aurea-Firma": ingesta.firmar(claves.clave_ingesta(), marca, cuerpo)})
    assert r.status_code == 422


# ── Alarmas ──
def alarmas(conexion):
    return conexion.execute("SELECT a.nivel, a.estado, a.valor, a.cerrada_en FROM alarma a ORDER BY a.id").fetchall()


def test_pasar_el_umbral_de_aviso_abre_una_alarma_y_volver_al_rango_la_cierra(api, conexion):
    enviar(api, [lectura("PT-102", 155.0, -30)])                  # nominal
    assert alarmas(conexion) == []
    enviar(api, [lectura("PT-102", 157.4, -20)])                  # aviso alto = 157
    enviar(api, [lectura("PT-102", 157.6, -10)])                  # sigue en aviso: no se abre otra
    abiertas = alarmas(conexion)
    assert len(abiertas) == 1 and abiertas[0]["nivel"] == "aviso" and abiertas[0]["estado"] == "abierta"
    enviar(api, [lectura("PT-102", 155.1, -5)])
    cerrada = alarmas(conexion)[0]
    assert cerrada["estado"] == "cerrada" and cerrada["cerrada_en"] is not None


def test_el_aviso_pasa_a_alarma_si_el_valor_sigue_subiendo(api, conexion):
    enviar(api, [lectura("PT-102", 157.5, -20)])
    enviar(api, [lectura("PT-102", 160.5, -10)])                  # alarma alta = 160
    filas = alarmas(conexion)
    assert len(filas) == 1 and filas[0]["nivel"] == "alarma" and filas[0]["valor"] == 160.5


def test_los_umbrales_bajos_tambien_cuentan(api, conexion):
    enviar(api, [lectura("PT-102", 151.0, -10)])                  # aviso bajo = 152
    assert alarmas(conexion)[0]["nivel"] == "aviso"


def test_una_lectura_atrasada_no_abre_ni_cierra_alarmas(api, conexion):
    enviar(api, [lectura("PT-102", 155.0, -10)])
    enviar(api, [lectura("PT-102", 159.0, -300)])                 # antigua y en aviso: se guarda, pero no abre nada
    assert guardadas(conexion) == 2 and alarmas(conexion) == []


def test_transicion_de_alarmas():
    assert ingesta.transicion(None, "normal") == "nada"
    assert ingesta.transicion(None, "aviso") == "abrir"
    assert ingesta.transicion("aviso", "aviso") == "nada"
    assert ingesta.transicion("aviso", "alarma") == "escalar"
    assert ingesta.transicion("alarma", "aviso") == "nada"
    assert ingesta.transicion("alarma", "normal") == "cerrar"
