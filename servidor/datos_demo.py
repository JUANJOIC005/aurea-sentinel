"""Cuentas de demostración de la central ficticia (9 supervisores, 6 técnicos, 2 auditores, 1 administrador).

    ./run.sh demo

La contraseña se toma de AUREA_DEMO_PASSWORD; si no está definida se usa PASSWORD_DEMO (solo para la demostración:
una instalación real no debe sembrar cuentas con una contraseña conocida).
Es seguro repetirlo: las cuentas que ya existen no se tocan.
"""
import os
import unicodedata

from . import db, migrate, seguridad

DOMINIO = "cn-valdecierzo.es"
PASSWORD_DEMO = "Valdecierzo-2026!"


def password_demo() -> str:
    return os.environ.get("AUREA_DEMO_PASSWORD") or PASSWORD_DEMO

# (nombre, rol, área, correo del supervisor si es técnico)
PERSONAS = [
    ("Laura Méndez Ortiz", "supervisor", "A1", None),
    ("Javier Ruiz Pastor", "supervisor", "A2", None),
    ("Marta Soler Vidal", "supervisor", "A3", None),
    ("Andrés Molina Gil", "supervisor", "A4", None),
    ("Elena Castro Ramos", "supervisor", "A5", None),
    ("Pablo Navarro León", "supervisor", "A6", None),
    ("Lucía Herrera Campos", "supervisor", "A7", None),
    ("Raúl Ortega Fuentes", "supervisor", "A8", None),
    ("Sara Iglesias Prieto", "supervisor", "A9", None),
    ("Diego Paredes Luna", "tecnico", None, "Laura Méndez Ortiz"),
    ("Nuria Vega Santos", "tecnico", None, "Laura Méndez Ortiz"),
    ("Iván Cano Rubio", "tecnico", None, "Javier Ruiz Pastor"),
    ("Carmen Lozano Díaz", "tecnico", None, "Javier Ruiz Pastor"),
    ("Óscar Medina Torres", "tecnico", None, "Marta Soler Vidal"),
    ("Mario Serrano Blanco", "tecnico", None, "Lucía Herrera Campos"),
    ("Beatriz Lara Quintana", "auditor", None, None),
    ("Rubén Ortiz Calvo", "auditor", None, None),
    ("Álvaro Campos Ibarra", "administrador", None, None),
]


def correo_de(nombre: str) -> str:
    """'Laura Méndez Ortiz' → 'laura.mendez@cn-valdecierzo.es'"""
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    nombre_pila, primer_apellido = sin_tildes.lower().split()[:2]
    return f"{nombre_pila}.{primer_apellido}@{DOMINIO}"


def crear_cuentas(conn, password: str) -> int:
    """Crea las cuentas que falten (ya activas). Devuelve cuántas ha creado."""
    hash_comun = seguridad.hashear(password)
    ids = {}
    creadas = 0
    for nombre, rol, area, supervisor in PERSONAS:  # los supervisores van antes que sus técnicos
        correo = correo_de(nombre)
        existente = conn.execute("SELECT id FROM usuario WHERE lower(correo) = ?", (correo,)).fetchone()
        if existente:
            ids[nombre] = existente["id"]
            continue
        fila = conn.execute(
            "INSERT INTO usuario (nombre, correo, password_hash, rol_id, area_id, supervisor_id, estado)"
            " VALUES (?, ?, ?, (SELECT id FROM rol WHERE codigo = ?),"
            "         (SELECT id FROM area WHERE codigo = ?), ?, 'activo') RETURNING id",
            (nombre, correo, hash_comun, rol, area, ids.get(supervisor)),
        ).fetchone()
        ids[nombre] = fila["id"]
        creadas += 1
    return creadas


def main() -> None:
    migrate.preparar()
    with db.conexion() as conn:
        creadas = crear_cuentas(conn, password_demo())
    print(f"Cuentas creadas: {creadas} de {len(PERSONAS)}.")
    print(f"Ejemplo de acceso: {correo_de(PERSONAS[0][0])} (Supervisor), {correo_de(PERSONAS[-1][0])} (Administrador)")


if __name__ == "__main__":
    main()
