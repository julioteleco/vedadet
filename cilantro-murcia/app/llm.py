"""Capa de explicación con LLM — ESTRICTAMENTE aguas abajo del motor.

El LLM NUNCA calcula agronomía. Recibe los números YA calculados por el motor
determinista como contexto de grounding y solo los traduce a lenguaje llano,
redacta alertas y responde preguntas (PARTE 2-D/E).

Si no hay API key configurada, devuelve una explicación determinista de plantilla
(la app sigue siendo 100% funcional sin LLM).
"""
from __future__ import annotations

import json
import os

SYSTEM_PROMPT = (
    "Eres un asistente de cultivo de cilantro para usuarios sin conocimientos en "
    "Murcia (España). Te paso un bloque JSON con cifras agronómicas YA CALCULADAS "
    "por un motor determinista (GDD, riesgo de espigado, riego ET0, helada). "
    "NUNCA inventes ni recalcules números: usa SOLO los del JSON. Explica en "
    "lenguaje claro y cercano qué debe hacer el usuario hoy."
)


def _template_explanation(grounding: dict) -> str:
    """Explicación de respaldo sin LLM, derivada solo de los números del motor."""
    parts = []
    if "bolting" in grounding:
        b = grounding["bolting"]
        parts.append(f"Riesgo de espigado: {b['score']}/100 ({b['band']}). {b['action']}")
    if "irrigation" in grounding:
        i = grounding["irrigation"]
        parts.append(f"Riego hoy: aplica {i['gross_need_mm']} L/m². {i['note']}")
    if "frost" in grounding:
        f = grounding["frost"]
        if f["severity"] != "ninguna":
            parts.append(f"Helada ({f['severity']}): {f['message']}")
    if "sowing" in grounding:
        s = grounding["sowing"]
        parts.append(
            f"Mejor fecha de siembra sugerida: {s['best_date']} "
            f"(riesgo máx. de espigado {s['max_bolt_risk']}/100).")
    if "alertas" in grounding:
        for a in grounding["alertas"]:
            parts.append(f"[{a['tipo']}/{a['severidad']}] {a['mensaje']} {a['accion']}")
    return " ".join(parts) or "Todo en orden: sin acciones para hoy."


def explain(grounding: dict, question: str | None = None) -> str:
    """Genera explicación en lenguaje natural a partir del grounding del motor.

    Usa Anthropic Claude si ANTHROPIC_API_KEY está presente; si no, plantilla.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _template_explanation(grounding)

    try:
        import anthropic
    except ImportError:
        return _template_explanation(grounding)

    client = anthropic.Anthropic(api_key=api_key)
    user_content = (
        "Cifras del motor (grounding, no recalcular):\n"
        + json.dumps(grounding, ensure_ascii=False, indent=2)
    )
    if question:
        user_content += f"\n\nPregunta del usuario: {question}"

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    return "".join(block.text for block in msg.content if block.type == "text")
