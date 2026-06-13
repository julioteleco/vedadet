"""Orquestación: junta meteo + motor determinista + explicación LLM.

Reutilizable desde la API (main.py) y la CLI (cli/demo.py).
"""
from __future__ import annotations

from datetime import date

from .data.murcia_climatology import ET0_DAILY_APPROX, monthly_normal
from .engine import bolting, frost, gdd, irrigation, photoperiod, sowing_window
from .weather import openmeteo


def _weather_or_climatology(lat: float, lon: float, use_live: bool):
    """Devuelve (recent_tmax, forecast_tmax, today_tmin, today_precip, et0, source)."""
    if use_live:
        try:
            wx = openmeteo.fetch_forecast(lat, lon, days=16)
            recent_tmax = wx.tmax[:3]              # proxy de pasado (forecast cercano)
            forecast_tmax = wx.tmax[:7]
            return (recent_tmax, forecast_tmax, wx.tmin[0], wx.precip[0],
                    wx.et0[0], "open-meteo")
        except Exception:
            pass  # fallback a climatología

    m = date.today().month
    tmax, tmin, precip_month = monthly_normal(m)
    recent = [tmax] * 7
    return (recent, [tmax] * 7, tmin, precip_month / 30.0,
            ET0_DAILY_APPROX[m], "climatology")


def bolting_recommendation(*, lat: float, lon: float, variety: str,
                           humidity_ok: bool, use_live: bool) -> dict:
    recent, fc, _tmin, _p, _et0, src = _weather_or_climatology(lat, lon, use_live)
    doy = date.today().timetuple().tm_yday
    photo = photoperiod.daylength_hours(lat, doy)
    res = bolting.bolting_risk(
        recent_tmax=recent, forecast_tmax=fc, photoperiod_h=photo,
        variety=variety, humidity_ok=humidity_ok)
    return {
        "score": res.score, "band": res.band, "action": res.action,
        "photoperiod_h": round(photo, 2), "components": res.components,
        "weather_source": src,
    }


def irrigation_recommendation(*, lat: float, lon: float, variety: str, stage: str,
                              leaching_fraction, use_live: bool) -> dict:
    _r, _fc, _tmin, precip, et0, src = _weather_or_climatology(lat, lon, use_live)
    adv = irrigation.daily_irrigation(
        et0_mm=et0, precip_mm=precip, stage=stage, variety=variety,
        leaching_fraction=leaching_fraction)
    return {
        "et0_mm": adv.et0_mm, "etc_mm": adv.etc_mm,
        "effective_rain_mm": adv.effective_rain_mm,
        "net_need_mm": adv.net_need_mm, "gross_need_mm": adv.gross_need_mm,
        "note": adv.note, "weather_source": src,
    }


def frost_recommendation(*, lat: float, lon: float, established: bool,
                         use_live: bool) -> dict:
    _r, _fc, tmin, _p, _et0, src = _weather_or_climatology(lat, lon, use_live)
    a = frost.check_frost(tmin, established=established)
    return {"severity": a.severity, "message": a.message,
            "tmin_c": a.tmin_c, "weather_source": src}


def sowing_recommendation(*, lat: float, variety: str, microclimate: str,
                          start: date, end: date, step_days: int,
                          objetivo: str) -> dict:
    target = "first_leaf_harvest" if objetivo == "hoja" else "seed_maturity"
    ranked = sowing_window.rank_sowing_dates(
        start, end, step_days=step_days, latitude=lat, variety=variety,
        microclimate=microclimate, target_stage=target)
    best = ranked[0]
    plan = sowing_window.stagger_plan(
        best.sow_date, n=4, microclimate=microclimate, variety=variety, latitude=lat)
    return {
        "best_date": best.sow_date.isoformat(),
        "harvest_date": best.harvest_date.isoformat(),
        "days_to_harvest": best.days_to_harvest,
        "max_bolt_risk": best.max_bolt_risk,
        "mean_bolt_risk": best.mean_bolt_risk,
        "frost_days": best.frost_days,
        "in_safe_calendar": best.in_safe_calendar,
        "ranking": [
            {"date": c.sow_date.isoformat(), "score": round(c.score, 1),
             "max_bolt_risk": c.max_bolt_risk, "frost_days": c.frost_days,
             "safe": c.in_safe_calendar}
            for c in ranked[:8]
        ],
        "stagger_plan": [
            {"date": c.sow_date.isoformat(), "harvest": c.harvest_date.isoformat(),
             "max_bolt_risk": c.max_bolt_risk}
            for c in plan
        ],
    }
