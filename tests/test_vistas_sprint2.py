"""T13 · Ventanas del Supervisor: verificación en dos pasos (03), panel del área (04) e histórico (05)."""
import time

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel

from cliente.modelo import datos
from cliente.vista import verificacion
from cliente.vista.graficas import BarraUmbrales, GraficaTemporal, Serie, Sparkline
from cliente.vista.historico import FILAS_POR_PAGINA, VistaHistorico
from cliente.vista.panel import VistaPanel
from cliente.vista.tarjetas import Indicador, TarjetaSensor
from cliente.vista.ventana_acceso import VentanaAcceso
from cliente.vista.verificacion import CasillasCodigo, VistaVerificacion
from servidor import qr, totp

PERFIL = {"id": 1, "nombre": "Laura Méndez Ortiz", "correo": "laura.mendez@cn-valdecierzo.es", "rol": "supervisor",
          "area": {"codigo": "A1", "nombre": "Reactor y circuito primario"}, "supervisor": None}
UMBRALES = {"aviso_bajo": None, "alarma_bajo": None, "aviso_alto": 327.0, "alarma_alto": 330.0}


def textos(widget):
    return [w.text() for w in widget.findChildren(QLabel) if w.isVisibleTo(widget)]


# ── Formato de cifras y fechas ──
@pytest.mark.parametrize("valor, esperado", [(325.6, "325,6"), (22140.0, "22.140"), (157.44, "157,4"), (2.5, "2,50"),
                                             (58.2, "58,2"), (-3.14159, "-3,14"), (0, "0,00"), (None, "—"),
                                             (1234567.0, "1.234.567")])
def test_las_cifras_se_escriben_a_la_espanola(valor, esperado):
    assert datos.numero(valor) == esperado


def test_decimales_explicitos_y_signo():
    assert datos.numero(1234.5678, 1) == "1.234,6" and datos.numero(5747, 0) == "5.747"
    assert datos.con_signo(3.58) == "+3,58" and datos.con_signo(-0.44) == "-0,44" and datos.con_signo(0.0) == "0,00"
    assert datos.con_signo(None) == "—"


def test_las_fechas_del_servidor_se_enseñan_en_hora_local():
    f = datos.fecha("2026-11-02T10:00:00Z")
    assert f.tzinfo is not None and f.utcoffset() is not None
    assert datos.fecha(None) is None and datos.hora(None) == "—" and datos.fecha_hora("") == "—"
    assert len(datos.hora("2026-11-02T10:00:00Z")) == 8 and "/2026 " in datos.fecha_hora("2026-11-02T10:00:00Z")


def test_ida_y_vuelta_de_fechas_con_el_servidor():
    local = datos.fecha("2026-11-02T10:15:30Z").replace(tzinfo=None)
    assert datos.a_utc_iso(local) == "2026-11-02T10:15:30Z"


# ── Casillas del código ──
def test_las_casillas_aceptan_solo_digitos_y_avisan_al_completar(qapp):
    c = CasillasCodigo()
    cambios = []
    c.cambiado.connect(cambios.append)
    QTest.keyClick(c.casillas[0], Qt.Key.Key_4)
    QTest.keyClick(c.casillas[1], Qt.Key.Key_A)                      # una letra no entra
    assert c.casillas[1].text() == "" and c.codigo() == "4" and not c.completo()
    for i, tecla in zip((1, 2, 3, 4, 5), (Qt.Key.Key_8, Qt.Key.Key_1, Qt.Key.Key_5, Qt.Key.Key_9, Qt.Key.Key_0)):
        QTest.keyClick(c.casillas[i], tecla)
    assert c.codigo() == "481590" and c.completo() and cambios[-1] == "481590"


def test_se_puede_pegar_el_codigo_entero_aunque_lleve_espacios_o_letras(qapp):
    c = CasillasCodigo()
    c.casillas[0].pegado.emit("48 15-90 x")
    assert c.codigo() == "481590"
    c.poner("12")
    assert c.codigo() == "12" and not c.completo()
    c.poner("1234567890")
    assert c.codigo() == "123456"


def test_borrar_en_una_casilla_vacia_vuelve_a_la_anterior_y_la_vacia(qapp):
    c = CasillasCodigo()
    c.poner("1234")
    c._retroceso(4)
    assert c.codigo() == "123"
    c._retroceso(0)                                     # en la primera no hay a dónde volver
    assert c.codigo() == "123"


