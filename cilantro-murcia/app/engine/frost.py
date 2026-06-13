"""Comprobación de helada (PARTE 2-A.6).

Plántulas: alerta alta si Tmin <= 0°C.
Cultivo establecido: tolera ~-2 a 0°C -> alerta de menor severidad.
Los avisos AEMET son el override autoritativo (integrar en v2).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import load_agronomy


@dataclass
class FrostAlert:
    severity: str   # "ninguna" | "media" | "alta"
    message: str
    tmin_c: float


def check_frost(forecast_tmin_c: float, established: bool = False,
                aemet_warning: bool = False) -> FrostAlert:
    """Evalúa riesgo de helada para un Tmin previsto."""
    cfg = load_agronomy()["frost"]
    hard = cfg["hard_frost_c"]
    tol = cfg["established_tolerance_c"]

    if aemet_warning:
        return FrostAlert("alta", "Aviso oficial de AEMET por helada: protege el cultivo.",
                          forecast_tmin_c)

    if not established:
        if forecast_tmin_c <= hard:
            return FrostAlert("alta",
                f"Helada esta noche (Tmin {forecast_tmin_c}°C). Las plántulas son "
                f"sensibles: cubre con manta térmica/túnel.", forecast_tmin_c)
        if forecast_tmin_c <= hard + 2:
            return FrostAlert("media",
                f"Frío intenso (Tmin {forecast_tmin_c}°C). Vigila las plántulas.",
                forecast_tmin_c)
        return FrostAlert("ninguna", "Sin riesgo de helada.", forecast_tmin_c)

    # cultivo establecido
    if forecast_tmin_c <= tol:
        return FrostAlert("alta",
            f"Helada fuerte (Tmin {forecast_tmin_c}°C) por debajo de la tolerancia "
            f"({tol}°C): cubre el cultivo.", forecast_tmin_c)
    if forecast_tmin_c <= hard:
        return FrostAlert("media",
            f"Helada ligera (Tmin {forecast_tmin_c}°C). El cilantro establecido la "
            f"tolera, pero vigila.", forecast_tmin_c)
    return FrostAlert("ninguna", "Sin riesgo de helada.", forecast_tmin_c)
