"""Pruebas 5, 6 y 7 de la adenda (§7) sobre el grafo v4 por capas."""

import itertools
import random

import networkx as nx
import pytest

from pesca import busqueda, grafo, laboratorio, pesos

G = grafo.construir_grafo()
COND = pesos.Condiciones(bote="madera_remo", temporada="aguas_bajas", nevera="deteriorada", acopios=frozenset({"CP01", "CP03"}))


def _todas_las_condiciones():
    for bote in ("madera_remo", "madera_motor", "aluminio_motor"):
        for temporada in ("aguas_bajas", "aguas_altas"):
            for nevera in pesos.NEVERAS:
                yield pesos.Condiciones(bote=bote, temporada=temporada, nevera=nevera, acopios=frozenset({"CP01", "CP03"}))


# ---------------------------------------------------------------- prueba 5: Dijkstra


@pytest.mark.parametrize("criterio", ["tiempo", "distancia"])
def test_dijkstra_igual_a_networkx_en_200_pares(criterio):
    gc = pesos.expandir_capas(G, COND)
    costo = pesos.funcion_costo(COND, criterio)
    rng = random.Random(42)
    estados = list(gc.nodes)
    pares = [(rng.choice(estados), rng.choice(estados)) for _ in range(200)]
    clave = "tau" if criterio == "tiempo" else "d_km"
    for o, d in pares:
        r = busqueda.dijkstra_capas(gc, o, {d}, costo)
        if nx.has_path(gc, o, d):
            assert r.costo == pytest.approx(nx.dijkstra_path_length(gc, o, d, weight=clave), abs=1e-9)
        else:
            assert not r.alcanzable


def _grafo_pequeno(semilla: int) -> nx.DiGraph:
    """8 lugares al azar con rio (en los dos sentidos), via y un pueblo dividido con cuarto frio."""
    rng = random.Random(semilla)
    g = nx.DiGraph()
    for k in range(8):
        g.add_node(f"n{k}", lat=4 + rng.random() * 0.1, lon=-72 + rng.random() * 0.1, tipo="punto_rio", nombre=f"n{k}")
    g.add_node("X:entra", lat=4.05, lon=-71.95, tipo="centro_poblado", nombre="X")
    g.add_node("X:sale", lat=4.05, lon=-71.95, tipo="centro_poblado", nombre="X")
    g.add_edge("X:entra", "X:sale", tipo="espera", modo="interno", d_km=0.0, sentido=0, centro="X", id="E")
    nodos = [f"n{k}" for k in range(8)]
    for u, v in itertools.permutations(nodos + ["X:entra", "X:sale"], 2):
        if u == "X:entra" or v == "X:sale" or g.has_edge(u, v) or rng.random() > 0.3:
            continue
        if rng.random() < 0.6:
            sentido = rng.choice([1, -1])
            g.add_edge(u, v, tipo="rio", modo="rio", d_km=rng.uniform(2, 40), sentido=sentido, id=f"{u}{v}")
        else:
            g.add_edge(u, v, tipo="via", modo="via", d_km=rng.uniform(2, 40), sentido=0, clase_via="por_confirmar", id=f"{u}{v}")
    return g


def _fuerza_bruta(gc: nx.DiGraph, origen, destinos, costo) -> float:
    """Enumera caminos simples sobre ESTADOS (lugar, capa): un lugar puede repetirse en otra capa."""
    mejor = float("inf")
    for d in destinos:
        if d not in gc:
            continue
        for camino in nx.all_simple_paths(gc, origen, d):
            w, t = 0.0, 0.0
            for u, v in zip(camino, camino[1:]):
                c = costo(u, v, gc.edges[u, v], t)
                w, t = w + c[0], t + c[1]
            mejor = min(mejor, w)
    return mejor


def test_dijkstra_por_calidad_igual_a_fuerza_bruta_sobre_estados():
    discrepancias = 0
    for semilla in range(60):
        g = _grafo_pequeno(semilla)
        cond = pesos.Condiciones(bote="madera_remo", temporada="aguas_bajas", nevera="deteriorada", acopios=frozenset({"X"}))
        gc = pesos.expandir_capas(g, cond)
        costo = pesos.funcion_costo(cond)
        destinos = {("n7", c) for c in pesos.CAPAS}
        r = busqueda.dijkstra_capas(gc, ("n0", "hielo"), destinos, costo)
        oraculo = _fuerza_bruta(gc, ("n0", "hielo"), destinos, costo)
        if r.alcanzable or oraculo < float("inf"):
            discrepancias += r.costo != pytest.approx(oraculo, abs=1e-9)
    assert discrepancias == 0


