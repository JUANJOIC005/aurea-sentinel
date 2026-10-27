"""Migraciones: aplica en orden los .sql de servidor/migrations que aún no estén aplicados.

    python -m servidor.migrate               # aplica las pendientes
    python -m servidor.migrate --desde-cero  # borra el archivo de la base de datos y la vuelve a crear
"""
import argparse
import sys
from pathlib import Path

from . import config, db

# Con la aplicación empaquetada (PyInstaller) los archivos viven junto al ejecutable.
CARPETA = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "servidor" / "migrations"


def desde_cero() -> None:
    """Borra la base de datos (el archivo y sus auxiliares). Solo para desarrollo y pruebas."""
    for sufijo in ("", "-wal", "-shm"):
        Path(str(config.RUTA_BD) + sufijo).unlink(missing_ok=True)


def aplicar(conn) -> list[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " nombre TEXT PRIMARY KEY, aplicada_en TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    hechas = {f["nombre"] for f in conn.execute("SELECT nombre FROM schema_migrations")}
    nuevas = []
    for fichero in sorted(CARPETA.glob("*.sql")):
        if fichero.name in hechas:
            continue
        # executescript confirma lo anterior y ejecuta el archivo entero; el registro va después
        conn.executescript(fichero.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (nombre) VALUES (?)", (fichero.name,))
        conn.commit()
        nuevas.append(fichero.name)
    return nuevas


def preparar() -> list[str]:
    """Crea o actualiza la base de datos. Es lo primero que hace la aplicación al arrancar."""
    with db.conexion() as conn:
        return aplicar(conn)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migraciones de AUREA Sentinel")
    parser.add_argument("--desde-cero", action="store_true", help="borra la base y la recrea")
    args = parser.parse_args()
    if args.desde_cero:
        desde_cero()
    nuevas = preparar()
    print("Base de datos:", config.RUTA_BD)
    print("Migraciones aplicadas:", ", ".join(nuevas) if nuevas else "ninguna (ya estaba al día)")


if __name__ == "__main__":
    main()
