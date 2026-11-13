"""Estado de un valor frente a los umbrales de su sensor: normal, aviso o alarma."""

NORMAL, AVISO, ALARMA = "normal", "aviso", "alarma"


def estado(valor: float, aviso_bajo: float | None, alarma_bajo: float | None,
           aviso_alto: float | None, alarma_alto: float | None) -> str:
    """Los umbrales que no existen (NULL en la base de datos) no se tienen en cuenta."""
    if (alarma_alto is not None and valor >= alarma_alto) or (alarma_bajo is not None and valor <= alarma_bajo):
        return ALARMA
    if (aviso_alto is not None and valor >= aviso_alto) or (aviso_bajo is not None and valor <= aviso_bajo):
        return AVISO
    return NORMAL
