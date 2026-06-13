"""Motor agronómico determinista para cultivo de cilantro en Murcia.

Todos los cálculos agronómicos viven aquí. El LLM SOLO explica estos números,
nunca los calcula (ver PARTE 2-D del documento de base).
"""
from . import bolting, frost, gdd, irrigation, photoperiod, sowing_window  # noqa: F401
