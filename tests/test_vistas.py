"""T07 y T08 · Ventanas: estructura común, nombre y rol visibles, adaptación al tamaño."""
from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtWidgets import QPushButton

from cliente.modelo.menus import MENUS
from cliente.modelo.sesion import Sesion
from cliente.vista import estilos
from cliente.vista.componentes import Avatar, InsigniaRol
from cliente.vista.login import VistaLogin
from cliente.vista.registro import VistaRegistro
from cliente.vista.ventana_base import VentanaBase

PERSONAS = {
    "supervisor": ("Laura Méndez Ortiz", "Supervisor", {"codigo": "A1", "nombre": "Reactor y circuito primario"}),
    "tecnico": ("Diego Paredes Luna", "Técnico", {"codigo": "A1", "nombre": "Reactor y circuito primario"}),
    "auditor": ("Beatriz Lara Quintana", "Auditor", None),
    "administrador": ("Álvaro Campos Ibarra", "Administrador", None),
}


def sesion(rol):
    nombre, _, area = PERSONAS[rol]
    expira = datetime.now(timezone.utc) + timedelta(minutes=15)
    return Sesion.desde_respuesta({
        "token": "t", "expira_en": expira.isoformat(),
        "usuario": {"id": 1, "nombre": nombre, "correo": "x@cn.es", "rol": rol, "area": area,
                    "supervisor": {"id": 2, "nombre": "Laura Méndez Ortiz"} if rol == "tecnico" else None}})


def textos(ventana):
    """Todos los textos visibles de una ventana, para comprobar que aparece el nombre y el rol."""
    from PySide6.QtWidgets import QLabel
    return [w.text() for w in ventana.findChildren(QLabel) if w.isVisibleTo(ventana)]


@pytest.mark.parametrize("rol", list(PERSONAS))
def test_todas_las_vistas_muestran_nombre_y_rol(qapp, rol):
    nombre, rol_visible, _ = PERSONAS[rol]
    ventana = VentanaBase(sesion(rol), "127.0.0.1:8000")
    ventana.resize(1500, 900)
    ventana.show()
    todo = " | ".join(textos(ventana))
    # cabecera (avatar + nombre + insignia), pie del menú y barra de estado
    nombres = [t for t in textos(ventana) if nombre in t]
    assert len(nombres) >= 3, nombres
    assert rol_visible in [t for t in textos(ventana)]
    assert todo.count(rol_visible) >= 3
    ventana.close()


def test_el_menu_depende_del_rol(qapp):
    for rol, secciones in MENUS.items():
        ventana = VentanaBase(sesion(rol), "127.0.0.1:8000")
        assert list(ventana.menu._botones) == [s.clave for s in secciones]
        ventana.close()


def test_el_area_aparece_en_el_pie_y_en_la_barra_de_estado(qapp):
    ventana = VentanaBase(sesion("supervisor"), "127.0.0.1:8000")
    ventana.show()
    assert any("A1 · Reactor y circuito primario" == t for t in textos(ventana))
    assert "A1 · Reactor y circuito primario" in ventana.barra.izquierda.text()
    ventana.close()


def test_el_tecnico_ve_su_area_y_el_auditor_todas(qapp):
    tecnico = VentanaBase(sesion("tecnico"), "x")
    auditor = VentanaBase(sesion("auditor"), "x")
    assert "A1" in tecnico.barra.izquierda.text()
    assert "Todas las áreas" in auditor.barra.izquierda.text()


def test_navegar_cambia_el_titulo_y_la_vista(qapp):
    ventana = VentanaBase(sesion("supervisor"), "x")
    assert ventana.cabecera.titulo.text() == "Panel del área A1"
    ventana.menu._botones["historico"].click()
    assert ventana.cabecera.titulo.text() == "Histórico de sensores"
    assert "Histórico de sensores" in ventana.windowTitle()
    assert ventana.menu._botones["historico"].isChecked() and not ventana.menu._botones["panel"].isChecked()


def test_cada_seccion_pendiente_dice_en_que_sprint_llega(qapp):
    ventana = VentanaBase(sesion("supervisor"), "x")
    ventana.mostrar("equipo")
    from PySide6.QtWidgets import QLabel
    todo = " ".join(l.text() for l in ventana.contenido.currentWidget().findChildren(QLabel))
    assert "Sprint 3" in todo and "Ventana 06" in todo and "Laura Méndez Ortiz" in todo


def test_una_ventana_real_sustituye_al_marcador(qapp):
    from PySide6.QtWidgets import QLabel
    ventana = VentanaBase(sesion("supervisor"), "x")
    propia = QLabel("Mi panel")
    ventana.registrar_vista("panel", propia)
    ventana.mostrar("panel")
    assert ventana.contenido.currentWidget() is propia
    ventana.registrar_vista("panel", QLabel("Otra"))     # al registrar otra vez se reemplaza la anterior
    assert ventana.contenido.count() == 1


def test_menu_completo_en_pantallas_grandes_y_de_iconos_en_pequenas(qapp):
    ventana = VentanaBase(sesion("supervisor"), "x")
    ventana.show()
    ventana.resize(1920, 1080)
    assert ventana.menu.width() == estilos.ANCHO_MENU and ventana.cabecera.chip.isVisible()
    assert ventana.menu._botones["panel"].text().strip() == "Panel del área"
    ventana.resize(1280, 720)
    assert ventana.menu.width() == estilos.ANCHO_MENU_REDUCIDO == 68
    assert not ventana.cabecera.chip.isVisible()              # el estado sigue en la barra inferior
    assert ventana.menu._botones["panel"].text() == "" and ventana.menu._botones["panel"].toolTip() == "Panel del área"
    ventana.resize(1366, 768)
    assert ventana.menu.width() == estilos.ANCHO_MENU
    ventana.close()


