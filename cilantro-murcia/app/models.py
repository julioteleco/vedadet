"""Modelo de datos (entidades) — PARTE 2-C del documento de base.

Pydantic para la API. En producción se mapean a PostgreSQL + PostGIS.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Microclimate(str, Enum):
    costa = "costa"
    valle = "valle"
    altiplano = "altiplano"


class Goal(str, Enum):
    hoja = "hoja"
    semilla = "semilla"


class Parcela(BaseModel):
    id: Optional[int] = None
    lat: float
    lon: float
    altitud_m: Optional[float] = None
    tipo_suelo: Optional[str] = None
    ph: Optional[float] = None
    ec_agua_dS_m: Optional[float] = Field(
        None, description="EC del agua de riego. CRÍTICO en Murcia: medir en campo.")
    microclima: Microclimate = Microclimate.valle
    estacion_siar: Optional[str] = None


class CicloCultivo(BaseModel):
    parcela_id: int
    variedad: str = "Calypso"
    fecha_siembra: date
    objetivo: Goal = Goal.hoja
    gdd_acum: float = 0.0
    etapa: str = "siembra"


# ---- Peticiones / respuestas de la API ----

class BoltingRequest(BaseModel):
    lat: float = 37.98
    lon: float = -1.13
    variety: str = "Santo"
    humidity_ok: bool = True
    use_live_weather: bool = True


class IrrigationRequest(BaseModel):
    lat: float = 37.98
    lon: float = -1.13
    variety: str = "Santo"
    stage: str = "cosecha_hoja"
    leaching_fraction: Optional[float] = None
    use_live_weather: bool = True


class SowingRequest(BaseModel):
    lat: float = 37.98
    lon: float = -1.13
    variety: str = "Calypso"
    microclimate: Microclimate = Microclimate.valle
    start: date
    end: date
    step_days: int = 7
    objetivo: Goal = Goal.hoja


class Alert(BaseModel):
    tipo: str            # sembrar | regar | espigado | helada | cosecha
    severidad: str       # ninguna | media | alta
    mensaje: str
    accion: str
    fecha_limite: Optional[date] = None


class OnboardRequest(BaseModel):
    lat: float = 37.98
    lon: float = -1.13
    ec_agua_dS_m: Optional[float] = None
    fetch_live: bool = True


class ParcelaCreate(BaseModel):
    nombre: str = "Mi parcela"
    lat: float
    lon: float
    altitud_m: Optional[float] = None
    tipo_suelo: Optional[str] = None
    ph: Optional[float] = None
    ec_agua_dS_m: Optional[float] = None
    microclima: Optional[Microclimate] = None
    auto_derive: bool = True   # deriva microclima/SIAR/municipio en el onboarding


class CicloCreate(BaseModel):
    parcela_id: int
    variedad: str = "Calypso"
    objetivo: Goal = Goal.hoja
    fecha_siembra: date


class ObservacionCreate(BaseModel):
    ciclo_id: int
    tipo: str            # emergencia | primera_hoja | espigado | semilla
    fecha: date
    gdd_al_observar: Optional[float] = None
    tmax_al_observar: Optional[float] = None
    nota: Optional[str] = None
