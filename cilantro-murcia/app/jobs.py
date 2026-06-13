"""Jobs programados (PARTE 2-E).

`run_daily_update` recorre los ciclos activos, actualiza GDD/etapa, genera
alertas y las envía por push. Pensado para un cron / APScheduler / Cloud Scheduler
que llame a este punto de entrada una vez al día.
"""
from __future__ import annotations

import logging

from .alerts import update_cycle_and_alert
from .db import CicloCultivo, SessionLocal
from .notifications import notify

logger = logging.getLogger("cilantro.jobs")


def run_daily_update(use_live: bool = True, push_token: str | None = None) -> dict:
    """Procesa todos los ciclos activos. Devuelve resumen."""
    session = SessionLocal()
    summary = {"ciclos": 0, "alertas": 0}
    try:
        ciclos = session.query(CicloCultivo).filter(
            CicloCultivo.estado == "activo").all()
        for ciclo in ciclos:
            alerts = update_cycle_and_alert(session, ciclo, use_live=use_live)
            summary["ciclos"] += 1
            summary["alertas"] += len(alerts)
            if push_token:
                for a in alerts:
                    if a.severidad in ("alta", "media"):
                        notify(push_token, f"Cilantro: {a.tipo}",
                               f"{a.mensaje} {a.accion}")
        logger.info("Job diario: %s", summary)
        return summary
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from .db import init_db
    init_db()
    print(run_daily_update(use_live=False))
