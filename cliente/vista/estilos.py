"""Sistema visual de AUREA AUDIT (mockups SV-1 y SV-2): colores, tipografía y hoja de estilos."""

AZUL = "#0B2D5B"        # azul institucional
ACERO = "#3B6EA8"       # azul acero
CIAN = "#00C2FF"        # solo foco y estado activo
PLATA = "#D7DEE7"       # bordes y divisores
BLANCO = "#FFFFFF"
FONDO = "#F4F6FA"       # fondo de la zona de contenido
TEXTO = "#1B2A41"
TEXTO_SUAVE = "#5E6E85"

EN_RANGO = "#1C8F5F"
AVISO = "#B87500"
ALARMA = "#C73636"
NEUTRO = "#5E6E85"

COLOR_ROL = {
    "supervisor": AZUL,
    "tecnico": ACERO,
    "auditor": "#1A7DA6",
    "administrador": "#46556E",
}

# Aptos es una fuente de Microsoft; si no está instalada se usa la siguiente de la lista.
FUENTES = '"Aptos", "Segoe UI", "Noto Sans", "DejaVu Sans", sans-serif'
FUENTE_TITULOS = '"Aptos Display", "Aptos", "Segoe UI", "Noto Sans", "DejaVu Sans", sans-serif'
FUENTE_MONO = '"Cascadia Mono", "DejaVu Sans Mono", monospace'

ANCHO_MENU = 224
ANCHO_MENU_REDUCIDO = 68
ANCHO_MINIMO_COMPLETO = 1366   # por debajo, menú de iconos y sin «Datos en vivo»


HOJA = f"""
QWidget {{ font-family: {FUENTES}; font-size: 14px; color: {TEXTO}; }}
QMainWindow, #Fondo {{ background: {FONDO}; }}
#PanelFormulario {{ background: {BLANCO}; }}
QToolTip {{ background: {AZUL}; color: {BLANCO}; border: none; padding: 4px 8px; }}

/* ── Textos ── */
QLabel#H1 {{ font-family: {FUENTE_TITULOS}; font-size: 22px; font-weight: 700; color: {AZUL}; }}
QLabel#H2 {{ font-family: {FUENTE_TITULOS}; font-size: 16px; font-weight: 700; color: {AZUL}; }}
QLabel#Suave {{ font-size: 13px; color: {TEXTO_SUAVE}; }}
QLabel#Etiqueta {{ font-size: 12px; font-weight: 700; color: {TEXTO}; }}
QLabel#Mayusculas {{ font-size: 11px; font-weight: 700; color: {TEXTO_SUAVE}; letter-spacing: 1px; }}

/* ── Campos de formulario (40 px, foco cian) ── */
QLineEdit, QComboBox, QPlainTextEdit {{
    background: {BLANCO}; border: 1px solid {PLATA}; border-radius: 6px;
    padding: 0 10px; font-size: 13px; selection-background-color: {ACERO};
}}
QLineEdit, QComboBox {{ min-height: 38px; }}
QPlainTextEdit {{ padding: 8px 10px; }}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border: 1px solid {CIAN}; }}
QLineEdit:disabled, QComboBox:disabled {{ background: {FONDO}; color: {TEXTO_SUAVE}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
    background: {BLANCO}; border: 1px solid {PLATA}; selection-background-color: {AZUL};
    selection-color: {BLANCO}; outline: none;
}}
QCheckBox {{ font-size: 12px; color: {TEXTO_SUAVE}; spacing: 6px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {PLATA}; border-radius: 3px; background: {BLANCO}; }}
QCheckBox::indicator:checked {{ background: {AZUL}; border-color: {AZUL}; }}

/* ── Botones ── */
QPushButton#Primario {{
    background: {AZUL}; color: {BLANCO}; border: 1px solid {AZUL};
    border-radius: 6px; min-height: 38px; font-weight: 700; padding: 0 18px;
}}
QPushButton#Primario:hover {{ background: #123C77; }}
QPushButton#Primario:focus {{ border: 2px solid {CIAN}; }}
QPushButton#Primario:disabled {{ background: #8A9BB5; border-color: #8A9BB5; }}
QPushButton#Secundario {{
    background: {BLANCO}; color: {AZUL}; border: 1px solid {PLATA};
    border-radius: 6px; min-height: 38px; font-weight: 700; padding: 0 18px;
}}
QPushButton#Secundario:hover {{ border-color: {ACERO}; }}
QPushButton#Secundario:focus {{ border: 2px solid {CIAN}; }}
QPushButton#Enlace {{
    background: transparent; border: none; color: {ACERO}; font-size: 12px; font-weight: 700;
    padding: 0; text-align: left;
}}
QPushButton#Enlace:hover {{ text-decoration: underline; }}

/* ── Avisos ── */
QLabel#AvisoInfo {{ background: #EEF3FA; border: 1px solid #DCE6F3; border-radius: 6px; padding: 9px 11px;
                    font-size: 12px; color: {TEXTO_SUAVE}; }}
QLabel#AvisoError {{ background: #FBECEC; border: 1px solid #F0C9C9; border-radius: 6px; padding: 9px 11px;
                     font-size: 12px; color: {ALARMA}; }}
QLabel#AvisoOk {{ background: #E8F5EE; border: 1px solid #BFE3CE; border-radius: 6px; padding: 9px 11px;
                  font-size: 12px; color: {EN_RANGO}; }}
QLabel#AvisoAmbar {{ background: #FFF6DD; border: 1px solid #F1DFA6; border-radius: 6px; padding: 9px 11px;
                     font-size: 12px; color: #7A5A00; }}

/* ── Menú lateral ── */
#MenuLateral {{ background: {BLANCO}; border-right: 1px solid {PLATA}; }}
QPushButton#ItemMenu {{
    background: transparent; border: none; border-radius: 6px; text-align: left;
    padding: 0 12px; min-height: 36px; font-size: 13px; color: {TEXTO};
}}
QPushButton#ItemMenu:hover {{ background: {FONDO}; }}
QPushButton#ItemMenu:checked {{ background: {AZUL}; color: {BLANCO}; font-weight: 700; }}
QPushButton#CerrarSesion {{
    background: transparent; border: none; text-align: left; padding: 4px 0;
    font-size: 12px; font-weight: 700; color: {TEXTO};
}}
QPushButton#CerrarSesion:hover {{ color: {ALARMA}; }}

/* ── Cabecera y tarjetas ── */
#PildoraUsuario {{ background: {BLANCO}; border: 1px solid {PLATA}; border-radius: 26px; }}
#Chip {{ background: {BLANCO}; border: 1px solid {PLATA}; border-radius: 12px; }}
#Tarjeta {{ background: {BLANCO}; border: 1px solid {PLATA}; border-radius: 10px; }}

/* ── Barra de estado ── */
#BarraEstado {{ background: {AZUL}; }}
#BarraEstado QLabel {{ color: {BLANCO}; font-size: 11px; }}
"""
