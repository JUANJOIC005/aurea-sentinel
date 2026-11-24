"""T15 · Tareas, incidencias y lecturas manuales, y reconocer alarmas (servidor)."""
import json
from datetime import date, timedelta

import pytest

from servidor.api import permisos
from tests import ayudas
from tests.conftest import CORREOS


@pytest.fixture
def como(api, entrar):
    """como("laura").post("/tareas", json=...) — peticiones con la sesión de esa persona."""
    class Sesion:
        def __init__(self, nombre):
            token, _ = entrar(CORREOS[nombre])
            self.cab = {"Authorization": f"Bearer {token}"}

        def get(self, ruta, **kw):
            return api.get(ruta, headers=self.cab, **kw)

        def post(self, ruta, **kw):
            return api.post(ruta, headers=self.cab, **kw)

        def patch(self, ruta, **kw):
            return api.patch(ruta, headers=self.cab, **kw)
    return Sesion


def tarea(como, central, nombre="laura", tecnico="diego", **extra):
    datos = {"titulo": "Calibración mensual TE-101", "tecnico_id": central[tecnico], "sensor_tag": "TE-101",
             "prioridad": "media"} | extra
    return como(nombre).post("/tareas", json=datos)


def eventos(conexion, accion):
    return conexion.execute("SELECT * FROM evento_auditoria WHERE accion = ? ORDER BY id", (accion,)).fetchall()


# ── Crear tareas ──
def test_el_supervisor_asigna_una_tarea_a_su_tecnico(como, central, conexion):
    r = tarea(como, central, descripcion="Comprobar deriva del termopar", fecha_limite=str(date.today()))
    assert r.status_code == 201
    t = r.json()
    assert (t["titulo"], t["estado"], t["prioridad"]) == ("Calibración mensual TE-101", "pendiente", "media")
    assert t["tecnico"]["nombre"] == "Diego Paredes Luna" and t["creada_por"]["nombre"] == "Laura Méndez Ortiz"
    assert t["sensor"] == {"tag": "TE-101", "nombre": t["sensor"]["nombre"]} and t["fecha_limite"] == str(date.today())
    assert [e["recurso"] for e in eventos(conexion, "tarea_creada")] == [f"tarea:{t['id']}"]


def test_una_tarea_sin_sensor_tambien_vale(como, central):
    r = tarea(como, central, sensor_tag=None, titulo="Ronda de verificación del área")
    assert r.status_code == 201 and r.json()["sensor"] is None


def test_no_se_asignan_tareas_a_tecnicos_de_otro_supervisor(como, central, conexion):
    r = tarea(como, central, tecnico="ivan")
    assert r.status_code == 403 and r.json() == {"detalle": permisos.MENSAJE_PROHIBIDO}
    assert json.loads(eventos(conexion, "acceso_denegado")[-1]["detalle"])["motivo"] == "tecnico_ajeno"
    assert conexion.execute("SELECT count(*) AS n FROM tarea").fetchone()["n"] == 0


@pytest.mark.parametrize("tecnico_id", [0, 999, -1])
def test_un_tecnico_que_no_existe_da_el_mismo_403(como, central, tecnico_id):
    r = como("laura").post("/tareas", json={"titulo": "Algo", "tecnico_id": tecnico_id})
    assert r.status_code == 403


def test_no_se_asignan_tareas_sobre_sensores_de_otra_area(como, central):
    assert tarea(como, central, sensor_tag="PT-201").status_code == 403
    assert tarea(como, central, sensor_tag="XX-999").status_code == 404


def test_una_tarea_ligada_a_una_alarma_toma_su_sensor(como, central, conexion):
    ayudas.abrir_alarma(conexion, "PT-102", "alarma", 161.0)
    alarma = conexion.execute("SELECT id FROM alarma").fetchone()["id"]
    t = tarea(como, central, sensor_tag=None, alarma_id=alarma, prioridad="alta").json()
    assert t["sensor"]["tag"] == "PT-102" and t["alarma_id"] == alarma
    assert tarea(como, central, sensor_tag="TE-101", alarma_id=alarma).status_code == 422


def test_una_alarma_de_otra_area_no_sirve_para_crear_tareas(como, central, conexion):
    ayudas.abrir_alarma(conexion, "PT-201", "alarma", 161.0)
    alarma = conexion.execute("SELECT id FROM alarma").fetchone()["id"]
    assert tarea(como, central, sensor_tag=None, alarma_id=alarma).status_code == 403


