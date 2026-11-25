"""T17 · Ventanas del Sprint 3 con datos de ejemplo: Equipo y tareas (06), Mi turno (07), Registrar incidencia (08),
alarmas con «Reconocer» y la lista de incidencias del técnico."""
from datetime import date, timedelta

import pytest
from PySide6.QtWidgets import QLabel

from cliente.modelo import datos
from cliente.modelo.sesion import Sesion
from cliente.vista.alarmas import VistaAlarmas
from cliente.vista.equipo import TarjetaTarea, VistaEquipo
from cliente.vista.incidencia import DialogoIncidencia, VistaIncidencias, a_numero
from cliente.vista.turno import VistaTurno

UMBRALES = {"aviso_bajo": None, "alarma_bajo": None, "aviso_alto": 327.0, "alarma_alto": 330.0}
DIEGO = {"id": 3, "nombre": "Diego Paredes Luna", "correo": "diego.paredes@cn-valdecierzo.es", "rol": "tecnico",
         "area": {"codigo": "A1", "nombre": "Reactor y circuito primario"},
         "supervisor": {"id": 1, "nombre": "Laura Méndez Ortiz"}}


def textos(widget):
    return [w.text() for w in widget.findChildren(QLabel) if w.isVisibleTo(widget)]


def sensor(tag="TE-101", valor=325.6, estado="normal", **extra):
    return {"tag": tag, "nombre": "Temperatura rama caliente", "magnitud": "Temperatura", "unidad": "°C",
            "area": {"codigo": "A1", "nombre": "Reactor"}, "min_fisico": 0.0, "max_fisico": 400.0,
            "valor_nominal": 325.6, "umbrales": UMBRALES, "valor": valor, "instante": "2026-11-20T10:00:00Z",
            "estado": estado, "edad_s": 5, "tendencia_1h": 0.1, "serie": [325.5, 325.6], "alarma": None} | extra


def tarea(id_=1, titulo="Calibración mensual TE-101", estado="pendiente", prioridad="media", **extra):
    return {"id": id_, "titulo": titulo, "descripcion": None, "prioridad": prioridad, "estado": estado,
            "fecha_limite": "2026-11-27", "creada_en": "2026-11-20T09:00:00Z",
            "cerrada_en": "2026-11-20T11:30:00Z" if estado == "hecha" else None, "alarma_id": None,
            "tecnico": {"id": 3, "nombre": "Diego Paredes Luna"}, "creada_por": {"id": 1, "nombre": "Laura Méndez Ortiz"},
            "sensor": {"tag": "TE-101", "nombre": "Temperatura rama caliente"}, "incidencias": 0,
            "ultima_incidencia": None} | extra


@pytest.fixture
def usuario_diego():
    return Sesion.desde_respuesta({"token": "t", "expira_en": "2099-01-01T00:00:00+00:00", "usuario": DIEGO}).usuario


# ── Ventana 06 · Equipo y tareas ──
@pytest.fixture
def equipo(qapp):
    v = VistaEquipo("Laura Méndez Ortiz", "A1")
    v.resize(1300, 900)
    v.show()
    yield v
    v.close()


def test_el_subtitulo_dice_de_quien_son_los_tecnicos(equipo):
    assert "Técnicos vinculados a Laura Méndez Ortiz · área A1" in textos(equipo)


def test_la_tabla_del_equipo_lleva_sensores_tareas_actividad_y_estado(equipo):
    equipo.poner_equipo([
        {"id": 3, "nombre": "Diego Paredes Luna", "sensores": ["TE-101", "FT-103"], "tareas_abiertas": 2,
         "estado": "ocupado", "ultima_actividad": {"instante": "2026-11-20T09:40:00Z", "tipo": "lectura_manual",
                                                   "sensor": "TE-101"}, "ultimo_acceso": None},
        {"id": 4, "nombre": "Nuria Vega Santos", "sensores": [], "tareas_abiertas": 0, "estado": "disponible",
         "ultima_actividad": None, "ultimo_acceso": None}])
    t = equipo.tabla_equipo
    assert t.rowCount() == 2
    assert [t.item(0, c).text() for c in range(4)][:3] == ["Diego Paredes Luna", "TE-101 · FT-103", "2"]
    assert "lectura manual TE-101" in t.item(0, 3).text() and t.item(1, 3).text() == "sin actividad registrada"
    assert "Ocupado" in t.cellWidget(0, 4).text() and "Disponible" in t.cellWidget(1, 4).text()
    assert [equipo.tecnico.itemText(i) for i in range(equipo.tecnico.count())] == ["Diego Paredes Luna",
                                                                                   "Nuria Vega Santos"]


