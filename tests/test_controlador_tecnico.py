"""T17 · Ventanas del Sprint 3 conectadas al servidor real: Equipo y tareas, Alarmas, Mi turno e incidencias."""
import pytest
from fastapi.testclient import TestClient
from PySide6.QtCore import QSettings

from cliente.controlador.supervisor import ControladorSupervisor
from cliente.controlador.tecnico import ControladorTecnico
from cliente.modelo.api import ClienteApi
from cliente.modelo.sesion import Sesion
from cliente.vista.ventana_base import VentanaBase
from servidor.api.main import app
from tests import ayudas
from tests.conftest import CLAVE, CORREOS


@pytest.fixture(autouse=True)
def ajustes_limpios(qapp):
    QSettings("AUREA AUDIT", "AUREA Sentinel").clear()


def cliente(nombre):
    api = ClienteApi(url="http://testserver", http=TestClient(app))
    datos = api.login(CORREOS[nombre], CLAVE)
    api.usar_token(datos["token"])
    return api, Sesion.desde_respuesta(datos)


@pytest.fixture
def supervisor(qapp, central):
    api, sesion = cliente("laura")
    ventana = VentanaBase(sesion, "testserver")
    ventana.show()
    control = ControladorSupervisor(api, sesion, ventana, elegir_archivo=lambda n: "", periodo_ms=3_600_000)
    yield api, ventana, control
    control.detener()
    ventana.close()


@pytest.fixture
def tecnico(qapp, central):
    api, sesion = cliente("diego")
    ventana = VentanaBase(sesion, "testserver")
    ventana.show()
    abiertos = []
    control = ControladorTecnico(api, sesion, ventana, periodo_ms=3_600_000, abrir_dialogo=abiertos.append)
    control.abiertos = abiertos
    yield api, ventana, control
    control.detener()
    ventana.close()


# ── Supervisor: Equipo y tareas (06) ──
def test_equipo_y_tareas_es_una_ventana_real_con_los_tecnicos_y_sensores_del_area(supervisor):
    _, ventana, control = supervisor
    ventana.mostrar("equipo")
    assert ventana.contenido.currentWidget() is control.equipo
    assert ventana.cabecera.titulo.text() == "Equipo y tareas"
    e = control.equipo
    assert [e.tecnico.itemText(i) for i in range(e.tecnico.count())] == ["Diego Paredes Luna", "Nuria Vega Santos"]
    assert [e.sensor.itemData(i) for i in range(e.sensor.count())] == [None, "TE-101", "PT-102", "FT-103", "LT-104"]


def test_el_supervisor_asigna_una_tarea_y_aparece_en_el_tablero(supervisor, conexion):
    _, ventana, control = supervisor
    ventana.mostrar("equipo")
    e = control.equipo
    e.titulo.setText("Calibración mensual LT-104")
    e.tecnico.setCurrentIndex(e.tecnico.findText("Nuria Vega Santos"))
    e.sensor.setCurrentIndex(e.sensor.findData("LT-104"))
    e.boton.click()
    assert "Tarea asignada a Nuria Vega Santos" in e.mensaje.text()
    assert [t.tarea_id for t in e.tarjetas("pendiente")] == [conexion.execute("SELECT id FROM tarea").fetchone()["id"]]
    assert e.titulo.text() == "" and e.boton.isEnabled()
    assert e.tabla_equipo.item(1, 2).text() == "1"


def test_si_el_servidor_rechaza_la_tarea_se_ve_su_mensaje(supervisor, monkeypatch):
    api, ventana, control = supervisor
    from cliente.modelo.api import ErrorApi
    def falla(_datos):
        raise ErrorApi(403, "No tienes permiso para esta operación.")
    monkeypatch.setattr(api, "crear_tarea", falla)
    ventana.mostrar("equipo")
    control.equipo.titulo.setText("Algo")
    control.equipo.boton.click()
    assert control.equipo.mensaje.text() == "No tienes permiso para esta operación." and control.equipo.boton.isEnabled()


def test_el_boton_del_panel_lleva_a_equipo_y_tareas(supervisor):
    _, ventana, control = supervisor
    control.panel.asignar_tarea.emit()
    assert ventana.contenido.currentWidget() is control.equipo


def test_el_indicador_del_panel_cuenta_las_tareas_del_equipo(supervisor, conexion, central):
    api, _, control = supervisor
    api.crear_tarea({"titulo": "Una", "tecnico_id": central["diego"]})
    control.refrescar()
    assert control.panel.kpi_tareas.cifra.text() == "1"


# ── Supervisor: Alarmas ──
def test_el_supervisor_reconoce_una_alarma_desde_su_ventana(supervisor, conexion):
    ayudas.abrir_alarma(conexion, "PT-102", "alarma", 161.0)
    _, ventana, control = supervisor
    ventana.mostrar("alarmas")
    assert ventana.contenido.currentWidget() is control.alarmas
    alarma = conexion.execute("SELECT id FROM alarma").fetchone()["id"]
    control.alarmas.botones_reconocer[alarma].click()
    assert control.alarmas.botones_reconocer == {}
    assert control.alarmas.tabla.item(0, 4).text() == "Reconocida por Laura Méndez Ortiz"
    assert conexion.execute("SELECT estado FROM alarma").fetchone()["estado"] == "reconocida"