@pytest.mark.parametrize("cambio, campo", [
    ({"titulo": "ab"}, "titulo"), ({"titulo": "   "}, "titulo"), ({"prioridad": "urgente"}, "prioridad"),
    ({"fecha_limite": "mañana"}, "fecha_limite"), ({"titulo": "x" * 121}, "titulo"),
])
def test_datos_mal_formados_dan_422(como, central, cambio, campo):
    r = tarea(como, central, **cambio)
    assert r.status_code == 422


def test_la_fecha_limite_no_puede_ser_pasada(como, central):
    r = tarea(como, central, fecha_limite=str(date.today() - timedelta(days=1)))
    assert r.status_code == 422 and "anterior a hoy" in r.json()["detalle"]


@pytest.mark.parametrize("nombre", ["diego", "beatriz", "alvaro"])
def test_solo_el_supervisor_crea_tareas(como, central, nombre):
    assert tarea(como, central, nombre=nombre).status_code == 403


# ── Ver tareas ──
def test_cada_uno_ve_solo_las_tareas_que_le_tocan(como, central):
    tarea(como, central, titulo="Para Diego")
    tarea(como, central, tecnico="nuria", titulo="Para Nuria", sensor_tag="FT-103")
    tarea(como, central, nombre="javier", tecnico="ivan", titulo="Para Iván", sensor_tag="PT-201")
    titulos = lambda n: sorted(t["titulo"] for t in como(n).get("/tareas").json()["tareas"])
    assert titulos("laura") == ["Para Diego", "Para Nuria"]
    assert titulos("javier") == ["Para Iván"]
    assert titulos("diego") == ["Para Diego"]
    assert titulos("nuria") == ["Para Nuria"]
    assert como("beatriz").get("/tareas").status_code == 403
    assert como("alvaro").get("/tareas").status_code == 403


def test_las_tareas_salen_ordenadas_por_prioridad_y_las_hechas_al_final(como, central):
    ids = {p: tarea(como, central, titulo=f"Prioridad {p}", prioridad=p).json()["id"] for p in ("baja", "alta", "media")}
    como("diego").patch(f"/tareas/{ids['alta']}/estado", json={"estado": "hecha"})
    assert [t["prioridad"] for t in como("laura").get("/tareas").json()["tareas"]] == ["media", "baja", "alta"]
    assert [t["titulo"] for t in como("laura").get("/tareas", params={"estado": "hecha"}).json()["tareas"]] == [
        "Prioridad alta"]


# ── Cambiar el estado ──
def test_el_tecnico_mueve_su_tarea_y_al_terminarla_queda_la_fecha_de_cierre(como, central, conexion):
    t = tarea(como, central).json()
    r = como("diego").patch(f"/tareas/{t['id']}/estado", json={"estado": "en_curso"})
    assert r.status_code == 200 and r.json()["estado"] == "en_curso" and r.json()["cerrada_en"] is None
    r = como("diego").patch(f"/tareas/{t['id']}/estado", json={"estado": "hecha"})
    assert r.json()["estado"] == "hecha" and r.json()["cerrada_en"].endswith("Z")
    r = como("diego").patch(f"/tareas/{t['id']}/estado", json={"estado": "pendiente"})
    assert r.json()["cerrada_en"] is None
    assert [json.loads(e["detalle"])["despues"] for e in eventos(conexion, "tarea_estado")] == [
        "en_curso", "hecha", "pendiente"]


def test_nadie_mueve_una_tarea_que_no_es_suya(como, central):
    t = tarea(como, central).json()
    assert como("nuria").patch(f"/tareas/{t['id']}/estado", json={"estado": "hecha"}).status_code == 403
    assert como("laura").patch(f"/tareas/{t['id']}/estado", json={"estado": "hecha"}).status_code == 403
    assert como("diego").patch("/tareas/9999/estado", json={"estado": "hecha"}).status_code == 404
    assert como("diego").patch(f"/tareas/{t['id']}/estado", json={"estado": "cerrada"}).status_code == 422


# ── Incidencias y lecturas manuales ──
def test_el_tecnico_registra_una_lectura_manual_ligada_a_su_tarea(como, central, conexion):
    t = tarea(como, central).json()
    r = como("diego").post("/incidencias", json={"sensor_tag": "TE-101", "tipo": "lectura_manual",
                                                 "valor_medido": 325.4, "tarea_id": t["id"],
                                                 "observaciones": "Patrón portátil calibrado"})
    assert r.status_code == 201
    i = r.json()
    assert i["sensor"]["tag"] == "TE-101" and i["tarea"]["id"] == t["id"]
    assert i["tecnico"]["nombre"] == "Diego Paredes Luna" and i["supervisor"]["nombre"] == "Laura Méndez Ortiz"
    assert i["valor_sistema"] == 325.6 and i["diferencia"] == pytest.approx(-0.2)
    assert len(eventos(conexion, "incidencia_registrada")) == 1
    assert como("laura").get("/tareas").json()["tareas"][0]["incidencias"] == 1


