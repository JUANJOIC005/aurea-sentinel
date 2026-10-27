"""Contraseñas (Argon2id), tokens de sesión y política de contraseñas."""
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from . import config

_hasher = PasswordHasher()  # Argon2id por defecto
_HASH_FICTICIO = _hasher.hash(secrets.token_urlsafe(16))

# Muestra pequeña de contraseñas habituales; en producción se usaría una lista filtrada completa.
_COMUNES = {
    "123456789012", "1234567890123", "password1234", "contraseña123", "contraseña1234",
    "qwertyuiop12", "qwertyuiopas", "administrador", "administrador1", "valdecierzo1",
    "centralnuclear", "abcdefghijkl", "iloveyou1234", "letmein123456", "welcome12345",
}


def hashear(password: str) -> str:
    return _hasher.hash(password)


def verificar(hash_guardado: str, password: str) -> bool:
    try:
        return _hasher.verify(hash_guardado, password)
    except (VerificationError, ValueError):
        return False


def verificar_ficticio(password: str) -> None:
    """Gasta el mismo tiempo que una verificación real (para que no se note si el correo existe)."""
    verificar(_HASH_FICTICIO, password)


def nuevo_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def comprobar_politica(password: str) -> list[str]:
    """Devuelve la lista de reglas que incumple la contraseña (vacía si es válida)."""
    problemas = []
    if len(password) < config.PASSWORD_MINIMO:
        problemas.append(f"debe tener al menos {config.PASSWORD_MINIMO} caracteres")
    if password.lower() in _COMUNES:
        problemas.append("aparece en las listas de contraseñas filtradas")
    if len(set(password)) < 5:
        problemas.append("usa demasiados caracteres repetidos")
    return problemas