def test_limpiar_y_bloquear_las_casillas(qapp):
    c = CasillasCodigo()
    c.poner("123456")
    c.bloquear(True)
    assert not any(x.isEnabled() for x in c.casillas)
    c.bloquear(False)
    c.limpiar()
    assert c.codigo() == "" and all(x.isEnabled() for x in c.casillas)


# ── Ventana 03 ──
@pytest.fixture
def vista03(qapp):
    v = VistaVerificacion()
    v.resize(1100, 700)
    v.poner_identidad(PERFIL)
    v.show()
    yield v
    v.close()


def test_la_ventana_03_enseña_nombre_rol_y_area_antes_de_pedir_el_codigo(vista03):
    todo = textos(vista03)
    assert "Laura Méndez Ortiz" in todo and "Supervisor" in todo
    assert any("A1 · Reactor y circuito primario" in t for t in todo)
    assert any("caducará tras 15 min" in t for t in todo)


def test_el_auditor_y_el_administrador_tienen_su_propia_caducidad(qapp, vista03):
    vista03.poner_identidad({**PERFIL, "nombre": "Álvaro Campos Ibarra", "rol": "administrador", "area": None})
    qapp.processEvents()                       # Qt muestra los widgets nuevos en la siguiente vuelta del bucle
    todo = textos(vista03)
    assert "Administrador" in todo and "Todas las áreas" in todo and any("tras 10 min" in t for t in todo)
    assert "Supervisor" not in todo                          # la insignia anterior se ha retirado


def test_el_boton_solo_se_activa_con_6_digitos_y_envia_el_codigo(vista03):
    enviados = []
    vista03.verificar.connect(enviados.append)
    assert not vista03.boton.isEnabled()
    vista03.casillas.poner("48159")
    assert not vista03.boton.isEnabled()
    vista03.casillas.poner("481590")
    assert vista03.boton.isEnabled()
    vista03.boton.click()
    assert enviados == ["481590"]
    vista03.casillas.entrar.emit()
    assert enviados == ["481590", "481590"]


def test_no_se_envia_un_codigo_incompleto(vista03):
    enviados = []
    vista03.verificar.connect(enviados.append)
    vista03.casillas.poner("123")
    vista03.casillas.entrar.emit()
    assert enviados == []


def test_cuenta_atras_del_codigo(vista03, monkeypatch):
    monkeypatch.setattr(verificacion.time, "time", lambda: 1000.0)       # 1000 % 30 = 10 → quedan 20 s
    vista03.actualizar_cuenta_atras()
    assert vista03.cuenta_atras.text() == "Código válido durante 20 s"
    assert totp.segundos_restantes(1000.0) == 20                          # coincide con el servidor


def test_error_ocupado_y_cambiar_de_usuario(vista03):
    vista03.mostrar_error("Código incorrecto. Te quedan 2 intentos.")
    assert vista03.aviso.isVisibleTo(vista03) and vista03.aviso.objectName() == "AvisoError"
    vista03.ocultar_aviso()
    assert not vista03.aviso.isVisibleTo(vista03)
    vista03.casillas.poner("123456")
    vista03.ocupado(True)
    assert vista03.boton.text() == "Comprobando…" and not vista03.boton.isEnabled() and not vista03.cambiar.isEnabled()
    vista03.ocupado(False)
    assert vista03.boton.isEnabled() and vista03.cambiar.isEnabled()
    pulsado = []
    vista03.cambiar_usuario.connect(lambda: pulsado.append(True))
    vista03.cambiar.click()
    assert pulsado == [True]


def test_la_primera_vez_enseña_el_qr_y_la_clave_en_grupos_de_cuatro(vista03):
    assert not vista03.bloque_qr.isVisibleTo(vista03)
    secreto = totp.nuevo_secreto()
    vista03.modo_configuracion(secreto, qr.svg(totp.uri(secreto, PERFIL["correo"])))
    assert vista03.bloque_qr.isVisibleTo(vista03) and "Configura" in vista03.titulo.text()
    assert not vista03.imagen_qr.pixmap().isNull()
    assert vista03.clave.text().replace(" ", "") == secreto and vista03.clave.text().count(" ") == 7
    vista03.limpiar()
    assert not vista03.bloque_qr.isVisibleTo(vista03) and vista03.titulo.text() == "Introduce el código"


