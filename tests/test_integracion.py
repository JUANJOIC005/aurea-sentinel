"""T18 · Pruebas de integración: flujos completos entre roles contra el servidor real.

Cada prueba recorre un caso de uso de principio a fin (como lo haría el equipo en la central) y comprueba, al final,
que el registro de auditoría sigue íntegro y recoge lo que ha pasado.
"""
import json
import time

import pytest

from servidor import auditoria, config
from servidor.api import registro
from tests import ayudas
from tests.conftest import CLAVE, CORREOS
from tests.test_ingesta import enviar, lectura


@pytest.fixture
def como(api, entrar):
    sesiones = {}

    def _como(nombre):
        if nombre not in sesiones:
            token, _ = entrar(CORREOS[nombre])
            sesiones[nombre] = {"Authorization": f"Bearer {token}"}
        cab = sesiones[nombre]

        class Sesion:
            get = staticmethod(lambda ruta, **kw: api.get(ruta, headers=cab, **kw))
            post = staticmethod(lambda ruta, **kw: api.post(ruta, headers=cab, **kw))
            patch = staticmethod(lambda ruta, **kw: api.patch(ruta, headers=cab, **kw))
        return Sesion
    return _como


def acciones(conexion) -> list[str]:
    return [f["accion"] for f in conexion.execute("SELECT accion FROM evento_auditoria ORDER BY id")]


def integro(conexion) -> bool:
    return auditoria.verificar(conexion)["integro"]


# ── Flujo 1 · El Supervisor asigna → el Técnico registra → el Supervisor lo ve ──
def test_flujo_supervisor_asigna_tecnico_registra_supervisor_ve(como, central, conexion):
    laura, diego = como("laura"), como("diego")
    # 1. Laura ve a su equipo y asigna una tarea a Diego sobre un sensor de su área
    equipo = laura.get("/equipo").json()["tecnicos"]
    assert [t["nombre"] for t in equipo] == ["Diego Paredes Luna", "Nuria Vega Santos"]
    tarea = laura.post("/tareas", json={"titulo": "Calibración mensual TE-101", "tecnico_id": central["diego"],
                                        "sensor_tag": "TE-101", "prioridad": "alta"}).json()
    assert laura.get("/lecturas/ultimas").json()["resumen"]["tareas_abiertas"] == 1
    # 2. Diego la ve en su turno, la empieza y registra una lectura manual ligada a ella
    mias = diego.get("/tareas").json()["tareas"]
    assert [t["id"] for t in mias] == [tarea["id"]] and mias[0]["creada_por"]["nombre"] == "Laura Méndez Ortiz"
    assert diego.patch(f"/tareas/{tarea['id']}/estado", json={"estado": "en_curso"}).status_code == 200
    incidencia = diego.post("/incidencias", json={"sensor_tag": "TE-101", "tipo": "lectura_manual",
                                                  "valor_medido": 325.4, "tarea_id": tarea["id"],
                                                  "observaciones": "Patrón portátil"}).json()
    assert incidencia["supervisor"]["nombre"] == "Laura Méndez Ortiz" and incidencia["diferencia"] == pytest.approx(-0.2)
    assert diego.patch(f"/tareas/{tarea['id']}/estado", json={"estado": "hecha"}).json()["cerrada_en"]
    # 3. Laura ve la tarea cerrada con su incidencia, la actividad de Diego y el contador a cero
    hecha = laura.get("/tareas", params={"estado": "hecha"}).json()["tareas"][0]
    assert hecha["id"] == tarea["id"] and hecha["incidencias"] == 1 and hecha["ultima_incidencia"] == incidencia["id"]
    diego_en_equipo = laura.get("/equipo").json()["tecnicos"][0]
    assert diego_en_equipo["ultima_actividad"]["tipo"] == "lectura_manual" and diego_en_equipo["estado"] == "disponible"
    assert laura.get("/lecturas/ultimas").json()["resumen"]["tareas_abiertas"] == 0
    assert [i["id"] for i in laura.get("/incidencias").json()["incidencias"]] == [incidencia["id"]]
    # 4. Todo queda, en orden, en un registro que sigue íntegro
    hechos = [a for a in acciones(conexion) if a in ("tarea_creada", "tarea_estado", "incidencia_registrada")]
    assert hechos == ["tarea_creada", "tarea_estado", "incidencia_registrada", "tarea_estado"]
    assert integro(conexion)


