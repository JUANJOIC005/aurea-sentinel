"""T13 · Panel del área e histórico: las ventanas del Supervisor con el servidor real."""
import json

import pytest
from fastapi.testclient import TestClient
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLabel

from cliente.controlador.aplicacion import Aplicacion
from cliente.controlador.supervisor import ControladorSupervisor, SIN_CONEXION
from cliente.modelo.api import ClienteApi, ErrorConexion
from cliente.modelo.sesion import Sesion
from cliente.vista.ventana_base import VentanaBase
from servidor.api.main import app
from tests import ayudas
from tests.conftest import CLAVE, CORREOS


@pytest.fixture(autouse=True)
def ajustes_limpios(qapp):
    QSettings("AUREA AUDIT", "AUREA Sentinel").clear()


def cliente(nombre="laura"):
    api = ClienteApi(url="http://testserver", http=TestClient(app))
    datos = api.login(CORREOS[nombre], CLAVE)
    api.usar_token(datos["token"])
    return api, Sesion.desde_respuesta(datos)


@pytest.fixture
def supervisor(qapp, central, tmp_path):
    api, sesion = cliente()
    ventana = VentanaBase(sesion, "testserver")
    ventana.resize(1440, 900)
    ventana.show()
    destino = {"ruta": str(tmp_path / "historico.csv")}
    control = ControladorSupervisor(api, sesion, ventana, elegir_archivo=lambda nombre: destino["ruta"],
                                    periodo_ms=3_600_000)
    control.destino = destino
    yield api, ventana, control
    control.detener()
    ventana.close()


def textos(widget):
    return [w.text() for w in widget.findChildren(QLabel) if w.isVisibleTo(widget)]


# ── Panel ──
def test_el_panel_enseña_los_datos_reales_del_area_del_supervisor(supervisor):
    api, ventana, control = supervisor
    assert ventana.contenido.currentWidget() is control.panel
    tarjetas = [t for t in control.panel._tarjetas if t.isVisibleTo(control.panel)]
    assert [t.tag for t in tarjetas] == ["TE-101", "PT-102", "FT-103", "LT-104"]
    assert "4" in control.panel.kpi_rango.cifra.text() and "0 en aviso · 0 en alarma" == control.panel.kpi_rango.contexto.text()
    assert control.panel.kpi_validas.cifra.text().startswith("100,0")


def test_la_ventana_con_el_panel_sigue_enseñando_nombre_y_rol(supervisor):
    api, ventana, control = supervisor
    todo = textos(ventana)
    assert len([t for t in todo if "Laura Méndez Ortiz" in t]) >= 3 and todo.count("Supervisor") >= 2


def test_el_panel_enseña_los_tecnicos_de_su_equipo(supervisor, qapp):
    api, ventana, control = supervisor
    qapp.processEvents()
    todo = " ".join(textos(control.panel))
    assert "Diego Paredes Luna" in todo and "TE-101 · PT-102" in todo and "Nuria Vega Santos" in todo
    assert "Iván Cano" not in todo                                   # es de otro supervisor


def test_una_lectura_en_aviso_cambia_la_tarjeta_el_indicador_y_la_tabla(supervisor, conexion):
    from datetime import timedelta
    api, ventana, control = supervisor
    ayudas.sembrar(conexion, "PT-102", [157.5], fin=ayudas.ahora() + timedelta(seconds=10))
    ayudas.abrir_alarma(conexion, "PT-102", "aviso", 157.5)
    control.refrescar()
    tarjeta = control.panel._tarjetas[1]
    assert "Aviso" in tarjeta.pildora.text() and "157,5" in tarjeta.valor.text()
    assert control.panel.kpi_alarmas.cifra.text() == "1" and "1 en aviso" in control.panel.kpi_rango.contexto.text()
    assert control.panel.tabla.rowCount() == 1 and control.panel.tabla.item(0, 1).text() == "Aviso"


def test_el_filtro_de_alarmas_pide_otra_lista_al_servidor(supervisor, conexion):
    api, ventana, control = supervisor
    ayudas.abrir_alarma(conexion, "TE-101", "aviso", 328.0, estado="cerrada", hace_minutos=3 * 24 * 60)
    control.refrescar()
    assert control.panel.tabla.rowCount() == 0
    control.panel._botones_filtro["7dias"].click()
    assert control.panel.tabla.rowCount() == 1 and control.panel.filtro_actual() == "7dias"
    control.refrescar()                                                # el refresco mantiene el filtro elegido
    assert control.panel.tabla.rowCount() == 1


