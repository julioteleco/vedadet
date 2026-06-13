"""Modelo de Grados-Día de Crecimiento (GDD) por etapa (PARTE 2-A.2).

Tbase = 4°C, corte Tcap = 30°C.
  Tmax' = min(Tmax, 30) ; Tmin' = max(Tmin, 4)
  GDD_dia = max(0, (Tmax' + Tmin')/2 − Tbase)
"""
from __future__ import annotations

from typing import Iterable

from ..config import load_agronomy


def gdd_day(tmax: float, tmin: float,
            t_base: float | None = None, t_cap: float | None = None) -> float:
    """GDD de un día con corte superior e inferior."""
    cfg = load_agronomy()["temperatures"]
    t_base = cfg["t_base"] if t_base is None else t_base
    t_cap = cfg["t_cap"] if t_cap is None else t_cap

    tmax_c = min(tmax, t_cap)
    tmin_c = max(tmin, t_base)
    return max(0.0, (tmax_c + tmin_c) / 2.0 - t_base)


def gdd_accumulate(daily_tmax: Iterable[float], daily_tmin: Iterable[float]) -> float:
    """GDD acumulados sobre una serie de días."""
    return sum(gdd_day(tx, tn) for tx, tn in zip(daily_tmax, daily_tmin))


def stage_from_gdd(gdd_accum: float) -> str:
    """Mapea GDD acumulados a etapa fenológica (umbrales calibrables)."""
    s = load_agronomy()["gdd_stages"]
    if gdd_accum < s["emergence"]:
        return "siembra"
    if gdd_accum < s["first_leaf_harvest"]:
        return "emergencia"
    if gdd_accum < s["green_seed"]:
        return "cosecha_hoja"
    if gdd_accum < s["seed_maturity"]:
        return "semilla_verde"
    return "semilla_madura"


def stage_progress(gdd_accum: float, target_stage: str = "first_leaf_harvest") -> float:
    """Progreso 0-1 hacia una etapa objetivo (para barra de progreso UX)."""
    target = load_agronomy()["gdd_stages"][target_stage]
    if target <= 0:
        return 1.0
    return max(0.0, min(1.0, gdd_accum / target))
