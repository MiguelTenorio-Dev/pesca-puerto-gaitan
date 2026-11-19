"""Laboratorio de algoritmos sobre el grafo v4 por capas (fase G4): correr, comparar y medir el transbordo."""

from __future__ import annotations

import math

import networkx as nx
import pandas as pd

from pesca import busqueda, config, grafo, pesos

ALGORITMOS = ("dijkstra", "a_estrella", "bfs")
MODOS = {"solo_rio": {"rio", "interno"}, "solo_via": {"via", "interno"}, "rio_y_via": {"rio", "via", "interno"}}


def pares() -> list[tuple[str, str]]:
    return [tuple(p) for p in config.parametro("busqueda_grafo.pares_comparacion")]


def restringir(g: nx.DiGraph, modo: str) -> nx.DiGraph:
    """Subgrafo con solo los arcos del modo pedido (los internos siempre)."""
    return g.edge_subgraph([(u, v) for u, v, a in g.edges(data=True) if a["modo"] in MODOS[modo]]).copy()


def correr(algoritmo: str, g: nx.DiGraph, origen: str, destino: str, cond: pesos.Condiciones, criterio: str = "calidad"):
    """Corre un algoritmo del estado (origen, hielo) hasta el destino en cualquier capa."""
    gc = pesos.expandir_capas(g, cond)
    inicio = (origen, "hielo")
    destinos = {(destino, c) for c in pesos.CAPAS if (destino, c) in gc}
    costo = pesos.funcion_costo(cond, criterio)
    if inicio not in gc or not destinos:
        return busqueda.ResultadoRuta(algoritmo, inicio, None, (), math.inf, math.inf, math.inf, (), 0.0)
    if algoritmo == "dijkstra":
        return busqueda.dijkstra_capas(gc, inicio, destinos, costo)
    if algoritmo == "a_estrella":
        return busqueda.a_estrella_capas(gc, inicio, destinos, costo, pesos.heuristica(gc, destino, cond, criterio))
    if algoritmo == "bfs":
        return busqueda.bfs_niveles(gc, inicio, destinos, costo)[0]
    raise ValueError(f"Algoritmo desconocido: {algoritmo}")


def comparar(g: nx.DiGraph, cond: pesos.Condiciones, lista: list[tuple[str, str]] | None = None, criterio: str = "calidad") -> pd.DataFrame:
    """Dijkstra vs A* vs BFS: costo, horas, km, tramos, estados expandidos y milisegundos."""
    filas = []
    for origen, destino in lista or pares():
        resultados = {a: correr(a, g, origen, destino, cond, criterio) for a in ALGORITMOS}
        optimo = resultados["dijkstra"].costo
        for algoritmo, r in resultados.items():
            filas.append({
                "par": f"{g.nodes[origen]['nombre']} → {g.nodes[destino]['nombre']}", "origen": origen, "destino": destino,
                "algoritmo": algoritmo, "costo": r.costo, "horas": r.horas, "km": r.km, "tramos": r.tramos,
                "nodos_expandidos": r.nodos_expandidos, "ms": r.ms,
                "pct_peor_que_dijkstra": 100 * (r.costo - optimo) / optimo if r.alcanzable and 0 < optimo < math.inf else 0.0,
            })
    return pd.DataFrame(filas)


def por_modos(g: nx.DiGraph, origen: str, destino: str, cond: pesos.Condiciones) -> pd.DataFrame:
    """ΔQ de la mejor ruta usando solo rio, solo via o ambos. El valor del transbordo es solo_rio − rio_y_via."""
    filas = []
    for modo in MODOS:
        sub = restringir(g, modo)
        r = correr("dijkstra", sub, origen, destino, cond) if origen in sub and destino in sub else None
        ok = r is not None and r.alcanzable
        filas.append({"modo": modo, "alcanzable": ok, "dq": r.costo if ok else math.nan, "calidad": max(0.0, 1 - r.costo) if ok else math.nan,
                      "horas": r.horas if ok else math.nan, "km": r.km if ok else math.nan})
    return pd.DataFrame(filas)


def valor_transbordo(tabla: pd.DataFrame) -> float:
    """Cuanta calidad salva poder cambiar de bote a carretera (0 si no cambia nada)."""
    t = tabla.set_index("modo")
    rio, ambos = t.at["solo_rio", "dq"], t.at["rio_y_via", "dq"]
    if math.isnan(ambos):
        return math.nan
    return (min(rio, 1.0) if not math.isnan(rio) else 1.0) - min(ambos, 1.0)


def lugares(g: nx.DiGraph) -> dict[str, str]:
    """Nodos que se pueden elegir como origen o destino: todo lo que no es un punto intermedio ni la salida de un pueblo."""
    return {n: f"{a['nombre']} ({n})" for n, a in g.nodes(data=True) if a.get("parte") != "sale"}


def ruta_texto(g: nx.DiGraph, r) -> list[str]:
    return grafo.ruta_a_texto(g, [n for n, _ in r.camino]) if r.alcanzable else []
