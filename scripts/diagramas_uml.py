import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyArrowPatch, Rectangle

plt.rcParams["font.family"] = "DejaVu Sans"
NEGRO, GRIS = "#222222", "#F2F2F2"


def lienzo(ancho, alto):
    fig, ax = plt.subplots(figsize=(ancho, alto))
    ax.set_xlim(0, ancho * 10)
    ax.set_ylim(0, alto * 10)
    ax.axis("off")
    return fig, ax


def flecha(ax, a, b, estilo="-|>", linea="-", texto=None, pos=0.5, desplaza=(0, 1.2), curva=0.0):
    f = FancyArrowPatch(a, b, arrowstyle=estilo, mutation_scale=11, lw=1, color=NEGRO,
                        linestyle=linea, connectionstyle=f"arc3,rad={curva}", shrinkA=0, shrinkB=0)
    ax.add_patch(f)
    if texto:
        ax.text(a[0] + (b[0] - a[0]) * pos + desplaza[0], a[1] + (b[1] - a[1]) * pos + desplaza[1],
                texto, fontsize=7.5, ha="center", va="bottom", style="italic",
                bbox=dict(fc="white", ec="none", pad=0.6))


def medidas(atributos, metodos, estereotipo):
    h_t = 6.2 if estereotipo else 4.4
    h_a = len(atributos) * 3.1 + 1.2 if atributos else 0
    h_m = len(metodos) * 3.1 + 1.2 if metodos else 0
    return h_t, h_a, h_m, 3.1


def alto_clase(atributos=(), metodos=(), estereotipo=None):
    return sum(medidas(atributos, metodos, estereotipo)[:3])


def clase(ax, x, y, w, titulo, atributos=(), metodos=(), estereotipo=None):
    h_t, h_a, h_m, alto_l = medidas(atributos, metodos, estereotipo)
    alto = h_t + h_a + h_m
    ax.add_patch(Rectangle((x, y - alto), w, alto, fc="white", ec=NEGRO, lw=1))
    ax.add_patch(Rectangle((x, y - h_t), w, h_t, fc=GRIS, ec=NEGRO, lw=1))
    if estereotipo:
        ax.text(x + w / 2, y - 1.7, f"«{estereotipo}»", fontsize=7, ha="center", va="center")
        ax.text(x + w / 2, y - 4.1, titulo, fontsize=9, ha="center", va="center", weight="bold")
    else:
        ax.text(x + w / 2, y - h_t / 2, titulo, fontsize=9, ha="center", va="center", weight="bold")
    for i, t in enumerate(atributos):
        ax.text(x + 1, y - h_t - 1.3 - i * alto_l, t, fontsize=7.5, va="top", family="DejaVu Sans Mono")
    if metodos:
        ax.add_patch(Rectangle((x, y - alto), w, h_m, fc="white", ec=NEGRO, lw=1))
        for i, t in enumerate(metodos):
            ax.text(x + 1, y - h_t - h_a - 1.3 - i * alto_l, t, fontsize=7.5, va="top", family="DejaVu Sans Mono")
    return alto


