"""Demo offline del motor agronómico de cilantro para Murcia.

Ejecuta TODO el núcleo determinista con climatología (sin red), imprimiendo:
  - perfil de fotoperiodo anual a 38°N
  - riesgo de espigado por mes
  - mejor ventana de siembra otoño-invierno + plan escalonado
  - ejemplo de riego ET0

Uso:  python -m cli.demo
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import service  # noqa: E402
from app.data.murcia_climatology import MURCIA_LAT, monthly_normal  # noqa: E402
from app.engine import bolting, photoperiod  # noqa: E402

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def linea(c="="):
    print(c * 64)


def demo_fotoperiodo():
    linea()
    print("FOTOPERIODO MENSUAL A 38°N (Murcia)  — umbral espigado 12 h")
    linea("-")
    for m in range(1, 13):
        doy = date(2025, m, 15).timetuple().tm_yday
        h = photoperiod.daylength_hours(MURCIA_LAT, doy)
        flag = "  <-- DÍA LARGO (riesgo)" if h > 12 else ""
        print(f"  {MESES[m-1]}: {h:5.2f} h{flag}")


def demo_bolting_por_mes(variety="Calypso"):
    linea()
    print(f"RIESGO DE ESPIGADO POR MES (var. {variety}, riego ok)")
    linea("-")
    for m in range(1, 13):
        tmax, _tmin, _p = monthly_normal(m)
        doy = date(2025, m, 15).timetuple().tm_yday
        photo = photoperiod.daylength_hours(MURCIA_LAT, doy)
        res = bolting.bolting_risk(
            recent_tmax=[tmax] * 7, forecast_tmax=[tmax] * 7,
            photoperiod_h=photo, variety=variety, humidity_ok=True)
        bar = "#" * int(res.score / 5)
        print(f"  {MESES[m-1]}: {res.score:5.1f} [{res.band:11s}] {bar}")


def demo_ventana_siembra():
    linea()
    print("OPTIMIZADOR DE VENTANA DE SIEMBRA (otoño-invierno, valle, Calypso)")
    linea("-")
    g = service.sowing_recommendation(
        lat=MURCIA_LAT, variety="Calypso", microclimate="valle",
        start=date(2025, 9, 1), end=date(2026, 3, 1),
        step_days=10, objetivo="hoja")
    print(f"  MEJOR fecha de siembra : {g['best_date']}")
    print(f"  Cosecha de hoja prevista: {g['harvest_date']} "
          f"({g['days_to_harvest']} días)")
    print(f"  Riesgo espigado máx.    : {g['max_bolt_risk']}/100")
    print(f"  Días de helada en ciclo : {g['frost_days']}")
    print("\n  Ranking de fechas (mejor->peor):")
    for c in g["ranking"]:
        print(f"    {c['date']}  score={c['score']:6.1f}  "
              f"bolt_max={c['max_bolt_risk']:5.1f}  helada={c['frost_days']}")
    print("\n  Plan escalonado (suministro continuo):")
    for c in g["stagger_plan"]:
        print(f"    siembra {c['date']} -> cosecha {c['harvest']} "
              f"(bolt_max {c['max_bolt_risk']})")


def demo_riego():
    linea()
    print("RIEGO ET0 (ejemplo etapa cosecha_hoja, julio climatológico)")
    linea("-")
    g = service.irrigation_recommendation(
        lat=MURCIA_LAT, lon=-1.13, variety="Santo", stage="cosecha_hoja",
        leaching_fraction=0.15, use_live=False)
    print(f"  ET0={g['et0_mm']} mm  ETc={g['etc_mm']} mm  "
          f"lluvia_ef={g['effective_rain_mm']} mm")
    print(f"  Necesidad neta : {g['net_need_mm']} L/m²")
    print(f"  Necesidad bruta: {g['gross_need_mm']} L/m² (con lavado)")
    print(f"  Nota: {g['note']}")


def main():
    print("\n*** CILANTRO MURCIA — DEMO DEL MOTOR AGRONÓMICO DETERMINISTA ***\n")
    demo_fotoperiodo()
    demo_bolting_por_mes()
    demo_ventana_siembra()
    demo_riego()
    linea()
    print("Demo completada. Arranca la API con: uvicorn app.main:app --reload")
    linea()


if __name__ == "__main__":
    main()
