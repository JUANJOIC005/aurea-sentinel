"""Carga de 30 días de histórico: una lectura cada 5 minutos de los 36 sensores, con sus alarmas.

    python -m servidor.historico               # carga 30 días si la base de datos no tiene lecturas
    python -m servidor.historico --reemplazar  # borra las lecturas y las alarmas y las vuelve a generar

Usa el mismo modelo que el simulador (valor nominal, deriva lenta, ruido y alguna excursión), con una semilla
fija: el histórico es siempre el mismo, así que las pruebas y las capturas se pueden repetir. Las usuarias y
usuarios (con los vínculos Supervisor → Técnico) los crea `datos_demo`, que ya cumple lo que pide el enunciado.
"""
import argparse
import random
from datetime import datetime, timedelta, timezone

from simulador.modelo import Sensor, SensorSimulado

from . import db, estados, ingesta, migrate

PASO_S = 300          # una lectura cada 5 minutos
SEMILLA = 2026


def hay_lecturas(conn) -> bool:
    return conn.execute("SELECT 1 FROM lectura LIMIT 1").fetchone() is not None


def cargar(conn, dias: int = 30, hasta: datetime | None = None, semilla: int = SEMILLA) -> dict:
    """Genera `dias` días de lecturas que terminan en `hasta` (ahora, por defecto) y las guarda."""
    hasta = (hasta or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(second=0, microsecond=0)
    hasta -= timedelta(minutes=hasta.minute % (PASO_S // 60))
    pasos = dias * 86400 // PASO_S
    inicio = hasta - timedelta(seconds=pasos * PASO_S)
    instantes = [(inicio + timedelta(seconds=i * PASO_S)).strftime(ingesta.FORMATO) for i in range(pasos + 1)]

    sensores = conn.execute(
        "SELECT id, tag, valor_nominal, min_fisico, max_fisico, aviso_bajo, alarma_bajo, aviso_alto, alarma_alto"
        "  FROM sensor WHERE activo ORDER BY id").fetchall()
    total, alarmas = 0, 0
    for s in sensores:
        simulado = SensorSimulado(
            Sensor(s["id"], s["tag"], s["valor_nominal"], s["min_fisico"], s["max_fisico"],
                   s["aviso_bajo"], s["alarma_bajo"], s["aviso_alto"], s["alarma_alto"]),
            random.Random(f"{semilla}-{s['tag']}"))
        filas, abierta = [], None          # abierta = [nivel, instante de apertura, valor]
        for instante in instantes:
            valor = simulado.siguiente(float(PASO_S))
            filas.append((s["id"], instante, valor))
            actual = estados.estado(valor, s["aviso_bajo"], s["alarma_bajo"], s["aviso_alto"], s["alarma_alto"])
            accion = ingesta.transicion(abierta[0] if abierta else None, actual)
            if accion == "abrir":
                abierta = [actual, instante, valor]
            elif accion == "escalar":
                abierta[0], abierta[2] = actual, valor
            elif accion == "cerrar":
                conn.execute("INSERT INTO alarma (sensor_id, nivel, valor, abierta_en, estado, cerrada_en)"
                             " VALUES (?, ?, ?, ?, 'cerrada', ?)", (s["id"], abierta[0], abierta[2], abierta[1], instante))
                alarmas += 1
                abierta = None
        if abierta:                         # sigue abierta en el último instante
            conn.execute("INSERT INTO alarma (sensor_id, nivel, valor, abierta_en) VALUES (?, ?, ?, ?)",
                         (s["id"], abierta[0], abierta[2], abierta[1]))
            alarmas += 1
        conn.executemany("INSERT INTO lectura (sensor_id, instante, valor) VALUES (?, ?, ?)"
                         " ON CONFLICT (sensor_id, instante) DO NOTHING", filas)
        total += len(filas)
    return {"sensores": len(sensores), "lecturas": total, "alarmas": alarmas, "desde": instantes[0],
            "hasta": instantes[-1]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga de histórico de AUREA Sentinel")
    parser.add_argument("--dias", type=int, default=30, help="días de histórico (30)")
    parser.add_argument("--reemplazar", action="store_true", help="borra las lecturas y alarmas existentes")
    args = parser.parse_args()
    migrate.preparar()
    with db.conexion() as conn:
        if args.reemplazar:
            conn.execute("DELETE FROM alarma")
            conn.execute("DELETE FROM lectura")
        elif hay_lecturas(conn):
            print("La base de datos ya tiene lecturas. Usa --reemplazar para generarlas de nuevo.")
            return
        resultado = cargar(conn, args.dias)
    print(f"Cargadas {resultado['lecturas']} lecturas de {resultado['sensores']} sensores "
          f"({resultado['desde']} → {resultado['hasta']} UTC) y {resultado['alarmas']} alarmas.")


if __name__ == "__main__":
    main()
