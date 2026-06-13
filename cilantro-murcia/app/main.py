"""API FastAPI del motor agronómico de cilantro (Murcia).

Arranque:  uvicorn app.main:app --reload
Docs:      http://localhost:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI

from . import __version__, llm, service
from .config import load_agronomy, load_varieties
from .models import BoltingRequest, IrrigationRequest, SowingRequest

app = FastAPI(
    title="Cilantro Murcia — Motor Agronómico",
    version=__version__,
    description="Motor determinista (GDD, fotoperiodo, espigado, riego ET0, "
                "helada) + explicación LLM. La IA solo explica, nunca calcula.",
)


@app.get("/health")
def health():
    return {"status": "ok", "version": __version__,
            "agronomy_config": load_agronomy()["version"]}


@app.get("/varieties")
def varieties():
    return load_varieties()


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