def casos_de_uso(salida):
    fig, ax = lienzo(11, 8.6)
    ax.add_patch(Rectangle((26, 3), 62, 80, fc="white", ec=NEGRO, lw=1.2))
    ax.text(57, 79.5, "AUREA Sentinel", fontsize=10, ha="center", weight="bold")

    def actor(x, y, nombre):
        ax.add_patch(plt.Circle((x, y + 7), 1.6, fc="white", ec=NEGRO, lw=1))
        ax.plot([x, x], [y + 5.4, y + 1.5], color=NEGRO, lw=1)
        ax.plot([x - 2.4, x + 2.4], [y + 4, y + 4], color=NEGRO, lw=1)
        ax.plot([x, x - 2], [y + 1.5, y - 1.5], color=NEGRO, lw=1)
        ax.plot([x, x + 2], [y + 1.5, y - 1.5], color=NEGRO, lw=1)
        ax.text(x, y - 3.5, nombre, fontsize=8.5, ha="center", va="top")
        return (x, y + 3.5)

    casos = {}

    def caso(clave, x, y, texto, ancho=24):
        ax.add_patch(Ellipse((x, y), ancho, 6.6, fc="white", ec=NEGRO, lw=1))
        ax.text(x, y, texto, fontsize=7.8, ha="center", va="center")
        casos[clave] = (x, y, ancho)

    caso("login", 57, 72, "Iniciar sesión (contraseña + código)", 32)
    caso("reg", 57, 64, "Registrarse (cuenta pendiente)", 28)
    caso("panel", 44, 54, "Ver panel de su área", 22)
    caso("hist", 44, 46, "Consultar histórico", 22)
    caso("alarma", 44, 38, "Reconocer alarmas", 22)
    caso("asig", 44, 30, "Asignar tareas", 22)
    caso("inc", 44, 22, "Registrar incidencias", 22)
    caso("regact", 72, 54, "Verificar registro de actividad", 26)
    caso("inf", 72, 46, "Exportar informes", 22)
    caso("aprob", 72, 30, "Aprobar cuentas", 20)
    caso("conf", 72, 22, "Configurar sensores", 22)
    caso("vin", 72, 14, "Gestionar vínculos", 22)

    sup = actor(10, 52, "Supervisor\nde área")
    tec = actor(10, 22, "Técnico\nde campo")
    aud = actor(103, 56, "Auditor")
    adm = actor(103, 20, "Administrador")

    def une(actor_xy, clave):
        x, y, w = casos[clave]
        lado = x - w / 2 if actor_xy[0] < 50 else x + w / 2
        flecha(ax, actor_xy, (lado, y), estilo="-")

    for clave in ("panel", "hist", "alarma", "asig", "login"):
        une(sup, clave)
    for clave in ("panel", "inc", "login", "reg"):
        une(tec, clave)
    for clave in ("regact", "inf", "login"):
        une(aud, clave)
    for clave in ("aprob", "conf", "vin", "login"):
        une(adm, clave)
    fig.savefig(salida, dpi=170, bbox_inches="tight", facecolor="white")


def clases(salida):
    fig, ax = lienzo(12.6, 8.8)
    ax.text(2, 88, "Cliente (MVC)", fontsize=10, weight="bold")
    ax.text(88, 88, "Servidor", fontsize=10, weight="bold")
    huecos = 5
    cajas = {}

    def pon(nombre, x, y, w, titulo, atr, met, est):
        h = clase(ax, x, y, w, titulo, atr, met, est)
        cajas[nombre] = (x, y, w, h)
        return y - h - huecos

    y = 84
    y = pon("va", 2, y, 30, "VentanaAcceso", ["vista_login", "vista_registro"], ["mostrar_login()", "mostrar_registro()"], "vista")
    y = pon("ca", 2, y, 30, "ControladorAcceso", ["api", "sesion"], ["entrar(correo, clave)", "registrar(datos)"], "controlador")
    y = pon("cs", 2, y, 30, "ControladorSesion", ["sesion", "temporizador"], ["cerrar()", "comprobar_caducidad()"], "controlador")
    y = 84
    y = pon("api", 42, y, 32, "ClienteApi", ["url_base", "token"], ["login(correo, clave)", "registro(datos)", "yo()", "logout()"], "modelo")
    y = pon("ses", 42, y, 32, "Sesion", ["usuario", "token", "caduca_en"], ["esta_activa()", "secciones_menu()"], "modelo")
    y = pon("usu", 42, y, 32, "Usuario", ["nombre", "correo", "rol", "area"], [], "modelo")
    y = 84
    y = pon("rt", 88, y, 36, "api (FastAPI)", [], ["POST /auth/login", "POST /auth/registro", "GET  /auth/yo", "POST /auth/logout"], "rutas")
    y = pon("us", 88, y, 36, "usuarios", [], ["por_correo()", "anotar_fallo()", "crear_pendiente()"], "módulo")
    y = pon("se", 88, y, 36, "sesiones", [], ["crear()", "validar()", "cerrar()"], "módulo")
    y = pon("sg", 88, y, 36, "seguridad", [], ["hashear()  Argon2id", "verificar()", "hash_token()  SHA-256"], "módulo")
    pon("au", 128, 84, 22, "auditoria", [], ["registrar()"], "módulo")

    def borde(n, lado, f=0.5):
        x, y, w, h = cajas[n]
        return {"l": (x, y - h * f), "r": (x + w, y - h * f), "t": (x + w * f, y), "b": (x + w * f, y - h)}[lado]

    flecha(ax, borde("va", "b", 0.3), borde("ca", "t", 0.3), linea="--", texto="avisa", desplaza=(4, 0))
    flecha(ax, borde("ca", "t", 0.7), borde("va", "b", 0.7), linea="--", texto="", estilo="-|>")
    flecha(ax, borde("ca", "r", 0.35), borde("api", "l", 0.55), linea="--", texto="usa")
    flecha(ax, borde("cs", "r", 0.35), borde("ses", "l", 0.35), linea="--", texto="usa")
    flecha(ax, borde("ses", "b", 0.5), borde("usu", "t", 0.5), estilo="-", texto="1", desplaza=(2, 0))
    flecha(ax, borde("api", "r", 0.4), borde("rt", "l", 0.4), linea="--", texto="HTTP / JSON", desplaza=(0, 1))
    flecha(ax, borde("rt", "r", 0.4), borde("au", "l", 0.4), linea="--", texto="")
    for arriba, abajo in (("rt", "us"), ("us", "se"), ("se", "sg")):
        pass
    ax.set_xlim(0, 152)
    ax.set_ylim(-12, 92)
    fig.savefig(salida, dpi=170, bbox_inches="tight", facecolor="white")


