"""Mapas Folium de la red y de las busquedas. Las paginas solo los dibujan."""

from __future__ import annotations

import folium
import networkx as nx

from pesca import red
from pesca.busqueda import ResultadoBusqueda

# Color de las aristas segun la fuente del dato
COLOR_ETIQUETA = {"MEDIDO": "#1a9850", "CALIBRADO": "#d4a017", "SIMULADO": "#f46d43"}
COLOR_TRANSBORDO = "#7b3294"
TEXTO_GRUPO = {
    "MEDIDO": "🟢 Medido (M01–M04, repartido por tramo)",
    "CALIBRADO": "🟡 Calibrado (sinuosidad de lo medido)",
    "SIMULADO": "🟠 Simulado (accesos estimados)",
}

# Color de la ruta segun el sentido
COLOR_SENTIDO = {"aguas_abajo": "#1a9850", "aguas_arriba": "#d73027", None: "#555555"}

COLOR_TIPO = {
    "acopio": "#d73027",
    "desembarque": "#fc8d59",
    "comunidad": "#7b3294",
    "zona_pesca": "#2166ac",
    "confluencia": "#878787",
    "punto_via": "#4d4d4d",
    "punto_rio": "#92c5de",
}

# Rampa de la exploracion: claro (primeros) a oscuro (ultimos)
RAMPA_EXPLORACION = ("#ffffb2", "#253494")
GUION_VIA = "8 6"


def _mapa_vacio(grafo: nx.DiGraph) -> folium.Map:
    lats = [a["lat"] for _, a in grafo.nodes(data=True)]
    lons = [a["lon"] for _, a in grafo.nodes(data=True)]
    mapa = folium.Map(tiles="OpenStreetMap", control_scale=True)
    mapa.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
    return mapa


def _aristas_unicas(grafo: nx.DiGraph):
    """Una arista por par de nodos (en los rios, la que va aguas abajo)."""
    vistos = set()
    for u, v, d in grafo.edges(data=True):
        par = frozenset((u, v))
        if par in vistos or d["sentido"] == "aguas_arriba":
            continue
        vistos.add(par)
        yield u, v, d


def _mezclar(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _texto_arista(d: dict) -> str:
    if d["modo"] == "transbordo":
        return "Transbordo río ↔ carretera"
    modo = "Río" if d["modo"] == red.CAPA_RIO else "Carretera"
    return f"{modo} · {d['distancia_km']:.1f} km · {d['fuente']}"


def _lugares(grafo: nx.DiGraph):
    """Un nodo por lugar (las dos capas se dibujan una sola vez)."""
    vistos = set()
    for n, a in grafo.nodes(data=True):
        if a["lugar"] not in vistos:
            vistos.add(a["lugar"])
            yield n, a


def mapa_red(grafo: nx.DiGraph) -> folium.Map:
    """Toda la red, con las aristas coloreadas por la fuente del dato."""
    mapa = _mapa_vacio(grafo)
    grupos = {e: folium.FeatureGroup(name=t) for e, t in TEXTO_GRUPO.items()}
    transbordos = folium.FeatureGroup(name="🟣 Transbordos")
    lugares = folium.FeatureGroup(name="Lugares")
    puntos = folium.FeatureGroup(name="Puntos del río y de la vía", show=False)

    for _, _, d in _aristas_unicas(grafo):
        if d["modo"] == "transbordo":
            folium.CircleMarker(
                d["geometria"][0], radius=11, color=COLOR_TRANSBORDO, weight=2, fill=False, tooltip=_texto_arista(d)
            ).add_to(transbordos)
            continue
        folium.PolyLine(
            d["geometria"],
            color=COLOR_ETIQUETA[d["etiqueta"]],
            weight=4 if d["modo"] == red.CAPA_RIO else 3,
            dash_array=None if d["modo"] == red.CAPA_RIO else GUION_VIA,
            tooltip=_texto_arista(d),
        ).add_to(grupos[d["etiqueta"]])

    for n, a in _lugares(grafo):
        generado = a["tipo"] in ("punto_rio", "punto_via")
        folium.CircleMarker(
            [a["lat"], a["lon"]],
            radius=3 if generado else 7,
            color=COLOR_TIPO.get(a["tipo"], "black"),
            fill=True,
            fill_opacity=0.9,
            tooltip=f"{a['lugar']} · {a['nombre']} ({a['tipo']}) · validado: {a['validado']}",
        ).add_to(puntos if generado else lugares)

    for capa in [*grupos.values(), transbordos, puntos, lugares]:
        capa.add_to(mapa)
    folium.LayerControl(collapsed=False).add_to(mapa)
    return mapa


def mapa_busqueda(grafo: nx.DiGraph, resultado: ResultadoBusqueda, paso: int | None = None) -> folium.Map:
    """La red en gris, los primeros `paso` nodos explorados y la ruta coloreada por sentido."""
    mapa = _mapa_vacio(grafo)
    for _, _, d in _aristas_unicas(grafo):
        if d["modo"] != "transbordo":
            folium.PolyLine(
                d["geometria"], color="#bdbdbd", weight=2,
                dash_array=None if d["modo"] == red.CAPA_RIO else GUION_VIA,
            ).add_to(mapa)

    if resultado.alcanzable:
        for u, v in zip(resultado.ruta, resultado.ruta[1:]):
            d = grafo.edges[u, v]
            if d["modo"] == "transbordo":
                folium.CircleMarker(
                    d["geometria"][0], radius=10, color=COLOR_TRANSBORDO, weight=3, tooltip="Transbordo"
                ).add_to(mapa)
                continue
            folium.PolyLine(
                d["geometria"], color=COLOR_SENTIDO[d["sentido"]], weight=7, opacity=0.85,
                dash_array=None if d["modo"] == red.CAPA_RIO else GUION_VIA, tooltip=_texto_arista(d),
            ).add_to(mapa)

    explorados = resultado.explorados[: paso if paso is not None else len(resultado.explorados)]
    total = max(1, len(resultado.explorados) - 1)
    for k, n in enumerate(explorados):
        a = grafo.nodes[n]
        folium.CircleMarker(
            [a["lat"], a["lon"]],
            radius=6,
            color="#333333",
            weight=1,
            fill=True,
            fill_color=_mezclar(*RAMPA_EXPLORACION, k / total),
            fill_opacity=0.95,
            tooltip=f"#{k + 1}: {a['nombre']}",
        ).add_to(mapa)

    for nodo, color, texto in ((resultado.origen, "green", "Origen"), (resultado.destino, "red", "Destino")):
        a = grafo.nodes[nodo]
        folium.Marker([a["lat"], a["lon"]], tooltip=f"{texto}: {a['nombre']}", icon=folium.Icon(color=color)).add_to(mapa)
    return mapa