# ── Flujo 2 · Una lectura firmada abre una alarma, se reconoce, se atiende y se cierra sola ──
def test_flujo_alarma_reconocida_atendida_y_cerrada(api, como, central, conexion):
    laura, diego = como("laura"), como("diego")
    # las lecturas de la central llegan hasta ahora: las del simulador son las siguientes
    assert enviar(api, [lectura("PT-102", 161.0, desplazamiento_s=5)]).status_code == 200
    alarma = laura.get("/alarmas").json()["alarmas"][0]
    assert (alarma["tag"], alarma["nivel"], alarma["estado"]) == ("PT-102", "alarma", "abierta")
    assert laura.post(f"/alarmas/{alarma['id']}/reconocer").json()["estado"] == "reconocida"
    tarea = laura.post("/tareas", json={"titulo": "Revisar presión del presionador", "tecnico_id": central["diego"],
                                        "alarma_id": alarma["id"], "prioridad": "alta"}).json()
    assert tarea["sensor"]["tag"] == "PT-102" and tarea["alarma_id"] == alarma["id"]
    diego.post("/incidencias", json={"sensor_tag": "PT-102", "tipo": "anomalia", "tarea_id": tarea["id"],
                                     "observaciones": "Válvula de alivio revisada"})
    diego.patch(f"/tareas/{tarea['id']}/estado", json={"estado": "hecha"})
    assert enviar(api, [lectura("PT-102", 155.0, desplazamiento_s=10)]).status_code == 200
    assert laura.get("/alarmas").json()["alarmas"] == []
    cerrada = laura.get("/alarmas", params={"filtro": "hoy"}).json()["alarmas"][0]
    assert cerrada["estado"] == "cerrada" and cerrada["reconocida_por"] == "Laura Méndez Ortiz"
    assert {"alarma_reconocida", "tarea_creada", "incidencia_registrada"} <= set(acciones(conexion))
    assert integro(conexion)


# ── Flujo 3 · Nadie se sale de lo suyo en mitad del trabajo ──
def test_flujo_cada_rol_se_queda_en_lo_suyo(como, central, conexion):
    laura, javier, diego, ivan = como("laura"), como("javier"), como("diego"), como("ivan")
    de_diego = laura.post("/tareas", json={"titulo": "Para Diego", "tecnico_id": central["diego"],
                                           "sensor_tag": "TE-101"}).json()
    javier.post("/tareas", json={"titulo": "Para Iván", "tecnico_id": central["ivan"], "sensor_tag": "PT-201"})
    assert javier.post("/tareas", json={"titulo": "Robo", "tecnico_id": central["diego"]}).status_code == 403
    assert ivan.patch(f"/tareas/{de_diego['id']}/estado", json={"estado": "hecha"}).status_code == 403
    assert ivan.post("/incidencias", json={"sensor_tag": "TE-101", "tipo": "inspeccion",
                                           "tarea_id": de_diego["id"]}).status_code == 403
    assert [t["titulo"] for t in javier.get("/tareas").json()["tareas"]] == ["Para Iván"]
    assert [t["titulo"] for t in diego.get("/tareas").json()["tareas"]] == ["Para Diego"]
    denegados = conexion.execute("SELECT count(*) AS n FROM evento_auditoria WHERE accion = 'acceso_denegado'"
                                 ).fetchone()["n"]
    assert denegados == 3 and integro(conexion)


# ── Flujo 4 · El Auditor revisa lo ocurrido: verifica la cadena y exporta un CSV firmado ──
def test_flujo_auditor_verifica_y_exporta_lo_ocurrido(como, central, conexion):
    laura, diego, beatriz = como("laura"), como("diego"), como("beatriz")
    t = laura.post("/tareas", json={"titulo": "Ronda", "tecnico_id": central["diego"]}).json()
    diego.post("/incidencias", json={"sensor_tag": "TE-101", "tipo": "inspeccion", "tarea_id": t["id"]})
    verificacion = beatriz.get("/auditoria/verificar").json()
    assert verificacion["integro"] and verificacion["sin_cadena"] == 0
    incidencias = beatriz.get("/incidencias").json()["incidencias"]
    assert len(incidencias) == 1 and incidencias[0]["tecnico"]["nombre"].startswith("Técnico n.º")
    csv_firmado = beatriz.get("/auditoria/exportar").content
    texto = csv_firmado.decode("utf-8-sig")
    assert "tarea_creada" in texto and "incidencia_registrada" in texto and "Diego" not in texto
    assert registro.comprobar_firma(csv_firmado)
    assert beatriz.post("/tareas", json={"titulo": "No", "tecnico_id": central["diego"]}).status_code == 403
    assert acciones(conexion)[-2:] == ["exportacion_auditoria", "acceso_denegado"] and integro(conexion)


# ── Flujo 5 · Entrada real con segundo factor y trabajo en la misma sesión ──
def test_flujo_supervisor_entra_con_codigo_y_asigna(api, central, conexion, monkeypatch):
    monkeypatch.setattr(config, "DOBLE_FACTOR_ACTIVO", True)
    secreto = ayudas.activar_2fa(conexion, central["laura"])
    paso1 = api.post("/auth/login", json={"correo": CORREOS["laura"], "password": CLAVE}).json()
    assert paso1["requiere_2fa"] and "token" not in paso1
    assert api.post("/tareas", json={"titulo": "x", "tecnico_id": central["diego"]},
                    headers={"Authorization": f"Bearer {paso1['desafio']}"}).status_code == 401
    sesion = api.post("/auth/2fa/verificar", json={"desafio": paso1["desafio"],
                                                   "codigo": ayudas.codigo_de(secreto)}).json()
    cab = {"Authorization": f"Bearer {sesion['token']}"}
    r = api.post("/tareas", json={"titulo": "Con doble factor", "tecnico_id": central["diego"]}, headers=cab)
    assert r.status_code == 201
    assert api.post("/auth/logout", headers=cab).status_code == 204
    assert api.get("/tareas", headers=cab).status_code == 401
    assert integro(conexion)


