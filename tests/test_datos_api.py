"""T11 · Datos de la central: cada persona ve solo lo suyo."""
import json
from datetime import timedelta

import pytest

from tests import ayudas
from tests.conftest import CORREOS


@pytest.fixture
def pedir(api, entrar):
    def _pedir(nombre, ruta, **params):
        token, _ = entrar(CORREOS[nombre])
        return api.get(ruta, params=params, headers={"Authorization": f"Bearer {token}"})
    return _pedir


def tags(respuesta):
    return [s["tag"] for s in respuesta.json()["sensores"]]


def denegaciones(conexion):
    return conexion.execute("SELECT * FROM evento_auditoria WHERE accion = 'acceso_denegado'").fetchall()


# ── Lecturas en directo ──
def test_el_supervisor_ve_los_4_sensores_de_su_area_y_solo_esos(central, pedir):
    r = pedir("laura", "/lecturas/ultimas")
    assert r.status_code == 200
    assert tags(r) == ["TE-101", "PT-102", "FT-103", "LT-104"]
    assert {s["area"]["codigo"] for s in r.json()["sensores"]} == {"A1"}
    assert tags(pedir("javier", "/lecturas/ultimas")) == ["PT-201", "LT-202", "TE-203", "FT-204"]


def test_la_tarjeta_de_un_sensor_lleva_valor_estado_tendencia_umbrales_y_serie(central, pedir):
    t = pedir("laura", "/lecturas/ultimas").json()["sensores"][0]
    assert t["tag"] == "TE-101" and t["unidad"] == "°C" and t["valor"] == 325.6 and t["estado"] == "normal"
    assert t["umbrales"] == {"aviso_bajo": None, "alarma_bajo": None, "aviso_alto": 327.0, "alarma_alto": 330.0}
    assert t["tendencia_1h"] == 0.0 and len(t["serie"]) == 12 and t["edad_s"] < 60
    assert t["instante"].endswith("Z") and t["alarma"] is None


@pytest.mark.parametrize("valor, estado", [(325.0, "normal"), (327.0, "aviso"), (328.5, "aviso"),
                                           (330.0, "alarma"), (399.0, "alarma")])
def test_el_estado_sale_de_comparar_el_ultimo_valor_con_los_umbrales(central, conexion, pedir, valor, estado):
    ayudas.sembrar(conexion, "TE-101", [valor], fin=ayudas.ahora() + timedelta(seconds=10))
    t = pedir("laura", "/lecturas/ultimas").json()["sensores"][0]
    assert (t["valor"], t["estado"]) == (valor, estado)


def test_umbrales_por_debajo_tambien_cuentan(central, conexion, pedir):
    ayudas.sembrar(conexion, "PT-102", [151.0], fin=ayudas.ahora() + timedelta(seconds=10))   # aviso bajo 152
    estado = {s["tag"]: s["estado"] for s in pedir("laura", "/lecturas/ultimas").json()["sensores"]}
    assert estado["PT-102"] == "aviso" and estado["TE-101"] == "normal"


def test_la_tendencia_es_la_diferencia_con_el_valor_de_hace_una_hora(central, conexion, pedir):
    conexion.execute("DELETE FROM lectura WHERE sensor_id = (SELECT id FROM sensor WHERE tag = 'PT-102')")
    ayudas.sembrar(conexion, "PT-102", [150.0, 151.0, 152.0, 153.0, 154.0, 155.0], paso_s=600)
    t = [s for s in pedir("laura", "/lecturas/ultimas").json()["sensores"] if s["tag"] == "PT-102"][0]
    assert t["tendencia_1h"] == 5.0


def test_el_resumen_cuenta_sensores_en_rango_aviso_y_alarma(central, conexion, pedir):
    ayudas.sembrar(conexion, "TE-101", [328.0], fin=ayudas.ahora() + timedelta(seconds=10))
    ayudas.sembrar(conexion, "PT-102", [161.0], fin=ayudas.ahora() + timedelta(seconds=10))
    ayudas.abrir_alarma(conexion, "PT-102", "alarma", 161.0)
    r = pedir("laura", "/lecturas/ultimas").json()["resumen"]
    assert (r["sensores"], r["en_rango"], r["en_aviso"], r["en_alarma"]) == (4, 2, 1, 1)
    assert r["alarmas_activas"] == 1 and r["tareas_abiertas"] is None
    assert r["lecturas_24h"] == 4 * 24 + 2 and r["pct_validas"] == 100.0


def test_un_sensor_sin_lecturas_sale_como_sin_datos(central, conexion, pedir):
    conexion.execute("DELETE FROM lectura WHERE sensor_id = (SELECT id FROM sensor WHERE tag = 'LT-104')")
    conexion.commit()
    t = [s for s in pedir("laura", "/lecturas/ultimas").json()["sensores"] if s["tag"] == "LT-104"][0]
    assert t["estado"] == "sin_datos" and t["valor"] is None and t["serie"] == []


