"""T16 · Registro de auditoría encadenado, verificación y exportación a CSV firmado."""
import csv
import io
import threading

import pytest

from servidor import auditoria, claves, config, db
from servidor.api import permisos, registro
from tests.conftest import CLAVE, CORREOS


@pytest.fixture
def cab(entrar):
    def _cab(nombre):
        token, _ = entrar(CORREOS[nombre])
        return {"Authorization": f"Bearer {token}"}
    return _cab


def movimiento(api, cab):
    """Un poco de actividad real: accesos, un fallo y una denegación."""
    api.post("/auth/login", json={"correo": CORREOS["laura"], "password": "no-es-la-buena-123"})
    api.get("/equipo", headers=cab("diego"))
    api.get("/lecturas/ultimas", headers=cab("laura"))


def sin_proteccion(conexion):
    """Para simular a alguien que manipula el archivo de la base de datos: quita los disparadores que lo impiden."""
    conexion.execute("DROP TRIGGER evento_auditoria_no_editar")
    conexion.execute("DROP TRIGGER evento_auditoria_no_borrar")
    conexion.commit()


# ── La cadena ──
def test_cada_evento_enlaza_con_el_anterior(api, central, cab, conexion):
    movimiento(api, cab)
    filas = conexion.execute("SELECT * FROM evento_auditoria ORDER BY id").fetchall()
    assert len(filas) == 4                    # fallo de login, login de Diego, su denegación y login de Laura
    assert filas[0]["hash_anterior"] == auditoria.ORIGEN
    for anterior, actual in zip(filas, filas[1:]):
        assert actual["hash_anterior"] == anterior["hash"]
        assert len(actual["hash"]) == 64


def test_la_huella_depende_de_todo_el_contenido():
    base = ("0" * 64, "2026-11-20 10:00:00", 3, "login", "sesion", "ok", "{}")
    h = auditoria.huella(*base)
    for i, cambio in enumerate(["1" * 64, "2026-11-20 10:00:01", 4, "logout", "otra", "fallo", '{"a":1}']):
        otra = list(base)
        otra[i] = cambio
        assert auditoria.huella(*otra) != h


def test_un_registro_sin_tocar_es_integro(api, central, cab, conexion):
    movimiento(api, cab)
    r = auditoria.verificar(conexion)
    assert r["integro"] and r["primer_error"] is None and r["encadenados"] == r["eventos"] and r["sin_cadena"] == 0


def test_si_se_cambia_un_evento_la_verificacion_dice_cual(api, central, cab, conexion):
    movimiento(api, cab)
    sin_proteccion(conexion)
    victima = conexion.execute("SELECT id FROM evento_auditoria WHERE accion = 'acceso_denegado'").fetchone()["id"]
    conexion.execute("UPDATE evento_auditoria SET resultado = 'ok' WHERE id = ?", (victima,))
    conexion.commit()
    r = auditoria.verificar(conexion)
    assert not r["integro"] and r["primer_error"]["id"] == victima and "modificado" in r["primer_error"]["motivo"]


def test_si_se_borra_un_evento_la_verificacion_lo_detecta(api, central, cab, conexion):
    movimiento(api, cab)
    sin_proteccion(conexion)
    ids = [f["id"] for f in conexion.execute("SELECT id FROM evento_auditoria ORDER BY id")]
    conexion.execute("DELETE FROM evento_auditoria WHERE id = ?", (ids[2],))
    conexion.commit()
    r = auditoria.verificar(conexion)
    assert not r["integro"] and r["primer_error"]["id"] == ids[3] and "anterior" in r["primer_error"]["motivo"]


def test_rehacer_la_huella_de_un_evento_cambiado_tampoco_cuela(api, central, cab, conexion):
    movimiento(api, cab)
    sin_proteccion(conexion)
    e = conexion.execute("SELECT * FROM evento_auditoria ORDER BY id LIMIT 1 OFFSET 1").fetchone()
    nueva = auditoria.huella(e["hash_anterior"], e["instante"], e["actor_id"], e["accion"], e["recurso"], "ok", "{}")
    conexion.execute("UPDATE evento_auditoria SET detalle = '{}', resultado = 'ok', hash = ? WHERE id = ?", (nueva, e["id"]))
    conexion.commit()
    r = auditoria.verificar(conexion)
    assert not r["integro"] and r["primer_error"]["id"] == e["id"] + 1


