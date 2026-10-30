import json
import os
import re
import subprocess
import sys
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen

REPO_PROPIETARIO, REPO_NOMBRE = "JUANJOIC005", "aurea-sentinel"
URL_TABLERO = "github.com/users/JUANJOIC005/projects/1"
COLUMNAS = ["Por hacer", "En curso", "En revisión", "Hecho"]

CONSULTA = """{ repository(owner:"%s", name:"%s"){ issues(first:50, orderBy:{field:CREATED_AT,direction:ASC}){ nodes{
  number title body milestone{title} labels(first:10){nodes{name}}
  timelineItems(first:50, itemTypes:[PROJECT_V2_ITEM_STATUS_CHANGED_EVENT]){ nodes{ ... on ProjectV2ItemStatusChangedEvent{createdAt status} } }
  projectItems(first:3){ nodes{ fieldValueByName(name:"Status"){ ... on ProjectV2ItemFieldSingleSelectValue{name} } } } } } } }"""

TINTA, GRIS, LINEA, FONDO = "#1F2933", "#616E7C", "#CBD2D9", "#F5F7FA"


def leer_tablero(en: str | None = None) -> dict:
    salida = subprocess.run(["gh", "api", "graphql", "-f", "query=" + CONSULTA % (REPO_PROPIETARIO, REPO_NOMBRE)],
                            capture_output=True, text=True, check=True).stdout
    tablero = {c: [] for c in COLUMNAS}
    for i in json.loads(salida)["data"]["repository"]["issues"]["nodes"]:
        if not (i["milestone"] or {}).get("title", "").startswith("Sprint 1"):
            continue
        items = i["projectItems"]["nodes"]
        if en:
            antes = [e for e in i["timelineItems"]["nodes"] if e["createdAt"] <= en]
            items = [{"fieldValueByName": {"name": antes[-1]["status"]}}] if antes else []
        estado = ((items[0]["fieldValueByName"] or {}).get("name") if items else None) or "Por hacer"
        etiquetas = [l["name"] for l in i["labels"]["nodes"]]
        responsable = next((e[6:] for e in etiquetas if e.startswith("resp: ")), "")
        prioridad = next((e for e in etiquetas if e in ("Imprescindible", "Importante", "Interesante")), "")
        horas = re.search(r"Horas estimadas:\*\*\s*(\d+)", i["body"] or "")
        codigo, _, titulo = i["title"].partition("] ")
        tablero[estado].append((codigo.lstrip("["), titulo, responsable, prioridad, int(horas.group(1)) if horas else 0))
    return tablero


def fuente(px: int, negrita: bool = False) -> QFont:
    f = QFont("Noto Sans")
    f.setPixelSize(px)
    f.setBold(negrita)
    return f


def dibujar(tablero: dict, etiqueta: str, salida: str, fecha: datetime | None = None) -> None:
    QGuiApplication([])
    ancho, margen, hueco = 1600, 40, 20
    alto_carta, paso = 70, 80
    alto = 150 + max(max(len(v) for v in tablero.values()), 1) * paso + 70
    img = QImage(ancho, alto, QImage.Format.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    p.setPen(QColor(TINTA))
    p.setFont(fuente(24, True))
    p.drawText(margen, 52, "AUREA Sentinel · Tablero Kanban")
    p.setPen(QColor(GRIS))
    p.setFont(fuente(14))
    p.drawText(margen, 80, f"Sprint 1 (19/10 – 01/11/2026) · {etiqueta} · {(fecha or datetime.now()):%d/%m/%Y %H:%M}")
    p.drawText(QRectF(0, 36, ancho - margen, 24), Qt.AlignmentFlag.AlignRight, URL_TABLERO)
    p.setPen(QPen(QColor(LINEA), 1))
    p.drawLine(margen, 100, ancho - margen, 100)

    ancho_col = (ancho - 2 * margen - 3 * hueco) / 4
    for k, nombre in enumerate(COLUMNAS):
        x, y = margen + k * (ancho_col + hueco), 118
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(FONDO))
        p.drawRect(QRectF(x, y, ancho_col, alto - y - 40))
        p.setBrush(QColor(TINTA))
        p.drawRect(QRectF(x, y, ancho_col, 3))
        horas = sum(t[4] for t in tablero[nombre])
        p.setPen(QColor(TINTA))
        p.setFont(fuente(14, True))
        p.drawText(int(x + 14), int(y + 30), nombre.upper())
        p.setPen(QColor(GRIS))
        p.setFont(fuente(13))
        p.drawText(QRectF(x, y + 12, ancho_col - 14, 24), Qt.AlignmentFlag.AlignRight,
                   f"{len(tablero[nombre])} tareas · {horas} h")
        for j, (codigo, titulo, responsable, prioridad, h) in enumerate(tablero[nombre]):
            cy = y + 48 + j * paso
            p.setPen(QPen(QColor(LINEA), 1))
            p.setBrush(QColor("white"))
            p.drawRect(QRectF(x + 10, cy, ancho_col - 20, alto_carta))
            p.setPen(QColor(GRIS))
            p.setFont(fuente(12, True))
            p.drawText(int(x + 22), int(cy + 22), codigo)
            p.setPen(QColor(TINTA))
            p.setFont(fuente(13, True))
            p.drawText(QRectF(x + 54, cy + 7, ancho_col - 70, 22), Qt.AlignmentFlag.AlignLeft,
                       p.fontMetrics().elidedText(titulo, Qt.TextElideMode.ElideRight, int(ancho_col - 70)))
            p.setPen(QColor(GRIS))
            p.setFont(fuente(12))
            p.drawText(int(x + 22), int(cy + 56), f"{responsable}  ·  {h} h  ·  {prioridad}")
    p.setPen(QColor(GRIS))
    p.setFont(fuente(12))
    total = sum(len(v) for v in tablero.values())
    p.drawText(margen, alto - 14, f"Total: {total} tareas · {sum(t[4] for v in tablero.values() for t in v)} h estimadas")
    p.end()
    img.save(salida)


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit("Uso: python3 scripts/kanban_captura.py <salida.png> \"texto\" [AAAA-MM-DDTHH:MM:SSZ]")
    en = sys.argv[3] if len(sys.argv) == 4 else None
    tablero = leer_tablero(en)
    fecha = datetime.fromisoformat(en.replace("Z", "+00:00")).astimezone().replace(tzinfo=None) if en else None
    dibujar(tablero, sys.argv[2], sys.argv[1], fecha)
    print({c: len(v) for c, v in tablero.items()})
