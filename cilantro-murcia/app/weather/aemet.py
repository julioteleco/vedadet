"""Cliente AEMET OpenData — predicción municipal oficial + avisos de helada.

Fuente OFICIAL para España. No da ET0 directa, pero sí predicción municipal y
avisos de fenómenos adversos (helada) que usamos como OVERRIDE autoritativo en
el chequeo de helada (PARTE 2-A.6 / 2-B).

API: https://opendata.aemet.es/  (clave gratuita)
Configurar:  export AEMET_API_KEY=...

Patrón AEMET en dos pasos: la primera respuesta trae una URL `datos` con el JSON
real. Si no hay clave/red, el motor sigue sin override oficial.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    import requests
except ImportError:
    requests = None  # type: ignore

BASE_URL = "https://opendata.aemet.es/opendata/api"

# Códigos INE de municipios de referencia en Murcia (subset).
MUNICIPIOS = {
    "murcia": "30030",
    "cartagena": "30016",
    "lorca": "30024",
    "jumilla": "30022",
    "caravaca": "30015",
    "yecla": "30043",
}


@dataclass
class AemetForecastDay:
    date: str
    tmax: float
    tmin: float
    prob_precip: float


def _get_with_redirect(url: str, api_key: str, timeout: float):
    r1 = requests.get(url, params={"api_key": api_key}, timeout=timeout)
    r1.raise_for_status()
    datos_url = r1.json()["datos"]
    r2 = requests.get(datos_url, timeout=timeout)
    r2.raise_for_status()
    return r2.json()


def fetch_municipal_forecast(municipio_ine: str,
                             timeout: float = 15.0) -> list[AemetForecastDay]:
    """Predicción diaria municipal AEMET. Lanza si falta clave/red."""
    if requests is None:
        raise RuntimeError("La librería 'requests' no está instalada.")
    api_key = os.environ.get("AEMET_API_KEY")
    if not api_key:
        raise RuntimeError("Falta AEMET_API_KEY.")

    url = f"{BASE_URL}/prediccion/especifica/municipio/diaria/{municipio_ine}"
    data = _get_with_redirect(url, api_key, timeout)
    dias = data[0]["prediccion"]["dia"]
    out = []
    for d in dias:
        temp = d.get("temperatura", {})
        probs = d.get("probPrecipitacion", [])
        out.append(AemetForecastDay(
            date=d.get("fecha", ""),
            tmax=float(temp.get("maxima", 0.0)),
            tmin=float(temp.get("minima", 0.0)),
            prob_precip=float(probs[0]["value"]) if probs else 0.0,
        ))
    return out


def has_frost_warning(municipio_ine: str, timeout: float = 15.0) -> bool:
    """True si la predicción AEMET incluye Tmin <= 0 en las próximas 48 h.

    Proxy del aviso oficial de fenómenos adversos por helada.
    """
    try:
        days = fetch_municipal_forecast(municipio_ine, timeout=timeout)
    except Exception:
        return False
    return any(d.tmin <= 0.0 for d in days[:2])
