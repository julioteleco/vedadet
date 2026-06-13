"""Cliente Open-Meteo (fuente meteorológica primaria, gratis no comercial).

Devuelve ET0 FAO-56 (et0_fao_evapotranspiration) + Tmax/Tmin/precip y forecast
hasta 16 días. Si no hay red, el resto del motor funciona con climatología.

Docs: https://open-meteo.com/en/docs
"""
from __future__ import annotations

from dataclasses import dataclass

try:
    import requests
except ImportError:  # el motor sigue funcionando offline
    requests = None  # type: ignore

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass
class DailyWeather:
    dates: list[str]
    tmax: list[float]
    tmin: list[float]
    precip: list[float]
    et0: list[float]


def fetch_forecast(latitude: float, longitude: float,
                   days: int = 16, timeout: float = 15.0) -> DailyWeather:
    """Trae forecast diario de Open-Meteo. Lanza si no hay `requests` o red."""
    if requests is None:
        raise RuntimeError("La librería 'requests' no está instalada.")

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "et0_fao_evapotranspiration",
        ]),
        "forecast_days": max(1, min(16, days)),
        "timezone": "auto",
    }
    resp = requests.get(FORECAST_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    d = resp.json()["daily"]
    return DailyWeather(
        dates=d["time"],
        tmax=d["temperature_2m_max"],
        tmin=d["temperature_2m_min"],
        precip=d["precipitation_sum"],
        et0=d["et0_fao_evapotranspiration"],
    )