def test_sin_equipo_no_se_puede_asignar(equipo):
    equipo.poner_equipo([])
    assert not equipo.boton.isEnabled() and "Todavía no tienes técnicos vinculados." in textos(equipo)


def test_el_tablero_reparte_las_tareas_en_tres_columnas(equipo):
    equipo.poner_tareas([tarea(1), tarea(2, "Revisar deriva", "en_curso", "alta"),
                         tarea(3, "Ronda", "hecha", "baja", ultima_incidencia=7)])
    assert [len(equipo.tarjetas(e)) for e in ("pendiente", "en_curso", "hecha")] == [1, 1, 1]
    assert [equipo._contadores[e].text() for e in ("pendiente", "en_curso", "hecha")] == ["1", "1", "1"]
    hecha = " ".join(textos(equipo.tarjetas("hecha")[0]))
    assert "cerrada" in hecha and "incidencia n.º 7" in hecha
    alta = " ".join(textos(equipo.tarjetas("en_curso")[0]))
    assert "Alta" in alta and "Diego Paredes Luna" in alta


def test_la_prioridad_se_ve_por_color_y_por_texto(qapp):
    for prioridad, texto in datos.PRIORIDADES.items():
        tarjeta = TarjetaTarea(tarea(prioridad=prioridad))
        assert texto in textos(tarjeta) or texto in [l.text() for l in tarjeta.findChildren(QLabel)]


def test_el_formulario_manda_lo_que_pide_el_servidor(equipo):
    equipo.poner_equipo([{"id": 3, "nombre": "Diego Paredes Luna", "sensores": [], "ultimo_acceso": None}])
    equipo.poner_sensores([sensor("TE-101"), sensor("PT-102")])
    enviados = []
    equipo.crear.connect(enviados.append)
    equipo.titulo.setText("  Calibrar TE-101  ")
    equipo.descripcion.setPlainText("Con el patrón portátil")
    equipo.sensor.setCurrentIndex(equipo.sensor.findData("PT-102"))
    equipo.prioridad.setCurrentIndex(equipo.prioridad.findData("alta"))
    equipo.boton.click()
    d = enviados[0]
    assert (d["titulo"], d["tecnico_id"], d["sensor_tag"], d["prioridad"]) == ("Calibrar TE-101", 3, "PT-102", "alta")
    assert d["descripcion"] == "Con el patrón portátil" and d["fecha_limite"] == str(date.today() + timedelta(days=3))
    assert not equipo.boton.isEnabled()                # espera a la respuesta del servidor


def test_el_formulario_avisa_antes_de_enviar(equipo):
    equipo.poner_equipo([{"id": 3, "nombre": "Diego Paredes Luna", "sensores": [], "ultimo_acceso": None}])
    enviados = []
    equipo.crear.connect(enviados.append)
    equipo.titulo.setText("ab")
    equipo.boton.click()
    assert enviados == [] and "al menos 3 letras" in equipo.mensaje.text()
    equipo.mostrar_resultado(True, "Tarea asignada a Diego.")
    assert equipo.mensaje.objectName() == "AvisoOk" and equipo.boton.isEnabled()


def test_la_fecha_limite_no_deja_elegir_el_pasado(equipo):
    from PySide6.QtCore import QDate
    assert equipo.fecha.minimumDate() == QDate.currentDate()


# ── Ventana 07 · Mi turno ──
@pytest.fixture
def turno(qapp):
    v = VistaTurno()
    v.resize(1300, 900)
    v.show()
    yield v
    v.close()