# ---------------------------------------------------------------- prueba 6: A*


@pytest.mark.parametrize("cond", list(_todas_las_condiciones()), ids=lambda c: f"{c.bote}-{c.temporada}-{c.nevera}")
def test_a_estrella_mismo_costo_y_menos_estados(cond):
    for origen, destino in laboratorio.pares():
        d = laboratorio.correr("dijkstra", G, origen, destino, cond)
        a = laboratorio.correr("a_estrella", G, origen, destino, cond)
        assert a.costo == pytest.approx(d.costo, abs=1e-12)
        assert a.nodos_expandidos <= d.nodos_expandidos


@pytest.mark.parametrize("criterio", ["calidad", "tiempo"])
def test_heuristica_nunca_sobreestima(criterio):
    for cond in _todas_las_condiciones():
        gc = pesos.expandir_capas(G, cond)
        costo = pesos.funcion_costo(cond, criterio)
        for destino in ("MER_CP01", "CP03:entra"):
            h = pesos.heuristica(gc, destino, cond, criterio)
            # costo optimo desde cada estado (t = 0: con hielo, el caso mas barato)
            objetivo = {(destino, c) for c in pesos.CAPAS}
            for n in gc.nodes:
                r = busqueda.dijkstra_capas(gc, n, objetivo, costo)
                if r.alcanzable:
                    assert h(n) <= r.costo + 1e-12, (n, destino)


def test_a_estrella_expande_menos_en_la_mayoria():
    tabla = laboratorio.comparar(G, COND)
    d = tabla[tabla["algoritmo"] == "dijkstra"]["nodos_expandidos"].to_numpy()
    a = tabla[tabla["algoritmo"] == "a_estrella"]["nodos_expandidos"].to_numpy()
    assert (a < d).sum() > len(d) / 2


# ---------------------------------------------------------------- prueba 7: BFS


def test_bfs_minimo_de_saltos_igual_a_networkx():
    gc = pesos.expandir_capas(G, COND)
    rng = random.Random(7)
    estados = list(gc.nodes)
    for _ in range(200):
        o, d = rng.choice(estados), rng.choice(estados)
        r, niveles = busqueda.bfs_niveles(gc, o, {d})
        if nx.has_path(gc, o, d):
            assert r.tramos == nx.shortest_path_length(gc, o, d)
        else:
            assert not r.alcanzable
    _, niveles = busqueda.bfs_niveles(gc, ("P02", "hielo"))
    assert niveles == nx.single_source_shortest_path_length(gc, ("P02", "hielo"))


def test_caso_documentado_bfs_pierde_mas_calidad_que_dijkstra():
    """Meta bajo → plaza, a remo, sin hielo, San Miguel con frio: BFS va por rio contra la corriente
    (menos tramos) y llega sin valor; Dijkstra va por San Miguel y sigue en camion refrigerado."""
    cond = COND.con(nevera="sin_hielo")
    bfs = laboratorio.correr("bfs", G, "P02", "MER_CP01", cond)
    dij = laboratorio.correr("dijkstra", G, "P02", "MER_CP01", cond)
    assert bfs.tramos < dij.tramos
    assert bfs.costo > dij.costo + 0.5
    assert any(n == "CP03:sale" for n, _ in dij.camino)


# ---------------------------------------------------------------- DFS


def test_tarjan_igual_a_networkx():
    for semilla in range(100):
        g = nx.gnm_random_graph(12, 16, seed=semilla)
        art, puentes = busqueda.puntos_articulacion(g)
        assert art == set(nx.articulation_points(g))
        assert {frozenset(e) for e in puentes} == {frozenset(e) for e in nx.bridges(g)}


def test_puntos_criticos_del_grafo_real():
    no_dirigido = G.to_undirected()
    art, puentes = busqueda.puntos_articulacion(no_dirigido)
    assert art == set(nx.articulation_points(no_dirigido))
    # cada zona de pesca cuelga de un solo punto del rio: si ese punto se corta, la zona queda aislada
    for zona in ("P01", "P02"):
        (punto,) = G.successors(zona)
        assert punto in art


def test_unimodal_vs_bimodal():
    cond = COND.con(nevera="sin_hielo")
    tabla = laboratorio.por_modos(G, "P02", "MER_CP01", cond).set_index("modo")
    assert not tabla.at["solo_via", "alcanzable"]
    assert tabla.at["rio_y_via", "dq"] < tabla.at["solo_rio", "dq"]
    assert laboratorio.valor_transbordo(tabla.reset_index()) > 0