def test_en_el_paso_2_la_barra_de_estado_ya_dice_quien_es(qapp):
    ventana = VentanaAcceso("127.0.0.1:8000")
    ventana.show()
    ventana.actualizar_conexion(True)
    assert "Sin sesión iniciada" in ventana.barra.izquierda.text()
    ventana.mostrar_verificacion(PERFIL)
    barra = ventana.barra.izquierda.text()
    assert "Laura Méndez Ortiz" in barra and "Supervisor" in barra and "A1" in barra
    assert "caduca en 15 min" in ventana.barra.derecha.text()
    ventana.actualizar_conexion(True)                       # el refresco periódico no pisa el paso 2
    assert "Laura Méndez Ortiz" in ventana.barra.izquierda.text()
    ventana.mostrar_login()
    assert "Sin sesión iniciada" in ventana.barra.izquierda.text()
    ventana.close()


# ── Gráficas ──
def pintar(widget, ancho=500, alto=300) -> QPixmap:
    widget.resize(ancho, alto)
    return widget.grab()


def test_la_minigrafica_se_dibuja_con_pocos_muchos_o_ningun_dato(qapp):
    s = Sparkline()
    for valores in ([], [1.0], [1.0, 1.0, 1.0], [1, 5, 2, 8, 3], list(range(500))):
        s.poner(valores)
        assert not pintar(s, 200, 40).isNull()


def test_la_barra_de_umbrales_calcula_su_rango_y_se_dibuja(qapp):
    b = BarraUmbrales()
    assert b.extremos() is None
    b.poner(UMBRALES, 325.6)
    bajo, alto = b.extremos()
    assert bajo < 325.6 < 330.0 < alto
    for umbrales, valor in ((UMBRALES, 331.0), ({k: None for k in UMBRALES}, 5.0), (UMBRALES, None),
                            ({"aviso_bajo": 152.0, "alarma_bajo": 150.0, "aviso_alto": 157.0, "alarma_alto": 160.0}, 155.0)):
        b.poner(umbrales, valor)
        assert not pintar(b, 200, 16).isNull()


def test_la_grafica_temporal_se_dibuja_en_todos_los_casos(qapp):
    g = GraficaTemporal()
    base = 1_700_000_000.0
    horas = [(base + 3600 * i, 325.0 + (i % 5)) for i in range(48)]
    casos = [
        ([], UMBRALES),                                                            # sin datos
        ([Serie("TE-101", [(base, 325.0)])], UMBRALES),                            # un solo punto
        ([Serie("TE-101", [(base, 325.0), (base + 3600, 325.0)])], UMBRALES),      # constante
        ([Serie("TE-101", horas, marcar_maximo=True, extra={"maximo": (horas[3][0], 331.0)})], UMBRALES),
        ([Serie("A", horas), Serie("B", [(x, y + 2) for x, y in horas])], {}),     # dos series, sin umbrales
        ([Serie("TE-101", [(base + 86400 * i, 320.0 + i) for i in range(30)])],
         {"aviso_bajo": 152.0, "alarma_bajo": 150.0, "aviso_alto": 157.0, "alarma_alto": 160.0}),   # umbrales lejanos
    ]
    for series, umbrales in casos:
        g.poner(series, umbrales, "°C")
        assert not pintar(g, 700, 300).isNull()


def test_la_grafica_ignora_los_umbrales_que_no_caben(qapp):
    g = GraficaTemporal()
    g.poner([Serie("PT", [(0.0, 155.0), (1.0, 155.4)])], {"aviso_alto": 157.0, "alarma_alto": 160.0, "aviso_bajo": None,
                                                           "alarma_bajo": None}, "bar")
    x0, x1, y0, y1 = g._rangos()
    assert y0 < 155.0 and y1 < 160.0                       # el umbral de alarma queda fuera del dibujo