def test_tamano_minimo_1024x640(qapp):
    ventana = VentanaBase(sesion("supervisor"), "x")
    ventana.show()
    ventana.resize(300, 300)
    assert (ventana.width(), ventana.height()) == (1024, 640)
    ventana.close()


def test_se_ve_bien_en_las_tres_resoluciones_de_prueba(qapp):
    for ancho, alto in ((1280, 720), (1920, 1080), (2560, 1440)):
        ventana = VentanaBase(sesion("supervisor"), "x")
        ventana.resize(ancho, alto)
        ventana.show()
        assert ventana.centralWidget().width() == ancho
        assert ventana.contenido.width() > 400            # el contenido nunca queda aplastado
        ventana.close()


def test_colores_de_marca_y_de_rol():
    assert estilos.AZUL == "#0B2D5B" and estilos.CIAN == "#00C2FF" and estilos.PLATA == "#D7DEE7"
    assert len(set(estilos.COLOR_ROL.values())) == 4
    assert estilos.COLOR_ROL["supervisor"] == estilos.AZUL


def test_componentes_de_identificacion(qapp):
    insignia = InsigniaRol("tecnico", "Técnico")
    assert estilos.ACERO in insignia.styleSheet()
    avatar = Avatar("LM", estilos.AZUL, 40)
    assert avatar.size().width() == 40
    avatar.grab()                                          # se dibuja sin fallar


# ── Login ──
def test_login_emite_lo_que_se_escribe(qapp):
    vista = VistaLogin()
    recibido = []
    vista.entrar.connect(lambda *datos: recibido.append(datos))
    vista.correo.setText("  laura@cn.es ")
    vista.password.setText("clave")
    vista.compartido.setChecked(True)
    vista.boton.click()
    assert recibido == [("laura@cn.es", "clave", True)]


def test_enter_en_la_contrasena_envia_el_formulario(qapp):
    vista = VistaLogin()
    recibido = []
    vista.entrar.connect(lambda *datos: recibido.append(datos))
    vista.correo.setText("a@b.c")
    vista.password.setText("x")
    vista.password.returnPressed.emit()
    assert len(recibido) == 1


def test_el_ojo_muestra_y_oculta_la_contrasena(qapp):
    from PySide6.QtWidgets import QLineEdit
    vista = VistaLogin()
    assert vista.password.echoMode() == QLineEdit.EchoMode.Password
    vista._ojo.trigger()
    assert vista.password.echoMode() == QLineEdit.EchoMode.Normal
    vista._ojo.trigger()
    assert vista.password.echoMode() == QLineEdit.EchoMode.Password


def test_avisos_del_login(qapp):
    vista = VistaLogin()
    vista.show()
    vista.mostrar_error("Mal")
    assert vista.aviso.isVisible() and vista.aviso.objectName() == "AvisoError"
    vista.mostrar_info("Bien")
    assert vista.aviso.objectName() == "AvisoOk" and vista.aviso.text() == "Bien"
    vista.ocultar_aviso()
    assert not vista.aviso.isVisible()
    vista._olvido()
    assert "administrador" in vista.aviso.text()
    vista.ocupado(True)
    assert not vista.boton.isEnabled() and vista.boton.text() == "Comprobando…"
    vista.ocupado(False)
    vista.password.setText("algo")
    vista.limpiar()
    assert vista.password.text() == ""


def test_login_tiene_el_enlace_de_registro(qapp):
    vista = VistaLogin()
    assert "Solicitar acceso" in " ".join(b.text() for b in vista.findChildren(QPushButton))
    pedido = []
    vista.solicitar_acceso.connect(lambda: pedido.append(1))
    next(b for b in vista.findChildren(QPushButton) if b.text() == "Solicitar acceso").click()
    assert pedido == [1]


# ── Registro ──
def test_registro_politica_de_contrasena_en_vivo(qapp):
    vista = VistaRegistro()
    assert "○ Mínimo 12" in vista.politica.text()
    vista.password.setText("Valdecierzo-2026-ok!")
    assert "✓ Mínimo 12" in vista.politica.text() and "○ coinciden" in vista.politica.text()
    vista.repetir.setText("Valdecierzo-2026-ok!")
    assert "✓ coinciden" in vista.politica.text()


def test_registro_habilita_los_campos_segun_el_rol(qapp):
    vista = VistaRegistro()
    vista.poner_areas([{"codigo": "A1", "nombre": "Reactor"}])
    vista.rol.setCurrentIndex(0)                          # supervisor
    assert vista.area.isEnabled() and not vista.supervisor.isEnabled()
    assert vista.datos()["area"] == "A1" and vista.datos()["supervisor_id"] is None
    vista.rol.setCurrentIndex(2)                          # auditor
    assert not vista.area.isEnabled() and vista.datos()["area"] is None


def test_registro_emite_los_datos_y_se_limpia(qapp):
    vista = VistaRegistro()
    recibido = []
    vista.enviar.connect(recibido.append)
    vista.nombre.setText("Marcos Gil Arroyo")
    vista.motivo.setPlainText("Turno de mañana")
    vista.boton.click()
    assert recibido[0]["nombre"] == "Marcos Gil Arroyo" and recibido[0]["motivo"] == "Turno de mañana"
    vista.limpiar()
    assert vista.nombre.text() == "" and vista.motivo.toPlainText() == ""
    vista.mostrar_error("x")
    vista.ocupado(True)
    assert vista.boton.text() == "Enviando…"
    vista.ocupado(False)
    vista.ocultar_aviso()
