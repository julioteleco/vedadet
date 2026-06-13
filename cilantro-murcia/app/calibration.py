"""Bucle de calibración (Recomendación #4 — la tarea de datos de mayor palanca).

Convierte las constantes ESTIMADAS en valores locales validados usando las
observaciones fenológicas reales registradas por ciclo:

  - GDD real a emergencia / primera hoja / semilla  -> recalibra gdd_stages
  - Tmax observada al espigar                        -> recalibra T_bolt
  - Retraso de espigado relativo entre variedades    -> recalibra bolt_factor

Devuelve PROPUESTAS de ajuste (no sobrescribe el YAML automáticamente: el
agrónomo revisa y aplica). Persiste en config/calibration_local.yaml.
"""
from __future__ import annotations

import statistics
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import CONFIG_DIR, load_agronomy
from .db import CicloCultivo, Observacion

LOCAL_CAL = CONFIG_DIR / "calibration_local.yaml"

# Mapeo tipo de observación -> clave de gdd_stages
_STAGE_KEY = {
    "emergencia": "emergence",
    "primera_hoja": "first_leaf_harvest",
    "semilla": "seed_maturity",
}


def propose_gdd_stages(session: Session, min_samples: int = 3) -> dict:
    """Propone nuevos umbrales GDD a partir de la mediana observada por etapa."""
    agro = load_agronomy()["gdd_stages"]
    obs = session.execute(
        select(Observacion).where(Observacion.gdd_al_observar.is_not(None))
    ).scalars().all()

    by_stage: dict[str, list[float]] = {}
    for o in obs:
        key = _STAGE_KEY.get(o.tipo)
        if key:
            by_stage.setdefault(key, []).append(o.gdd_al_observar)

    proposals = {}
    for key, vals in by_stage.items():
        if len(vals) >= min_samples:
            proposals[key] = {
                "current": agro.get(key),
                "proposed": round(statistics.median(vals), 1),
                "n": len(vals),
            }
    return proposals


def propose_t_bolt(session: Session, min_samples: int = 3) -> dict | None:
    """Si hay observaciones de espigado con Tmax, propone bajar/subir T_bolt.

    Si el cilantro espiga consistentemente por debajo del T_bolt actual,
    propone bajarlo (Recomendación #6).
    """
    cfg = load_agronomy()["bolting"]
    obs = session.execute(
        select(Observacion).where(
            Observacion.tipo == "espigado",
            Observacion.tmax_al_observar.is_not(None),
        )
    ).scalars().all()
    if len(obs) < min_samples:
        return None
    tmaxes = [o.tmax_al_observar for o in obs]
    observed = round(statistics.median(tmaxes), 1)
    return {
        "current_t_bolt": cfg["t_bolt"],
        "observed_median_tmax_at_bolt": observed,
        "proposed_t_bolt": observed,
        "n": len(obs),
        "note": ("Espiga por debajo del umbral actual: conviene BAJAR T_bolt."
                 if observed < cfg["t_bolt"] else
                 "Umbral coherente o conviene subirlo ligeramente."),
    }


def propose_variety_factors(session: Session, min_samples: int = 2) -> dict:
    """Recalibra el ranking de resistencia comparando días-a-espigado por variedad.

    Usa el ciclo: días desde siembra hasta observación 'espigado'. Más días =
    más resistente -> factor menor, normalizado contra 'Santo'.
    """
    rows = session.execute(
        select(CicloCultivo, Observacion)
        .join(Observacion, Observacion.ciclo_id == CicloCultivo.id)
        .where(Observacion.tipo == "espigado")
    ).all()

    days_by_variety: dict[str, list[int]] = {}
    for ciclo, obs in rows:
        days = (obs.fecha - ciclo.fecha_siembra).days
        if days > 0:
            days_by_variety.setdefault(ciclo.variedad, []).append(days)

    medians = {v: statistics.median(d) for v, d in days_by_variety.items()
               if len(d) >= min_samples}
    if "Santo" not in medians or not medians:
        return {}

    santo = medians["Santo"]
    proposals = {}
    for v, med in medians.items():
        # factor proporcional inverso a la resistencia relativa (Santo = 1.0)
        factor = round(min(1.5, max(0.5, santo / med)), 3)
        proposals[v] = {"median_days_to_bolt": med, "proposed_bolt_factor": factor}
    return proposals


def run_calibration(session: Session) -> dict:
    """Ejecuta todas las propuestas y las persiste en calibration_local.yaml."""
    report = {
        "gdd_stages": propose_gdd_stages(session),
        "t_bolt": propose_t_bolt(session),
        "variety_factors": propose_variety_factors(session),
    }
    with open(LOCAL_CAL, "w", encoding="utf-8") as fh:
        yaml.safe_dump(report, fh, allow_unicode=True, sort_keys=False)
    return report
