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


def componentes_dfs(grafo: nx.Graph) -> list[set[str]]:
    """Componentes conexos por DFS (pila explicita), ignorando el sentido de los arcos."""
    vecinos = {n: set() for n in grafo.nodes}
    for u, v in grafo.edges():
        vecinos[u].add(v)
        vecinos[v].add(u)
    visitados: set[str] = set()
    componentes = []
    for inicio in grafo.nodes:
        if inicio in visitados:
            continue
        componente, pila = set(), [inicio]
        visitados.add(inicio)
        while pila:
            u = pila.pop()
            componente.add(u)
            for v in vecinos[u] - visitados:
                visitados.add(v)
                pila.append(v)
        componentes.append(componente)
    return componentes


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


# ---------------------------------------------------------------- grafo v4 por capas (adenda §1, §3.7, §3.9; fase G4)
#
# Los nodos son estados (lugar, capa). El costo de un arco depende de la hora t a la que se entra
# (el hielo se acaba), asi que la funcion de costo recibe t:  costo(u, v, datos, t) -> (w, τ) o None.
# Dijkstra es valido porque w >= 0 y el costo cumple FIFO: llegar mas tarde nunca abarata lo que sigue
# (adenda §3.7). La etiqueta de cada estado es (w, t).

Costo = Callable[[object, object, dict, float], "tuple[float, float] | None"]


@dataclass(frozen=True)
class ResultadoRuta:
    algoritmo: str
    origen: object
    destino: object  # el estado de llegada (None si no se llego)
    camino: tuple  # () si no hay camino
    costo: float
    horas: float
    km: float
    explorados: tuple  # orden en que cada estado sale de la cola
    ms: float

    @property
    def alcanzable(self) -> bool:
        return bool(self.camino)

    @property
    def nodos_expandidos(self) -> int:
        return len(self.explorados)

    @property
    def tramos(self) -> int:
        return max(0, len(self.camino) - 1)


def _como_conjunto(destinos) -> set:
    """Un estado (tupla) o una coleccion de estados (set, frozenset o list)."""
    if destinos is None:
        return set()
    return set(destinos) if isinstance(destinos, (set, frozenset, list)) else {destinos}


def _km(grafo: nx.DiGraph, camino: tuple) -> float:
    return float(sum(grafo.edges[u, v].get("d_km", 0.0) for u, v in zip(camino, camino[1:])))


def _busqueda_t(algoritmo: str, grafo: nx.DiGraph, origen, destinos, costo: Costo, h, t0: float):
    """Mejor primero con prioridad w + h(n) y etiqueta (w, t). Con h = 0 es Dijkstra.

    Sin destinos recorre todo y devuelve las etiquetas (para matrices de costos).
    """
    inicio = time.perf_counter()
    objetivo = _como_conjunto(destinos)
    w = {origen: 0.0}
    t = {origen: t0}
    previo: dict = {origen: None}
    llegada = itertools.count()
    cola = [(h(origen), h(origen), next(llegada), origen)]
    cerrados: set = set()
    explorados: list = []
    alcanzado = None
    while cola:
        _, _, _, u = heapq.heappop(cola)
        if u in cerrados:
            continue
        cerrados.add(u)
        explorados.append(u)
        if u in objetivo:
            alcanzado = u
            break
        for v, datos in grafo.succ[u].items():
            if v in cerrados:
                continue
            c = costo(u, v, datos, t[u])
            if c is None:
                continue
            dw, tau = c
            if dw < 0:
                raise ValueError(f"Peso negativo en {u} → {v}: Dijkstra y A* exigen pesos ≥ 0")
            nuevo = w[u] + dw
            if nuevo < w.get(v, math.inf):
                w[v], t[v], previo[v] = nuevo, t[u] + tau, u
                hv = h(v)
                heapq.heappush(cola, (nuevo + hv, hv, next(llegada), v))
    ms = 1000 * (time.perf_counter() - inicio)
    return w, t, previo, explorados, alcanzado, ms


def _resultado(algoritmo, grafo, origen, w, t, previo, explorados, alcanzado, ms, t0) -> ResultadoRuta:
    if alcanzado is None:
        return ResultadoRuta(algoritmo, origen, None, (), math.inf, math.inf, math.inf, tuple(explorados), ms)
    camino = _reconstruir(previo, alcanzado)
    return ResultadoRuta(algoritmo, origen, alcanzado, camino, w[alcanzado], t[alcanzado] - t0, _km(grafo, camino), tuple(explorados), ms)


def dijkstra_capas(grafo: nx.DiGraph, origen, destinos, costo: Costo, t0: float = 0.0) -> ResultadoRuta:
    """Busqueda de costo uniforme hasta el primer estado de `destinos` que sale de la cola."""
    _validar_estado(grafo, origen)
    salida = _busqueda_t("dijkstra", grafo, origen, destinos, costo, lambda _: 0.0, t0)
    return _resultado("dijkstra", grafo, origen, *salida, t0)