def test_el_tecnico_ve_solo_los_sensores_que_le_ha_asignado_su_supervisor(central, pedir):
    assert tags(pedir("diego", "/lecturas/ultimas")) == ["TE-101", "PT-102"]
    assert tags(pedir("nuria", "/lecturas/ultimas")) == ["FT-103", "LT-104"]
    assert tags(pedir("ivan", "/lecturas/ultimas")) == ["PT-201", "LT-202"]


def test_el_auditor_solo_recibe_agregados_nunca_valores_sueltos(central, conexion, pedir):
    ayudas.sembrar(conexion, "TE-101", [328.0], fin=ayudas.ahora() + timedelta(seconds=10))
    r = pedir("beatriz", "/lecturas/ultimas")
    datos = r.json()
    assert datos["agregado"] is True and len(datos["areas"]) == 9
    a1 = datos["areas"][0]
    assert (a1["area"]["codigo"], a1["sensores"], a1["normal"], a1["aviso"]) == ("A1", 4, 3, 1)
    texto = r.text
    assert '"valor"' not in texto and '"tag"' not in texto and "328" not in texto


def test_el_administrador_no_ve_datos_en_directo(central, pedir, conexion):
    assert pedir("alvaro", "/lecturas/ultimas").status_code == 403
    assert len(denegaciones(conexion)) == 1


# ── Histórico ──
@pytest.fixture
def con_historia(central, conexion):
    """TE-101 con cinco lecturas conocidas, la última en `fin`; devuelve `fin`."""
    fin = ayudas.ahora()
    conexion.execute("DELETE FROM lectura WHERE sensor_id = (SELECT id FROM sensor WHERE tag = 'TE-101')")
    ayudas.sembrar(conexion, "TE-101", [320.0, 326.0, 328.0, 331.0, 325.0], paso_s=600, fin=fin)
    return fin


def test_el_historico_resume_el_periodo(con_historia, pedir):
    r = pedir("laura", "/lecturas/historico", tag="TE-101", horas=1, hasta=con_historia.isoformat())
    assert r.status_code == 200
    datos = r.json()
    assert datos["sensor"]["tag"] == "TE-101" and datos["agregado"] is True
    assert datos["resumen"] == {"minimo": 320.0, "maximo": 331.0, "media": 326.0, "lecturas": 5, "validas": 5,
                                "pct_en_rango": 60.0}
    assert sum(p["lecturas"] for p in datos["puntos"]) == 5
    assert any(p["estado"] == "alarma" for p in datos["puntos"])           # el 331 pasa la alarma (330)
    assert all(p["hora"].endswith(":00:00Z") for p in datos["puntos"])


def test_sin_fechas_el_historico_termina_en_la_ultima_lectura(con_historia, pedir):
    datos = pedir("laura", "/lecturas/historico", tag="TE-101", horas=24).json()
    assert datos["hasta"] == con_historia.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert datos["resumen"]["lecturas"] == 5


def test_se_puede_pedir_un_periodo_personalizado(con_historia, pedir):
    desde = (con_historia - timedelta(minutes=25)).isoformat()
    datos = pedir("laura", "/lecturas/historico", tag="TE-101", desde=desde, hasta=con_historia.isoformat()).json()
    assert datos["resumen"]["lecturas"] == 3 and datos["resumen"]["minimo"] == 325.0


def test_el_supervisor_no_ve_el_historico_de_otra_area(central, pedir, conexion):
    r = pedir("laura", "/lecturas/historico", tag="PT-201")
    assert r.status_code == 403 and "PT-201" not in r.text
    f = denegaciones(conexion)[0]
    assert f["recurso"] == "historico:ver" and json.loads(f["detalle"])["tag"] == "PT-201"
    assert pedir("javier", "/lecturas/historico", tag="PT-201").status_code == 200


def test_un_sensor_que_no_existe_da_404_y_no_403(central, pedir):
    assert pedir("laura", "/lecturas/historico", tag="XX-999").status_code == 404


def test_el_tecnico_solo_consulta_los_sensores_asignados(central, pedir, conexion):
    assert pedir("diego", "/lecturas/historico", tag="PT-102").status_code == 200
    assert pedir("diego", "/lecturas/historico", tag="FT-103").status_code == 403       # de su área, pero de Nuria
    assert pedir("diego", "/lecturas/historico", tag="PT-201").status_code == 403       # de otra área
    assert len(denegaciones(conexion)) == 2


@pytest.mark.parametrize("rol, dias, esperado", [("laura", 30, 200), ("laura", 31, 422),
                                                 ("diego", 7, 200), ("diego", 8, 422),
                                                 ("beatriz", 30, 200), ("beatriz", 31, 422)])
def test_cada_rol_tiene_su_limite_de_dias_de_historico(con_historia, pedir, rol, dias, esperado):
    desde = (con_historia - timedelta(days=dias)).isoformat()
    r = pedir(rol, "/lecturas/historico", tag="TE-101", desde=desde, hasta=con_historia.isoformat())
    assert r.status_code == esperado
    if esperado == 422:
        assert "como máximo" in r.json()["detalle"]