def test_si_no_hay_conexion_el_panel_avisa_y_se_recupera(supervisor, monkeypatch):
    api, ventana, control = supervisor
    original = api.lecturas_ultimas
    monkeypatch.setattr(api, "lecturas_ultimas", lambda: (_ for _ in ()).throw(ErrorConexion("caído")))
    control.refrescar()
    assert control.panel.error.isVisibleTo(control.panel) and SIN_CONEXION.format(servidor="testserver") in control.panel.error.text()
    monkeypatch.setattr(api, "lecturas_ultimas", original)
    control.refrescar()
    assert not control.panel.error.isVisibleTo(control.panel)


def test_si_el_servidor_niega_algo_el_panel_lo_dice(supervisor, conexion, central):
    api, ventana, control = supervisor
    conexion.execute("UPDATE usuario SET estado = 'bloqueado' WHERE id = ?", (central["laura"],))
    conexion.commit()
    control.refrescar()
    assert control.panel.error.isVisibleTo(control.panel) and "Sesión no válida" in control.panel.error.text()


def test_el_refresco_automatico_solo_trabaja_con_el_panel_a_la_vista(supervisor, monkeypatch):
    api, ventana, control = supervisor
    llamadas = []
    monkeypatch.setattr(control, "refrescar", lambda: llamadas.append(1))
    control._al_tic()
    assert llamadas == [1]
    ventana.mostrar("historico")
    llamadas.clear()
    control._al_tic()
    assert llamadas == []
    ventana.mostrar("panel")                                           # al volver al panel se refresca en el acto
    assert llamadas == [1]


def test_detener_para_el_reloj(supervisor):
    api, ventana, control = supervisor
    assert control._reloj.isActive()
    control.detener()
    assert not control._reloj.isActive()


# ── Histórico ──
def test_pulsar_un_sensor_abre_su_historico_ya_consultado(supervisor):
    api, ventana, control = supervisor
    control.panel.abrir_historico.emit("PT-102")
    assert ventana.contenido.currentWidget() is control.historico
    assert control.historico.sensor.currentData() == "PT-102"
    assert control.historico.tabla.rowCount() > 0 and "PT-102" in control.historico.titulo_grafica.text()
    assert "155,0" in control.historico.kpi_media.cifra.text() and ventana.cabecera.titulo.text() == "Histórico de sensores"


def test_el_historico_ofrece_los_4_sensores_del_area(supervisor):
    api, ventana, control = supervisor
    h = control.historico
    assert [h.sensor.itemData(i) for i in range(h.sensor.count())] == ["TE-101", "PT-102", "FT-103", "LT-104"]


def test_el_historico_dibuja_dos_sensores_si_se_comparan(supervisor):
    api, ventana, control = supervisor
    control.consultar({"tag": "PT-102", "horas": 24, "desde": None, "hasta": None, "comparar": "TE-101"})
    assert [s.nombre for s in control.historico.grafica._series] == ["PT-102", "TE-101"]


def test_pedir_el_historico_de_otra_area_da_error_y_no_enseña_datos(supervisor, conexion):
    api, ventana, control = supervisor
    control.consultar({"tag": "PT-201", "horas": 24, "desde": None, "hasta": None, "comparar": None})
    h = control.historico
    assert h.error.isVisibleTo(h) and "No tienes permiso" in h.error.text() and h.boton_aplicar.isEnabled()
    assert h.tabla.rowCount() == 0
    assert conexion.execute("SELECT count(*) AS n FROM evento_auditoria WHERE accion = 'acceso_denegado'"
                            ).fetchone()["n"] == 1


def test_un_periodo_demasiado_largo_se_explica(supervisor):
    from datetime import timedelta
    api, ventana, control = supervisor
    fin = ayudas.ahora()
    control.consultar({"tag": "TE-101", "horas": None, "comparar": None, "hasta": fin.strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "desde": (fin - timedelta(days=31)).strftime("%Y-%m-%dT%H:%M:%SZ")})
    assert "como máximo 30 días" in control.historico.error.text()


