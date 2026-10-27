"""Genera las actas del Sprint 1 en PDF con la plantilla de actas de AUREA AUDIT.

    python3 scripts/actas_pdf.py <carpeta_salida>

Deja en blanco lo que solo saben los asistentes (horas, lugar, quién redacta, asistentes y firmas).
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QMarginsF, QSizeF, QUrl
from PySide6.QtGui import QGuiApplication, QPageLayout, QPageSize, QPdfWriter, QTextDocument

LOGO = Path(__file__).resolve().parent.parent / "cliente" / "recursos" / "aurea_logo.png"
BLANCO = "&nbsp;" * 40

CSS = """
body { font-family: 'Noto Sans'; font-size: 10pt; color: #1F2933; }
h1 { font-size: 15pt; color: #0B2D5B; margin: 0; }
h2 { font-size: 11pt; color: #0B2D5B; margin-top: 14px; margin-bottom: 4px; }
p, li { margin-top: 2px; margin-bottom: 2px; }
td, th { padding: 4px; }
th { background-color: #E6EBF2; text-align: left; }
.suave { color: #616E7C; }
"""


def campos(filas):
    celdas = "".join(f"<tr><td width='28%'><b>{k}</b></td><td>{v}</td></tr>" for k, v in filas)
    return f"<table width='100%' border='1' cellspacing='0' style='border-color:#CBD2D9'>{celdas}</table>"


def tareas(filas):
    cab = "<tr><th>Nº</th><th>Tarea</th><th>Responsable</th><th>Fecha límite</th><th>Estado</th></tr>"
    cuerpo = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in f) + "</tr>" for f in filas)
    return f"<table width='100%' border='1' cellspacing='0' style='border-color:#CBD2D9'>{cab}{cuerpo}</table>"


def lista(items, numerada=True):
    marca = "ol" if numerada else "ul"
    return f"<{marca}>" + "".join(f"<li>{i}</li>" for i in items) + f"</{marca}>"


def tabla_firmas():
    nombres = ["Sergio García", "Gonzalo Revuelta", "Juan José Ibáñez", "Itzel Fajardo"]
    celdas = "".join(f"<td width='25%' height='60' valign='bottom' align='center'><br><br><br><br>{n}</td>" for n in nombres)
    return f"<table width='100%' border='1' cellspacing='0' style='border-color:#CBD2D9'><tr>{celdas}</tr></table>"


TAREAS = [
    ("T01", "Repositorio, ramas y tablero Kanban", "Itzel", "24/10"),
    ("T02", "Esqueleto MVC del cliente y del servidor", "Sergio", "28/10"),
    ("T03", "Base de datos y migraciones (9 áreas, 36 sensores)", "Gonzalo", "28/10"),
    ("T09", "Análisis de amenazas y tabla de permisos", "Itzel", "29/10"),
    ("T06", "Simulador de sensores v1", "Gonzalo", "01/11"),
    ("T07", "Ventana base con la identidad de AUREA AUDIT", "Juan José", "30/10"),
    ("T04", "Login con Argon2id y sesión", "Sergio", "31/10"),
    ("T05", "Registro con cuenta pendiente", "Sergio", "01/11"),
    ("T08", "Ventanas de login y registro", "Juan José", "01/11"),
    ("T10", "Pruebas de login y registro", "Itzel", "01/11"),
]

ASISTENTES = ("[&nbsp;&nbsp;] Sergio García (Product Owner) &nbsp; [&nbsp;&nbsp;] Gonzalo Revuelta &nbsp; "
              "[&nbsp;&nbsp;] Juan José Ibáñez &nbsp; [&nbsp;&nbsp;] Itzel Fajardo (Scrum Master)<br>Otros: ____________")


def acta(numero, titulo, tipo, fecha, orden, desarrollo, hallazgos, acuerdos, estado, proxima, observaciones):
    html = f"""<html><head><style>{CSS}</style></head><body>
<table width='100%'><tr><td width='22%'><img src='{QUrl.fromLocalFile(str(LOGO)).toString()}' width='110'></td>
<td valign='middle'><span class='suave'>AUREA AUDIT · Auditoría tecnológica<br>Proyecto de Ingeniería I · Curso 2026-2027</span>
<h1>ACTA Nº {numero} · REUNIÓN DE AUREA AUDIT</h1><b>{titulo}</b></td></tr></table>
<br>
{campos([("Fecha", fecha), ("Hora de inicio", "____ : ____"), ("Hora de finalización", "____ : ____"),
         ("Lugar / modalidad", "______________________________"), ("Redacta el acta", "______________________________"),
         ("Tipo de reunión", tipo), ("Asistentes", ASISTENTES)])}
<h2>Orden del día</h2>{lista(orden)}
<h2>Desarrollo y puntos tratados</h2>{desarrollo}
<h2>Hallazgos / cuestiones técnicas</h2>{lista(hallazgos, False)}
<h2>Acuerdos adoptados</h2>{lista(acuerdos)}
<h2>Tareas y responsables</h2>{tareas([(i, t, r, f, estado) for i, t, r, f in TAREAS])}
<h2>Próxima reunión</h2><p>{proxima}</p>
<h2>Observaciones</h2><p>{observaciones}</p>
<h2>Conformidad de los participantes</h2>
<p>Con la firma o aprobación de esta acta, los participantes manifiestan que su contenido refleja los asuntos tratados y los acuerdos alcanzados.</p>
{tabla_firmas()}
</body></html>"""
    return html


ACTA_02 = dict(
    numero="02", titulo="Planificación del Sprint 1", tipo="Proyecto (planificación de sprint)", fecha="20 / 10 / 2026",
    orden=["Objetivo y capacidad del Sprint 1.", "Reparto de las tareas T01 a T10.",
           "Orden de integración y criterios de «hecho».", "Herramientas y entregables del sprint."],
    desarrollo="""
<p><b>1. Objetivo y capacidad.</b> Dejar construida la base funcional: proyecto organizado, base de datos, login y registro,
simulador de sensores y ventana base con la marca de AUREA AUDIT. Capacidad de 120 horas: 30 por persona (26 de tareas y 4 de Scrum y actas).</p>
<p><b>2. Reparto.</b> Itzel: repositorio, análisis de amenazas y pruebas. Sergio: arquitectura MVC, login y registro.
Gonzalo: base de datos y simulador. Juan José: ventana base, login y registro (ventanas).</p>
<p><b>3. Integración.</b> Repositorio y Kanban, esqueleto MVC, base de datos, ventana base, login contra la base de datos,
conexión de la ventana de login, registro y simulador, pruebas. Una tarea está hecha cuando otra persona ha revisado el código,
las pruebas pasan, la ventana es igual que el mockup con nombre y rol visibles, y queda anotada en el acta.</p>
<p><b>4. Herramientas y entregables.</b> Python con PySide6 (cliente), FastAPI (servidor) y SQLite (base de datos), todo en una aplicación local que se entrega como un único .exe de Windows.
Código en GitHub (ramas main y develop), tablero Kanban, actas en PDF, autoevaluación por pares, enlace al repositorio,
copia en .zip y documentación actualizada.</p>""",
    hallazgos=["El PDF del calendario sale con las casillas mezcladas; hay que confirmar las fechas de entrega en el Campus Virtual.",
               "El formulario de registro del mockup lista los supervisores antes de iniciar sesión; valorar si es un riesgo."],
    acuerdos=["Aprobar el reparto de tareas y las 120 horas del Sprint 1.",
              "Trabajar en la rama develop y fusionar en main solo tras la revisión de otra persona.",
              "Usar el logotipo oficial de AUREA AUDIT y la paleta aprobada en el acta nº 01 en todas las ventanas.",
              "Registrar las tareas en el tablero Kanban y anotar los cambios de estado."],
    estado="Por hacer",
    proxima="Fecha prevista: 30 / 10 / 2026. Objetivo principal: revisión y retrospectiva del Sprint 1.",
    observaciones="______________________________________________",
)

ACTA_03 = dict(
    numero="03", titulo="Revisión y retrospectiva del Sprint 1", tipo="Proyecto (revisión y retrospectiva de sprint)",
    fecha="30 / 10 / 2026",
    orden=["Revisión de lo construido en el Sprint 1.", "Estado del tablero Kanban.", "Retrospectiva del equipo.",
           "Entregables del 1 de noviembre y preparación del Sprint 2."],
    desarrollo="""
<p><b>1. Revisión.</b> Las tareas T01 a T10 están terminadas: repositorio y ramas, esqueleto MVC, base de datos con migraciones
(9 áreas, 36 sensores, 18 cuentas de ejemplo), login con Argon2id y sesión, registro pendiente, simulador, ventana base,
ventanas de login y registro, análisis de amenazas y pruebas (144 pruebas pasan, cobertura del 92 %).</p>
<p><b>2. Tablero.</b> Las 10 tareas del Sprint 1 están en «Hecho» y las del Sprint 2 en «Por hacer». Se guarda una captura
del tablero con la fecha del día como prueba del cierre.</p>
<p><b>3. Retrospectiva.</b><br>Qué ha ido bien: ______________________________<br>Qué hay que mejorar: ______________________________<br>
Qué probamos en el Sprint 2: ______________________________</p>
<p><b>4. Entregas.</b> Actas en PDF, capturas del Kanban (inicio y fin), enlace al repositorio con main actualizada, copia en .zip,
documentación actualizada y autoevaluación de cada persona.</p>""",
    hallazgos=["GitHub no permite proteger main en un repositorio privado de cuenta gratuita: se sustituye por la norma de que nada entra en main sin revisión de otra persona.",
               "La unión de develop a main (PR #21) necesita la revisión de otra persona antes de hacerse."],
    acuerdos=["Hacer la revisión cruzada del código y unir develop a main antes del 1 de noviembre.",
              "Cada persona rellena y sube su autoevaluación antes de la entrega.",
              "Empezar el Sprint 2 el 2 de noviembre con la reunión de planificación."],
    estado="Hecho",
    proxima="Fecha prevista: 02 / 11 / 2026. Objetivo principal: planificación del Sprint 2.",
    observaciones="______________________________________________",
)


def escribir(html: str, salida: Path, titulo: str) -> None:
    pdf = QPdfWriter(str(salida))
    pdf.setResolution(96)
    pdf.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    pdf.setPageMargins(QMarginsF(18, 16, 18, 16), QPageLayout.Unit.Millimeter)
    pdf.setTitle(titulo)
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    doc.setHtml(html)
    doc.setPageSize(QSizeF(pdf.width(), pdf.height()))
    doc.print_(pdf)


if __name__ == "__main__":
    QGuiApplication([])
    carpeta = Path(sys.argv[1])
    carpeta.mkdir(parents=True, exist_ok=True)
    escribir(acta(**ACTA_02), carpeta / "Acta_02_Planificacion_Sprint_1.pdf", "Acta nº 02 - Planificación del Sprint 1")
    escribir(acta(**ACTA_03), carpeta / "Acta_03_Revision_y_retrospectiva_Sprint_1.pdf", "Acta nº 03 - Revisión y retrospectiva del Sprint 1")