def test_el_auditor_ve_el_historico_de_cualquier_area_pero_agregado(central, pedir):
    datos = pedir("beatriz", "/lecturas/historico", tag="PT-201").json()
    assert datos["agregado"] is True and "lecturas" in datos["resumen"]


@pytest.mark.parametrize("params", [{"tag": "TE-101", "desde": "ayer"},
                                    {"tag": "TE-101", "horas": 0},
                                    {"tag": "TE-101", "horas": 9999},
                                    {"horas": 5}])
def test_peticiones_mal_formadas_dan_422(central, pedir, params):
    assert pedir("laura", "/lecturas/historico", **params).status_code == 422


def test_el_inicio_debe_ser_anterior_al_fin(con_historia, pedir):
    r = pedir("laura", "/lecturas/historico", tag="TE-101", desde=con_historia.isoformat(),
              hasta=(con_historia - timedelta(hours=1)).isoformat())
    assert r.status_code == 422


# ── CSV ──
def test_el_supervisor_exporta_csv_y_queda_en_el_registro(con_historia, pedir, conexion):
    r = pedir("laura", "/lecturas/historico/csv", tag="TE-101", horas=1, hasta=con_historia.isoformat())
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="historico_TE-101_' in r.headers["content-disposition"]
    lineas = r.text.lstrip("﻿").strip().split("\r\n")
    assert lineas[0] == "hora_utc;minimo;maximo;media;lecturas;estado" and len(lineas) >= 2
    evento = conexion.execute("SELECT * FROM evento_auditoria WHERE accion = 'exportacion_csv'").fetchone()
    assert evento["resultado"] == "ok" and evento["recurso"] == "historico:TE-101"
    assert json.loads(evento["detalle"])["filas"] == len(lineas) - 1


def test_el_csv_de_otra_area_se_deniega_y_no_se_registra_como_exportacion(central, pedir, conexion):
    assert pedir("laura", "/lecturas/historico/csv", tag="PT-201").status_code == 403
    assert conexion.execute("SELECT count(*) AS n FROM evento_auditoria WHERE accion = 'exportacion_csv'"
                            ).fetchone()["n"] == 0


# ── Alarmas, equipo e inventario ──
def test_cada_supervisor_ve_solo_las_alarmas_de_su_area(central, conexion, pedir):
    ayudas.abrir_alarma(conexion, "TE-101", "aviso", 328.0)
    ayudas.abrir_alarma(conexion, "PT-201", "alarma", 73.0)
    laura = pedir("laura", "/alarmas").json()["alarmas"]
    assert [a["tag"] for a in laura] == ["TE-101"] and laura[0]["nivel"] == "aviso"
    assert [a["tag"] for a in pedir("javier", "/alarmas").json()["alarmas"]] == ["PT-201"]


def test_el_tecnico_ve_las_alarmas_de_sus_sensores(central, conexion, pedir):
    ayudas.abrir_alarma(conexion, "TE-101", "aviso", 328.0)
    assert [a["tag"] for a in pedir("diego", "/alarmas").json()["alarmas"]] == ["TE-101"]
    assert pedir("nuria", "/alarmas").json()["alarmas"] == []


def test_los_filtros_de_alarmas(central, conexion, pedir):
    ayudas.abrir_alarma(conexion, "TE-101", "aviso", 328.0)
    ayudas.abrir_alarma(conexion, "PT-102", "aviso", 157.5, estado="cerrada", hace_minutos=30)
    ayudas.abrir_alarma(conexion, "FT-103", "aviso", 22600.0, estado="cerrada", hace_minutos=3 * 24 * 60)
    por_filtro = {f: sorted(a["tag"] for a in pedir("laura", "/alarmas", filtro=f).json()["alarmas"])
                  for f in ("activas", "hoy", "7dias")}
    assert por_filtro["activas"] == ["TE-101"]
    assert "PT-102" in por_filtro["7dias"] and "FT-103" in por_filtro["7dias"] and "TE-101" in por_filtro["7dias"]
    assert pedir("laura", "/alarmas", filtro="nunca").status_code == 422


def test_el_supervisor_ve_a_sus_tecnicos_con_sus_sensores(central, pedir):
    laura = pedir("laura", "/equipo").json()["tecnicos"]
    assert [(t["nombre"], t["sensores"]) for t in laura] == [("Diego Paredes Luna", ["TE-101", "PT-102"]),
                                                              ("Nuria Vega Santos", ["FT-103", "LT-104"])]
    assert [t["nombre"] for t in pedir("javier", "/equipo").json()["tecnicos"]] == ["Iván Cano Rubio"]
    assert "password" not in pedir("laura", "/equipo").text


def test_el_inventario_es_para_auditor_y_administrador_y_de_solo_lectura(central, pedir, api, entrar):
    for nombre in ("beatriz", "alvaro"):
        datos = pedir(nombre, "/sensores").json()["sensores"]
        assert len(datos) == 36 and datos[0]["umbrales"]["aviso_alto"] == 327.0
    token, _ = entrar(CORREOS["beatriz"])
    r = api.post("/sensores", headers={"Authorization": f"Bearer {token}"}, json={})
    assert r.status_code == 405
