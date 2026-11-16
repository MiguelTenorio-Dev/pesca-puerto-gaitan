"""Volumenes calibrados con el SEPEC 2022 y pescadores sinteticos.

Volumen real = SEPEC × factor_subregistro, por mes:
- malecon: lo registrado en el Malecon de Puerto Gaitan (venta directa en la plaza);
- san_miguel: lo registrado en San Miguel (5,5 t repartidas con el perfil mensual del Malecon);
- senora y vichada: lo no registrado, (factor - 1) × registrado, repartido con
  fraccion_informal_vichada.
Los pescadores se derivan para que su volumen esperado reproduzca exactamente esas metas.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd

from pesca import config, red

SITIOS = ("malecon", "san_miguel", "senora", "vichada")
DESEMBARQUE_FIJO = {"malecon": "D_MALECON", "san_miguel": "A02"}
SITIO_SEPEC = {"malecon": "malecon_puerto_gaitan", "san_miguel": "san_miguel_puerto_gaitan"}
KG_POR_T = 1000.0


def meses() -> pd.DataFrame:
    """Meses con registro SEPEC del Malecon: toneladas, dias y si hay veda."""
    sepec = config.cargar_sepec()
    malecon = sepec[sepec["sitio"] == SITIO_SEPEC["malecon"]].copy()
    periodo = pd.PeriodIndex(malecon["periodo"], freq="M")
    return pd.DataFrame(
        {
            "mes": periodo.astype(str),
            "dias": periodo.days_in_month,
            "malecon_t": malecon["toneladas"].to_numpy(),
            "veda": malecon["nota"].fillna("").str.contains("veda").to_numpy(),
        }
    ).set_index("mes")


def metas_volumen() -> pd.DataFrame:
    """Toneladas por mes y sitio (SEPEC × factor_subregistro) y kg/dia de cada sitio."""
    m = meses()
    sepec = config.cargar_sepec()
    total_san_miguel = sepec.loc[sepec["sitio"] == SITIO_SEPEC["san_miguel"], "toneladas"].sum()
    factor = config.parametro("volumen.factor_subregistro")
    fv = config.parametro("poblacion.fraccion_informal_vichada")
    t = pd.DataFrame(index=m.index)
    t["malecon"] = m["malecon_t"]
    t["san_miguel"] = total_san_miguel * m["malecon_t"] / m["malecon_t"].sum()
    informal = (factor - 1) * (t["malecon"] + t["san_miguel"])
    t["senora"] = informal * (1 - fv)
    t["vichada"] = informal * fv
    for s in SITIOS:
        t[f"{s}_kg_dia"] = t[s] * KG_POR_T / m["dias"]
    t["dias"] = m["dias"]
    t["veda"] = m["veda"]
    return t


def actividad() -> pd.Series:
    """Actividad de cada mes frente al mes pico (1 = el mes de mas desembarcos)."""
    m = meses()
    por_dia = m["malecon_t"] / m["dias"]
    return por_dia / por_dia.max()


def actividad_diagnostico() -> float:
    """Actividad de un mes tipico fuera de veda (el que simula el diagnostico)."""
    m = meses()
    return float(actividad()[~m["veda"]].mean())


def _ubicaciones_cercanas(grafo: nx.DiGraph, zona: str) -> list[str]:
    """Nodos de rio a lo sumo a radio_ubicacion_km por agua de la zona."""
    rio = red.subgrafo_modo(grafo, red.CAPA_RIO).to_undirected(as_view=True)
    inicio = red.clave(zona, red.CAPA_RIO)
    radio = config.parametro("poblacion.radio_ubicacion_km")
    cerca = nx.single_source_dijkstra_path_length(rio, inicio, cutoff=radio, weight="distancia_km")
    return sorted(n for n in cerca if grafo.nodes[n]["tipo"] in ("punto_rio", "zona_pesca", "comunidad"))


def desembarque_de(sitio: str, zona: str, desembarque_senora: str) -> str:
    if sitio in DESEMBARQUE_FIJO:
        return DESEMBARQUE_FIJO[sitio]
    if sitio == "senora":
        return desembarque_senora
    return config.parametro("poblacion.desembarque_vichada")[zona]


def generar_poblacion(rng: np.random.Generator, desembarque_senora: str, grafo: nx.DiGraph | None = None) -> pd.DataFrame:
    """Pescadores sinteticos cuyo volumen esperado en el mes pico reproduce las metas.

    Columnas: id, sitio, zona, ubicacion (nodo@rio), desembarque, embarcacion, nevera_buena,
    horas_hielo, kg_por_faena, p_faena_pico (probabilidad de salir a pescar un dia del mes pico).
    """
    grafo = grafo if grafo is not None else red.construir_red()
    p = config.parametro
    metas = metas_volumen()
    p_pico = p("poblacion.faenas_semana") / 7
    kg_base = p("poblacion.kg_por_faena")
    variacion = p("volumen.variacion_pescadores")
    mezcla = p("flota.mezcla")
    tipos, pesos = list(mezcla), np.array(list(mezcla.values()), dtype=float)
    zonas_por_sitio = p("poblacion.zonas_por_sitio")
    cercanas: dict[str, list[str]] = {}

    filas = []
    for sitio in SITIOS:
        meta_pico = metas[f"{sitio}_kg_dia"].max()
        if meta_pico <= 0:
            continue
        n = max(1, round(meta_pico / (kg_base * p_pico)))
        kg = kg_base * rng.uniform(1 - variacion, 1 + variacion, size=n)
        kg *= meta_pico / (kg.sum() * p_pico)  # el volumen esperado da exactamente la meta
        zonas = rng.choice(zonas_por_sitio[sitio], size=n)
        embarcaciones = rng.choice(tipos, size=n, p=pesos / pesos.sum())
        neveras = rng.random(n) < p("cadena_actual.fraccion_nevera_buena")
        for i in range(n):
            zona = str(zonas[i])
            if zona not in cercanas:
                cercanas[zona] = _ubicaciones_cercanas(grafo, zona)
            filas.append(
                {
                    "id": f"{sitio}_{i + 1:02d}",
                    "sitio": sitio,
                    "zona": zona,
                    "ubicacion": str(rng.choice(cercanas[zona])),
                    "desembarque": desembarque_de(sitio, zona, desembarque_senora),
                    "embarcacion": str(embarcaciones[i]),
                    "nevera_buena": bool(neveras[i]),
                    "horas_hielo": p("degradacion.horas_hielo_nevera_nueva" if neveras[i] else "degradacion.horas_hielo_nevera_deteriorada"),
                    "kg_por_faena": float(kg[i]),
                    "p_faena_pico": p_pico,
                }
            )
    return pd.DataFrame(filas)


def aplicar_subsidio_motor(poblacion: pd.DataFrame) -> pd.DataFrame:
    """Subsidio de motor (I6): una fraccion fija de los botes de madera a remo pasa a madera con motor.

    El sorteo usa la semilla general, asi la misma poblacion da siempre los mismos subsidiados.
    """
    p = config.parametro
    pob = poblacion.copy()
    remo = pob.index[pob["embarcacion"] == "madera_remo"]
    rng = np.random.default_rng(p("general.semilla"))
    elegidos = remo[rng.random(len(remo)) < p("inversiones.fraccion_remo_a_motor")]
    pob.loc[elegidos, "embarcacion"] = "madera_motor"
    return pob


def volumen_mensual(poblacion: pd.DataFrame) -> pd.DataFrame:
    """Toneladas esperadas por mes y sitio que produce la poblacion."""
    act = actividad()
    dias = meses()["dias"]
    diario = (poblacion["kg_por_faena"] * poblacion["p_faena_pico"]).groupby(poblacion["sitio"]).sum()
    salida = pd.DataFrame(index=act.index)
    for sitio in SITIOS:
        salida[sitio] = diario.get(sitio, 0.0) * act * dias / KG_POR_T
    return salida