def secuencia(salida):
    fig, ax = lienzo(12.4, 8.4)
    nombres = ["Usuario", "VistaLogin", "ControladorAcceso", "ClienteApi", "API /auth/login", "SQLite"]
    xs = [10, 32, 54, 76, 98, 118]
    for x, n in zip(xs, nombres):
        ax.add_patch(Rectangle((x - 9.5, 76), 19, 5, fc=GRIS, ec=NEGRO, lw=1))
        ax.text(x, 78.5, n, fontsize=7.6, ha="center", va="center", weight="bold")
        ax.plot([x, x], [18, 76], color=NEGRO, lw=0.8, ls=(0, (4, 3)))
    pasos = [
        (0, 1, 71, "escribe correo y contraseña", False),
        (1, 2, 66, "entrar(correo, clave)", False),
        (2, 3, 61, "login(correo, clave)", False),
        (3, 4, 56, "POST /auth/login", False),
        (4, 5, 51, "buscar usuario por correo", False),
        (5, 4, 46, "usuario (o nada)", True),
        (4, 5, 33, "crear sesión (SHA-256 del token)\ny anotar el evento", False),
        (4, 3, 28, "200 token y perfil  /  401 «credenciales incorrectas»", True),
        (3, 2, 24, "Sesion(usuario, token)", True),
        (2, 1, 20, "mostrar ventana según el rol", True),
    ]
    for a, b, y, t, vuelta in pasos:
        flecha(ax, (xs[a], y), (xs[b], y), estilo="-|>", linea="--" if vuelta else "-")
        ax.text((xs[a] + xs[b]) / 2, y + 0.9, t, fontsize=7.2, ha="center", va="bottom")
    ax.add_patch(Rectangle((xs[4] - 1, 36.5), 2, 7.5, fc="white", ec=NEGRO, lw=1))
    ax.text(xs[4] - 3, 40.3, "comprobar clave con Argon2id\n(también si el usuario no existe)",
            fontsize=7.2, ha="right", va="center", style="italic")
    ax.add_patch(Rectangle((3, 3), 122, 11, fc="none", ec=NEGRO, lw=0.8))
    ax.text(4.5, 11.8, "alt", fontsize=7.5, weight="bold", va="center")
    ax.text(10, 7.5, "a los 5 fallos seguidos la cuenta se bloquea 15 minutos y se anota en la auditoría; "
                     "al usuario le sigue saliendo el mismo mensaje.", fontsize=7.2, va="center")
    ax.set_xlim(0, 128)
    ax.set_ylim(0, 84)
    fig.savefig(salida, dpi=170, bbox_inches="tight", facecolor="white")


