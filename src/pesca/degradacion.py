"""Modelo de degradacion (especificacion §6).

Fase 1: solo la tasa relativa de deterioro RRS(T). La Fase 2 agrega los estados de
conservacion, la calidad por etapas y el factor de precio.
"""

from __future__ import annotations

from pesca import config


def rrs(t_c: float) -> float:
    """Tasa relativa de deterioro frente al hielo: RRS(0 °C) = 1 y RRS = 0 por debajo del corte."""
    if t_c < config.parametro("degradacion.t_corte_rrs_c"):
        return 0.0
    return (1 + config.parametro("degradacion.coef_ratkowsky") * t_c) ** 2
