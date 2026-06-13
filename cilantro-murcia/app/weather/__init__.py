"""Integración meteorológica.

Estrategia (provider.py): Open-Meteo primaria (ET0 FAO + forecast) calibrada con
SIAR (ET0 Penman-Monteith local), AEMET como override de helada oficial, y
climatología de Murcia como fallback offline. Ver PARTE 2-B.
"""
from . import aemet, openmeteo, provider, siar  # noqa: F401