def base_datos(salida):
    fig, ax = lienzo(12.5, 10.4)
    esquema = {
        "rol": ["id PK", "nombre"],
        "area": ["id PK", "codigo", "nombre"],
        "sensor": ["id PK", "codigo", "area_id FK", "magnitud", "unidad", "umbral_aviso", "umbral_alarma"],
        "lectura": ["sensor_id FK", "instante", "valor"],
        "usuario": ["id PK", "nombre", "correo (único)", "password_hash", "rol_id FK", "area_id FK",
                    "supervisor_id FK", "estado", "intentos_fallidos", "bloqueado_hasta"],
        "alarma": ["id PK", "sensor_id FK", "nivel", "reconocida_por FK"],
        "tarea": ["id PK", "creada_por FK", "asignada_a FK", "sensor_id FK", "alarma_id FK", "estado"],
        "sesion": ["id PK", "usuario_id FK", "token_hash", "rol", "caduca_en"],
        "incidencia": ["id PK", "tecnico_id FK", "tarea_id FK", "sensor_id FK", "descripcion"],
        "evento_auditoria": ["id PK", "actor_id FK", "accion", "resultado", "instante", "(hash: sprint 3)"],
    }
    columnas = [(3, 26, ["rol", "area", "sensor", "lectura"]), (45, 30, ["usuario", "alarma", "tarea"]),
                (92, 30, ["sesion", "incidencia", "evento_auditoria"])]
    pos = {}
    for x, w, nombres in columnas:
        y = 92
        for n in nombres:
            h = clase(ax, x, y, w, n, esquema[n])
            pos[n] = (x, y, w, h)
            y -= h + 8

    def lado(n, l, f=0.5):
        x, y, w, h = pos[n]
        return {"l": (x, y - h * f), "r": (x + w, y - h * f), "t": (x + w * f, y), "b": (x + w * f, y - h)}[l]

    uniones = [("usuario", "l", 0.12, "rol", "r", 0.5), ("usuario", "l", 0.2, "area", "r", 0.5),
               ("sesion", "l", 0.3, "usuario", "r", 0.3), ("sensor", "t", 0.5, "area", "b", 0.5),
               ("lectura", "t", 0.5, "sensor", "b", 0.5), ("alarma", "l", 0.5, "sensor", "r", 0.5),
               ("tarea", "t", 0.5, "alarma", "b", 0.5), ("incidencia", "l", 0.4, "tarea", "r", 0.4),
               ("evento_auditoria", "l", 0.3, "usuario", "r", 0.8)]
    for a, la, fa, b, lb, fb in uniones:
        flecha(ax, lado(a, la, fa), lado(b, lb, fb), estilo="-", texto="N:1", desplaza=(0, 0.6))
    ax.text(62, -9, "usuario.supervisor_id apunta a otro usuario (el Supervisor del Técnico). "
                    "tarea, incidencia y alarma también apuntan a usuario.", fontsize=7.5, ha="center", style="italic")
    ax.set_xlim(0, 126)
    ax.set_ylim(-12, 94)
    fig.savefig(salida, dpi=170, bbox_inches="tight", facecolor="white")


if __name__ == "__main__":
    carpeta = Path(sys.argv[1])
    carpeta.mkdir(parents=True, exist_ok=True)
    casos_de_uso(carpeta / "uml_casos_de_uso.png")
    clases(carpeta / "uml_clases.png")
    secuencia(carpeta / "uml_secuencia_login.png")
    base_datos(carpeta / "uml_base_de_datos.png")
