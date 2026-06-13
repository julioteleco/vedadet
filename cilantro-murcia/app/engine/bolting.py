"""Score de riesgo de espigado / bolting (0-100) (PARTE 2-A.3).

Combina calor reciente, fotoperiodo y calor proyectado, mitigado por humedad,
y escalado por el factor de resistencia de la variedad.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..config import get_variety, load_agronomy


@dataclass
class BoltingResult:
    score: float          # 0-100
    band: str             # "seguro" | "precaucion" | "alto"
    action: str           # mensaje de acción
    components: dict       # desglose para grounding del LLM


def _heat_load(recent_tmax: Sequence[float], t_bolt: float,
               decay: float, window: int) -> float:
    """Carga de calor ponderada exponencialmente (más reciente = más peso).

    recent_tmax debe venir ordenada de más antigua -> más reciente.
    """
    recent = list(recent_tmax)[-window:]
    if not recent:
        return 0.0
    n = len(recent)
    total = 0.0
    weight_sum = 0.0
    for i, tmax in enumerate(recent):
        # el día más reciente (i = n-1) recibe peso 1; los antiguos decaen
        w = decay ** (n - 1 - i)
        excess = max(0.0, tmax - t_bolt)
        total += w * excess
        weight_sum += w
    return total / weight_sum if weight_sum else 0.0


def _normalize_excess(excess_c: float, scale_c: float = 10.0) -> float:
    """Normaliza un exceso térmico (°C) a 0-1 con saturación suave."""
    return max(0.0, min(1.0, excess_c / scale_c))


def bolting_risk(
    *,
    recent_tmax: Sequence[float],
    forecast_tmax: Sequence[float],
    photoperiod_h: float,
    variety: str = "Santo",
    humidity_ok: bool = True,
    overrides: dict | None = None,
) -> BoltingResult:
    """Calcula el BoltRisk.

    recent_tmax: máximas de los últimos N días (antiguo -> reciente).
    forecast_tmax: máximas previstas próximos ~7 días.
    photoperiod_h: fotoperiodo del día (h).
    humidity_ok: True si el riego/humedad está bajo control (mitiga).
    """
    cfg = load_agronomy()["bolting"]
    if overrides:
        cfg = {**cfg, **overrides}
    w = cfg["weights"]

    t_bolt = cfg["t_bolt"]
    heat_load = _heat_load(recent_tmax, t_bolt, cfg["heat_decay"], cfg["heat_window_days"])

    forecast_excess = (
        sum(max(0.0, tx - t_bolt) for tx in forecast_tmax) / len(forecast_tmax)
        if forecast_tmax else 0.0
    )

    term_photo = max(0.0, photoperiod_h - cfg["dl_crit"]) / (cfg["dl_max"] - cfg["dl_crit"])
    term_photo = max(0.0, min(1.0, term_photo))

    term_heat = _normalize_excess(heat_load)
    term_forecast = _normalize_excess(forecast_excess)
    humidity_bonus = 1.0 if humidity_ok else 0.0

    raw = (
        w["w_heat"] * term_heat
        + w["w_photo"] * term_photo
        + w["w_forecast"] * term_forecast
        - w["w_humidity"] * humidity_bonus
    )
    raw = max(0.0, min(1.0, raw)) * 100.0

    factor = get_variety(variety)["bolt_factor"]
    score = max(0.0, min(100.0, raw * factor))

    th = cfg["thresholds"]
    if score < th["safe_below"]:
        band = "seguro"
        action = "Seguro sembrar / continuar."
    elif score < th["caution_below"]:
        band = "precaucion"
        action = "Solo variedad slow-bolt + sombra de tarde; cosecha temprano."
    else:
        band = "alto"
        action = "NO sembrar en campo abierto; cosecha lo existente cuanto antes."

    return BoltingResult(
        score=round(score, 1),
        band=band,
        action=action,
        components={
            "term_heat": round(term_heat, 3),
            "term_photo": round(term_photo, 3),
            "term_forecast": round(term_forecast, 3),
            "humidity_ok": humidity_ok,
            "variety_factor": factor,
            "heat_load_c": round(heat_load, 2),
            "t_bolt": t_bolt,
        },
    )
