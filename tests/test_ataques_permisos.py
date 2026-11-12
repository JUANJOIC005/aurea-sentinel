"""T14 · Pruebas de permisos: intentos de ver datos de otra área o de sensores que no le tocan a la persona.

Se monta la central completa (un supervisor en cada una de las 9 áreas, dos técnicos, un auditor y un administrador)
y cada persona intenta leer lo que la tabla de permisos de T09 le prohíbe. Los resultados están en el capítulo 7.2 de
DOCUMENTACION.md.
"""
import json

import pytest

from servidor import config
from tests import ayudas
from tests.conftest import CLAVE

AREAS = [f"A{n}" for n in range(1, 10)]
SENSORES = {
    "A1": ["TE-101", "PT-102", "FT-103", "LT-104"], "A2": ["PT-201", "LT-202", "TE-203", "FT-204"],
    "A3": ["ST-301", "VT-302", "JT-303", "TE-304"], "A4": ["PT-401", "TE-402", "AT-403", "MT-404"],
    "A5": ["TE-501", "LT-502", "RT-503", "CT-504"], "A6": ["TE-601", "TE-602", "FT-603", "VT-604"],
    "A7": ["ET-701", "FT-702", "LT-703", "TE-704"], "A8": ["RT-801", "RT-802", "WT-803", "TE-804"],
    "A9": ["NT-901", "NT-902", "NT-903", "NT-904"],
}
PAREJAS = [(propia, otra) for propia in AREAS for otra in AREAS if otra != propia]   # 9 × 8 = 72

CORREO_SUPERVISOR = "supervisor.{}@cn-valdecierzo.es"
CORREOS = {"diego": "diego.paredes@cn-valdecierzo.es", "ivan": "ivan.cano@cn-valdecierzo.es",
           "beatriz": "beatriz.lara@cn-valdecierzo.es", "alvaro": "alvaro.campos@cn-valdecierzo.es"}


@pytest.fixture
def planta(crear_usuario, conexion):
    """Central completa con lecturas. Diego (A1) tiene TE-101 y PT-102; Iván (A2) tiene PT-201."""
    ids = {area: crear_usuario(f"Supervisor del área {area}", CORREO_SUPERVISOR.format(area.lower()),
                               "supervisor", area) for area in AREAS}
    ids["diego"] = crear_usuario("Diego Paredes Luna", CORREOS["diego"], "tecnico", None, ids["A1"])
    ids["ivan"] = crear_usuario("Iván Cano Rubio", CORREOS["ivan"], "tecnico", None, ids["A2"])
    ids["beatriz"] = crear_usuario("Beatriz Lara Quintana", CORREOS["beatriz"], "auditor", None)
    ids["alvaro"] = crear_usuario("Álvaro Campos Ibarra", CORREOS["alvaro"], "administrador", None)
    for tecnico, supervisor, etiquetas in (("diego", "A1", ("TE-101", "PT-102")), ("ivan", "A2", ("PT-201",))):
        for etiqueta in etiquetas:
            ayudas.asignar(conexion, ids[tecnico], etiqueta, ids[supervisor])
    ayudas.sembrar_nominal(conexion)
    return ids


def cabecera(entrar, quien: str) -> dict:
    correo = CORREO_SUPERVISOR.format(quien.lower()) if quien in AREAS else CORREOS[quien]
    token, _ = entrar(correo)
    return {"Authorization": f"Bearer {token}"}


def claves_de(objeto) -> set[str]:
    """Todas las claves que aparecen en una respuesta JSON, a cualquier profundidad."""
    if isinstance(objeto, dict):
        return set(objeto) | set().union(*(claves_de(v) for v in objeto.values()))
    if isinstance(objeto, list):
        return set().union(*(claves_de(v) for v in objeto)) if objeto else set()
    return set()


def denegaciones(conexion) -> list[dict]:
    return conexion.execute("SELECT actor_id, recurso, detalle FROM evento_auditoria"
                            " WHERE accion = 'acceso_denegado' ORDER BY id").fetchall()


def test_el_catalogo_de_la_prueba_coincide_con_la_base(planta, conexion):
    filas = conexion.execute("SELECT s.tag, a.codigo FROM sensor s JOIN area a ON a.id = s.area_id"
                             " ORDER BY s.id").fetchall()
    real = {}
    for f in filas:
        real.setdefault(f["codigo"], []).append(f["tag"])
    assert real == SENSORES


# ── Supervisor contra las otras áreas ──
@pytest.mark.parametrize("propia, otra", PAREJAS)
def test_un_supervisor_no_ve_el_historico_de_otra_area(api, planta, entrar, conexion, propia, otra):
    cab = cabecera(entrar, propia)
    for tag in SENSORES[otra]:
        r = api.get("/lecturas/historico", params={"tag": tag}, headers=cab)
        assert r.status_code == 403, f"{propia} → {tag}: {r.status_code}"
        assert "puntos" not in r.json() and "sensor" not in r.json()
    anotadas = [json.loads(f["detalle"])["tag"] for f in denegaciones(conexion)]
    assert anotadas == SENSORES[otra]