def test_los_eventos_anteriores_a_la_cadena_se_cuentan_aparte(conexion):
    conexion.execute("INSERT INTO evento_auditoria (accion, resultado) VALUES ('antiguo', 'ok')")
    conexion.execute("INSERT INTO evento_auditoria (accion, resultado) VALUES ('antiguo', 'ok')")
    conexion.commit()
    auditoria.registrar(conexion, "nuevo", "ok")
    conexion.commit()
    r = auditoria.verificar(conexion)
    assert r["integro"] and (r["sin_cadena"], r["encadenados"]) == (2, 1)
    conexion.execute("INSERT INTO evento_auditoria (accion, resultado) VALUES ('colado', 'ok')")
    conexion.commit()
    assert auditoria.verificar(conexion)["primer_error"]["motivo"].startswith("Evento sin huella")


def test_muchas_escrituras_a_la_vez_no_rompen_la_cadena(central):
    def escribir(n):
        for i in range(10):
            with db.conexion() as conn:
                auditoria.registrar(conn, "concurrente", "ok", detalle={"hilo": n, "i": i})
    hilos = [threading.Thread(target=escribir, args=(n,)) for n in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    with db.conexion() as conn:
        r = auditoria.verificar(conn)
    assert r["integro"] and r["encadenados"] == 40


# ── Consulta ──
def test_el_auditor_ve_todo_el_registro_sin_nombres(api, central, cab):
    movimiento(api, cab)
    eventos = api.get("/auditoria/eventos", headers=cab("beatriz")).json()["eventos"]
    assert eventos[0]["id"] > eventos[-1]["id"]                       # lo más reciente primero
    assert {e["accion"] for e in eventos} >= {"login", "acceso_denegado"}
    texto = str(eventos)
    assert "Laura" not in texto and "Diego" not in texto and "Usuario n.º" in texto
    denegado = [e for e in eventos if e["accion"] == "acceso_denegado"][0]
    assert denegado["actor"] == f"Usuario n.º {central['diego']}" and denegado["rol"] == "Técnico"


def test_los_filtros_del_registro(api, central, cab):
    movimiento(api, cab)
    pedir = lambda **p: api.get("/auditoria/eventos", params=p, headers=cab("beatriz")).json()["eventos"]
    assert {e["accion"] for e in pedir(accion="acceso_denegado")} == {"acceso_denegado"}
    assert {e["resultado"] for e in pedir(resultado="fallo")} == {"fallo"}
    assert len(pedir(limite=2)) == 2
    assert pedir(desde="2099-01-01") == []
    assert api.get("/auditoria/eventos", params={"resultado": "raro"}, headers=cab("beatriz")).status_code == 422


def test_el_administrador_solo_ve_sus_propios_eventos(api, central, cab):
    movimiento(api, cab)
    api.get("/lecturas/ultimas", headers=cab("alvaro"))               # una denegación suya
    eventos = api.get("/auditoria/eventos", headers=cab("alvaro")).json()["eventos"]
    assert eventos and all(e["actor"] == "Álvaro Campos Ibarra" for e in eventos)


@pytest.mark.parametrize("nombre", ["laura", "diego"])
def test_supervisor_y_tecnico_no_entran_en_el_registro(api, central, cab, nombre):
    for ruta in ("/auditoria/eventos", "/auditoria/verificar", "/auditoria/exportar"):
        assert api.get(ruta, headers=cab(nombre)).status_code == 403


def test_el_administrador_no_verifica_ni_exporta(api, central, cab):
    assert api.get("/auditoria/verificar", headers=cab("alvaro")).status_code == 403
    assert api.get("/auditoria/exportar", headers=cab("alvaro")).status_code == 403


def test_la_verificacion_por_la_api_queda_en_el_registro(api, central, cab, conexion):
    movimiento(api, cab)
    r = api.get("/auditoria/verificar", headers=cab("beatriz")).json()
    assert r["integro"] is True and r["eventos"] > 0
    assert conexion.execute("SELECT count(*) AS n FROM evento_auditoria WHERE accion = 'verificacion_auditoria'"
                            ).fetchone()["n"] == 1


# ── Exportación a CSV firmado ──
def exportar(api, cab, **params):
    r = api.get("/auditoria/exportar", params=params, headers=cab("beatriz"))
    assert r.status_code == 200, r.text
    return r


def test_el_csv_lleva_cabecera_eventos_sin_nombres_y_firma(api, central, cab):
    movimiento(api, cab)
    r = exportar(api, cab)
    texto = r.content.decode("utf-8-sig")
    lineas = texto.strip("\r\n").split("\r\n")
    assert lineas[0].startswith("# AUREA Sentinel · registro de auditoría") and "cadena íntegra" in lineas[0]
    assert lineas[1] == ";".join(registro.COLUMNAS)
    assert lineas[-1] == registro.PREFIJO_FIRMA + r.headers["X-Aurea-Firma"]
    filas = list(csv.DictReader(io.StringIO("\n".join(lineas[1:-1])), delimiter=";"))
    assert filas and all(f["actor"].startswith(("Usuario n.º", "Sistema")) for f in filas)
    assert "Laura" not in texto and "attachment" in r.headers["Content-Disposition"]


def test_la_firma_del_csv_se_comprueba_y_un_cambio_la_rompe(api, central, cab):
    movimiento(api, cab)
    contenido = exportar(api, cab).content
    assert registro.comprobar_firma(contenido)
    assert api.post("/auditoria/comprobar-firma", content=contenido, headers=cab("beatriz")).json() == {"valida": True}
    tocado = contenido.replace(b"denegado", b"ok", 1)
    assert not registro.comprobar_firma(tocado)
    assert api.post("/auditoria/comprobar-firma", content=tocado, headers=cab("beatriz")).json() == {"valida": False}
    assert not registro.comprobar_firma(contenido.rsplit(b"# firma", 1)[0])
    assert api.post("/auditoria/comprobar-firma", content=b"", headers=cab("beatriz")).status_code == 422


def test_otra_clave_no_firma_igual(api, central, cab, monkeypatch):
    contenido = exportar(api, cab).content
    monkeypatch.setenv("AUREA_CLAVE_EXPORTACION", "otra-clave-distinta")
    assert not registro.comprobar_firma(contenido)


def test_cada_exportacion_queda_en_el_registro_y_la_cadena_sigue_integra(api, central, cab, conexion):
    movimiento(api, cab)
    exportar(api, cab, accion="login")
    fila = conexion.execute("SELECT actor_id, detalle FROM evento_auditoria WHERE accion = 'exportacion_auditoria'").fetchone()
    assert fila["actor_id"] == central["beatriz"] and '"accion": "login"' in fila["detalle"]
    assert auditoria.verificar(conexion)["integro"]


def test_si_la_cadena_esta_rota_el_csv_lo_dice(api, central, cab, conexion):
    movimiento(api, cab)
    sin_proteccion(conexion)
    conexion.execute("UPDATE evento_auditoria SET detalle = '{\"x\":1}' WHERE id = 2")
    conexion.commit()
    assert "cadena ROTA" in exportar(api, cab).content.decode("utf-8-sig").split("\r\n")[0]


def test_la_clave_de_exportacion_vive_fuera_del_repositorio(monkeypatch):
    monkeypatch.delenv("AUREA_CLAVE_EXPORTACION", raising=False)
    archivo = config.RUTA_BD.parent / claves.NOMBRE_ARCHIVO_EXPORTACION
    archivo.unlink(missing_ok=True)
    clave = claves.clave_exportacion()
    assert archivo.is_file() and len(clave) == 64 and claves.clave_exportacion() == clave
    assert clave != claves.clave_ingesta()
    assert config.RAIZ not in archivo.parents


def test_la_tabla_de_permisos_del_registro():
    assert permisos.PERMISOS[("auditoria", "ver")] == {"auditor": "todo", "administrador": "propias"}
    assert permisos.PERMISOS[("auditoria", "exportar")] == {"auditor": "todo"}