def test_sin_conexion_el_historico_avisa(supervisor, monkeypatch):
    api, ventana, control = supervisor
    monkeypatch.setattr(api, "historico", lambda *a, **k: (_ for _ in ()).throw(ErrorConexion("caído")))
    control.consultar({"tag": "TE-101", "horas": 24, "desde": None, "hasta": None, "comparar": None})
    assert "No se puede conectar" in control.historico.error.text() and control.historico.boton_aplicar.isEnabled()


# ── Exportar a CSV ──
def test_exportar_guarda_el_csv_y_queda_en_el_registro(supervisor, conexion):
    api, ventana, control = supervisor
    control.historico.elegir_sensor("TE-101")
    control.exportar({"tag": "TE-101", "horas": 24, "desde": None, "hasta": None, "comparar": None})
    contenido = open(control.destino["ruta"], encoding="utf-8-sig").read()
    assert contenido.splitlines()[0] == "hora_utc;minimo;maximo;media;lecturas;estado"
    assert len(contenido.splitlines()) >= 2 and "325.6" in contenido
    h = control.historico
    assert h.error.objectName() == "AvisoOk" and "Exportado" in h.error.text() and "auditoría" in h.error.text()
    evento = conexion.execute("SELECT * FROM evento_auditoria WHERE accion = 'exportacion_csv'").fetchone()
    assert evento["resultado"] == "ok" and json.loads(evento["detalle"])["filas"] == len(contenido.splitlines()) - 1


def test_si_se_cancela_el_guardado_no_se_escribe_nada(supervisor, tmp_path):
    api, ventana, control = supervisor
    control.destino["ruta"] = ""
    control.exportar({"tag": "TE-101", "horas": 24, "desde": None, "hasta": None, "comparar": None})
    assert not (tmp_path / "historico.csv").exists() and not control.historico.error.isVisibleTo(control.historico)


def test_exportar_un_sensor_de_otra_area_da_error(supervisor, tmp_path):
    api, ventana, control = supervisor
    control.exportar({"tag": "PT-201", "horas": 24, "desde": None, "hasta": None, "comparar": None})
    assert "No tienes permiso" in control.historico.error.text() and not (tmp_path / "historico.csv").exists()


def test_sin_conexion_exportar_avisa(supervisor, monkeypatch, tmp_path):
    api, ventana, control = supervisor
    monkeypatch.setattr(api, "historico_csv", lambda *a, **k: (_ for _ in ()).throw(ErrorConexion("caído")))
    control.exportar({"tag": "TE-101", "horas": 24, "desde": None, "hasta": None, "comparar": None})
    assert "No se puede conectar" in control.historico.error.text() and not (tmp_path / "historico.csv").exists()


# ── La aplicación entera ──
def test_al_entrar_un_supervisor_se_abre_su_panel_y_al_salir_se_para(qapp, central):
    api = ClienteApi(url="http://testserver", http=TestClient(app))
    aplicacion = Aplicacion(api)
    aplicacion.iniciar()
    aplicacion.control_acceso.iniciar_sesion(CORREOS["laura"], CLAVE, False)
    assert aplicacion.control_supervisor is not None and aplicacion.base.isVisible()
    panel = aplicacion.control_supervisor.panel
    assert aplicacion.base.contenido.currentWidget() is panel and panel._tarjetas
    aplicacion.base.menu._botones["historico"].click()
    assert aplicacion.base.contenido.currentWidget() is aplicacion.control_supervisor.historico
    aplicacion.control_sesion.cerrar()
    assert aplicacion.control_supervisor is None and aplicacion.base is None and aplicacion.acceso.isVisible()
    aplicacion.acceso.close()


def test_el_tecnico_no_recibe_el_panel_del_supervisor(qapp, central):
    api = ClienteApi(url="http://testserver", http=TestClient(app))
    aplicacion = Aplicacion(api)
    aplicacion.iniciar()
    aplicacion.control_acceso.iniciar_sesion(CORREOS["diego"], CLAVE, False)
    assert aplicacion.control_supervisor is None and aplicacion.base is not None
    assert "Mi turno" in aplicacion.base.menu._botones["turno"].toolTip()
    aplicacion.control_sesion.cerrar()
    aplicacion.acceso.close()