@pytest.mark.parametrize("propia", AREAS)
def test_un_supervisor_no_exporta_el_csv_de_otra_area(api, planta, entrar, conexion, propia):
    cab = cabecera(entrar, propia)
    for otra in AREAS:
        r = api.get("/lecturas/historico/csv", params={"tag": SENSORES[otra][0]}, headers=cab)
        assert r.status_code == (200 if otra == propia else 403), f"{propia} → {otra}"
    exportaciones = conexion.execute("SELECT recurso FROM evento_auditoria WHERE accion = 'exportacion_csv'"
                                     ).fetchall()
    assert [f["recurso"] for f in exportaciones] == [f"historico:{SENSORES[propia][0]}"]


@pytest.mark.parametrize("propia", AREAS)
def test_las_lecturas_en_directo_solo_traen_el_area_propia(api, planta, entrar, propia):
    r = api.get("/lecturas/ultimas", headers=cabecera(entrar, propia))
    assert r.status_code == 200
    assert [s["tag"] for s in r.json()["sensores"]] == SENSORES[propia]
    assert {s["area"]["codigo"] for s in r.json()["sensores"]} == {propia}
    assert r.json()["resumen"]["sensores"] == 4


@pytest.mark.parametrize("propia", AREAS)
def test_las_alarmas_de_otras_areas_no_aparecen(api, planta, entrar, conexion, propia):
    for area in AREAS:
        ayudas.abrir_alarma(conexion, SENSORES[area][0], "alarma", 999.0)
    r = api.get("/alarmas", headers=cabecera(entrar, propia))
    assert r.status_code == 200
    assert [a["tag"] for a in r.json()["alarmas"]] == [SENSORES[propia][0]]


def test_un_supervisor_no_ve_a_los_tecnicos_de_otro(api, planta, entrar):
    assert [t["nombre"] for t in api.get("/equipo", headers=cabecera(entrar, "A1")).json()["tecnicos"]] == [
        "Diego Paredes Luna"]
    assert [t["nombre"] for t in api.get("/equipo", headers=cabecera(entrar, "A2")).json()["tecnicos"]] == [
        "Iván Cano Rubio"]
    assert api.get("/equipo", headers=cabecera(entrar, "A3")).json()["tecnicos"] == []


# ── Técnico contra los sensores que no tiene asignados ──
@pytest.mark.parametrize("tag", ["FT-103", "LT-104"])
def test_un_tecnico_no_ve_sensores_de_su_area_que_no_tiene_asignados(api, planta, entrar, tag):
    r = api.get("/lecturas/historico", params={"tag": tag}, headers=cabecera(entrar, "diego"))
    assert r.status_code == 403


@pytest.mark.parametrize("otra", AREAS[1:])
def test_un_tecnico_no_ve_sensores_de_otra_area(api, planta, entrar, otra):
    cab = cabecera(entrar, "diego")
    for tag in SENSORES[otra]:
        assert api.get("/lecturas/historico", params={"tag": tag}, headers=cab).status_code == 403, tag


def test_un_tecnico_no_ve_el_sensor_asignado_a_otro_tecnico(api, planta, entrar):
    assert api.get("/lecturas/historico", params={"tag": "PT-201"},
                   headers=cabecera(entrar, "diego")).status_code == 403
    assert api.get("/lecturas/historico", params={"tag": "TE-101"},
                   headers=cabecera(entrar, "ivan")).status_code == 403


def test_las_lecturas_y_alarmas_del_tecnico_son_solo_las_de_sus_sensores(api, planta, entrar, conexion):
    for tag in ("TE-101", "FT-103", "PT-201"):
        ayudas.abrir_alarma(conexion, tag, "aviso", 1.0)
    cab = cabecera(entrar, "diego")
    assert [s["tag"] for s in api.get("/lecturas/ultimas", headers=cab).json()["sensores"]] == ["TE-101", "PT-102"]
    assert [a["tag"] for a in api.get("/alarmas", headers=cab).json()["alarmas"]] == ["TE-101"]


def test_al_quitarle_un_sensor_al_tecnico_pierde_el_acceso_en_el_momento(api, planta, entrar, conexion):
    cab = cabecera(entrar, "diego")
    assert api.get("/lecturas/historico", params={"tag": "PT-102"}, headers=cab).status_code == 200
    conexion.execute("DELETE FROM asignacion_sensor WHERE tecnico_id = ?"
                     " AND sensor_id = (SELECT id FROM sensor WHERE tag = 'PT-102')", (planta["diego"],))
    conexion.commit()
    assert api.get("/lecturas/historico", params={"tag": "PT-102"}, headers=cab).status_code == 403


@pytest.mark.parametrize("ruta", ["/lecturas/historico/csv?tag=TE-101", "/equipo", "/sensores"])
def test_un_tecnico_no_entra_en_lo_que_su_rol_no_tiene(api, planta, entrar, ruta):
    assert api.get(ruta, headers=cabecera(entrar, "diego")).status_code == 403


