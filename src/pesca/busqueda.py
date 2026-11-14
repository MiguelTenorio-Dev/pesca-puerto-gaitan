"""Dijkstra, A* y BFS propios (material del curso), mas su comparacion.

Las tres funciones reciben un grafo dirigido de networkx y devuelven un ResultadoBusqueda
con la ruta, su costo y el orden en que se exploraron los nodos. El peso es una funcion
(u, v, datos) -> costo o None; None significa que la arista no se puede usar.
Los tests las validan contra networkx.
"""

from __future__ import annotations

import heapq
import itertools
import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

import networkx as nx
import pandas as pd

from pesca import config, transporte

ALGORITMOS = ("dijkstra", "a_estrella", "bfs")

Peso = Callable[[str, str, dict], float | None]


@dataclass(frozen=True)
class ResultadoBusqueda:
    algoritmo: str
    origen: str
    destino: str
    ruta: tuple[str, ...]  # () si no hay camino
    costo: float  # costo de la ruta con el peso dado; inf si no hay camino
    explorados: tuple[str, ...]  # orden de exploracion: cada nodo cuando sale de la cola
    tiempo_computo_s: float

    @property
    def alcanzable(self) -> bool:
        return bool(self.ruta)

    @property
    def tramos(self) -> int:
        return max(0, len(self.ruta) - 1)

    @property
    def n_explorados(self) -> int:
        return len(self.explorados)


def _validar(grafo: nx.DiGraph, origen: str, destino: str) -> None:
    for nodo in (origen, destino):
        if nodo not in grafo:
            raise KeyError(f"El nodo '{nodo}' no está en el grafo")


def _reconstruir(previo: dict[str, str | None], destino: str) -> tuple[str, ...]:
    if destino not in previo:
        return ()
    ruta = [destino]
    while previo[ruta[-1]] is not None:
        ruta.append(previo[ruta[-1]])
    return tuple(reversed(ruta))


def _mejor_primero(
    algoritmo: str, grafo: nx.DiGraph, origen: str, destino: str, peso: Peso, heuristica: Callable[[str], float]
) -> ResultadoBusqueda:
    """Busqueda por mejor primero con prioridad g + h. Con h = 0 es Dijkstra.

    Cola de prioridad (heapq) con borrado perezoso: un nodo puede entrar varias veces y solo
    cuenta la primera vez que sale. Los empates en f se rompen a favor del menor h y despues
    por orden de llegada, para que el resultado sea determinista.
    """
    _validar(grafo, origen, destino)
    inicio = time.perf_counter()
    g = {origen: 0.0}
    previo: dict[str, str | None] = {origen: None}
    llegada = itertools.count()
    h0 = heuristica(origen)
    cola = [(h0, h0, next(llegada), origen)]
    cerrados: set[str] = set()
    explorados: list[str] = []

    while cola:
        _, _, _, u = heapq.heappop(cola)
        if u in cerrados:
            continue
        cerrados.add(u)
        explorados.append(u)
        if u == destino:
            break
        for v, datos in grafo.succ[u].items():
            if v in cerrados:
                continue
            w = peso(u, v, datos)
            if w is None:
                continue
            if w < 0:
                raise ValueError(f"Peso negativo en {u} → {v}: Dijkstra y A* exigen pesos ≥ 0")
            nuevo = g[u] + w
            if nuevo < g.get(v, math.inf):
                g[v] = nuevo
                previo[v] = u
                hv = heuristica(v)
                heapq.heappush(cola, (nuevo + hv, hv, next(llegada), v))

    alcanzado = destino in cerrados
    return ResultadoBusqueda(
        algoritmo=algoritmo,
        origen=origen,
        destino=destino,
        ruta=_reconstruir(previo, destino) if alcanzado else (),
        costo=g[destino] if alcanzado else math.inf,
        explorados=tuple(explorados),
        tiempo_computo_s=time.perf_counter() - inicio,
    )


def dijkstra(grafo: nx.DiGraph, origen: str, destino: str, peso: Peso) -> ResultadoBusqueda:
    """Ruta de costo minimo. Explora en orden de costo acumulado desde el origen."""
    return _mejor_primero("dijkstra", grafo, origen, destino, peso, lambda _: 0.0)