@pytest.mark.parametrize("tipo", ["inspeccion", "anomalia"])
def test_una_inspeccion_o_una_anomalia_no_necesitan_valor(como, central, tipo):
    r = como("diego").post("/incidencias", json={"sensor_tag": "PT-102", "tipo": tipo})
    assert r.status_code == 201 and r.json()["valor_medido"] is None and r.json()["diferencia"] is None


def test_una_lectura_manual_sin_valor_o_imposible_se_rechaza(como, central, conexion):
    sesion = como("diego")
    assert sesion.post("/incidencias", json={"sensor_tag": "TE-101", "tipo": "lectura_manual"}).status_code == 422
    r = sesion.post("/incidencias", json={"sensor_tag": "TE-101", "tipo": "lectura_manual", "valor_medido": -500.0})
    assert r.status_code == 422 and "rango físico" in r.json()["detalle"]
    r = sesion.post("/incidencias", json={"sensor_tag": "TE-101", "tipo": "lectura_manual", "valor_medido": "325"})
    assert r.status_code == 422
    assert conexion.execute("SELECT count(*) AS n FROM incidencia").fetchone()["n"] == 0


def test_solo_se_registran_incidencias_de_los_sensores_asignados(como, central):
    sesion = como("diego")
    assert sesion.post("/incidencias", json={"sensor_tag": "FT-103", "tipo": "inspeccion"}).status_code == 403
    assert sesion.post("/incidencias", json={"sensor_tag": "PT-201", "tipo": "inspeccion"}).status_code == 403
    assert sesion.post("/incidencias", json={"sensor_tag": "XX-999", "tipo": "inspeccion"}).status_code == 404


def test_la_tarea_de_una_incidencia_tiene_que_ser_suya_y_del_mismo_sensor(como, central):
    de_nuria = tarea(como, central, tecnico="nuria", sensor_tag="FT-103").json()
    de_diego = tarea(como, central, sensor_tag="PT-102").json()
    sesion = como("diego")
    r = sesion.post("/incidencias", json={"sensor_tag": "TE-101", "tipo": "inspeccion", "tarea_id": de_nuria["id"]})
    assert r.status_code == 403
    r = sesion.post("/incidencias", json={"sensor_tag": "TE-101", "tipo": "inspeccion", "tarea_id": de_diego["id"]})
    assert r.status_code == 422 and "otro sensor" in r.json()["detalle"]
    assert sesion.post("/incidencias", json={"sensor_tag": "TE-101", "tipo": "inspeccion",
                                             "tarea_id": 9999}).status_code == 404


@pytest.mark.parametrize("nombre", ["laura", "beatriz", "alvaro"])
def test_solo_el_tecnico_registra_incidencias(como, central, nombre):
    assert como(nombre).post("/incidencias", json={"sensor_tag": "TE-101", "tipo": "inspeccion"}).status_code == 403


def test_cada_uno_ve_las_incidencias_que_le_tocan_y_el_auditor_sin_nombres(como, central):
    como("diego").post("/incidencias", json={"sensor_tag": "TE-101", "tipo": "inspeccion"})
    como("nuria").post("/incidencias", json={"sensor_tag": "FT-103", "tipo": "anomalia"})
    como("ivan").post("/incidencias", json={"sensor_tag": "PT-201", "tipo": "inspeccion"})
    tags = lambda n, **p: sorted(i["sensor"]["tag"] for i in como(n).get("/incidencias", params=p).json()["incidencias"])
    assert tags("laura") == ["FT-103", "TE-101"]
    assert tags("javier") == ["PT-201"]
    assert tags("diego") == ["TE-101"]
    assert tags("laura", tag="FT-103") == ["FT-103"]
    auditor = como("beatriz").get("/incidencias").json()["incidencias"]
    assert len(auditor) == 3 and all(i["tecnico"]["nombre"].startswith("Técnico n.º") for i in auditor)
    assert "Diego" not in json.dumps(auditor, ensure_ascii=False)
    assert como("alvaro").get("/incidencias").status_code == 403


