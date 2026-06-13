"""Carga de las constantes agronómicas versionadas (config/*.yaml).

Toda la agronomía vive en YAML para que el experto la calibre sin tocar código.
"""
from __future__ import annotations

import functools
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@functools.lru_cache(maxsize=1)
def load_agronomy() -> dict:
    with open(CONFIG_DIR / "agronomy.yaml", "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@functools.lru_cache(maxsize=1)
def load_varieties() -> dict:
    with open(CONFIG_DIR / "varieties.yaml", "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get_variety(name: str) -> dict:
    """Devuelve el dict de una variedad por nombre (case-insensitive)."""
    name_l = name.strip().lower()
    for v in load_varieties()["varieties"]:
        if v["name"].lower() == name_l:
            return v
    raise KeyError(f"Variedad desconocida: {name!r}")


def kc_set_for_variety(name: str) -> dict:
    v = get_variety(name)
    return load_agronomy()["kc_sets"][v["kc_set"]]
