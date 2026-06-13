"""Motor de alertas diarias por ciclo de cultivo (PARTE 2-C/D).

Para un ciclo activo: actualiza GDD/etapa con la meteo del día y emite alertas
deterministas (espigado / riego / helada / cosecha). El LLM las redacta llano.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta

from .config import load_agronomy
from .db import Alerta, CicloCultivo, Parcela, SnapshotMeteo
from .engine import bolting, frost, gdd, irrigation, photoperiod
from .weather import provider


@dataclass
class GeneratedAlert:
    tipo: str
    severidad: str
    mensaje: str
    accion: str
    fecha_limite: date | None = None


def _established(ciclo: CicloCultivo) -> bool:
    return ciclo.etapa not in ("siembra", "emergencia")


def update_cycle_and_alert(session, ciclo: CicloCultivo, *,
                           use_live: bool = True,
                           persist: bool = True) -> list[GeneratedAlert]:
    """Actualiza GDD/etapa del ciclo y genera las alertas del día."""
    parcela: Parcela = ciclo.parcela
    wx = provider.get_weather(
        parcela.lat, parcela.lon, use_live=use_live,
        municipio_ine=parcela.municipio_ine)

    today = date.today()
    doy = today.timetuple().tm_yday
    photo = photoperiod.daylength_hours(parcela.lat, doy)

    # avanza GDD del día y persiste snapshot
    gdd_today = gdd.gdd_day(wx.forecast_tmax[0], wx.today_tmin)
    ciclo.gdd_acum = round(ciclo.gdd_acum + gdd_today, 1)
    ciclo.etapa = gdd.stage_from_gdd(ciclo.gdd_acum)

    if persist:
        session.add(SnapshotMeteo(
            parcela_id=parcela.id, fecha=today,
            tmax=wx.forecast_tmax[0], tmin=wx.today_tmin,
            precip=wx.today_precip, et0=wx.et0_today,
            fotoperiodo=round(photo, 2), fuente=wx.source))

    alerts: list[GeneratedAlert] = []

    # --- helada ---
    fa = frost.check_frost(wx.today_tmin, established=_established(ciclo),
                           aemet_warning=wx.aemet_frost_warning)
    if fa.severity != "ninguna":
        alerts.append(GeneratedAlert("helada", fa.severity, fa.message,
                                     "Cubre con manta térmica / túnel esta noche.",
                                     today))

    # --- espigado ---
    br = bolting.bolting_risk(
        recent_tmax=wx.recent_tmax, forecast_tmax=wx.forecast_tmax,
        photoperiod_h=photo, variety=ciclo.variedad, humidity_ok=True)
    if br.band != "seguro":
        sev = "alta" if br.band == "alto" else "media"
        alerts.append(GeneratedAlert("espigado", sev,
            f"Riesgo de espigado {br.score}/100 ({br.band}).", br.action, today))

    # --- riego ---
    adv = irrigation.daily_irrigation(
        et0_mm=wx.et0_today, precip_mm=wx.today_precip, stage=ciclo.etapa,
        variety=ciclo.variedad,
        leaching_fraction=(0.15 if (parcela.ec_agua_dS_m or 0) > 1.5 else None))
    if adv.gross_need_mm > 0.5:
        alerts.append(GeneratedAlert("regar", "media",
            f"Necesidad de riego hoy: {adv.gross_need_mm} L/m².",
            adv.note, today))

    # --- cosecha ---
    s = load_agronomy()["gdd_stages"]
    if ciclo.objetivo == "hoja" and ciclo.gdd_acum >= s["first_leaf_harvest"]:
        alerts.append(GeneratedAlert("cosecha", "media",
            "Hoja lista para cosecha (cut-and-come-again).",
            "Corta tallos externos a 10-15 cm, máx. 1/3. El corte frecuente "
            "retrasa el espigado.", today))
    elif ciclo.objetivo == "semilla" and ciclo.gdd_acum >= s["seed_maturity"]:
        alerts.append(GeneratedAlert("cosecha", "media",
            "Semilla en madurez.", "Cosecha cuando las umbelas pardeen.", today))

    if persist:
        for a in alerts:
            session.add(Alerta(parcela_id=parcela.id, ciclo_id=ciclo.id,
                               tipo=a.tipo, severidad=a.severidad,
                               mensaje=a.mensaje, accion=a.accion,
                               fecha_limite=a.fecha_limite))
        session.commit()

    return alerts


def alerts_as_grounding(alerts: list[GeneratedAlert]) -> dict:
    """Empaqueta las alertas para grounding del LLM."""
    return {"alertas": [asdict(a) for a in alerts]}
