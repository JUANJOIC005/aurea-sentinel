"""T11 · Sensores de cada técnico: reparto de la demostración y reglas de la base de datos."""
import sqlite3

import pytest

from servidor import datos_demo


def asignaciones(conexion):
    return conexion.execute(
        "SELECT t.nombre AS tecnico, s.tag FROM asignacion_sensor x JOIN usuario t ON t.id = x.tecnico_id"
        " JOIN sensor s ON s.id = x.sensor_id ORDER BY t.id, s.id").fetchall()


def test_los_tecnicos_de_demostracion_tienen_los_sensores_de_su_area(conexion):
    datos_demo.crear_cuentas(conexion, "Valdecierzo-2026!")
    por_tecnico = {}
    for f in asignaciones(conexion):
        por_tecnico.setdefault(f["tecnico"], []).append(f["tag"])
    assert por_tecnico["Diego Paredes Luna"] == ["TE-101", "FT-103"]            # Laura reparte entre sus dos técnicos
    assert por_tecnico["Nuria Vega Santos"] == ["PT-102", "LT-104"]
    assert len(por_tecnico["Óscar Medina Torres"]) == 4                          # Marta solo tiene uno: los cuatro
    assert set(por_tecnico) == {"Diego Paredes Luna", "Nuria Vega Santos", "Iván Cano Rubio", "Carmen Lozano Díaz",
                                "Óscar Medina Torres", "Mario Serrano Blanco"}


def test_todos_los_sensores_de_un_area_con_tecnicos_quedan_asignados(conexion):
    datos_demo.crear_cuentas(conexion, "Valdecierzo-2026!")
    sin_tecnico = conexion.execute(
        "SELECT s.tag FROM sensor s WHERE s.area_id IN (SELECT area_id FROM usuario WHERE supervisor_id IS NOT NULL)"
        " AND s.id NOT IN (SELECT sensor_id FROM asignacion_sensor)").fetchall()
    assert sin_tecnico == []


def test_repetir_la_asignacion_no_duplica_nada(conexion):
    datos_demo.crear_cuentas(conexion, "Valdecierzo-2026!")
    antes = len(asignaciones(conexion))
    assert datos_demo.asignar_sensores(conexion) == 0
    assert len(asignaciones(conexion)) == antes == 16


def test_solo_se_asignan_sensores_a_tecnicos(central, conexion):
    with pytest.raises(sqlite3.IntegrityError, match="Solo se asignan sensores a técnicos"):
        conexion.execute("INSERT INTO asignacion_sensor (tecnico_id, sensor_id) VALUES (?, 1)", (central["laura"],))


def test_un_tecnico_no_recibe_sensores_de_otra_area(central, conexion):
    with pytest.raises(sqlite3.IntegrityError, match="El sensor es de otra área"):
        conexion.execute("INSERT INTO asignacion_sensor (tecnico_id, sensor_id)"
                         " VALUES (?, (SELECT id FROM sensor WHERE tag = 'PT-201'))", (central["diego"],))
