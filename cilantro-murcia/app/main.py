"""API FastAPI del motor agronómico de cilantro (Murcia) — v2 completa.

Arranque:  uvicorn app.main:app --reload
Docs:      http://localhost:8000/docs
UI web:    http://localhost:8000/
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import __version__, alerts as alerts_mod, calibration, llm, onboarding, service
from .config import load_agronomy, load_varieties
from .db import (Alerta, CicloCultivo, Observacion, Parcela, get_session,
                init_db)
from .models import (BoltingRequest, CicloCreate, IrrigationRequest,
                    ObservacionCreate, OnboardRequest, ParcelaCreate,
                    SowingRequest)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Cilantro Murcia — Motor Agronómico",
    version=__version__,
    description="Motor determinista (GDD, fotoperiodo, espigado, riego ET0, "
                "helada) + persistencia + calibración + alertas. La IA solo "
                "explica, nunca calcula.",
    lifespan=lifespan,
)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


# --------------------------------------------------------------------- básicos
@app.get("/health")
def health():
    return {"status": "ok", "version": __version__,
            "agronomy_config": load_agronomy()["version"]}


@app.get("/varieties")
def varieties():
    return load_varieties()


# ----------------------------------------------------------------- onboarding
@app.post("/onboard")
def onboard(req: OnboardRequest):
    r = onboarding.onboard(req.lat, req.lon, ec_agua_dS_m=req.ec_agua_dS_m,
                           fetch_live=req.fetch_live)
    return r.__dict__


# ------------------------------------------------------------------- parcelas
@app.post("/parcelas")
def create_parcela(req: ParcelaCreate, db: Session = Depends(get_session)):
    data = req.model_dump()
    auto = data.pop("auto_derive")
    micro = data.pop("microclima")
    p = Parcela(**{k: v for k, v in data.items() if v is not None})
    if auto:
        r = onboarding.onboard(req.lat, req.lon, ec_agua_dS_m=req.ec_agua_dS_m,
                               fetch_live=False)
        p.microclima = micro.value if micro else r.microclima
        p.estacion_siar = r.estacion_siar
        p.municipio_ine = r.municipio_ine
        if p.altitud_m is None:
            p.altitud_m = r.altitud_m
    elif micro:
        p.microclima = micro.value
    db.add(p); db.commit(); db.refresh(p)
    return _parcela_dict(p)


@app.get("/parcelas")
def list_parcelas(db: Session = Depends(get_session)):
    return [_parcela_dict(p) for p in db.query(Parcela).all()]


@app.get("/parcelas/{pid}")
def get_parcela(pid: int, db: Session = Depends(get_session)):
    p = db.get(Parcela, pid)
    if not p:
        raise HTTPException(404, "Parcela no encontrada")
    return _parcela_dict(p)


# --------------------------------------------------------------------- ciclos
@app.post("/ciclos")
def create_ciclo(req: CicloCreate, db: Session = Depends(get_session)):
    if not db.get(Parcela, req.parcela_id):
        raise HTTPException(404, "Parcela no encontrada")
    c = CicloCultivo(parcela_id=req.parcela_id, variedad=req.variedad,
                     objetivo=req.objetivo.value, fecha_siembra=req.fecha_siembra)
    db.add(c); db.commit(); db.refresh(c)
    return _ciclo_dict(c)


@app.get("/ciclos/{cid}")
def get_ciclo(cid: int, db: Session = Depends(get_session)):
    c = db.get(CicloCultivo, cid)
    if not c:
        raise HTTPException(404, "Ciclo no encontrado")
    return _ciclo_dict(c)


@app.post("/ciclos/{cid}/daily-update")
def daily_update(cid: int, use_live: bool = False,
                 db: Session = Depends(get_session)):
    """Actualiza GDD/etapa del ciclo y genera alertas del día (con explicación)."""
    c = db.get(CicloCultivo, cid)
    if not c:
        raise HTTPException(404, "Ciclo no encontrado")
    alerts = alerts_mod.update_cycle_and_alert(db, c, use_live=use_live)
    grounding = alerts_mod.alerts_as_grounding(alerts)
    return {
        "ciclo": _ciclo_dict(c),
        "alertas": grounding["alertas"],
        "explanation": llm.explain(grounding),
    }


# -------------------------------------------------------------- observaciones
@app.post("/observaciones")
def create_observacion(req: ObservacionCreate, db: Session = Depends(get_session)):
    if not db.get(CicloCultivo, req.ciclo_id):
        raise HTTPException(404, "Ciclo no encontrado")
    o = Observacion(**req.model_dump())
    db.add(o); db.commit(); db.refresh(o)
    return {"id": o.id, "ciclo_id": o.ciclo_id, "tipo": o.tipo,
            "fecha": o.fecha.isoformat()}


@app.post("/calibracion/run")
def run_calibration(db: Session = Depends(get_session)):
    """Genera propuestas de recalibración a partir de las observaciones reales."""
    return calibration.run_calibration(db)


# ------------------------------------------------------------------- alertas
@app.get("/parcelas/{pid}/alertas")
def list_alertas(pid: int, db: Session = Depends(get_session)):
    rows = db.query(Alerta).filter(Alerta.parcela_id == pid).order_by(
        Alerta.creada.desc()).limit(50).all()
    return [{"tipo": a.tipo, "severidad": a.severidad, "mensaje": a.mensaje,
             "accion": a.accion,
             "fecha_limite": a.fecha_limite.isoformat() if a.fecha_limite else None}
            for a in rows]


# ------------------------------------------------------ recomendaciones (motor)
@app.post("/recommend/bolting")
def recommend_bolting(req: BoltingRequest):
    g = service.bolting_recommendation(
        lat=req.lat, lon=req.lon, variety=req.variety,
        humidity_ok=req.humidity_ok, use_live=req.use_live_weather)
    g["explanation"] = llm.explain({"bolting": g})
    return g


@app.post("/recommend/irrigation")
def recommend_irrigation(req: IrrigationRequest):
    g = service.irrigation_recommendation(
        lat=req.lat, lon=req.lon, variety=req.variety, stage=req.stage,
        leaching_fraction=req.leaching_fraction, use_live=req.use_live_weather)
    g["explanation"] = llm.explain({"irrigation": g})
    return g


@app.post("/recommend/sowing")
def recommend_sowing(req: SowingRequest):
    g = service.sowing_recommendation(
        lat=req.lat, variety=req.variety, microclimate=req.microclimate.value,
        start=req.start, end=req.end, step_days=req.step_days,
        objetivo=req.objetivo.value)
    g["explanation"] = llm.explain({"sowing": g})
    return g


# ---------------------------------------------------------------- helpers/UI
def _parcela_dict(p: Parcela) -> dict:
    return {"id": p.id, "nombre": p.nombre, "lat": p.lat, "lon": p.lon,
            "altitud_m": p.altitud_m, "ph": p.ph, "ec_agua_dS_m": p.ec_agua_dS_m,
            "microclima": p.microclima, "estacion_siar": p.estacion_siar,
            "municipio_ine": p.municipio_ine}


def _ciclo_dict(c: CicloCultivo) -> dict:
    return {"id": c.id, "parcela_id": c.parcela_id, "variedad": c.variedad,
            "objetivo": c.objetivo, "fecha_siembra": c.fecha_siembra.isoformat(),
            "etapa": c.etapa, "gdd_acum": c.gdd_acum, "estado": c.estado}


if WEB_DIR.exists():
    @app.get("/")
    def index():
        return FileResponse(str(WEB_DIR / "index.html"))

    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
