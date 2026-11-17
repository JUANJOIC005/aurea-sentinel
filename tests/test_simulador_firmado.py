"""T12 · El simulador envía las lecturas firmadas al servidor."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from servidor import claves, config, descubrimiento
from servidor.api.main import app
from simulador import __main__ as simulador
from simulador.destinos import DestinoApi, ErrorDestino
from simulador.modelo import Lectura


def destino(clave=None, http=None):
    return DestinoApi(config.RUTA_BD, "http://testserver", clave or claves.clave_ingesta(),
                      http=http or TestClient(app))


def una_lectura(valor=325.6):
    return [Lectura(1, "TE-101", datetime.now(timezone.utc) - timedelta(seconds=2), valor)]


def test_el_simulador_envia_firmado_y_el_servidor_guarda(conexion):
    d = destino()
    try:
        sensores = d.sensores()
        reloj = iter(datetime.now(timezone.utc) - timedelta(seconds=10 - 5 * i) for i in range(3))
        hechos = simulador.ejecutar(d, sensores, 5.0, 3, semilla=1, dormir=lambda _: None, reloj=lambda: next(reloj))
    finally:
        d.cerrar()
    assert hechos == 3
    assert conexion.execute("SELECT count(*) AS n FROM lectura").fetchone()["n"] == 108


def test_con_otra_clave_el_servidor_rechaza_y_no_se_guarda_nada(conexion):
    d = destino(clave=b"clave-equivocada")
    try:
        with pytest.raises(ErrorDestino, match="401"):
            d.enviar(una_lectura())
    finally:
        d.cerrar()
    assert conexion.execute("SELECT count(*) AS n FROM lectura").fetchone()["n"] == 0


def test_si_el_simulador_inventa_un_valor_imposible_el_servidor_lo_rechaza(conexion):
    d = destino()
    try:
        with pytest.raises(ErrorDestino, match="422"):
            d.enviar(una_lectura(valor=1000.0))        # TE-101 llega como máximo a 400 °C
    finally:
        d.cerrar()
    assert conexion.execute("SELECT count(*) AS n FROM lectura").fetchone()["n"] == 0


def test_el_cuerpo_lleva_fechas_en_utc():
    d = destino()
    try:
        cuerpo = d.cuerpo([Lectura(1, "TE-101", datetime(2026, 11, 2, 12, 0, 5, tzinfo=timezone.utc), 1.5)])
    finally:
        d.cerrar()
    assert cuerpo == b'{"lecturas":[{"tag":"TE-101","instante":"2026-11-02T12:00:05Z","valor":1.5}]}'


class DestinoQueFalla:
    def __init__(self, fallos):
        self.fallos, self.enviadas = fallos, 0

    def enviar(self, lecturas):
        if self.fallos:
            self.fallos -= 1
            raise ErrorDestino("servidor cerrado")
        self.enviadas += 1


def test_un_fallo_suelto_no_para_el_simulador():
    destino_roto = DestinoQueFalla(fallos=1)
    hechos = simulador.ejecutar(destino_roto, [], 5.0, 3, semilla=1, dormir=lambda _: None)
    assert hechos == 3 and destino_roto.enviadas == 2


def test_tras_cinco_fallos_seguidos_se_rinde():
    with pytest.raises(ErrorDestino):
        simulador.ejecutar(DestinoQueFalla(fallos=99), [], 5.0, None, semilla=1, dormir=lambda _: None)


def test_sin_aplicacion_abierta_el_simulador_lo_dice(monkeypatch):
    monkeypatch.delenv("AUREA_API_URL", raising=False)
    descubrimiento.retirar()
    with pytest.raises(ErrorDestino, match="ninguna aplicación"):
        simulador.buscar_servidor(None)


def test_si_la_direccion_anotada_no_responde_el_simulador_lo_dice(monkeypatch):
    monkeypatch.delenv("AUREA_API_URL", raising=False)
    with pytest.raises(ErrorDestino, match="no responde"):
        simulador.buscar_servidor("http://127.0.0.1:9")


def test_el_simulador_encuentra_la_aplicacion_abierta(monkeypatch):
    from servidor import local
    monkeypatch.delenv("AUREA_API_URL", raising=False)
    servidor = local.iniciar()
    try:
        assert simulador.buscar_servidor(None) == servidor.url
    finally:
        servidor.parar()


def test_la_linea_de_comandos_manda_lecturas_firmadas_a_la_aplicacion(conexion, monkeypatch):
    from servidor import local
    monkeypatch.delenv("AUREA_API_URL", raising=False)
    servidor = local.iniciar()
    try:
        monkeypatch.setattr("sys.argv", ["simulador", "--ciclos", "2", "--intervalo", "0.01", "--semilla", "3"])
        simulador.main()
    finally:
        servidor.parar()
    assert conexion.execute("SELECT count(*) AS n FROM lectura").fetchone()["n"] > 0


def test_la_linea_de_comandos_sin_aplicacion_termina_con_error(monkeypatch, capsys):
    monkeypatch.delenv("AUREA_API_URL", raising=False)
    descubrimiento.retirar()
    monkeypatch.setattr("sys.argv", ["simulador", "--ciclos", "1"])
    with pytest.raises(SystemExit) as salida:
        simulador.main()
    assert salida.value.code == 1
    assert "--destino bd" in capsys.readouterr().err


def test_con_destino_bd_no_hace_falta_la_aplicacion(conexion, monkeypatch):
    descubrimiento.retirar()
    monkeypatch.setattr("sys.argv", ["simulador", "--destino", "bd", "--ciclos", "1"])
    simulador.main()
    assert conexion.execute("SELECT count(*) AS n FROM lectura").fetchone()["n"] == 36
