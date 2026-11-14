"""Monte Carlo generico: muestrea los parametros que tienen `rango` en parametros.yaml.

Uso:
    rng = np.random.default_rng(semilla)
    with config.sobrescribir(muestrear(rng)):
        ...  # todo lo que llame a config.parametro ve la muestra
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from pesca import config

PERCENTIL_BAJO, PERCENTIL_ALTO = 5, 95


def muestrear(rng: np.random.Generator) -> dict[str, Any]:
    """Una muestra uniforme de cada parametro con rango (entera si el rango es entero)."""
    muestra: dict[str, Any] = {}
    for ruta, h in config.hojas_parametros():
        if "rango" not in h:
            continue
        minimo, maximo = h["rango"]
        if isinstance(h["valor"], int) and isinstance(minimo, int) and isinstance(maximo, int):
            muestra[ruta] = int(rng.integers(minimo, maximo + 1))
        else:
            muestra[ruta] = float(rng.uniform(minimo, maximo))
    muestra["flota.mezcla"] = muestrear_mezcla(rng)
    return muestra


def muestrear_mezcla(rng: np.random.Generator) -> dict[str, float]:
    """Mezcla de flota con ±variacion_pp en cada tipo, sin negativos y renormalizada."""
    base = config.hoja("flota.mezcla")["valor"]
    pp = config.parametro("flota.variacion_pp")
    crudo = {k: max(0.0, v + rng.uniform(-pp, pp)) for k, v in base.items()}
    total = sum(crudo.values())
    return {k: v / total for k, v in crudo.items()}


def generadores(n: int, semilla: int) -> list[np.random.Generator]:
    """n generadores independientes y reproducibles a partir de una semilla."""
    return [np.random.default_rng(s) for s in np.random.SeedSequence(semilla).spawn(n)]


def correr(funcion: Callable[[int, np.random.Generator], Any], n: int, semilla: int) -> list[Any]:
    """Corre funcion(i, rng) n veces, cada una con su generador y su muestra de parametros."""
    resultados = []
    for i, rng in enumerate(generadores(n, semilla)):
        with config.sobrescribir(muestrear(rng)):
            resultados.append(funcion(i, rng))
    return resultados


def resumir(valores: pd.Series) -> dict[str, float]:
    """Media e intervalo del 90 % (percentiles 5 y 95)."""
    return {
        "media": float(valores.mean()),
        "p5": float(np.percentile(valores, PERCENTIL_BAJO)),
        "p95": float(np.percentile(valores, PERCENTIL_ALTO)),
    }
