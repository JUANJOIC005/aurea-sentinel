"""Segundo factor: códigos de 6 dígitos que cambian cada 30 segundos (TOTP, RFC 6238).

Sin librerías externas: HMAC-SHA1 sobre el contador de tiempo, como Google Authenticator y Microsoft Authenticator.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

PERIODO = 30          # segundos que vale cada código
DIGITOS = 6
VENTANA = 1           # se aceptan también el código anterior y el siguiente (relojes algo desajustados)
EMISOR = "AUREA Sentinel"


def nuevo_secreto() -> str:
    """20 bytes al azar en base32 (32 caracteres), que es lo que entienden las aplicaciones autenticadoras."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _clave(secreto: str) -> bytes:
    return base64.b32decode(secreto.upper() + "=" * (-len(secreto) % 8))


def codigo(secreto: str, paso: int) -> str:
    mac = hmac.new(_clave(secreto), struct.pack(">Q", paso), hashlib.sha1).digest()
    desplazamiento = mac[-1] & 0x0F
    numero = struct.unpack(">I", mac[desplazamiento:desplazamiento + 4])[0] & 0x7FFFFFFF
    return str(numero % 10 ** DIGITOS).zfill(DIGITOS)


def paso_actual(ahora: float | None = None) -> int:
    return int((time.time() if ahora is None else ahora) // PERIODO)


def segundos_restantes(ahora: float | None = None) -> int:
    """Cuánto falta para que cambie el código."""
    ahora = time.time() if ahora is None else ahora
    return PERIODO - int(ahora % PERIODO)


def verificar(secreto: str, texto: str, ultimo_paso: int = 0, ahora: float | None = None) -> int | None:
    """Devuelve el paso del código si es correcto y no se había usado ya, o None."""
    texto = (texto or "").replace(" ", "")
    if len(texto) != DIGITOS or not texto.isdigit():
        return None
    actual = paso_actual(ahora)
    for paso in range(actual - VENTANA, actual + VENTANA + 1):
        if hmac.compare_digest(codigo(secreto, paso), texto):
            return paso if paso > ultimo_paso else None
    return None


def uri(secreto: str, correo: str, emisor: str = EMISOR) -> str:
    """Lo que lleva el QR: la aplicación autenticadora lo lee y guarda el secreto."""
    return (f"otpauth://totp/{quote(emisor)}:{quote(correo)}?secret={secreto}&issuer={quote(emisor)}"
            f"&algorithm=SHA1&digits={DIGITOS}&period={PERIODO}")