# ── Tarjetas y panel ──
def tarjeta(tag="TE-101", nombre="Temperatura rama caliente", unidad="°C", valor=325.6, estado="normal", alarma=None,
            serie=None, tendencia=-0.44, edad=3, umbrales=UMBRALES):
    return {"tag": tag, "nombre": nombre, "magnitud": "Temperatura", "unidad": unidad,
            "area": {"codigo": "A1", "nombre": "Reactor"}, "min_fisico": 0, "max_fisico": 400, "valor_nominal": 325.6,
            "umbrales": umbrales, "valor": valor, "instante": "2026-11-03T16:25:00Z", "estado": estado,
            "edad_s": edad, "tendencia_1h": tendencia, "serie": serie if serie is not None else [325.0, 326.0, 325.6],
            "alarma": alarma}


def ultimas(*sensores, alarmas=0):
    return {"sensores": list(sensores), "resumen": {
        "sensores": len(sensores), "en_rango": sum(s["estado"] == "normal" for s in sensores),
        "en_aviso": sum(s["estado"] == "aviso" for s in sensores),
        "en_alarma": sum(s["estado"] == "alarma" for s in sensores), "alarmas_activas": alarmas,
        "tareas_abiertas": None, "lecturas_24h": 5747, "validas_24h": 5735, "pct_validas": 99.8}}


def test_el_indicador_enseña_cifra_y_contexto(qapp):
    i = Indicador("Sensores en rango")
    i.poner("3 / 4", "1 en aviso")
    assert i.cifra.text() == "3 / 4" and i.contexto.text() == "1 en aviso"


def test_la_tarjeta_de_sensor_enseña_valor_estado_en_texto_y_tendencia(qapp):
    t = TarjetaSensor()
    t.poner(tarjeta(estado="aviso", valor=327.4, tendencia=3.58))
    todo = " ".join(w.text() for w in t.findChildren(QLabel))
    assert "TE-101" in todo and "327,4" in todo and "°C" in todo
    assert "Aviso" in todo                                    # el color nunca va solo: siempre con texto
    assert "▲ +3,58" in todo and "Última lectura" in todo and "hace" not in todo


@pytest.mark.parametrize("estado, texto", [("normal", "En rango"), ("aviso", "Aviso"), ("alarma", "Alarma"),
                                           ("sin_datos", "Sin datos")])
def test_cada_estado_sale_con_su_texto(qapp, estado, texto):
    t = TarjetaSensor()
    t.poner(tarjeta(estado=estado, valor=None if estado == "sin_datos" else 325.6))
    assert texto in t.pildora.text()


def test_una_tarjeta_sin_lecturas_o_con_datos_viejos_lo_dice(qapp):
    t = TarjetaSensor()
    sin = tarjeta(estado="sin_datos", valor=None, serie=[], tendencia=None)
    sin["instante"] = None
    t.poner(sin)
    assert "Sin lecturas todavía" in t.pie.text() and t.valor.text().count("—") == 1
    t.poner(tarjeta(edad=600))
    assert "hace 10 min" in t.pie.text()


def test_pulsar_una_tarjeta_pide_su_historico(qapp):
    t = TarjetaSensor()
    t.poner(tarjeta(tag="PT-102"))
    elegidos = []
    t.elegido.connect(elegidos.append)
    QTest.mouseClick(t, Qt.MouseButton.LeftButton)
    assert elegidos == ["PT-102"]


@pytest.fixture
def panel(qapp):
    p = VistaPanel("A1")
    p.resize(1300, 800)
    p.show()
    yield p
    p.close()


CUATRO = [tarjeta(), tarjeta("PT-102", "Presión del presionador", "bar", 157.4, "aviso", "aviso", tendencia=3.0),
          tarjeta("FT-103", "Caudal refrigerante primario", "m³/h", 22140.0, "normal"),
          tarjeta("LT-104", "Nivel del presionador", "%", 58.2, "normal")]


def test_el_panel_enseña_los_4_sensores_y_los_indicadores(panel):
    panel.poner_datos(ultimas(*CUATRO, alarmas=1))
    visibles = [t for t in panel._tarjetas if t.isVisibleTo(panel)]
    assert [t.tag for t in visibles] == ["TE-101", "PT-102", "FT-103", "LT-104"]
    assert "3" in panel.kpi_rango.cifra.text() and "/ 4" in panel.kpi_rango.cifra.text()
    assert "1 en aviso · 0 en alarma" == panel.kpi_rango.contexto.text()
    assert panel.kpi_alarmas.cifra.text() == "1" and "PT-102 · aviso" in panel.kpi_alarmas.contexto.text()
    assert "99,8" in panel.kpi_validas.cifra.text() and "5.747 medidas" in panel.kpi_validas.contexto.text()
    assert panel.kpi_tareas.cifra.text() == "—"


