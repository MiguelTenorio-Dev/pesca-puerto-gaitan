import networkx as nx
import pytest

from pesca import busqueda, config, red

G = red.construir_red()
TOLERANCIA = config.parametro("red.tolerancia_calibracion")


def _capa(modo: str) -> nx.DiGraph:
    return G.edge_subgraph([(u, v) for u, v, d in G.edges(data=True) if d["modo"] == modo])


@pytest.mark.parametrize("fila", red.objetivos_medidos().to_dict("records"), ids=lambda f: f["id"])
def test_reproduce_lo_medido(fila):
    # Con el Dijkstra propio, por distancia y solo dentro de la capa de la ruta medida
    capa = _capa(fila["modo"])
    r = busqueda.dijkstra(
        capa, red.clave(fila["origen"], fila["modo"]), red.clave(fila["destino"], fila["modo"]),
        lambda u, v, d: d["distancia_km"],
    )
    assert r.costo == pytest.approx(fila["km_medido"], rel=TOLERANCIA)


def test_tabla_de_calibracion():
    cal = red.calibracion(G)
    assert set(cal["id"]) == {"M01", "M02", "M03", "M04"}
    assert (cal["error_pct"].abs() <= 100 * TOLERANCIA).all()


def test_sin_rio_entre_cuencas():
    assert red.aristas_entre_cuencas(G) == []
    rio = _capa(red.CAPA_RIO)
    meta = [n for n in rio if G.nodes[n]["cuenca"] == "meta"]
    vichada = [n for n in rio if G.nodes[n]["cuenca"] == "vichada"]
    assert meta and vichada
    alcanzables = set(nx.descendants(rio, meta[0])) | {meta[0]}
    assert not alcanzables & set(vichada)


def test_cuenca_de_la_traza_coincide_con_la_del_nodo():
    for u, v, d in G.edges(data=True):
        if d["modo"] == red.CAPA_RIO:
            assert G.nodes[u]["cuenca"] == d["cuenca"] == G.nodes[v]["cuenca"], (u, v)


def test_cada_arista_de_rio_tiene_su_inversa():
    for u, v, d in G.edges(data=True):
        if d["modo"] != red.CAPA_RIO:
            continue
        inversa = G.edges[v, u]
        assert {d["sentido"], inversa["sentido"]} == {"aguas_abajo", "aguas_arriba"}
        assert inversa["distancia_km"] == pytest.approx(d["distancia_km"])


def test_toda_arista_tiene_fuente_y_etiqueta():
    for u, v, d in G.edges(data=True):
        assert d["fuente"], (u, v)
        assert d["etiqueta"] in config.ETIQUETAS, (u, v)
        assert d["modo"] in config.MODOS


def test_distancia_no_menor_que_linea_recta():
    # Condicion de la heuristica admisible de A*
    for u, v, d in G.edges(data=True):
        a, b = G.nodes[u], G.nodes[v]
        assert d["distancia_km"] >= red.haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]) - 1e-9, (u, v)


def test_sinuosidades_mayores_que_uno():
    assert all(s >= 1 for s in G.graph["sinuosidad"].values())


def test_separacion_de_puntos_del_rio():
    separacion = config.parametro("rio.separacion_candidatos_km")
    for u, v, d in G.edges(data=True):
        if d["modo"] == red.CAPA_RIO:
            assert d["distancia_km"] <= separacion + 1e-9, (u, v)
    assert any(a["tipo"] == "punto_rio" for _, a in G.nodes(data=True))


def test_todos_los_lugares_estan_en_el_grafo():
    lugares = {a["lugar"] for _, a in G.nodes(data=True)}
    assert set(config.cargar_nodos()["id"]) <= lugares


def test_cada_zona_llega_a_la_plaza():
    for n, a in G.nodes(data=True):
        if a["tipo"] == "zona_pesca":
            assert nx.has_path(G, n, "A01@via"), n


def test_transbordos_en_lugares_con_dos_capas():
    for n, a in G.nodes(data=True):
        otro = red.clave(a["lugar"], red.CAPA_VIA)
        if a["capa"] == red.CAPA_RIO and otro in G:
            assert G.edges[n, otro]["modo"] == "transbordo"
            assert G.edges[otro, n]["modo"] == "transbordo"
    assert G.edges["A02@rio", "A02@via"]["modo"] == "transbordo"


def test_san_miguel_queda_rio_abajo():
    capa = _capa(red.CAPA_RIO)
    ruta = nx.shortest_path(capa, "A02@rio", "D_MALECON@rio", weight="distancia_km")
    sentidos = [G.edges[u, v]["sentido"] for u, v in zip(ruta, ruta[1:])]
    assert set(sentidos) == {"aguas_arriba"}


def test_haversine_conocido():
    # Un grado de latitud ≈ 111,2 km
    assert red.haversine_km(4.0, -72.0, 5.0, -72.0) == pytest.approx(111.19, rel=1e-3)


KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>M02</name>
<LineString><coordinates>
-72.0,4.0,0 -72.0,4.1,0 -72.0,4.2,0
</coordinates></LineString></Placemark></Document></kml>"""


def test_cargar_kml(tmp_path):
    ruta = tmp_path / "M02_prueba.kml"
    ruta.write_text(KML, encoding="utf-8")
    coords = red.cargar_kml(ruta)
    assert coords == [(4.0, -72.0), (4.1, -72.0), (4.2, -72.0)]
    assert red.longitud_km(coords) == pytest.approx(red.haversine_km(4.0, -72.0, 4.2, -72.0))


def test_kml_tiene_prioridad_sobre_el_csv(tmp_path):
    (tmp_path / "M02_prueba.kml").write_text(KML, encoding="utf-8")
    objetivos = red.objetivos_medidos(tmp_path).set_index("id")
    assert objetivos.at["M02", "fuente"].startswith("KML")
    assert objetivos.at["M02", "km_medido"] == pytest.approx(red.haversine_km(4.0, -72.0, 4.2, -72.0))
    assert objetivos.at["M04", "km_medido"] == 41.65


def test_cortar_conserva_la_longitud():
    coords = [(4.0, -72.0), (4.05, -71.95), (4.1, -71.9)]
    trozos = red._cortar(coords, 3)
    assert len(trozos) == 3
    assert sum(red.longitud_km(t) for t in trozos) == pytest.approx(red.longitud_km(coords), rel=1e-6)
    assert trozos[0][0] == coords[0] and trozos[-1][-1] == coords[-1]