# ── Auditor: solo agregados ──
def test_el_auditor_no_recibe_ningun_valor_suelto_en_directo(api, planta, entrar):
    r = api.get("/lecturas/ultimas", headers=cabecera(entrar, "beatriz"))
    assert r.status_code == 200 and r.json()["agregado"] is True
    assert not claves_de(r.json()) & {"valor", "serie", "tag", "umbrales", "tendencia_1h"}
    assert sum(a["sensores"] for a in r.json()["areas"]) == 36


@pytest.mark.parametrize("area", ["A1", "A5", "A9"])
def test_el_historico_del_auditor_esta_resumido_por_horas(api, planta, entrar, area):
    r = api.get("/lecturas/historico", params={"tag": SENSORES[area][0]}, headers=cabecera(entrar, "beatriz"))
    assert r.status_code == 200 and r.json()["agregado"] is True
    assert "valor" not in claves_de(r.json())
    assert all(set(p) == {"hora", "minimo", "maximo", "media", "lecturas", "validas", "estado"}
               for p in r.json()["puntos"])


@pytest.mark.parametrize("ruta", ["/lecturas/historico/csv?tag=TE-101", "/alarmas", "/equipo"])
def test_el_auditor_no_entra_en_lo_que_su_rol_no_tiene(api, planta, entrar, ruta):
    assert api.get(ruta, headers=cabecera(entrar, "beatriz")).status_code == 403


# ── Administrador: gestiona, pero no ve datos de sensores ──
@pytest.mark.parametrize("ruta", ["/lecturas/ultimas", "/lecturas/historico?tag=TE-101",
                                  "/lecturas/historico/csv?tag=TE-101", "/alarmas", "/equipo"])
def test_el_administrador_no_ve_datos_de_la_planta(api, planta, entrar, ruta):
    assert api.get(ruta, headers=cabecera(entrar, "alvaro")).status_code == 403


# ── Trucos para saltarse el filtro ──
@pytest.mark.parametrize("tag", ["pt-201", " PT-201", "PT-201 ", "PT-201' OR '1'='1", "PT-201' --", "%", "PT-2_1",
                                 "PT‑201", "PT-201;DROP TABLE lectura"])
def test_un_tag_retocado_no_abre_datos_de_otra_area(api, planta, entrar, conexion, tag):
    r = api.get("/lecturas/historico", params={"tag": tag}, headers=cabecera(entrar, "A1"))
    assert r.status_code in (403, 404, 422), f"{tag!r}: {r.status_code}"
    assert "puntos" not in r.json()
    assert conexion.execute("SELECT count(*) AS n FROM lectura").fetchone()["n"] == 36 * 24


def test_repetir_el_parametro_tag_no_cuela_un_sensor_ajeno(api, planta, entrar):
    cab = cabecera(entrar, "A1")
    for orden in (("TE-101", "PT-201"), ("PT-201", "TE-101")):
        r = api.get("/lecturas/historico", params=[("tag", orden[0]), ("tag", orden[1])], headers=cab)
        if r.status_code == 200:
            assert r.json()["sensor"]["area"]["codigo"] == "A1"
        else:
            assert r.status_code == 403


def test_si_cambian_a_un_supervisor_de_area_deja_de_ver_la_anterior_sin_volver_a_entrar(api, planta, entrar,
                                                                                         conexion):
    cab = cabecera(entrar, "A1")
    assert api.get("/lecturas/historico", params={"tag": "TE-101"}, headers=cab).status_code == 200
    conexion.execute("UPDATE usuario SET area_id = (SELECT id FROM area WHERE codigo = 'A3') WHERE id = ?",
                     (planta["A1"],))
    conexion.commit()
    assert api.get("/lecturas/historico", params={"tag": "TE-101"}, headers=cab).status_code == 403
    assert [s["tag"] for s in api.get("/lecturas/ultimas", headers=cab).json()["sensores"]] == SENSORES["A3"]


def test_el_desafio_del_doble_factor_no_sirve_como_sesion(api, planta, monkeypatch):
    monkeypatch.setattr(config, "DOBLE_FACTOR_ACTIVO", True)
    r = api.post("/auth/login", json={"correo": CORREO_SUPERVISOR.format("a1"), "password": CLAVE})
    assert r.json()["requiere_2fa"] is True
    cab = {"Authorization": f"Bearer {r.json()['desafio']}"}
    for ruta in ("/lecturas/ultimas", "/lecturas/historico?tag=TE-101", "/alarmas", "/auth/yo"):
        assert api.get(ruta, headers=cab).status_code == 401, ruta


def test_cada_intento_de_otra_area_queda_anotado_con_quien_y_que_sensor(api, planta, entrar, conexion):
    api.get("/lecturas/historico", params={"tag": "PT-201"}, headers=cabecera(entrar, "A1"))
    api.get("/lecturas/historico", params={"tag": "LT-104"}, headers=cabecera(entrar, "diego"))
    filas = denegaciones(conexion)
    assert [(f["actor_id"], f["recurso"], json.loads(f["detalle"])) for f in filas] == [
        (planta["A1"], "historico:ver", {"motivo": "area_o_asignacion", "tag": "PT-201"}),
        (planta["diego"], "historico:ver", {"motivo": "area_o_asignacion", "tag": "LT-104"}),
    ]
