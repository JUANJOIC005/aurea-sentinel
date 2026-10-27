# Receta de PyInstaller para generar un único ejecutable:   pyinstaller aurea_sentinel.spec
# En Windows produce dist/AUREA Sentinel.exe; en Linux, dist/AUREA Sentinel.
from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ["aurea_sentinel.py"],
    datas=[("cliente/recursos", "cliente/recursos"), ("servidor/migrations", "servidor/migrations")],
    hiddenimports=collect_submodules("uvicorn") + collect_submodules("argon2"),
    excludes=["tkinter", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="AUREA Sentinel",
    icon="cliente/recursos/aurea_isotipo.png",
    console=False,          # aplicación de ventanas: sin consola negra
    upx=False,
)