def test_mi_turno_ensena_solo_los_sensores_asignados(turno):
    turno.poner_datos({"sensores": [sensor("TE-101"), sensor("LT-104", 58.2)], "resumen": {}})
    visibles = [t for t in turno._tarjetas if t.isVisibleTo(turno)]
    assert [t.tag for t in visibles] == ["TE-101", "LT-104"]
    assert not turno.banner.isVisibleTo(turno)


def test_un_sensor_en_aviso_saca_el_banner_con_acceso_al_sensor(turno):
    turno.poner_datos({"sensores": [sensor("TE-101"), sensor("PT-102", 157.4, "aviso", nombre="Presión")],
                       "resumen": {}})
    assert turno.banner.isVisibleTo(turno) and "Aviso en PT-102" in turno.texto_banner.text()
    elegidos = []
    turno.ver_sensor.connect(elegidos.append)
    turno.boton_banner.click()
    assert elegidos == ["PT-102"]


def test_mis_tareas_con_prioridad_limite_quien_la_asigno_y_botones(turno):
    turno.poner_tareas([tarea(1), tarea(2, "Revisar deriva", "en_curso", "alta"), tarea(3, "Ronda", "hecha")])
    filas = turno.filas_tarea()
    assert [f.tarea_id for f in filas] == [1, 2, 3] and turno.contador_tareas.text() == "2"
    todo = " ".join(textos(turno))
    assert "asignada por Laura Méndez Ortiz" in todo and "límite 27/11" in todo and "Cerrada" in todo
    cambios = []
    turno.cambiar_estado.connect(lambda i, e: cambios.append((i, e)))
    filas[0].botones["estado"].click()
    filas[1].botones["estado"].click()
    assert cambios == [(1, "en_curso"), (2, "hecha")]
    assert filas[2].botones == {}                      # una hecha no tiene acciones


def test_las_acciones_rapidas_abren_el_registro_con_el_tipo_y_la_tarea(turno):
    turno.poner_datos({"sensores": [sensor()], "resumen": {}})
    turno.poner_tareas([tarea(5)])
    pedidos = []
    turno.registrar.connect(pedidos.append)
    turno.boton_incidencia.click()
    turno.boton_lectura.click()
    turno.filas_tarea()[0].botones["registrar"].click()
    assert pedidos == [{"tipo": "inspeccion"}, {"tipo": "lectura_manual"}, {"tipo": "inspeccion", "tarea_id": 5}]


def test_sin_sensores_no_se_puede_registrar(turno):
    turno.poner_datos({"sensores": [], "resumen": {}})
    assert not turno.boton_incidencia.isEnabled() and "todavía no te ha asignado sensores" in turno.resumen.text()


def test_la_grafica_es_de_7_dias_con_sus_umbrales(turno):
    turno.poner_grafica({"sensor": {"tag": "LT-104", "unidad": "%", "umbrales": UMBRALES},
                         "puntos": [{"hora": "2026-11-19T10:00:00Z", "media": 58.0}, {"hora": "2026-11-20T10:00:00Z",
                                                                                     "media": 58.4}]})
    assert turno.titulo_grafica.text() == "LT-104 · últimos 7 días" and len(turno.grafica._series[0].puntos) == 2
    turno.poner_resumen(1, 2, 1)
    assert "2 lecturas manuales · 1 incidencias · 1 tareas cerradas" in turno.resumen.text()


# ── Ventana 08 · Registrar incidencia ──
def dialogo(usuario, **kw):
    d = DialogoIncidencia(usuario, [sensor("TE-101"), sensor("PT-102", 155.0, nombre="Presión", unidad="bar",
                                                             min_fisico=0.0, max_fisico=200.0)],
                          [tarea(1), tarea(2, "Para PT-102", sensor={"tag": "PT-102", "nombre": "Presión"}),
                           tarea(3, "Ya hecha", "hecha")], **kw)
    d.show()
    return d


def test_el_dialogo_repite_nombre_y_rol_y_precarga_sensor_y_tarea(qapp, usuario_diego):
    d = dialogo(usuario_diego, tarea_id=2)
    todo = " ".join(textos(d))
    assert "Diego Paredes Luna" in todo and "Técnico" in todo
    assert d.sensor.currentData() == "PT-102" and d.tarea.currentData() == 2
    assert d.isModal()
    d.close()