def a_estrella(
    grafo: nx.DiGraph, origen: str, destino: str, peso: Peso, heuristica: Callable[[str], float]
) -> ResultadoBusqueda:
    """Ruta de costo minimo guiada hacia el destino. Optima si la heuristica es admisible y consistente."""
    return _mejor_primero("a_estrella", grafo, origen, destino, peso, heuristica)


def bfs(grafo: nx.DiGraph, origen: str, destino: str, peso: Peso | None = None) -> ResultadoBusqueda:
    """Ruta con menos tramos. Ignora km, corriente y deterioro.

    `peso` solo sirve para saltar aristas infactibles y para reportar el costo real de la
    ruta encontrada. Sin peso, el costo es el numero de tramos.
    """
    _validar(grafo, origen, destino)
    inicio = time.perf_counter()
    previo: dict[str, str | None] = {origen: None}
    cola = deque([origen])
    explorados: list[str] = []
    while cola:
        u = cola.popleft()
        explorados.append(u)
        if u == destino:
            break
        for v, datos in grafo.succ[u].items():
            if v in previo or (peso is not None and peso(u, v, datos) is None):
                continue
            previo[v] = u
            cola.append(v)

    ruta = _reconstruir(previo, destino)
    if not ruta:
        costo = math.inf
    elif peso is None:
        costo = float(len(ruta) - 1)
    else:
        costo = sum(peso(u, v, grafo.edges[u, v]) for u, v in zip(ruta, ruta[1:]))
    return ResultadoBusqueda("bfs", origen, destino, ruta, costo, tuple(explorados), time.perf_counter() - inicio)


# ---------------------------------------------------------------- comparacion


def correr(
    algoritmo: str, grafo: nx.DiGraph, origen: str, destino: str, perfil: transporte.Perfil, criterio: str = "perdida"
) -> ResultadoBusqueda:
    """Corre un algoritmo con el peso y la heuristica que corresponden al perfil."""
    w = transporte.peso(perfil, criterio)
    if algoritmo == "dijkstra":
        return dijkstra(grafo, origen, destino, w)
    if algoritmo == "a_estrella":
        return a_estrella(grafo, origen, destino, w, transporte.heuristica(grafo, destino, perfil, criterio))
    if algoritmo == "bfs":
        return bfs(grafo, origen, destino, w)
    raise ValueError(f"Algoritmo desconocido: {algoritmo}")


def comparar(
    grafo: nx.DiGraph,
    pares: list[tuple[str, str]],
    perfil: transporte.Perfil,
    criterio: str = "perdida",
) -> pd.DataFrame:
    """Tabla Dijkstra vs A* vs BFS: costo, horas, km, tramos, nodos explorados y tiempo de computo."""
    filas = []
    for origen, destino in pares:
        resultados = {a: correr(a, grafo, origen, destino, perfil, criterio) for a in ALGORITMOS}
        optimo = resultados["dijkstra"].costo
        for algoritmo, r in resultados.items():
            fila = {
                "par": f"{grafo.nodes[origen]['nombre']} → {grafo.nodes[destino]['nombre']}",
                "origen": origen,
                "destino": destino,
                "algoritmo": algoritmo,
                "costo": r.costo,
                "tramos": r.tramos,
                "nodos_explorados": r.n_explorados,
                "ms": 1000 * r.tiempo_computo_s,
                "pct_peor_que_dijkstra": 100 * (r.costo - optimo) / optimo if optimo > 0 and r.alcanzable else 0.0,
                "horas": math.nan,
                "km": math.nan,
            }
            if r.alcanzable:
                resumen = transporte.resumen_ruta(grafo, r.ruta, perfil)
                fila["horas"], fila["km"] = resumen["horas"], resumen["km"]
            filas.append(fila)
    return pd.DataFrame(filas)


def pares_comparacion() -> list[tuple[str, str]]:
    return [tuple(par) for par in config.parametro("busqueda.pares_comparacion")]
