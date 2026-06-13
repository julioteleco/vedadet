"""Onboarding del usuario sin conocimientos (PARTE 2-D).

Localiza la parcela en el mapa y deriva automáticamente:
  - altitud (Open-Meteo elevation API; fallback heurístico)
  - clase de microclima (costa / valle / altiplano)
  - estación SIAR más cercana
  - municipio INE (para avisos AEMET)
y FUERZA la entrada de la EC del agua (Recomendación #5: sin umbral de
salinidad publicado para cilantro -> hay que medir).
"""
from __future__ import annotations

from dataclasses import dataclass

from .weather import aemet, siar

try:
    import requests
except ImportError:
    requests = None  # type: ignore

ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"


def fetch_altitude(lat: float, lon: float, timeout: float = 10.0) -> float | None:
    """Altitud (m) de Open-Meteo; None si no hay red."""
    if requests is None:
        return None
    try:
        r = requests.get(ELEVATION_URL,
                         params={"latitude": lat, "longitude": lon}, timeout=timeout)
        r.raise_for_status()
        return float(r.json()["elevation"][0])
    except Exception:
        return None


def classify_microclimate(lat: float, lon: float, altitude_m: float | None) -> str:
    """Clasifica el microclima dentro de la Región de Murcia (PARTE 1-E).

    - costa:    cerca del litoral (Cartagena / Mar Menor), muy pocas heladas
    - altiplano: altitud alta (>500 m) o NO interior, helada invernal real
    - valle:    valle del Segura por defecto
    """
    if altitude_m is not None and altitude_m >= 500:
        return "altiplano"
    # litoral: longitud cercana al mar (este de ~-1.05) y latitud baja
    if lon >= -1.05 and lat <= 37.85:
        return "costa"
    # interior norte (Jumilla/Yecla/Caravaca) sin altitud conocida
    if lat >= 38.2:
        return "altiplano"
    return "valle"


def nearest_municipio(lat: float, lon: float) -> str:
    """Municipio INE aproximado más cercano (para AEMET)."""
    import math
    # centroides aproximados de los municipios de referencia
    centroids = {
        "30030": (37.99, -1.13),   # Murcia
        "30016": (37.63, -0.99),   # Cartagena
        "30024": (37.67, -1.70),   # Lorca
        "30022": (38.48, -1.33),   # Jumilla
        "30015": (38.11, -1.86),   # Caravaca
        "30043": (38.61, -1.11),   # Yecla
    }

    def dist(c):
        return (c[0] - lat) ** 2 + (c[1] - lon) ** 2

    return min(centroids.items(), key=lambda kv: dist(kv[1]))[0]


@dataclass
class OnboardingResult:
    lat: float
    lon: float
    altitud_m: float | None
    microclima: str
    estacion_siar: str
    municipio_ine: str
    needs_water_ec: bool
    advice: str


def onboard(lat: float, lon: float, ec_agua_dS_m: float | None = None,
            fetch_live: bool = True) -> OnboardingResult:
    """Deriva el perfil de la parcela a partir de su localización."""
    alt = fetch_altitude(lat, lon) if fetch_live else None
    micro = classify_microclimate(lat, lon, alt)
    estacion = siar.nearest_station(lat, lon)
    muni = nearest_municipio(lat, lon)

    needs_ec = ec_agua_dS_m is None
    advice_parts = [
        f"Parcela clasificada como '{micro}'.",
        f"Estación SIAR de referencia: {estacion}.",
    ]
    if needs_ec:
        advice_parts.append(
            "IMPORTANTE: mide la EC (conductividad) del agua de riego. La "
            "tolerancia a la sal del cilantro no está cuantificada y el agua "
            "del Segura/mezclada puede ser salina. Usa goteo + fracción de lavado.")
    elif ec_agua_dS_m and ec_agua_dS_m > 1.5:
        advice_parts.append(
            f"EC del agua = {ec_agua_dS_m} dS/m (elevada): activa fracción de "
            "lavado en el riego y prioriza goteo.")

    return OnboardingResult(
        lat=lat, lon=lon, altitud_m=alt, microclima=micro,
        estacion_siar=estacion, municipio_ine=muni,
        needs_water_ec=needs_ec, advice=" ".join(advice_parts),
    )