def a_estrella_capas(grafo: nx.DiGraph, origen, destinos, costo: Costo, h: Callable, t0: float = 0.0) -> ResultadoRuta:
    """A*: Dijkstra guiado por h. Da el mismo costo si h es admisible y consistente (adenda §3.9)."""
    _validar_estado(grafo, origen)
    salida = _busqueda_t("a_estrella", grafo, origen, destinos, costo, h, t0)
    return _resultado("a_estrella", grafo, origen, *salida, t0)


def dijkstra_todos(grafo: nx.DiGraph, origen, costo: Costo, t0: float = 0.0) -> tuple[dict, dict, dict]:
    """Etiquetas (w, t) y predecesores de todos los estados alcanzables desde el origen."""
    _validar_estado(grafo, origen)
    w, t, previo, *_ = _busqueda_t("dijkstra", grafo, origen, None, costo, lambda _: 0.0, t0)
    return w, t, previo


def camino_hasta(previo: dict, destino) -> tuple:
    return _reconstruir(previo, destino)


def bfs_niveles(grafo: nx.DiGraph, origen, destinos=None, costo: Costo | None = None) -> tuple[ResultadoRuta, dict]:
    """BFS: niveles (numero de tramos desde el origen), alcanzabilidad y la ruta de menos saltos.

    `costo` solo sirve para saltar arcos infactibles y para reportar el costo real de la ruta hallada.
    """
    _validar_estado(grafo, origen)
    inicio = time.perf_counter()
    objetivo = _como_conjunto(destinos)
    nivel = {origen: 0}
    previo: dict = {origen: None}
    cola = deque([origen])
    explorados: list = []
    alcanzado = None
    while cola:
        u = cola.popleft()
        explorados.append(u)
        if u in objetivo:
            alcanzado = u
            break
        for v, datos in grafo.succ[u].items():
            if v in nivel or (costo is not None and costo(u, v, datos, 0.0) is None):
                continue
            nivel[v], previo[v] = nivel[u] + 1, u
            cola.append(v)
    ms = 1000 * (time.perf_counter() - inicio)
    if alcanzado is None:
        return ResultadoRuta("bfs", origen, None, (), math.inf, math.inf, math.inf, tuple(explorados), ms), nivel
    camino = _reconstruir(previo, alcanzado)
    w, t = 0.0, 0.0
    for u, v in zip(camino, camino[1:]):
        c = costo(u, v, grafo.edges[u, v], t) if costo is not None else (1.0, 0.0)
        w, t = w + c[0], t + c[1]
    return ResultadoRuta("bfs", origen, alcanzado, camino, w, t, _km(grafo, camino), tuple(explorados), ms), nivel


def puntos_articulacion(grafo: nx.Graph) -> tuple[set, list]:
    """Puntos de articulacion y puentes (Tarjan, DFS) de la proyeccion no dirigida.

    Un punto de articulacion es un nodo que, si se quita, desconecta el grafo; un puente, un tramo.
    """
    vecinos = {n: set() for n in grafo.nodes}
    for u, v in grafo.edges():
        if u != v:
            vecinos[u].add(v)
            vecinos[v].add(u)
    orden, bajo, padre = {}, {}, {}
    articulaciones, puentes = set(), []
    contador = itertools.count()
    for raiz in grafo.nodes:
        if raiz in orden:
            continue
        padre[raiz] = None
        orden[raiz] = bajo[raiz] = next(contador)
        hijos_raiz = 0
        pila = [(raiz, iter(sorted(vecinos[raiz], key=str)))]
        while pila:
            u, it = pila[-1]
            avanzo = False
            for v in it:
                if v not in orden:
                    padre[v] = u
                    orden[v] = bajo[v] = next(contador)
                    if u == raiz:
                        hijos_raiz += 1
                    pila.append((v, iter(sorted(vecinos[v], key=str))))
                    avanzo = True
                    break
                if v != padre[u]:
                    bajo[u] = min(bajo[u], orden[v])
            if avanzo:
                continue
            pila.pop()
            p = padre[u]
            if p is not None:
                bajo[p] = min(bajo[p], bajo[u])
                if bajo[u] > orden[p]:
                    puentes.append((p, u))
                if padre[p] is not None and bajo[u] >= orden[p]:
                    articulaciones.add(p)
        if hijos_raiz > 1:
            articulaciones.add(raiz)
    return articulaciones, puentes


def _validar_estado(grafo: nx.DiGraph, nodo) -> None:
    if nodo not in grafo:
        raise KeyError(f"El nodo '{nodo}' no está en el grafo")
