"""T03 · Base de datos: catálogo, claves, restricciones y migraciones."""
import sqlite3

import pytest

from servidor import migrate


def test_hay_9_areas_4_roles_y_36_sensores(conexion):
    cuenta = lambda t: conexion.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"]
    assert cuenta("area") == 9
    assert cuenta("rol") == 4
    assert cuenta("sensor") == 36


def test_cada_area_tiene_4_sensores(conexion):
    filas = conexion.execute("SELECT a.codigo, count(*) AS n FROM sensor s JOIN area a ON a.id = s.area_id"
                             " GROUP BY a.codigo").fetchall()
    assert len(filas) == 9 and all(f["n"] == 4 for f in filas)


def test_el_valor_nominal_de_cada_sensor_esta_en_rango(conexion):
    filas = conexion.execute("SELECT tag FROM sensor WHERE valor_nominal NOT BETWEEN min_fisico AND max_fisico"
                             " OR valor_nominal >= coalesce(aviso_alto, 1e999)"
                             " OR valor_nominal <= coalesce(aviso_bajo, -1e999)").fetchall()
    assert filas == []


def test_migraciones_repetidas_no_hacen_nada(conexion):
    assert migrate.aplicar(conexion) == []


def test_las_tablas_del_modelo_existen(conexion):
    tablas = {f["tablename"] for f in conexion.execute("SELECT name AS tablename FROM sqlite_master WHERE type = 'table'")}
    esperadas = {"usuario", "rol", "area", "sensor", "lectura", "alarma", "tarea", "incidencia",
                 "evento_auditoria", "sesion", "schema_migrations"}
    assert esperadas <= tablas


def test_un_tecnico_necesita_supervisor(crear_usuario):
    with pytest.raises(sqlite3.IntegrityError, match="necesita un supervisor"):
        crear_usuario(nombre="Diego Paredes Luna", correo="diego@cn.es", rol="tecnico", area="A1")


def test_el_supervisor_de_un_tecnico_debe_ser_supervisor(crear_usuario):
    auditor = crear_usuario(nombre="Beatriz Lara Quintana", correo="beatriz@cn.es", rol="auditor", area=None)
    with pytest.raises(sqlite3.IntegrityError, match="no es un supervisor"):
        crear_usuario(nombre="Diego Paredes Luna", correo="diego@cn.es", rol="tecnico", area=None,
                      supervisor_id=auditor)


def test_el_tecnico_hereda_el_area_de_su_supervisor(crear_usuario, conexion):
    sup = crear_usuario()
    tec = crear_usuario(nombre="Diego Paredes Luna", correo="diego@cn.es", rol="tecnico", area=None,
                        supervisor_id=sup)
    area = conexion.execute("SELECT a.codigo FROM usuario u JOIN area a ON a.id = u.area_id WHERE u.id = ?",
                            (tec,)).fetchone()
    assert area["codigo"] == "A1"


def test_el_tecnico_no_puede_estar_en_otra_area(crear_usuario):
    sup = crear_usuario()
    with pytest.raises(sqlite3.IntegrityError, match="área de su supervisor"):
        crear_usuario(nombre="Diego Paredes Luna", correo="diego@cn.es", rol="tecnico", area="A2",
                      supervisor_id=sup)


def test_solo_los_tecnicos_tienen_supervisor(crear_usuario):
    sup = crear_usuario()
    with pytest.raises(sqlite3.IntegrityError, match="Solo los técnicos"):
        crear_usuario(nombre="Javier Ruiz Pastor", correo="javier@cn.es", rol="supervisor", area="A2",
                      supervisor_id=sup)


def test_un_supervisor_necesita_area(crear_usuario):
    with pytest.raises(sqlite3.IntegrityError, match="necesita un área"):
        crear_usuario(area=None)


def test_el_correo_es_unico_sin_distinguir_mayusculas(crear_usuario):
    crear_usuario()
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        crear_usuario(nombre="Otra Persona", correo="LAURA.MENDEZ@cn-valdecierzo.es")


def test_correo_invalido_rechazado(crear_usuario):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        crear_usuario(correo="sin-arroba")


def test_umbrales_desordenados_rechazados(conexion):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conexion.execute(
            "INSERT INTO sensor (tag, nombre, magnitud, unidad, area_id, valor_nominal, min_fisico, max_fisico,"
            " aviso_alto, alarma_alto) VALUES ('XX-999', 'x', 'x', 'x', 1, 5, 0, 10, 8, 7)")


def test_lectura_duplicada_rechazada(conexion):
    conexion.execute("INSERT INTO lectura (sensor_id, instante, valor) VALUES (1, datetime('now'), 1.0)")
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conexion.execute("INSERT INTO lectura (sensor_id, instante, valor) SELECT sensor_id, instante, 2 FROM lectura")


def test_una_tarea_no_se_asigna_a_uno_mismo(crear_usuario, conexion):
    sup = crear_usuario()
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conexion.execute("INSERT INTO tarea (titulo, creada_por, asignada_a) VALUES ('x', ?, ?)", (sup, sup))


def test_una_lectura_manual_necesita_valor(crear_usuario, conexion):
    sup = crear_usuario()
    tec = crear_usuario(nombre="Diego Paredes Luna", correo="diego@cn.es", rol="tecnico", area=None,
                        supervisor_id=sup)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conexion.execute("INSERT INTO incidencia (tecnico_id, sensor_id, tipo) VALUES (?, 1, 'lectura_manual')",
                         (tec,))


def test_el_registro_de_auditoria_no_se_edita_ni_se_borra(conexion):
    conexion.execute("INSERT INTO evento_auditoria (accion, resultado) VALUES ('prueba', 'ok')")
    conexion.commit()
    with pytest.raises(sqlite3.IntegrityError, match="no se puede modificar"):
        conexion.execute("UPDATE evento_auditoria SET accion = 'otra'")
    conexion.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="no se puede modificar"):
        conexion.execute("DELETE FROM evento_auditoria")
