import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINOS = ["Anteproyecto_AUREA_Sentinel.md", "Memoria AUREA Sentinel.md"]
INICIO, FIN = "<!-- DOCUMENTACION:inicio -->", "<!-- DOCUMENTACION:fin -->"


def como_anexo(texto: str) -> str:
    salida = []
    for linea in texto.splitlines():
        if linea.startswith("# "):
            continue
        linea = re.sub(r"^(#{2,3}) (\d+(?:\.\d+)*)\.? ", r"\1 A.\2 ", linea)
        salida.append(linea)
    return "\n".join(salida).strip()


def main() -> None:
    carpeta = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ.parent
    anexo = como_anexo((RAIZ / "DOCUMENTACION.md").read_text(encoding="utf-8"))
    for nombre in DESTINOS:
        ruta = carpeta / nombre
        if not ruta.is_file():
            print(f"{nombre}: no existe, se omite")
            continue
        texto = ruta.read_text(encoding="utf-8")
        if INICIO not in texto or FIN not in texto:
            print(f"{nombre}: faltan las marcas del anexo, se omite")
            continue
        antes, resto = texto.split(INICIO, 1)
        _, despues = resto.split(FIN, 1)
        ruta.write_text(f"{antes}{INICIO}\n\n{anexo}\n\n{FIN}{despues}", encoding="utf-8")
        print(f"{nombre}: anexo actualizado")


if __name__ == "__main__":
    main()
