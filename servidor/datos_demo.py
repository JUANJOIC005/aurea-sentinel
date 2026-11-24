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
    asignar_sensores(conn)
    return creadas


def asignar_sensores(conn) -> int:
    """Reparte los sensores de cada área entre los técnicos de su supervisor (el técnico ve «sus sensores»).
    Con un solo técnico se queda con los cuatro; con dos, dos cada uno. Se puede repetir sin duplicar nada."""
    nuevas = 0
    for sup in conn.execute("SELECT u.id, u.area_id FROM usuario u JOIN rol r ON r.id = u.rol_id"
                            " WHERE r.codigo = 'supervisor'").fetchall():
        tecnicos = conn.execute("SELECT id FROM usuario WHERE supervisor_id = ? ORDER BY id", (sup["id"],)).fetchall()
        sensores = conn.execute("SELECT id FROM sensor WHERE area_id = ? ORDER BY id", (sup["area_id"],)).fetchall()
        for i, sensor in enumerate(sensores):
            if not tecnicos:
                break
            tecnico = tecnicos[i % len(tecnicos)]
            nuevas += conn.execute(
                "INSERT OR IGNORE INTO asignacion_sensor (tecnico_id, sensor_id, asignado_por) VALUES (?, ?, ?)",
                (tecnico["id"], sensor["id"], sup["id"])).rowcount
    return nuevas


# Tareas de ejemplo para que el Supervisor y sus técnicos no empiecen con las ventanas vacías (T15).
# (título, prioridad, estado, días hasta la fecha límite; el sensor es el n-ésimo asignado al técnico)
TAREAS_DEMO = [
    ("Calibración mensual de {tag}", "media", "pendiente", 3, 0),
    ("Revisar la deriva de {tag} frente al sensor redundante", "alta", "en_curso", 1, 1),
    ("Ronda de verificación de {tag}", "baja", "hecha", 0, 0),
]


def sembrar_trabajo(conn) -> int:
    """Crea tareas de ejemplo para cada técnico (y una inspección en la que ya está hecha). Solo si no hay ninguna."""
    if conn.execute("SELECT 1 FROM tarea LIMIT 1").fetchone():
        return 0
    creadas = 0
    tecnicos = conn.execute("SELECT u.id, u.supervisor_id FROM usuario u JOIN rol r ON r.id = u.rol_id"
                            " WHERE r.codigo = 'tecnico' AND u.estado = 'activo' ORDER BY u.id").fetchall()
    for t in tecnicos:
        sensores = conn.execute("SELECT s.id, s.tag FROM asignacion_sensor x JOIN sensor s ON s.id = x.sensor_id"
                                " WHERE x.tecnico_id = ? ORDER BY s.id", (t["id"],)).fetchall()
        if not sensores:
            continue
        for titulo, prioridad, estado, dias, n in TAREAS_DEMO:
            sensor = sensores[n % len(sensores)]
            fila = conn.execute(
                "INSERT INTO tarea (titulo, creada_por, asignada_a, sensor_id, prioridad, estado, fecha_limite,"
                " cerrada_en) VALUES (?, ?, ?, ?, ?, ?, date('now', ?), CASE WHEN ? = 'hecha' THEN datetime('now')"
                " END) RETURNING id",
                (titulo.format(tag=sensor["tag"]), t["supervisor_id"], t["id"], sensor["id"], prioridad, estado,
                 f"+{dias} days", estado)).fetchone()
            if estado == "hecha":
                conn.execute("INSERT INTO incidencia (tecnico_id, tarea_id, sensor_id, tipo, observaciones)"
                             " VALUES (?, ?, ?, 'inspeccion', 'Sin anomalías visibles.')",
                             (t["id"], fila["id"], sensor["id"]))
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