def test_sin_alarmas_el_indicador_lo_dice(panel):
    panel.poner_datos(ultimas(*[tarjeta(tag=f"S-{i}") for i in range(4)]))
    assert panel.kpi_alarmas.cifra.text() == "0" and panel.kpi_alarmas.contexto.text() == "Ninguna activa"


def test_si_hay_menos_sensores_se_ocultan_las_tarjetas_sobrantes(panel):
    panel.poner_datos(ultimas(*CUATRO))
    panel.poner_datos(ultimas(*CUATRO[:2]))
    assert [t.isVisibleTo(panel) for t in panel._tarjetas] == [True, True, False, False]


def test_las_tarjetas_pasan_a_dos_columnas_en_ventanas_estrechas(panel):
    panel.poner_datos(ultimas(*CUATRO))
    panel.resize(1300, 800)
    assert {panel.rejilla.getItemPosition(i)[0] for i in range(4)} == {0}          # una fila de 4
    panel.resize(800, 800)
    posiciones = [panel.rejilla.getItemPosition(i) for i in range(4)]
    assert {p[0] for p in posiciones} == {0, 1}                                    # dos filas de 2


def test_pulsar_un_sensor_del_panel_abre_su_historico(panel):
    panel.poner_datos(ultimas(*CUATRO))
    abiertos = []
    panel.abrir_historico.connect(abiertos.append)
    QTest.mouseClick(panel._tarjetas[1], Qt.MouseButton.LeftButton)
    assert abiertos == ["PT-102"]


ALARMAS = [{"id": 1, "tag": "PT-102", "nombre": "Presión del presionador", "unidad": "bar", "nivel": "aviso",
            "valor": 157.4, "abierta_en": "2026-11-03T10:30:00Z", "cerrada_en": None, "estado": "abierta",
            "reconocida_por": None},
           {"id": 2, "tag": "TE-101", "nombre": "Temperatura rama caliente", "unidad": "°C", "nivel": "alarma",
            "valor": 331.0, "abierta_en": "2026-11-02T03:10:00Z", "cerrada_en": "2026-11-02T03:40:00Z",
            "estado": "cerrada", "reconocida_por": None}]


def test_la_tabla_de_alarmas_enseña_nivel_valor_y_estado(panel):
    panel.poner_alarmas(ALARMAS)
    assert panel.tabla.rowCount() == 2 and panel.tabla.isVisibleTo(panel) and not panel.sin_alarmas.isVisibleTo(panel)
    assert panel.tabla.item(0, 0).text() == "PT-102 · Presión del presionador"
    assert (panel.tabla.item(0, 1).text(), panel.tabla.item(0, 2).text()) == ("Aviso", "157,4 bar")
    assert panel.tabla.item(0, 4).text() == "Abierta" and panel.tabla.item(1, 4).text().startswith("Cerrada")
    assert panel.tabla.item(1, 1).text() == "Alarma"


def test_sin_alarmas_se_enseña_un_mensaje_segun_el_filtro(panel):
    panel.poner_alarmas([])
    assert not panel.tabla.isVisibleTo(panel) and "No hay alarmas activas" in panel.sin_alarmas.text()
    filtros = []
    panel.filtro_alarmas.connect(filtros.append)
    panel._botones_filtro["7dias"].click()
    assert filtros == ["7dias"] and panel.filtro_actual() == "7dias"
    panel.poner_alarmas([])
    assert "7 días" in panel.sin_alarmas.text()


def test_el_equipo_lista_a_los_tecnicos_vinculados(qapp, panel):
    panel.poner_equipo([{"id": 5, "nombre": "Diego Paredes Luna", "correo": "d@cn.es", "sensores": ["TE-101", "PT-102"],
                         "ultimo_acceso": "2026-11-03T08:00:00Z"},
                        {"id": 6, "nombre": "Nuria Vega Santos", "correo": "n@cn.es", "sensores": [],
                         "ultimo_acceso": None}])
    qapp.processEvents()
    todo = " ".join(textos(panel))
    assert "Diego Paredes Luna" in todo and "TE-101 · PT-102" in todo and "último acceso" in todo
    assert "Nuria Vega Santos" in todo and "sin sensores asignados" in todo and "aún no ha entrado" in todo
    panel.poner_equipo([])
    qapp.processEvents()
    todo = " ".join(textos(panel))
    assert "Diego Paredes Luna" not in todo and "Todavía no tienes técnicos vinculados" in todo
    assert not panel.error.isVisibleTo(panel)


