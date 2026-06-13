"""Proveedor meteorológico unificado (estrategia PARTE 2-B).

Orden de preferencia y rol de cada fuente:
  1. Open-Meteo  -> ET0 FAO continua + Tmax/Tmin/precip + forecast 16 d (PRIMARIA)
  2. SIAR        -> ET0 Penman-Monteith local para CALIBRAR el sesgo de Open-Meteo
  3. AEMET       -> override autoritativo de helada (avisos oficiales)
  4. Climatología-> fallback offline (nunca quedarse sin datos)

Devuelve un WeatherBundle homogéneo para el motor y registra la fuente usada.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..data.murcia_climatology import ET0_DAILY_APPROX, monthly_normal
from . import aemet, openmeteo, siar


@dataclass
class WeatherBundle:
    recent_tmax: list[float]
    forecast_tmax: list[float]
    today_tmin: float
    today_precip: float
    et0_today: float
    forecast_et0: list[float] = field(default_factory=list)
    source: str = "climatology"
    siar_station: str | None = None
    et0_calibration_factor: float = 1.0
    aemet_frost_warning: bool = False


def _climatology_bundle() -> WeatherBundle:
    m = date.today().month
    tmax, tmin, precip_month = monthly_normal(m)
    return WeatherBundle(
        recent_tmax=[tmax] * 7,
        forecast_tmax=[tmax] * 7,
        today_tmin=tmin,
        today_precip=precip_month / 30.0,
        et0_today=ET0_DAILY_APPROX[m],
        forecast_et0=[ET0_DAILY_APPROX[m]] * 7,
        source="climatology",
    )


def _siar_calibration(lat: float, lon: float, om_et0: float) -> tuple[str | None, float]:
    """Factor de calibración de ET0 (SIAR/Open-Meteo) usando ayer.

    Devuelve (estacion, factor). factor=1.0 si no hay datos SIAR.
    """
    station = siar.nearest_station(lat, lon)
    try:
        from datetime import timedelta
        y = (date.today() - timedelta(days=2)).isoformat()
        rows = siar.fetch_daily(station, y, y)
        if rows and rows[0].et0 > 0 and om_et0 > 0:
            factor = max(0.5, min(1.5, rows[0].et0 / om_et0))
            return station, round(factor, 3)
    except Exception:
        pass
    return station, 1.0


def get_weather(lat: float, lon: float, *, use_live: bool = True,
                municipio_ine: str | None = None,
                calibrate_with_siar: bool = True) -> WeatherBundle:
    """Punto de entrada único para el motor."""
    if not use_live:
        return _climatology_bundle()

    try:
        wx = openmeteo.fetch_forecast(lat, lon, days=16)
        bundle = WeatherBundle(
            recent_tmax=wx.tmax[:3],
            forecast_tmax=wx.tmax[:7],
            today_tmin=wx.tmin[0],
            today_precip=wx.precip[0],
            et0_today=wx.et0[0],
            forecast_et0=wx.et0[:7],
            source="open-meteo",
        )
    except Exception:
        bundle = _climatology_bundle()

    if calibrate_with_siar and bundle.source == "open-meteo":
        station, factor = _siar_calibration(lat, lon, bundle.et0_today)
        bundle.siar_station = station
        bundle.et0_calibration_factor = factor
        if factor != 1.0:
            bundle.et0_today = round(bundle.et0_today * factor, 2)
            bundle.forecast_et0 = [round(e * factor, 2) for e in bundle.forecast_et0]
            bundle.source = "open-meteo+siar"

    if municipio_ine:
        bundle.aemet_frost_warning = aemet.has_frost_warning(municipio_ine)

    return bundle
