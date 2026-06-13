"""Fotoperiodo a partir de latitud y día del año (PARTE 2-A.1).

declinación:  δ = 23,45 · sin(360·(284 + J)/365)
ángulo hor.:  ω = arccos[(sin(z) − sin φ·sin δ)/(cos φ·cos δ)]   z = −0,833°
duración día = 2·ω / 15   (ω en grados)
"""
from __future__ import annotations

import math

ZENITH_CIVIL = -0.833  # corrección de refracción + semidiámetro solar


def solar_declination(day_of_year: int) -> float:
    """Declinación solar (grados) para el día del año J (1-365/366)."""
    return 23.45 * math.sin(math.radians(360.0 * (284 + day_of_year) / 365.0))


def daylength_hours(latitude_deg: float, day_of_year: int,
                    zenith_deg: float = ZENITH_CIVIL) -> float:
    """Duración del día en horas para una latitud y día del año.

    Maneja sol de medianoche / noche polar haciendo clamp del coseno a [-1, 1].
    """
    decl = solar_declination(day_of_year)
    phi = math.radians(latitude_deg)
    d = math.radians(decl)

    denom = math.cos(phi) * math.cos(d)
    if abs(denom) < 1e-12:
        return 12.0
    cos_omega = (math.sin(math.radians(zenith_deg)) - math.sin(phi) * math.sin(d)) / denom
    cos_omega = max(-1.0, min(1.0, cos_omega))  # clamp para latitudes extremas

    omega_deg = math.degrees(math.acos(cos_omega))
    return 2.0 * omega_deg / 15.0


def is_long_day(latitude_deg: float, day_of_year: int, dl_crit: float = 12.0) -> bool:
    """¿El fotoperiodo supera el umbral crítico de día largo?"""
    return daylength_hours(latitude_deg, day_of_year) > dl_crit
