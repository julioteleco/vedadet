"""Cliente SIAR — Sistema de Información Agroclimática para el Regadío.

Red del Ministerio de Agricultura (España). Aporta ET0 Penman-Monteith de
estaciones reales en el regadío de Murcia: la fuente LOCAL autoritativa para
calibrar la ET0 de Open-Meteo (PARTE 2-B).

API: https://servicio.mapa.gob.es/apisiar/  (requiere clave gratuita)
Configurar:  export SIAR_API_KEY=...

Si no hay clave o red, el motor sigue con Open-Meteo / climatología.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    import requests
except ImportError:
    requests = None  # type: ignore

BASE_URL = "https://servicio.mapa.gob.es/apisiar/API/v1"

# Estaciones SIAR representativas de la Región de Murcia (código -> (nombre, lat, lon)).
# Subset curado; en producción se carga el catálogo completo vía /Estaciones.
MURCIA_STATIONS = {
    "MU01": ("Murcia (La Alberca)", 37.94, -1.13),
    "MU21": ("Cartagena (La Palma)", 37.68, -0.95),
    "MU52": ("Jumilla", 38.43, -1.33),
    "MU62": ("Caravaca de la Cruz", 38.08, -1.86),
    "MU42": ("Lorca", 37.68, -1.70),
    "MU31": ("Torre Pacheco", 37.74, -0.95),
}


@dataclass
class SiarDaily:
    station: str
    date: str
    et0: float
    tmax: float
    tmin: float
    precip: float


def nearest_station(lat: float, lon: float) -> str:
    """Código de la estación SIAR más cercana (haversine simple)."""
    import math

    def dist(s):
        _n, slat, slon = s
        dlat = math.radians(slat - lat)
        dlon = math.radians(slon - lon)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat)) * math.cos(math.radians(slat))
             * math.sin(dlon / 2) ** 2)
        return 2 * 6371 * math.asin(math.sqrt(a))

    return min(MURCIA_STATIONS.items(), key=lambda kv: dist(kv[1]))[0]


def fetch_daily(station: str, start: str, end: str,
                timeout: float = 15.0) -> list[SiarDaily]:
    """Datos diarios de una estación SIAR (start/end en 'YYYY-MM-DD').

    Lanza si falta clave/red/requests; el llamador hace fallback.
    """
    if requests is None:
        raise RuntimeError("La librería 'requests' no está instalada.")
    api_key = os.environ.get("SIAR_API_KEY")
    if not api_key:
        raise RuntimeError("Falta SIAR_API_KEY.")

    url = f"{BASE_URL}/Datos/Diarios/{station}"
    resp = requests.get(
        url,
        params={"ClaveAPI": api_key, "FechaInicial": start, "FechaFinal": end},
        timeout=timeout,
    )
    resp.raise_for_status()
    rows = resp.json().get("Datos", [])
    out = []
    for r in rows:
        out.append(SiarDaily(
            station=station,
            date=r.get("Fecha", ""),
            et0=float(r.get("EtPMon", r.get("Et0", 0.0)) or 0.0),
            tmax=float(r.get("TempMax", 0.0) or 0.0),
            tmin=float(r.get("TempMin", 0.0) or 0.0),
            precip=float(r.get("Precipitacion", 0.0) or 0.0),
        ))
    return out
