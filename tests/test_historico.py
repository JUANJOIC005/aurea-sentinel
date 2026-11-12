"""T12 · Carga de 30 días de histórico y datos de demostración."""
from datetime import datetime, timezone

from servidor import datos_demo, descubrimiento, historico, local

FIN = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def valores(conexion):
    return [tuple(f.values()) for f in conexion.execute("SELECT sensor_id, instante, valor FROM lectura ORDER BY 1, 2")]


def test_30_dias_de_lecturas_de_los_36_sensores(conexion):
    resultado = historico.cargar(conexion, dias=30, hasta=FIN)
    pasos = 30 * 288 + 1                                           # una cada 5 minutos
    assert resultado["sensores"] == 36 and resultado["lecturas"] == 36 * pasos
    fila = conexion.execute("SELECT count(*) AS n, count(DISTINCT sensor_id) AS s, min(instante) AS desde,"
                            " max(instante) AS hasta FROM lectura").fetchone()
    assert (fila["n"], fila["s"]) == (36 * pasos, 36)
    assert (fila["desde"], fila["hasta"]) == ("2026-10-11 12:00:00", "2026-11-10 12:00:00")


def test_todas_las_lecturas_estan_dentro_del_rango_fisico(conexion):
    historico.cargar(conexion, dias=2, hasta=FIN)
    fuera = conexion.execute("SELECT count(*) AS n FROM lectura l JOIN sensor s ON s.id = l.sensor_id"
                             " WHERE l.valor < s.min_fisico OR l.valor > s.max_fisico").fetchone()["n"]
    assert fuera == 0


def test_los_valores_son_realistas_en_torno_al_nominal(conexion):
    historico.cargar(conexion, dias=5, hasta=FIN)
    filas = conexion.execute(
        "SELECT s.tag, avg(l.valor) AS media, s.valor_nominal AS nominal,"
        "       s.aviso_alto - s.valor_nominal AS margen_alto"
        "  FROM lectura l JOIN sensor s ON s.id = l.sensor_id WHERE s.aviso_alto IS NOT NULL GROUP BY s.id").fetchall()
    assert filas
    for f in filas:
        assert abs(f["media"] - f["nominal"]) < f["margen_alto"], f["tag"]


def test_el_historico_es_siempre_el_mismo_con_la_misma_semilla(conexion):
    historico.cargar(conexion, dias=1, hasta=FIN)
    primero = valores(conexion)
    conexion.execute("DELETE FROM alarma")
    conexion.execute("DELETE FROM lectura")
    historico.cargar(conexion, dias=1, hasta=FIN)
    assert valores(conexion) == primero
    conexion.execute("DELETE FROM lectura")
    historico.cargar(conexion, dias=1, hasta=FIN, semilla=7)
    assert valores(conexion) != primero


def test_el_historico_incluye_alarmas_y_las_cerradas_tienen_fecha_de_cierre(conexion):
    historico.cargar(conexion, dias=30, hasta=FIN)
    total = conexion.execute("SELECT count(*) AS n FROM alarma").fetchone()["n"]
    assert total > 0
    mal = conexion.execute("SELECT count(*) AS n FROM alarma WHERE (estado = 'cerrada') != (cerrada_en IS NOT NULL)"
                           "  OR (cerrada_en IS NOT NULL AND cerrada_en < abierta_en)").fetchone()["n"]
    assert mal == 0


def test_hay_lecturas(conexion):
    assert historico.hay_lecturas(conexion) is False
    historico.cargar(conexion, dias=1, hasta=FIN)
    assert historico.hay_lecturas(conexion) is True


def test_la_primera_vez_la_aplicacion_carga_30_dias_de_historico(conexion, monkeypatch):
    monkeypatch.delenv("AUREA_SIN_HISTORICO")
    conexion.execute("DELETE FROM usuario")
    conexion.commit()
    assert local.preparar_base_de_datos() is True
    assert conexion.execute("SELECT count(*) AS n FROM lectura").fetchone()["n"] > 36 * 8000
    assert conexion.execute("SELECT count(*) AS n FROM usuario").fetchone()["n"] == len(datos_demo.PERSONAS)
    n = conexion.execute("SELECT count(*) AS n FROM lectura").fetchone()["n"]
    assert local.preparar_base_de_datos() is False                 # la segunda vez no vuelve a cargar nada
    assert conexion.execute("SELECT count(*) AS n FROM lectura").fetchone()["n"] == n


def test_el_servidor_local_anota_su_direccion_mientras_esta_abierto():
    servidor = local.iniciar()
    try:
        assert descubrimiento.leer() == servidor.url
    finally:
        servidor.parar()
    assert descubrimiento.leer() is None


def test_la_direccion_anotada_rota_se_ignora():
    descubrimiento.publicar("http://127.0.0.1:1")
    (descubrimiento._ruta()).write_text("no es json", encoding="utf-8")
    assert descubrimiento.leer() is None
    descubrimiento.retirar()
    descubrimiento.retirar()                                       # borrar dos veces no da error


def test_los_usuarios_y_vinculos_de_demostracion_cumplen_el_enunciado(conexion):
    datos_demo.crear_cuentas(conexion, "Valdecierzo-2026!")
    por_rol = {f["codigo"]: f["n"] for f in conexion.execute(
        "SELECT r.codigo, count(*) AS n FROM usuario u JOIN rol r ON r.id = u.rol_id GROUP BY 1")}
    assert por_rol["supervisor"] >= 9 and por_rol["tecnico"] >= 4
    con_varios = conexion.execute("SELECT count(*) AS n FROM (SELECT supervisor_id FROM usuario"
                                  " WHERE supervisor_id IS NOT NULL GROUP BY supervisor_id HAVING count(*) > 1)").fetchone()
    assert con_varios["n"] >= 2
