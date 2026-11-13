"""Comunicación con el servidor. El cliente nunca habla con la base de datos."""
import os

import httpx

URL_POR_DEFECTO = "http://127.0.0.1:8000"


class ErrorApi(Exception):
    """El servidor ha contestado con un error (credenciales malas, datos inválidos…)."""

    def __init__(self, estado: int, mensaje: str):
        super().__init__(mensaje)
        self.estado = estado
        self.mensaje = mensaje


class ErrorConexion(Exception):
    """No se ha podido hablar con el servidor."""


class ClienteApi:
    def __init__(self, url: str | None = None, http: httpx.Client | None = None):
        self.url = (url or os.environ.get("AUREA_API_URL", URL_POR_DEFECTO)).rstrip("/")
        self._http = http or httpx.Client(base_url=self.url, timeout=5.0)
        self._token: str | None = None

    @property
    def servidor(self) -> str:
        """host:puerto, para enseñarlo en la barra de estado."""
        return self.url.split("://", 1)[-1]

    def usar_token(self, token: str | None) -> None:
        self._token = token

    def _llamar(self, metodo: str, ruta: str, crudo: bool = False, **kwargs):
        cabeceras = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        try:
            respuesta = self._http.request(metodo, ruta, headers=cabeceras, **kwargs)
        except httpx.HTTPError as error:
            raise ErrorConexion(str(error)) from error
        if respuesta.status_code >= 400:
            try:
                mensaje = respuesta.json().get("detalle", "Error del servidor.")
            except ValueError:
                mensaje = "Error del servidor."
            raise ErrorApi(respuesta.status_code, mensaje)
        if crudo:
            return respuesta.content
        return respuesta.json() if respuesta.content else None

    # ── Acceso ──
    def login(self, correo: str, password: str) -> dict:
        """Devuelve la sesión, o {"requiere_2fa": True, "desafio": …} si falta el código de 6 dígitos."""
        return self._llamar("POST", "/auth/login", json={"correo": correo, "password": password})

    def configurar_2fa(self, desafio: str) -> dict:
        """Secreto, enlace y QR (SVG) para la aplicación autenticadora. Solo la primera vez."""
        return self._llamar("POST", "/auth/2fa/configurar", json={"desafio": desafio})

    def activar_2fa(self, desafio: str, codigo: str) -> dict:
        return self._llamar("POST", "/auth/2fa/activar", json={"desafio": desafio, "codigo": codigo})

    def verificar_2fa(self, desafio: str, codigo: str) -> dict:
        return self._llamar("POST", "/auth/2fa/verificar", json={"desafio": desafio, "codigo": codigo})

    def registro(self, datos: dict) -> dict:
        return self._llamar("POST", "/auth/registro", json=datos)

    def yo(self) -> dict:
        return self._llamar("GET", "/auth/yo")

    def logout(self) -> None:
        self._llamar("POST", "/auth/logout")

    # ── Datos públicos para el formulario de registro ──
    def areas(self) -> list[dict]:
        return self._llamar("GET", "/publico/areas")

    def supervisores(self, area: str) -> list[dict]:
        return self._llamar("GET", "/publico/supervisores", params={"area": area})

    # ── Datos de la central (el servidor filtra según el rol y el área) ──
    def lecturas_ultimas(self) -> dict:
        return self._llamar("GET", "/lecturas/ultimas")

    def historico(self, tag: str, horas: int = 24, desde: str | None = None, hasta: str | None = None) -> dict:
        return self._llamar("GET", "/lecturas/historico",
                            params=_sin_vacios(tag=tag, horas=horas, desde=desde, hasta=hasta))

    def historico_csv(self, tag: str, horas: int = 24, desde: str | None = None, hasta: str | None = None) -> bytes:
        return self._llamar("GET", "/lecturas/historico/csv", crudo=True,
                            params=_sin_vacios(tag=tag, horas=horas, desde=desde, hasta=hasta))

    def alarmas(self, filtro: str = "activas") -> list[dict]:
        return self._llamar("GET", "/alarmas", params={"filtro": filtro})["alarmas"]

    def equipo(self) -> list[dict]:
        return self._llamar("GET", "/equipo")["tecnicos"]

    def salud(self) -> bool:
        try:
            self._llamar("GET", "/salud")
            return True
        except (ErrorApi, ErrorConexion):
            return False


def _sin_vacios(**parametros) -> dict:
    return {k: v for k, v in parametros.items() if v is not None}