def test_el_boton_de_asignar_tarea_espera_al_sprint_3(panel):
    boton = [b for b in panel.findChildren(type(panel._botones_filtro["hoy"])) if "Asignar" in b.text()][0]
    assert not boton.isEnabled() and "Sprint 3" in boton.toolTip()


def test_el_panel_avisa_del_area_y_de_los_errores(panel):
    assert any("área A1" in t for t in textos(panel))
    panel.mostrar_error("No se puede conectar con el servidor.")
    assert panel.error.isVisibleTo(panel) and "No se puede conectar" in panel.error.text()
    panel.mostrar_error(None)
    assert not panel.error.isVisibleTo(panel)


# ── Histórico ──
SENSORES = [tarjeta("TE-101"), tarjeta("TE-203", "Temperatura agua de alimentación", "°C"),
            tarjeta("PT-102", "Presión del presionador", "bar")]


def resultado(n=3, tag="TE-101", estado="normal"):
    puntos = [{"hora": f"2026-11-02T{h % 24:02d}:00:00Z".replace("2026-11-02", f"2026-11-{2 + h // 24:02d}"),
               "minimo": 324.0 + h % 3, "maximo": 326.0 + h % 3, "media": 325.0 + h % 3, "lecturas": 12, "validas": 12,
               "estado": estado} for h in range(n)]
    return {"sensor": {"tag": tag, "nombre": "Temperatura rama caliente", "unidad": "°C", "umbrales": UMBRALES,
                       "area": {"codigo": "A1", "nombre": "Reactor"}, "magnitud": "Temperatura", "min_fisico": 0,
                       "max_fisico": 400, "valor_nominal": 325.6},
            "agregado": True, "desde": "2026-11-02T00:00:00Z", "hasta": "2026-11-03T00:00:00Z",
            "resumen": {"minimo": 324.0, "maximo": 328.4, "media": 325.0, "lecturas": 12 * n, "validas": 12 * n - 9,
                        "pct_en_rango": 98.2}, "puntos": puntos}


@pytest.fixture
def historico(qapp):
    h = VistaHistorico()
    h.resize(1200, 900)
    h.poner_sensores(SENSORES)
    h.show()
    yield h
    h.close()


def test_el_historico_ofrece_los_sensores_del_panel_y_compara_solo_la_misma_unidad(historico):
    assert [historico.sensor.itemData(i) for i in range(historico.sensor.count())] == ["TE-101", "TE-203", "PT-102"]
    assert [historico.comparar.itemData(i) for i in range(historico.comparar.count())] == [None, "TE-203"]
    historico.elegir_sensor("PT-102")
    assert [historico.comparar.itemData(i) for i in range(historico.comparar.count())] == [None]
    historico.poner_sensores(SENSORES)                             # al refrescar se conserva el sensor elegido
    assert historico.sensor.currentData() == "PT-102"


def test_los_botones_de_periodo_cambian_lo_que_se_pide(historico):
    assert historico.parametros() == {"tag": "TE-101", "horas": 168, "desde": None, "hasta": None, "comparar": None}
    historico._botones_periodo["24h"].click()
    assert historico.parametros()["horas"] == 24
    historico._botones_periodo["30d"].click()
    assert historico.parametros()["horas"] == 720
    assert not historico.rango.isVisibleTo(historico)


def test_el_periodo_personalizado_pide_fechas_en_utc(historico):
    historico._botones_periodo["personalizado"].click()
    assert historico.rango.isVisibleTo(historico)
    historico.desde.setDate(QDate(2026, 11, 1))
    historico.hasta.setDate(QDate(2026, 11, 3))
    p = historico.parametros()
    assert p["horas"] is None
    patron = r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$"
    import re
    assert re.match(patron, p["desde"]) and re.match(patron, p["hasta"]) and p["desde"] < p["hasta"]


