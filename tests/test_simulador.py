"""T06 · Simulador de sensores."""
import random
from datetime import datetime, timedelta, timezone

import pytest

from servidor import config
from simulador import modelo
from simulador.__main__ import ejecutar, generar
from simulador.destinos import DestinoBaseDeDatos
from simulador.modelo import Sensor, SensorSimulado

PRESIONADOR = Sensor(2, "PT-102", 155.0, 0, 200, 152.0, 150.0, 157.0, 160.0)
SOLO_ALTO = Sensor(3, "VT-302", 2.5, 0, 20, None, None, 7.1, 11.2)
SIN_UMBRALES = Sensor(4, "XX-000", 50.0, 0, 100)


def simular(sensor, pasos, dt=5.0, semilla=1, excursiones=False):
    s = SensorSimulado(sensor, random.Random(semilla))
    return [s.siguiente(dt, excursiones) for _ in range(pasos)]


def test_distancia_al_aviso():
    assert PRESIONADOR.distancia_al_aviso == pytest.approx(2.0)     # el aviso más cercano (157 − 155)
    assert SOLO_ALTO.distancia_al_aviso == pytest.approx(4.6)
    assert SIN_UMBRALES.distancia_al_aviso == pytest.approx(5.0)    # 5 % del rango físico


def test_los_valores_siguen_dentro_del_rango_fisico():
    valores = simular(Sensor(9, "NT-904", 0.0, 0, 10000, None, None, 1.0, 5.0), 5000)
    assert all(0 <= v <= 10000 for v in valores)


def test_sin_excursiones_se_mantiene_en_rango_normal():
    for sensor in (PRESIONADOR, SOLO_ALTO):
        valores = simular(sensor, 20000)
        fuera = [v for v in valores if v >= (sensor.aviso_alto or 1e9) or v <= (sensor.aviso_bajo or -1e9)]
        assert len(fuera) / len(valores) < 0.01, sensor.tag


def test_los_valores_giran_en_torno_al_valor_nominal():
    valores = simular(PRESIONADOR, 20000)
    media = sum(valores) / len(valores)
    assert abs(media - PRESIONADOR.valor_nominal) < PRESIONADOR.distancia_al_aviso * 0.5


def test_las_lecturas_tienen_ruido_y_no_son_constantes():
    valores = simular(PRESIONADOR, 100)
    assert len(set(valores)) > 90


def test_la_misma_semilla_da_la_misma_simulacion():
    assert simular(PRESIONADOR, 200, semilla=7) == simular(PRESIONADOR, 200, semilla=7)
    assert simular(PRESIONADOR, 200, semilla=7) != simular(PRESIONADOR, 200, semilla=8)


def test_una_excursion_sobrepasa_el_umbral_de_aviso(monkeypatch):
    monkeypatch.setattr(modelo, "EXCURSION_CADA_HORAS", 0.05)       # muy frecuentes, para la prueba
    valores = simular(PRESIONADOR, 3000, excursiones=True)
    assert max(valores) > PRESIONADOR.aviso_alto or min(valores) < PRESIONADOR.aviso_bajo


def test_sin_umbrales_no_hay_excursiones(monkeypatch):
    monkeypatch.setattr(modelo, "EXCURSION_CADA_HORAS", 0.05)
    valores = simular(SIN_UMBRALES, 2000, excursiones=True)
    assert max(valores) - min(valores) < 40


def test_las_excursiones_terminan(monkeypatch):
    monkeypatch.setattr(modelo, "EXCURSION_CADA_HORAS", 1e9)         # prácticamente nunca empiezan solas
    s = SensorSimulado(PRESIONADOR, random.Random(3))
    s._empezar_excursion()
    for _ in range(200):                                              # 200 × 5 s > 600 s de excursión
        s.siguiente(5.0, True)
    assert s._excursion is None


def test_generar_devuelve_una_lectura_por_sensor():
    ahora = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
    simulados = [SensorSimulado(s, random.Random(1)) for s in (PRESIONADOR, SOLO_ALTO)]
    lecturas = generar(simulados, ahora, 5.0)
    assert [(l.tag, l.instante) for l in lecturas] == [("PT-102", ahora), ("VT-302", ahora)]


class DestinoEnMemoria:
    def __init__(self):
        self.lecturas = []

    def enviar(self, lecturas):
        self.lecturas.extend(lecturas)

    def cerrar(self):
        pass


def test_ejecutar_hace_los_ciclos_pedidos_y_duerme_entre_ellos():
    destino, pausas = DestinoEnMemoria(), []
    hechos = ejecutar(destino, [PRESIONADOR, SOLO_ALTO], 5.0, 3, semilla=1, dormir=pausas.append)
    assert hechos == 3 and len(destino.lecturas) == 6
    assert pausas == [5.0, 5.0]                                       # no duerme después del último ciclo


def test_ejecutar_se_para_con_ctrl_c():
    def interrumpir(_):
        raise KeyboardInterrupt
    assert ejecutar(DestinoEnMemoria(), [PRESIONADOR], 5.0, None, None, dormir=interrumpir) == 1


# ── Contra la base de datos real ──
def test_el_simulador_guarda_lecturas_de_los_36_sensores(conexion):
    destino = DestinoBaseDeDatos(config.RUTA_BD)
    try:
        sensores = destino.sensores()
        assert len(sensores) == 36
        reloj = iter(datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc) + timedelta(seconds=5 * i) for i in range(3))
        ejecutar(destino, sensores, 5.0, 3, semilla=42, dormir=lambda _: None, reloj=lambda: next(reloj))
    finally:
        destino.cerrar()
    fila = conexion.execute("SELECT count(*) AS n, count(DISTINCT sensor_id) AS sensores,"
                            " count(DISTINCT instante) AS instantes FROM lectura").fetchone()
    assert (fila["n"], fila["sensores"], fila["instantes"]) == (108, 36, 3)


def test_las_lecturas_guardadas_estan_en_su_rango_fisico(conexion):
    destino = DestinoBaseDeDatos(config.RUTA_BD)
    try:
        inicio = datetime(2026, 11, 1, tzinfo=timezone.utc)
        contador = iter(inicio + timedelta(seconds=i) for i in range(50))
        ejecutar(destino, destino.sensores(), 5.0, 50, semilla=5, dormir=lambda _: None,
                 reloj=lambda: next(contador))
    finally:
        destino.cerrar()
    fuera = conexion.execute("SELECT count(*) AS n FROM lectura l JOIN sensor s ON s.id = l.sensor_id"
                             " WHERE l.valor < s.min_fisico OR l.valor > s.max_fisico").fetchone()["n"]
    assert fuera == 0


def test_repetir_un_instante_no_duplica_lecturas(conexion):
    destino = DestinoBaseDeDatos(config.RUTA_BD)
    try:
        fijo = datetime(2026, 11, 1, tzinfo=timezone.utc)
        ejecutar(destino, destino.sensores(), 5.0, 2, semilla=1, dormir=lambda _: None, reloj=lambda: fijo)
    finally:
        destino.cerrar()
    assert conexion.execute("SELECT count(*) AS n FROM lectura").fetchone()["n"] == 36
