import math

import networkx as nx
import pytest

from pesca import busqueda, config, red, transporte
from pesca.escenario import Escenario

G = red.construir_red()
BASE = Escenario.base()
ESCENARIOS = {
    "base": BASE,
    "aguas_altas": BASE.con(temporada="aguas_altas"),
    "con_frio": BASE.con(hielo_a_bordo=True, camion_refrigerado=True),
}
NODOS = config.cargar_nodos()
ORIGENES = [red.clave(i, red.CAPA_RIO) for i in NODOS.loc[NODOS["tipo"].isin(transporte.TIPOS_ORIGEN), "id"]]
DESTINOS = [n for n, a in G.nodes(data=True) if a["tipo"] == "acopio"]
CASOS = [
    (nombre, emb, criterio)
    for nombre in ESCENARIOS
    for emb in transporte.embarcaciones()
    for criterio in transporte.CRITERIOS
]


def _perfil(nombre, emb):
    return transporte.Perfil.desde_escenario(ESCENARIOS[nombre], emb)


def _costo_networkx(origen, destino, w):
    try:
        return nx.dijkstra_path_length(G, origen, destino, weight=w)
    except nx.NetworkXNoPath:
        return math.inf


def _costo_ruta(ruta, w):
    return sum(w(u, v, G.edges[u, v]) for u, v in zip(ruta, ruta[1:]))


# ---------------------------------------------------------------- grafo de juguete


def _juguete():
    g = nx.DiGraph()
    for u, v, w in [("S", "A", 1), ("S", "B", 4), ("A", "B", 2), ("A", "C", 5), ("B", "C", 1), ("C", "T", 3), ("B", "T", 6)]:
        g.add_edge(u, v, w=w)
    return g


def _w(u, v, d):
    return d["w"]


def test_dijkstra_a_mano():
    # S=0, A=1, B=3 (S-A-B), C=4 (S-A-B-C), T=7 (S-A-B-C-T)
    r = busqueda.dijkstra(_juguete(), "S", "T", _w)
    assert r.ruta == ("S", "A", "B", "C", "T")
    assert r.costo == 7
    assert r.explorados == ("S", "A", "B", "C", "T")
    assert r.tramos == 4


def test_bfs_a_mano():
    # Menos tramos: S-B-T (2 tramos) aunque cueste 10 en vez de 7
    r = busqueda.bfs(_juguete(), "S", "T", _w)
    assert r.ruta == ("S", "B", "T")
    assert r.costo == 10
    assert r.explorados == ("S", "A", "B", "C", "T")
    assert busqueda.bfs(_juguete(), "S", "T").costo == 2


def test_a_estrella_con_h_cero_es_dijkstra():
    d = busqueda.dijkstra(_juguete(), "S", "T", _w)
    a = busqueda.a_estrella(_juguete(), "S", "T", _w, lambda _: 0.0)
    assert (a.ruta, a.costo, a.explorados) == (d.ruta, d.costo, d.explorados)


def test_sin_camino():
    g = _juguete()
    g.add_node("Z")
    for r in (busqueda.dijkstra(g, "S", "Z", _w), busqueda.a_estrella(g, "S", "Z", _w, lambda _: 0.0), busqueda.bfs(g, "S", "Z", _w)):
        assert not r.alcanzable
        assert r.costo == math.inf
        assert r.ruta == ()


def test_arista_infactible_se_ignora():
    # Sin A-B, lo mejor es S-B-C-T = 4 + 1 + 3
    def sin_ab(u, v, d):
        return None if (u, v) == ("A", "B") else d["w"]

    r = busqueda.dijkstra(_juguete(), "S", "T", sin_ab)
    assert r.ruta == ("S", "B", "C", "T")
    assert r.costo == 8


def test_origen_igual_destino():
    r = busqueda.dijkstra(_juguete(), "S", "S", _w)
    assert r.ruta == ("S",) and r.costo == 0 and r.tramos == 0


def test_nodo_inexistente():
    with pytest.raises(KeyError):
        busqueda.dijkstra(_juguete(), "S", "nada", _w)