# ── Flujo 6 · El mismo recorrido desde el modelo del cliente (lo que usan las ventanas) ──
def test_flujo_desde_el_cliente_de_escritorio(central):
    from fastapi.testclient import TestClient

    from cliente.modelo.api import ClienteApi, ErrorApi
    from servidor.api.main import app

    def entrar(nombre):
        api = ClienteApi(url="http://testserver", http=TestClient(app))
        api.usar_token(api.login(CORREOS[nombre], CLAVE)["token"])
        return api

    laura, diego = entrar("laura"), entrar("diego")
    tarea = laura.crear_tarea({"titulo": "Inspección TE-101", "tecnico_id": central["diego"], "sensor_tag": "TE-101"})
    assert [t["id"] for t in diego.tareas()] == [tarea["id"]]
    diego.cambiar_estado_tarea(tarea["id"], "en_curso")
    diego.crear_incidencia({"sensor_tag": "TE-101", "tipo": "inspeccion", "tarea_id": tarea["id"]})
    diego.cambiar_estado_tarea(tarea["id"], "hecha")
    assert laura.tareas("hecha")[0]["incidencias"] == 1
    with pytest.raises(ErrorApi) as error:
        diego.crear_tarea({"titulo": "No puedo", "tecnico_id": central["nuria"]})
    assert error.value.estado == 403


# ── Flujo 7 · Una sesión caducada a mitad del trabajo no deja seguir ──
def test_flujo_sesion_caducada_en_mitad_del_trabajo(como, central, conexion):
    laura = como("laura")
    t = laura.post("/tareas", json={"titulo": "Antes de caducar", "tecnico_id": central["diego"]})
    assert t.status_code == 201
    conexion.execute("UPDATE sesion SET creada_en = datetime('now', '-2 hours'), expira_en = datetime('now', '-1 minute')")
    conexion.commit()
    assert laura.post("/tareas", json={"titulo": "Después", "tecnico_id": central["diego"]}).status_code == 401
    assert conexion.execute("SELECT count(*) AS n FROM tarea").fetchone()["n"] == 1


# ── Flujo 8 · Una jornada con varias personas a la vez deja el registro íntegro ──
def test_flujo_jornada_con_mucha_actividad(api, como, central, conexion):
    laura, javier = como("laura"), como("javier")
    for i in range(5):
        laura.post("/tareas", json={"titulo": f"Tarea {i}", "tecnico_id": central["nuria"], "sensor_tag": "FT-103"})
        javier.post("/tareas", json={"titulo": f"Tarea {i}", "tecnico_id": central["ivan"], "sensor_tag": "PT-201"})
        enviar(api, [lectura("TE-101", 325.6, desplazamiento_s=-10 - i), lectura("PT-201", 155.0, -10 - i)])
    nuria, ivan = como("nuria"), como("ivan")
    for t in nuria.get("/tareas").json()["tareas"]:
        nuria.post("/incidencias", json={"sensor_tag": "FT-103", "tipo": "inspeccion", "tarea_id": t["id"]})
        nuria.patch(f"/tareas/{t['id']}/estado", json={"estado": "hecha"})
    for t in ivan.get("/tareas").json()["tareas"][:2]:
        ivan.patch(f"/tareas/{t['id']}/estado", json={"estado": "en_curso"})
    assert laura.get("/lecturas/ultimas").json()["resumen"]["tareas_abiertas"] == 0
    assert javier.get("/lecturas/ultimas").json()["resumen"]["tareas_abiertas"] == 5
    r = auditoria.verificar(conexion)
    assert r["integro"] and r["encadenados"] == r["eventos"] >= 30


# ── El manual de usuario existe, cubre cada rol y sus capturas están en el repositorio ──
def test_el_manual_de_usuario_cubre_cada_rol_y_sus_capturas_existen():
    import re
    from pathlib import Path
    manual = config.RAIZ / "docs" / "Manual de usuario.md"
    texto = manual.read_text(encoding="utf-8")
    for apartado in ("## 2. Entrar en la aplicación", "## 3. Supervisor", "## 4. Técnico", "## 5. Auditor",
                     "## 6. Administrador", "## 7. Problemas frecuentes"):
        assert apartado in texto
    imagenes = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", texto)
    assert len(imagenes) == 4 and all((manual.parent / Path(i)).is_file() for i in imagenes)
