"""Optimizador de ventana de siembra (PARTE 2-A.5).

Para cada fecha candidata simula la trayectoria GDD con climatología hasta la
cosecha de hoja prevista, integra el BoltRisk a lo largo de la vida del cultivo,
estima riesgo de helada y coste hídrico, y ordena las fechas.

Usa climatología de Murcia para la simulación (v1, offline). En v2, mezclar con
forecast de Open-Meteo/AEMET para el horizonte cercano.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from ..config import get_variety, load_agronomy
from ..data.murcia_climatology import ET0_DAILY_APPROX, MURCIA_LAT, monthly_normal
from . import bolting, gdd, photoperiod


@dataclass
class CandidateDate:
    sow_date: date
    harvest_date: date
    days_to_harvest: int
    mean_bolt_risk: float
    max_bolt_risk: float
    frost_days: int
    et0_total_mm: float
    in_safe_calendar: bool
    score: float = field(default=0.0)


def _interp_day(d: date):
    """(tmax, tmin, precip_mes) climatológicos para una fecha."""
    return monthly_normal(d.month)


def simulate_candidate(
    sow_date: date,
    *,
    latitude: float = MURCIA_LAT,
    variety: str = "Calypso",
    microclimate: str = "valle",
    target_stage: str = "first_leaf_harvest",
    humidity_ok: bool = True,
) -> CandidateDate:
    """Simula un ciclo desde sow_date hasta alcanzar el GDD objetivo."""
    agro = load_agronomy()
    target_gdd = agro["gdd_stages"][target_stage]
    bolt_delay = get_variety(variety)["bolt_delay_days"]

    gdd_accum = 0.0
    cum_tmax: list[float] = []
    bolt_scores: list[float] = []
    frost_days = 0
    et0_total = 0.0

    d = sow_date
    max_days = 150  # tope de seguridad
    for _ in range(max_days):
        tmax, tmin, _precip = _interp_day(d)
        cum_tmax.append(tmax)
        gdd_accum += gdd.gdd_day(tmax, tmin)
        et0_total += ET0_DAILY_APPROX[d.month]

        if tmin <= agro["frost"]["hard_frost_c"]:
            frost_days += 1

        doy = d.timetuple().tm_yday
        photo = photoperiod.daylength_hours(latitude, doy)
        # forecast aproximado: próximos 7 días de climatología
        fc_tmax = [_interp_day(d + timedelta(days=k))[0] for k in range(1, 8)]
        br = bolting.bolting_risk(
            recent_tmax=cum_tmax[-agro["bolting"]["heat_window_days"]:],
            forecast_tmax=fc_tmax,
            photoperiod_h=photo,
            variety=variety,
            humidity_ok=humidity_ok,
        )
        bolt_scores.append(br.score)

        if gdd_accum >= target_gdd:
            break
        d += timedelta(days=1)

    days_to_harvest = (d - sow_date).days + 1
    in_safe = d.month in set(agro["sowing_calendar"][microclimate]["safe_months"]) and \
        sow_date.month in set(agro["sowing_calendar"][microclimate]["safe_months"])

    return CandidateDate(
        sow_date=sow_date,
        harvest_date=d,
        days_to_harvest=days_to_harvest,
        mean_bolt_risk=round(sum(bolt_scores) / len(bolt_scores), 1),
        max_bolt_risk=round(max(bolt_scores), 1),
        frost_days=frost_days,
        et0_total_mm=round(et0_total, 1),
        in_safe_calendar=in_safe,
    )


def rank_sowing_dates(
    start: date,
    end: date,
    *,
    step_days: int = 7,
    latitude: float = MURCIA_LAT,
    variety: str = "Calypso",
    microclimate: str = "valle",
    target_stage: str = "first_leaf_harvest",
) -> list[CandidateDate]:
    """Evalúa fechas candidatas y las ordena (mejor primero).

    Score = minimizar BoltRisk máximo + helada + coste hídrico, premiar estar
    dentro del calendario seguro.
    """
    candidates: list[CandidateDate] = []
    d = start
    while d <= end:
        c = simulate_candidate(
            d, latitude=latitude, variety=variety,
            microclimate=microclimate, target_stage=target_stage,
        )
        # menor es mejor
        c.score = (
            c.max_bolt_risk * 1.0
            + c.frost_days * 8.0
            + c.et0_total_mm * 0.05
            + (0.0 if c.in_safe_calendar else 25.0)
        )
        candidates.append(c)
        d += timedelta(days=step_days)

    return sorted(candidates, key=lambda x: x.score)


def stagger_plan(
    best_sow: date,
    *,
    n: int = 4,
    microclimate: str = "valle",
    variety: str = "Calypso",
    latitude: float = MURCIA_LAT,
) -> list[CandidateDate]:
    """Plan escalonado de suministro continuo (cada 14-21 días)."""
    agro = load_agronomy()
    interval = agro["sowing_calendar"]["stagger_days"][0]  # 14 d
    out = []
    for i in range(n):
        d = best_sow + timedelta(days=interval * i)
        out.append(simulate_candidate(
            d, latitude=latitude, variety=variety, microclimate=microclimate))
    return out