def test_peso_negativo():
    with pytest.raises(ValueError):
        busqueda.dijkstra(_juguete(), "S", "T", lambda u, v, d: -1)


# ---------------------------------------------------------------- red real contra networkx


@pytest.mark.parametrize("escenario,emb,criterio", CASOS)
def test_dijkstra_igual_a_networkx(escenario, emb, criterio):
    w = transporte.peso(_perfil(escenario, emb), criterio)
    for o in ORIGENES:
        for d in DESTINOS:
            r = busqueda.dijkstra(G, o, d, w)
            esperado = _costo_networkx(o, d, w)
            assert r.costo == pytest.approx(esperado, rel=1e-9, abs=1e-12), (o, d)
            if r.alcanzable:
                assert r.ruta[0] == o and r.ruta[-1] == d
                assert _costo_ruta(r.ruta, w) == pytest.approx(r.costo)


@pytest.mark.parametrize("escenario,emb,criterio", CASOS)
def test_a_estrella_mismo_costo_y_menos_nodos(escenario, emb, criterio):
    p = _perfil(escenario, emb)
    w = transporte.peso(p, criterio)
    for o in ORIGENES:
        for d in DESTINOS:
            dj = busqueda.dijkstra(G, o, d, w)
            a = busqueda.a_estrella(G, o, d, w, transporte.heuristica(G, d, p, criterio))
            assert a.costo == pytest.approx(dj.costo, rel=1e-9, abs=1e-12), (o, d)
            assert a.n_explorados <= dj.n_explorados, (o, d)


@pytest.mark.parametrize("escenario,emb,criterio", CASOS)
def test_heuristica_admisible_y_consistente(escenario, emb, criterio):
    p = _perfil(escenario, emb)
    w = transporte.peso(p, criterio)
    inverso = G.reverse(copy=False)
    for d in DESTINOS:
        h = transporte.heuristica(G, d, p, criterio)
        # Costo exacto de cada nodo al destino: Dijkstra de networkx sobre el grafo invertido
        exacto = nx.single_source_dijkstra_path_length(inverso, d, weight=w)
        for n, costo in exacto.items():
            assert h(n) <= costo + 1e-12, (n, d)
        for u, v, datos in G.edges(data=True):
            c = w(u, v, datos)
            if c is not None:
                assert h(u) <= c + h(v) + 1e-12, (u, v, d)


@pytest.mark.parametrize("escenario,emb", [(e, m) for e in ESCENARIOS for m in transporte.embarcaciones()])
def test_bfs_menos_tramos_y_costo_no_menor(escenario, emb):
    w = transporte.peso(_perfil(escenario, emb))
    factible = G.edge_subgraph([(u, v) for u, v, d in G.edges(data=True) if w(u, v, d) is not None])
    for o in ORIGENES:
        for d in DESTINOS:
            b = busqueda.bfs(G, o, d, w)
            dj = busqueda.dijkstra(G, o, d, w)
            if not dj.alcanzable:
                assert not b.alcanzable
                continue
            assert b.tramos == nx.shortest_path_length(factible, o, d)
            assert b.costo >= dj.costo - 1e-12


def test_tabla_comparativa():
    pares = busqueda.pares_comparacion()
    assert 5 <= len(pares) <= 10
    tabla = busqueda.comparar(G, pares, _perfil("base", "madera_remo"))
    assert len(tabla) == 3 * len(pares)
    assert {"par", "algoritmo", "costo", "horas", "km", "tramos", "nodos_explorados", "ms", "pct_peor_que_dijkstra"} <= set(tabla.columns)
    por_par = tabla.pivot(index="par", columns="algoritmo", values="costo")
    assert (por_par["a_estrella"] - por_par["dijkstra"]).abs().max() < 1e-12
    assert (por_par["bfs"] >= por_par["dijkstra"] - 1e-12).all()
    assert (tabla.loc[tabla["algoritmo"] == "dijkstra", "pct_peor_que_dijkstra"] == 0).all()


def test_algoritmo_desconocido():
    with pytest.raises(ValueError):
        busqueda.correr("dfs", G, "P01@rio", "A01@via", _perfil("base", "madera_remo"))