# ── Reconocer alarmas ──
def test_el_supervisor_reconoce_una_alarma_de_su_area(como, central, conexion):
    ayudas.abrir_alarma(conexion, "PT-102", "alarma", 161.0)
    alarma = conexion.execute("SELECT id FROM alarma").fetchone()["id"]
    r = como("laura").post(f"/alarmas/{alarma}/reconocer")
    assert r.status_code == 200 and r.json()["estado"] == "reconocida" and r.json()["reconocida_por"] == "Laura Méndez Ortiz"
    fila = conexion.execute("SELECT estado, reconocida_por, reconocida_en FROM alarma").fetchone()
    assert fila["estado"] == "reconocida" and fila["reconocida_por"] == central["laura"] and fila["reconocida_en"]
    assert como("laura").post(f"/alarmas/{alarma}/reconocer").status_code == 409
    assert len(eventos(conexion, "alarma_reconocida")) == 1
    assert [a["estado"] for a in como("laura").get("/alarmas").json()["alarmas"]] == ["reconocida"]


def test_no_se_reconocen_alarmas_de_otra_area_ni_cerradas(como, central, conexion):
    ayudas.abrir_alarma(conexion, "PT-201", "alarma", 161.0)
    ayudas.abrir_alarma(conexion, "TE-101", "aviso", 328.0, estado="cerrada")
    ajena, cerrada = [f["id"] for f in conexion.execute("SELECT id FROM alarma ORDER BY id")]
    assert como("laura").post(f"/alarmas/{ajena}/reconocer").status_code == 403
    assert como("laura").post(f"/alarmas/{cerrada}/reconocer").status_code == 409
    assert como("laura").post("/alarmas/9999/reconocer").status_code == 404
    for nombre in ("diego", "beatriz", "alvaro"):
        assert como(nombre).post(f"/alarmas/{cerrada}/reconocer").status_code == 403


# ── Panel y equipo ──
def test_el_panel_cuenta_las_tareas_abiertas_del_equipo(como, central):
    a = tarea(como, central).json()
    tarea(como, central, tecnico="nuria", sensor_tag="FT-103")
    como("diego").patch(f"/tareas/{a['id']}/estado", json={"estado": "hecha"})
    assert como("laura").get("/lecturas/ultimas").json()["resumen"]["tareas_abiertas"] == 1
    assert como("diego").get("/lecturas/ultimas").json()["resumen"]["tareas_abiertas"] == 0
    assert como("nuria").get("/lecturas/ultimas").json()["resumen"]["tareas_abiertas"] == 1


def test_el_equipo_lleva_tareas_abiertas_estado_y_ultima_actividad(como, central):
    t = tarea(como, central).json()
    como("diego").patch(f"/tareas/{t['id']}/estado", json={"estado": "en_curso"})
    como("diego").post("/incidencias", json={"sensor_tag": "TE-101", "tipo": "inspeccion"})
    diego, nuria = como("laura").get("/equipo").json()["tecnicos"]
    assert (diego["tareas_abiertas"], diego["estado"]) == (1, "ocupado")
    assert diego["ultima_actividad"]["sensor"] == "TE-101" and diego["ultima_actividad"]["tipo"] == "inspeccion"
    assert (nuria["tareas_abiertas"], nuria["estado"], nuria["ultima_actividad"]) == (0, "disponible", None)


def test_la_tabla_de_permisos_del_sprint_3(central):
    p = permisos.PERMISOS
    assert p[("tareas", "crear")] == {"supervisor": "equipo"}
    assert p[("tareas", "cambiar_estado")] == {"tecnico": "propias"}
    assert p[("incidencias", "crear")] == {"tecnico": "asignados"}
    assert p[("alarmas", "reconocer")] == {"supervisor": "area"}
    assert "administrador" not in p[("incidencias", "ver")]


# ── Datos de demostración ──
def test_la_demostracion_trae_tareas_de_ejemplo_coherentes(conexion):
    from servidor import datos_demo
    datos_demo.crear_cuentas(conexion, "Valdecierzo-2026!")
    assert datos_demo.sembrar_trabajo(conexion) == 18            # 6 técnicos × 3 tareas
    assert datos_demo.sembrar_trabajo(conexion) == 0             # no se repite
    malas = conexion.execute(
        "SELECT count(*) AS n FROM tarea t JOIN usuario tec ON tec.id = t.asignada_a JOIN sensor s ON s.id = t.sensor_id"
        " WHERE t.creada_por <> tec.supervisor_id OR s.area_id <> tec.area_id"
        " OR NOT EXISTS (SELECT 1 FROM asignacion_sensor x WHERE x.tecnico_id = tec.id AND x.sensor_id = s.id)"
    ).fetchone()["n"]
    assert malas == 0
    estados = {f["estado"]: f["n"] for f in conexion.execute("SELECT estado, count(*) AS n FROM tarea GROUP BY estado")}
    assert estados == {"pendiente": 6, "en_curso": 6, "hecha": 6}
    assert conexion.execute("SELECT count(*) AS n FROM incidencia").fetchone()["n"] == 6