def test_aplicar_y_exportar_envian_los_parametros(historico):
    pedidos, exportados = [], []
    historico.consultar.connect(pedidos.append)
    historico.exportar.connect(exportados.append)
    historico.comparar.setCurrentIndex(1)
    historico.boton_aplicar.click()
    historico.boton_csv.click()
    assert pedidos[0]["comparar"] == "TE-203" and pedidos[0]["tag"] == "TE-101"
    assert exportados == pedidos


def test_sin_sensores_aplicar_no_hace_nada(qapp):
    h = VistaHistorico()
    pedidos = []
    h.consultar.connect(pedidos.append)
    h.aplicar()
    assert pedidos == []


def test_el_historico_enseña_estadisticas_grafica_y_tabla(historico):
    historico.poner_resultado(resultado(5))
    assert "324,0" in historico.kpi_min.cifra.text() and "328,4" in historico.kpi_max.cifra.text()
    assert "325,0" in historico.kpi_media.cifra.text() and "98,2" in historico.kpi_rango.cifra.text()
    assert historico.kpi_validas.cifra.text() == "51" and historico.kpi_validas.contexto.text() == "de 60 lecturas"
    assert historico.titulo_grafica.text() == "TE-101 · Temperatura rama caliente (°C)"
    assert len(historico.grafica._series) == 1 and historico.grafica._series[0].marcar_maximo
    assert historico.tabla.rowCount() == 5 and "1–5 de 5 filas" in historico.cuenta.text()
    assert historico.tabla.item(0, 5).text() == "En rango"


def test_la_tabla_enseña_primero_lo_mas_reciente_y_resalta_los_avisos(historico):
    r = resultado(3)
    r["puntos"][2]["estado"] = "aviso"
    historico.poner_resultado(r)
    assert historico.tabla.item(0, 5).text() == "Aviso"                        # la última hora, arriba
    assert historico.tabla.item(0, 0).text() != historico.tabla.item(2, 0).text()


def test_la_tabla_se_pagina_de_10_en_10(historico):
    historico.poner_resultado(resultado(25))
    assert historico.tabla.rowCount() == FILAS_POR_PAGINA and "1–10 de 25" in historico.cuenta.text()
    assert not historico.anterior.isEnabled() and historico.siguiente.isEnabled()
    historico.siguiente.click()
    assert "11–20 de 25" in historico.cuenta.text() and historico.anterior.isEnabled()
    historico.siguiente.click()
    assert historico.tabla.rowCount() == 5 and "21–25 de 25" in historico.cuenta.text()
    assert not historico.siguiente.isEnabled()
    historico.anterior.click()
    assert "11–20 de 25" in historico.cuenta.text()


def test_comparar_dibuja_dos_series(historico):
    historico.poner_resultado(resultado(5), resultado(5, tag="TE-203"))
    assert [s.nombre for s in historico.grafica._series] == ["TE-101", "TE-203"]
    assert "comparado con TE-203" in historico.leyenda.text()


def test_un_periodo_sin_lecturas_no_rompe_la_ventana(historico):
    vacio = resultado(0)
    vacio["resumen"] = {"minimo": None, "maximo": None, "media": None, "lecturas": 0, "validas": 0,
                        "pct_en_rango": None}
    historico.poner_resultado(vacio)
    assert historico.tabla.rowCount() == 0 and "0–0 de 0 filas" in historico.cuenta.text()
    assert historico.kpi_min.cifra.text().startswith("—") and historico.kpi_rango.cifra.text() == "—"
    assert not historico.grafica.grab().isNull()


def test_avisos_de_error_e_informacion_y_boton_ocupado(historico):
    historico.mostrar_error("Puedes consultar como máximo 30 días de una vez.")
    assert historico.error.isVisibleTo(historico) and historico.error.objectName() == "AvisoError"
    historico.mostrar_info("Exportado.")
    assert historico.error.objectName() == "AvisoOk"
    historico.ocultar_error()
    assert not historico.error.isVisibleTo(historico)
    historico.ocupado(True)
    assert not historico.boton_aplicar.isEnabled() and historico.boton_aplicar.text() == "Consultando…"
    historico.ocupado(False)
    assert historico.boton_aplicar.isEnabled()