def test_solo_ofrece_tareas_abiertas_de_ese_sensor(qapp, usuario_diego):
    d = dialogo(usuario_diego, tag="TE-101")
    ofrecidas = [d.tarea.itemData(i) for i in range(d.tarea.count())]
    assert ofrecidas == [None, 1]
    d.close()


def test_el_valor_se_compara_con_el_del_sistema_y_su_tolerancia(qapp, usuario_diego):
    d = dialogo(usuario_diego, tipo="lectura_manual")
    d.valor.setText("325,4")
    assert "diferencia -0,20" in d.comparacion.text() and "(dentro)" in d.comparacion.text()
    d.valor.setText("340")
    assert "(fuera" in d.comparacion.text()
    d.close()


def test_el_dialogo_valida_antes_de_enviar(qapp, usuario_diego):
    d = dialogo(usuario_diego, tipo="lectura_manual")
    enviados = []
    d.guardar.connect(enviados.append)
    d.boton.click()
    assert enviados == [] and "necesita el valor" in d.error.text()
    d.valor.setText("doce")
    d.boton.click()
    assert enviados == [] and "tiene que ser un número" in d.error.text()
    d.valor.setText("-5")
    d.boton.click()
    assert enviados == [] and "rango físico" in d.error.text()
    d.valor.setText("325,4")
    d.observaciones.setPlainText("Patrón calibrado")
    d.boton.click()
    assert enviados == [{"sensor_tag": "TE-101", "tipo": "lectura_manual", "valor_medido": 325.4,
                         "observaciones": "Patrón calibrado", "tarea_id": None}]
    d.close()


def test_una_inspeccion_no_necesita_valor(qapp, usuario_diego):
    d = dialogo(usuario_diego)
    enviados = []
    d.guardar.connect(enviados.append)
    d.botones_tipo["anomalia"].click()
    d.boton.click()
    assert enviados[0]["tipo"] == "anomalia" and enviados[0]["valor_medido"] is None
    d.close()


@pytest.mark.parametrize("texto, valor", [("325,4", 325.4), ("325.4", 325.4), (" 1 200,5 ", 1200.5), ("x", None),
                                          ("1,2,3", None)])
def test_los_numeros_se_escriben_con_coma_o_punto(texto, valor):
    assert a_numero(texto) == valor


# ── Lista de incidencias y alarmas ──
def test_la_lista_de_incidencias(qapp):
    v = VistaIncidencias()
    v.show()
    v.poner([{"id": 1, "tipo": "lectura_manual", "valor_medido": 325.4, "observaciones": "Ok",
              "creada_en": "2026-11-20T10:00:00Z", "sensor": {"tag": "TE-101", "nombre": "T", "unidad": "°C"},
              "tarea": {"id": 1, "titulo": "Calibración"}, "tecnico": {"id": 3, "nombre": "Diego"},
              "supervisor": {"id": 1, "nombre": "Laura"}}])
    assert v.tabla.rowCount() == 1 and v.tabla.item(0, 2).text() == "Lectura manual"
    assert v.tabla.item(0, 3).text() == "325,4 °C" and v.tabla.item(0, 4).text() == "Calibración"
    v.poner([])
    assert v.vacia.isVisibleTo(v)
    v.close()


def test_las_alarmas_abiertas_se_pueden_reconocer(qapp):
    v = VistaAlarmas()
    v.show()
    alarma = {"id": 9, "tag": "PT-102", "nombre": "Presión", "unidad": "bar", "nivel": "alarma", "valor": 161.0,
              "abierta_en": "2026-11-20T10:00:00Z", "cerrada_en": None, "estado": "abierta", "reconocida_por": None}
    v.poner([alarma, alarma | {"id": 10, "estado": "reconocida", "reconocida_por": "Laura Méndez Ortiz"}])
    assert list(v.botones_reconocer) == [9] and "Reconocida por Laura Méndez Ortiz" == v.tabla.item(1, 4).text()
    pedidos = []
    v.reconocer.connect(pedidos.append)
    v.botones_reconocer[9].click()
    assert pedidos == [9]
    v.close()
