"""Riego basado en ET0 (FAO-56) y balance hídrico (PARTE 2-A.4).

ETc = Kc · ET0 ;  necesidad_neta = ETc − lluvia_efectiva
Agua salina: bruto = neto / (1 − LF)
Fallback ET0 Hargreaves cuando no hay ET0 de API.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..config import kc_set_for_variety, load_agronomy


def et0_hargreaves(tmax: float, tmin: float, ra_mj_m2_day: float) -> float:
    """ET0 (mm/día) por Hargreaves cuando no hay ET0 Penman-Monteith.

    Ra = radiación extraterrestre (MJ/m²/día). El 0,408 convierte MJ a mm.
    ET0 = 0,0023 · (0,408·Ra) · (Tmean + 17,8) · sqrt(Tmax − Tmin)
    """
    tmean = (tmax + tmin) / 2.0
    dt = max(0.0, tmax - tmin)
    return 0.0023 * (0.408 * ra_mj_m2_day) * (tmean + 17.8) * math.sqrt(dt)


def extraterrestrial_radiation(latitude_deg: float, day_of_year: int) -> float:
    """Ra (MJ/m²/día) FAO-56 ec. 21, para alimentar Hargreaves."""
    phi = math.radians(latitude_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * day_of_year)
    decl = 0.409 * math.sin(2 * math.pi / 365 * day_of_year - 1.39)
    ws_arg = max(-1.0, min(1.0, -math.tan(phi) * math.tan(decl)))
    ws = math.acos(ws_arg)
    gsc = 0.0820  # constante solar MJ/m²/min
    ra = (24 * 60 / math.pi) * gsc * dr * (
        ws * math.sin(phi) * math.sin(decl)
        + math.cos(phi) * math.cos(decl) * math.sin(ws)
    )
    return ra


def kc_for_stage(stage: str, variety: str = "Santo") -> float:
    """Kc de la etapa para una variedad (usa su kc_set)."""
    kc = kc_set_for_variety(variety)
    # la curva de hoja usa initial/development/mid/end
    mapping = {
        "siembra": "initial",
        "emergencia": "initial",
        "cosecha_hoja": kc.get("development") and "development" or "mid",
        "semilla_verde": "mid",
        "semilla_madura": "end",
    }
    key = mapping.get(stage, "mid")
    return kc.get(key, kc.get("mid", 1.0))


@dataclass
class IrrigationAdvice:
    et0_mm: float
    etc_mm: float
    effective_rain_mm: float
    net_need_mm: float
    gross_need_mm: float    # tras fracción de lavado
    note: str


def effective_rain(precip_mm: float) -> float:
    """Lluvia efectiva sencilla (USDA-SCS simplificado para eventos pequeños)."""
    if precip_mm <= 0:
        return 0.0
    if precip_mm < 5:
        return 0.0  # evento pequeño: se evapora
    return round(0.8 * precip_mm - 2.0, 2)


def daily_irrigation(
    *,
    et0_mm: float,
    precip_mm: float,
    stage: str,
    variety: str = "Santo",
    leaching_fraction: float | None = None,
) -> IrrigationAdvice:
    """Necesidad de riego del día (mm = L/m²)."""
    cfg = load_agronomy()["irrigation"]
    lf = cfg["default_leaching_fraction"] if leaching_fraction is None else leaching_fraction

    kc = kc_for_stage(stage, variety)
    etc = kc * et0_mm
    eff_rain = effective_rain(precip_mm)
    net = max(0.0, etc - eff_rain)
    gross = net / (1 - lf) if lf < 1 else net

    note = "Goteo recomendado (follaje seco reduce mancha bacteriana)."
    if lf > 0:
        note += f" Incluye fracción de lavado LF={lf} por agua salina."

    return IrrigationAdvice(
        et0_mm=round(et0_mm, 2),
        etc_mm=round(etc, 2),
        effective_rain_mm=round(eff_rain, 2),
        net_need_mm=round(net, 2),
        gross_need_mm=round(gross, 2),
        note=note,
    )


@dataclass
class WaterBalanceState:
    depletion_mm: float = 0.0   # Dr: agotamiento en zona radical

    def update(self, etc_mm: float, eff_rain_mm: float, irrigation_mm: float = 0.0):
        cfg = load_agronomy()["irrigation"]
        taw = cfg["taw_mm"]
        self.depletion_mm = min(taw, max(0.0,
            self.depletion_mm + etc_mm - eff_rain_mm - irrigation_mm))
        return self.depletion_mm

    def should_irrigate(self) -> bool:
        cfg = load_agronomy()["irrigation"]
        raw = cfg["raw_fraction_p"] * cfg["taw_mm"]
        return self.depletion_mm >= raw
