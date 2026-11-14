"""Modelo de degradacion (especificacion §6).

RRS(T) = (1 + coef·T)² si T >= -10 °C, 0 si no. Calidad Q = 1 - Σ horas·RRS(T) / VU0.

Estados de conservacion de un lote:
- ambiente: T ambiente;
- icopor_hielo: T de frio mientras dure el hielo; despues el lote sigue a T ambiente;
- congelado: RRS = 0. La congelacion lenta castiga el precio una sola vez;
- falla: corte de luz mas largo que horas_descongelacion; el lote se deteriora a T ambiente.

La perdida se lleva por etapa (faena, rio, espera, carretera) y es aditiva: sirve como
peso del grafo y el diagnostico la reporta por etapa.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pesca import config

AMBIENTE, ICOPOR_HIELO, CONGELADO, FALLA = "ambiente", "icopor_hielo", "congelado", "falla"
ESTADOS = (AMBIENTE, ICOPOR_HIELO, CONGELADO, FALLA)
ETAPAS = ("faena", "rio", "espera", "carretera")
CONGELACION_LENTA = "congelacion_lenta"
ETAPAS_COP = (*ETAPAS, CONGELACION_LENTA)


def rrs(t_c: float) -> float:
    """Tasa relativa de deterioro frente al hielo: RRS(0 °C) = 1 y RRS = 0 por debajo del corte."""
    if t_c < config.parametro("degradacion.t_corte_rrs_c"):
        return 0.0
    return (1 + config.parametro("degradacion.coef_ratkowsky") * t_c) ** 2


def temperatura(estado: str) -> float:
    if estado in (AMBIENTE, FALLA):
        return config.parametro("degradacion.t_ambiente_c")
    if estado == ICOPOR_HIELO:
        return config.parametro("degradacion.t_frio_c")
    if estado == CONGELADO:
        return config.parametro("degradacion.t_congelado_c")
    raise ValueError(f"Estado desconocido: {estado}")


@dataclass
class Lote:
    """Pescado de una faena. `perdida` es la fraccion de vida util consumida en cada etapa."""

    kg: float
    hielo_restante_h: float = 0.0
    congelado: bool = False
    no_llego: bool = False
    perdida: dict[str, float] = field(default_factory=lambda: dict.fromkeys(ETAPAS, 0.0))
    horas: dict[str, float] = field(default_factory=lambda: dict.fromkeys(ETAPAS, 0.0))


def avanzar(lote: Lote, horas: float, etapa: str, estado: str) -> None:
    """Acumula `horas` en `etapa`. En icopor gasta primero el hielo y despues sigue a T ambiente."""
    if etapa not in ETAPAS:
        raise ValueError(f"Etapa desconocida: {etapa}")
    if horas < 0:
        raise ValueError("Las horas no pueden ser negativas")
    vu0 = config.parametro("degradacion.vu0_h")
    if estado == ICOPOR_HIELO:
        con_hielo = min(horas, lote.hielo_restante_h)
        lote.hielo_restante_h -= con_hielo
        grados_hora = con_hielo * rrs(temperatura(ICOPOR_HIELO)) + (horas - con_hielo) * rrs(temperatura(AMBIENTE))
    else:
        grados_hora = horas * rrs(temperatura(estado))
    lote.perdida[etapa] += grados_hora / vu0
    lote.horas[etapa] += horas


def congelar(lote: Lote) -> None:
    """Entra al congelador: deja de deteriorarse y queda marcado para el castigo de precio."""
    lote.congelado = True
    lote.hielo_restante_h = 0.0


def poner_hielo(lote: Lote, horas: float) -> None:
    lote.hielo_restante_h = max(lote.hielo_restante_h, horas)


def perdida_total(lote: Lote) -> float:
    return sum(lote.perdida.values())


def calidad(lote: Lote) -> float:
    """Calidad entre 0 y 1 al momento de la venta (0 si el lote no llego)."""
    if lote.no_llego:
        return 0.0
    return max(0.0, 1.0 - perdida_total(lote))


def factor_precio(q: float) -> float:
    """Factor de precio escalonado segun la calidad."""
    for escalon in config.parametro("precio_calidad.escalones"):
        if q >= escalon["calidad_min"]:
            return escalon["factor"]
    return 0.0


def precio_base() -> float:
    """COP/kg en la plaza de Puerto Gaitan para pescado en perfecto estado."""
    p = config.parametro
    mezcla = p("precios.mezcla_cachama")
    villavicencio = mezcla * p("precios.cachama_cop_kg") + (1 - mezcla) * p("precios.bagre_rayado_cop_kg")
    return villavicencio * p("precios.factor_precio_local")


def valor_lote(lote: Lote, precio: float | None = None) -> dict[str, float]:
    """Valor recibido y COP perdidos por etapa (suman exactamente el total perdido).

    - congelacion_lenta: kg·P0·factor(Q)·(1 - factor_precio_congelado), si el lote se congelo;
    - el resto, kg·P0·(1 - factor(Q)), se reparte en proporcion a la perdida de calidad de cada etapa.
    Un lote que no llego (no pudo remontar) pierde todo en la etapa del rio.
    """
    p0 = precio_base() if precio is None else precio
    q = calidad(lote)
    f = 0.0 if lote.no_llego else factor_precio(q)
    f_cong = config.parametro("degradacion.factor_precio_congelado") if lote.congelado else 1.0
    posible = lote.kg * p0
    recibido = posible * f * f_cong
    por_etapa = dict.fromkeys(ETAPAS_COP, 0.0)
    por_etapa[CONGELACION_LENTA] = posible * f * (1 - f_cong)
    resto = posible * (1 - f)
    total = perdida_total(lote)
    if lote.no_llego:
        por_etapa["rio"] += resto
    elif total > 0:
        for etapa in ETAPAS:
            por_etapa[etapa] += resto * lote.perdida[etapa] / total
    return {
        "kg": lote.kg,
        "calidad": q,
        "factor_precio": f * f_cong,
        "cop_posible": posible,
        "cop_recibido": recibido,
        "cop_perdido": posible - recibido,
        **{f"cop_{e}": v for e, v in por_etapa.items()},
        **{f"perdida_{e}": lote.perdida[e] for e in ETAPAS},
        **{f"horas_{e}": lote.horas[e] for e in ETAPAS},
    }