# ── Técnico: Mi turno (07) ──
def test_el_tecnico_entra_en_mi_turno_con_sus_sensores_y_sus_tareas(tecnico, supervisor, central):
    api_sup = supervisor[0]
    api_sup.crear_tarea({"titulo": "Revisar TE-101", "tecnico_id": central["diego"], "sensor_tag": "TE-101",
                         "prioridad": "alta"})
    api_sup.crear_tarea({"titulo": "Tarea de Nuria", "tecnico_id": central["nuria"]})
    _, ventana, control = tecnico
    control.refrescar()
    assert ventana.contenido.currentWidget() is control.turno and ventana.cabecera.titulo.text() == "Mi turno"
    assert [t.tag for t in control.turno._tarjetas if not t.isHidden()] == ["TE-101", "PT-102"]
    assert [f.tarea_id for f in control.turno.filas_tarea()] and control.turno.contador_tareas.text() == "1"
    assert control.turno.titulo_grafica.text() == "PT-102 · últimos 7 días"


def test_el_tecnico_mueve_su_tarea(tecnico, supervisor, central, conexion):
    supervisor[0].crear_tarea({"titulo": "Revisar TE-101", "tecnico_id": central["diego"]})
    _, _, control = tecnico
    control.refrescar()
    control.turno.filas_tarea()[0].botones["estado"].click()
    assert conexion.execute("SELECT estado FROM tarea").fetchone()["estado"] == "en_curso"
    control.turno.filas_tarea()[0].botones["estado"].click()
    assert conexion.execute("SELECT estado FROM tarea").fetchone()["estado"] == "hecha"
    assert "1 tareas cerradas" in control.turno.resumen.text()


def test_el_tecnico_registra_una_lectura_manual_desde_el_dialogo(tecnico, conexion):
    _, ventana, control = tecnico
    control.turno.boton_lectura.click()
    dialogo = control.abiertos[-1]
    assert dialogo.tipo() == "lectura_manual" and dialogo.sensor.currentData() == "TE-101"
    dialogo.valor.setText("325,4")
    dialogo.boton.click()
    fila = conexion.execute("SELECT tipo, valor_medido FROM incidencia").fetchone()
    assert (fila["tipo"], fila["valor_medido"]) == ("lectura_manual", 325.4)
    assert control.incidencias.tabla.rowCount() == 1 and "1 lecturas manuales" in control.turno.resumen.text()


def test_la_incidencia_ligada_a_una_tarea_queda_en_el_tablero_del_supervisor(tecnico, supervisor, central, conexion):
    tarea = supervisor[0].crear_tarea({"titulo": "Inspeccionar PT-102", "tecnico_id": central["diego"],
                                       "sensor_tag": "PT-102"})
    _, _, control = tecnico
    control.refrescar()
    control.turno.filas_tarea()[0].botones["registrar"].click()
    dialogo = control.abiertos[-1]
    assert dialogo.tarea.currentData() == tarea["id"] and dialogo.sensor.currentData() == "PT-102"
    dialogo.observaciones.setPlainText("Sin fugas")
    dialogo.boton.click()
    _, ventana_sup, control_sup = supervisor
    ventana_sup.mostrar("equipo")
    assert control_sup.equipo.tabla_equipo.item(0, 3).text().endswith("inspección visual PT-102")


def test_si_el_servidor_rechaza_la_incidencia_el_dialogo_sigue_abierto_con_el_motivo(tecnico, monkeypatch):
    api, _, control = tecnico
    from cliente.modelo.api import ErrorApi
    def falla(_datos):
        raise ErrorApi(422, "El valor medido está fuera del rango físico del sensor.")
    monkeypatch.setattr(api, "crear_incidencia", falla)
    control.turno.boton_incidencia.click()
    dialogo = control.abiertos[-1]
    dialogo.boton.click()
    assert "rango físico" in dialogo.error.text() and dialogo.boton.isEnabled()


def test_el_historico_del_tecnico_tiene_sus_sensores_y_7_dias(tecnico):
    _, ventana, control = tecnico
    control.turno.ver_sensor.emit("PT-102")
    assert ventana.contenido.currentWidget() is control.historico
    assert [control.historico.sensor.itemData(i) for i in range(control.historico.sensor.count())] == ["TE-101", "PT-102"]


def test_al_cerrar_la_sesion_se_paran_los_relojes(qapp, central):
    from cliente.controlador.aplicacion import Aplicacion
    api, sesion = cliente("diego")
    aplicacion = Aplicacion(api)
    aplicacion.abrir_sesion(sesion)
    assert aplicacion.control_tecnico is not None and aplicacion.control_supervisor is None
    aplicacion.cerrar_sesion("")
    assert aplicacion.control_tecnico is None
