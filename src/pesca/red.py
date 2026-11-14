"""Red multimodal dirigida: rio + carretera + transbordo, calibrada con M01–M04.

Cada lugar puede tener dos nodos (dos capas): "<id>@rio" y "<id>@via". Los une una
arista de transbordo en cada sentido. Los rios tienen una arista aguas abajo y otra
aguas arriba por tramo; las carreteras, una en cada sentido sin corriente.

Calibracion (especificacion §4.5):
- sinuosidad de cada modo = km medidos / km en linea recta sobre la traza, sumando las
  rutas medidas de ese modo; se aplica a los tramos sin medir;
- los tramos compartidos por varias rutas medidas usan esa sinuosidad y los tramos
  exclusivos de una ruta se escalan para que la ruta sume exactamente lo medido.
Ningun factor puede ser menor que 1: asi cada arista mide al menos la linea recta
entre sus extremos, que es lo que hace admisible la heuristica de A*.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import networkx as nx
import pandas as pd

from pesca import config

CAPA_RIO = "rio"
CAPA_VIA = "via"
RADIO_TIERRA_KM = 6371.0088

# Lugares de distancias_medidas.csv -> id del nodo segun el modo de la ruta.
# Puerto Gaitan por rio es el malecon; por carretera, la plaza.
LUGARES_MEDIDOS = {
    CAPA_RIO: {"yucao_pueblo": "C01", "san_miguel": "A02", "puerto_gaitan": "D_MALECON"},
    CAPA_VIA: {"yucao_pueblo": "C01", "san_miguel": "A02", "puerto_gaitan": "A01"},
}

# Lugares que reciben un acceso por carretera y un transbordo aunque no esten sobre una via
TIPOS_CON_ACCESO = {"acopio", "desembarque"}

FUENTE_ACCESO = "acceso estimado: línea recta × sinuosidad de las vías"
FUENTE_TRANSBORDO = "transbordo río ↔ carretera (tiempo en parametros.yaml)"


# ---------------------------------------------------------------- geometria


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en linea recta sobre la esfera (km)."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = f2 - f1, math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(a))


def longitud_km(coords: list[tuple[float, float]]) -> float:
    """Longitud de una polilinea [(lat, lon), ...] sumando haversine."""
    return sum(haversine_km(*a, *b) for a, b in zip(coords, coords[1:]))


def _cortar(coords: list[tuple[float, float]], partes: int) -> list[list[tuple[float, float]]]:
    """Divide una polilinea en `partes` trozos de igual longitud (interpolando en lat/lon)."""
    if partes == 1:
        return [list(coords)]
    largos = [haversine_km(*a, *b) for a, b in zip(coords, coords[1:])]
    total = sum(largos)
    trozos, actual = [], [coords[0]]
    meta, i, recorrido = total / partes, 0, 0.0
    for k in range(1, partes):
        objetivo = meta * k
        while recorrido + largos[i] < objetivo:
            recorrido += largos[i]
            i += 1
            actual.append(coords[i])
        t = (objetivo - recorrido) / largos[i]
        (la1, lo1), (la2, lo2) = coords[i], coords[i + 1]
        corte = (la1 + t * (la2 - la1), lo1 + t * (lo2 - lo1))
        actual.append(corte)
        trozos.append(actual)
        actual = [corte]
    actual.extend(coords[i + 1 :])
    trozos.append(actual)
    return trozos


# ---------------------------------------------------------------- KML


def cargar_kml(ruta: Path) -> list[tuple[float, float]]:
    """Vertices (lat, lon) de los LineString de un KML de Google Earth, en orden."""
    coords: list[tuple[float, float]] = []
    for elem in ET.parse(ruta).iter():
        if elem.tag.endswith("LineString"):
            for hijo in elem:
                if hijo.tag.endswith("coordinates") and hijo.text:
                    for punto in hijo.text.split():
                        lon, lat, *_ = (float(x) for x in punto.split(","))
                        coords.append((lat, lon))
    if len(coords) < 2:
        raise ValueError(f"{ruta.name}: el KML no tiene un LineString con al menos dos puntos")
    return coords


def objetivos_medidos(dir_kml: Path = config.DIR_KML) -> pd.DataFrame:
    """Rutas medidas M01–M04 con su nodo de origen y destino y la mejor fuente disponible.

    Prioridad: KML medido (rutas_kml/M0x*.kml) > distancias_medidas.csv.
    """
    filas = []
    for m in config.cargar_distancias_medidas().itertuples():
        lugares = LUGARES_MEDIDOS[m.modo]
        km, fuente = float(m.distancia_km), "medido en Google Earth (distancias_medidas.csv)"
        kml = sorted(Path(dir_kml).glob(f"{m.id}*.kml"))
        if kml:
            km, fuente = longitud_km(cargar_kml(kml[0])), f"KML medido ({kml[0].name})"
        filas.append(
            {"id": m.id, "modo": m.modo, "origen": lugares[m.origen], "destino": lugares[m.destino], "km_medido": km, "fuente": fuente}
        )
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- tramos y calibracion


@dataclass
class Tramo:
    """Pedazo de una traza entre dos lugares con nombre consecutivos."""

    modo: str
    traza: str
    nombre_traza: str
    cuenca: str | None
    desde: str
    hasta: str
    coords: list[tuple[float, float]]
    crudo_km: float = 0.0
    factor: float = 1.0
    etiqueta: str = "CALIBRADO"
    fuente: str = ""
    rutas: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.crudo_km = longitud_km(self.coords)


def _tramos_de(trazas: pd.DataFrame, modo: str) -> list[Tramo]:
    tramos = []
    for traza, filas in trazas.groupby("traza", sort=False):
        filas = filas.sort_values("orden")
        cuenca = filas["cuenca"].iloc[0] if "cuenca" in filas else None
        nombre_traza = filas["nombre"].iloc[0]
        desde, coords = None, []
        for f in filas.itertuples():
            # En las vias cada vertice es un nodo; en los rios, solo los que tienen id
            id_nodo = f.id_nodo if isinstance(f.id_nodo, str) else (f"{traza}_{f.orden}" if modo == CAPA_VIA else None)
            coords.append((f.lat, f.lon))
            if id_nodo is None:
                continue
            if desde is not None:
                tramos.append(Tramo(modo, traza, nombre_traza, cuenca, desde, id_nodo, coords))
            desde, coords = id_nodo, [(f.lat, f.lon)]
    return tramos


def _calibrar(tramos: list[Tramo], objetivos: pd.DataFrame, escala_sinuosidad: float) -> dict[str, float]:
    """Asigna factor, etiqueta y fuente a cada tramo. Devuelve la sinuosidad de cada modo."""
    sinuosidad = {}
    for modo in (CAPA_RIO, CAPA_VIA):
        propios = [t for t in tramos if t.modo == modo]
        medidas = objetivos[objetivos["modo"] == modo]
        g = nx.Graph()
        for i, t in enumerate(propios):
            g.add_edge(t.desde, t.hasta, crudo=t.crudo_km, indice=i)

        caminos = {}
        for m in medidas.itertuples():
            nodos = nx.shortest_path(g, m.origen, m.destino, weight="crudo")
            caminos[m.id] = [g.edges[a, b]["indice"] for a, b in zip(nodos, nodos[1:])]
            for i in caminos[m.id]:
                propios[i].rutas.append(m.id)
        uso = Counter(i for camino in caminos.values() for i in camino)

        crudo_rutas = sum(propios[i].crudo_km for camino in caminos.values() for i in camino)
        s = medidas["km_medido"].sum() / crudo_rutas
        if s < 1:
            raise ValueError(f"Sinuosidad de {modo} = {s:.3f} < 1: las coordenadas de las trazas son demasiado largas")
        sinuosidad[modo] = float(s)
        ids = " y ".join(medidas["id"])

        for i, t in enumerate(propios):
            if uso[i] == 0:
                t.factor, t.etiqueta = s * escala_sinuosidad, "CALIBRADO"
                t.fuente = f"línea recta × sinuosidad calibrada con {ids}"
            elif uso[i] > 1:
                t.factor, t.etiqueta = s, "CALIBRADO"
                t.fuente = f"compartido por {' y '.join(t.rutas)}: sinuosidad calibrada"

        for m in medidas.itertuples():
            exclusivos = [i for i in caminos[m.id] if uso[i] == 1]
            if not exclusivos:
                continue
            fijo = sum(propios[i].crudo_km * propios[i].factor for i in caminos[m.id] if uso[i] > 1)
            f = (m.km_medido - fijo) / sum(propios[i].crudo_km for i in exclusivos)
            if f < 1:
                raise ValueError(
                    f"{m.id}: el factor de los tramos exclusivos queda en {f:.3f} < 1. "
                    "Revisa las coordenadas de la traza: miden más que la ruta medida."
                )
            for i in exclusivos:
                propios[i].factor, propios[i].etiqueta = f, "MEDIDO"
                propios[i].fuente = f"{m.id}, {m.fuente}; repartido por tramo"
    return sinuosidad


# ---------------------------------------------------------------- grafo


def clave(lugar: str, capa: str) -> str:
    return f"{lugar}@{capa}"


def separar(nodo: str) -> tuple[str, str]:
    lugar, capa = nodo.rsplit("@", 1)
    return lugar, capa


def _agregar_nodo(g: nx.DiGraph, lugar: str, capa: str, **atributos) -> str:
    n = clave(lugar, capa)
    if n not in g:
        g.add_node(n, lugar=lugar, capa=capa, **atributos)
    return n


def _atributos_lugar(nodos: pd.DataFrame, lugar: str, lat: float, lon: float, tipo: str, nombre: str) -> dict:
    if lugar in nodos.index:
        fila = nodos.loc[lugar]
        return {
            "nombre": fila["nombre"],
            "tipo": fila["tipo"],
            "cuenca": fila["cuenca"],
            "lat": float(fila["lat"]),
            "lon": float(fila["lon"]),
            "validado": fila["validado"],
        }
    return {"nombre": nombre, "tipo": tipo, "cuenca": None, "lat": lat, "lon": lon, "validado": "no"}


@cache
def construir_red(escala_sinuosidad: float = 1.0) -> nx.DiGraph:
    """Grafo dirigido multimodal calibrado.

    `escala_sinuosidad` multiplica la sinuosidad de los tramos sin medir (Monte Carlo ±20 %).
    """
    nodos = config.cargar_nodos().set_index("id")
    separacion = config.parametro("rio.separacion_candidatos_km")
    objetivos = objetivos_medidos()
    tramos = _tramos_de(config.cargar_rios(), CAPA_RIO) + _tramos_de(config.cargar_vias(), CAPA_VIA)
    sinuosidad = _calibrar(tramos, objetivos, escala_sinuosidad)

    g = nx.DiGraph(sinuosidad=sinuosidad)
    contador_rio: Counter[str] = Counter()
    for t in tramos:
        (la1, lo1), (la2, lo2) = t.coords[0], t.coords[-1]
        ini = _agregar_nodo(g, t.desde, t.modo, **_atributos_lugar(nodos, t.desde, la1, lo1, "punto_via", t.nombre_traza))
        fin = _agregar_nodo(g, t.hasta, t.modo, **_atributos_lugar(nodos, t.hasta, la2, lo2, "punto_via", t.nombre_traza))
        comunes = {"modo": t.modo, "traza": t.traza, "cuenca": t.cuenca, "etiqueta": t.etiqueta, "fuente": t.fuente}

        if t.modo == CAPA_VIA:
            d = t.crudo_km * t.factor
            g.add_edge(ini, fin, distancia_km=d, sentido=None, geometria=t.coords, **comunes)
            g.add_edge(fin, ini, distancia_km=d, sentido=None, geometria=t.coords[::-1], **comunes)
            continue

        # Rio: se parte el tramo en trozos de a lo sumo `separacion` km con punto_rio intermedios
        partes = max(1, math.ceil(t.crudo_km * t.factor / separacion))
        trozos = _cortar(t.coords, partes)
        previo = ini
        for k, trozo in enumerate(trozos):
            if k == len(trozos) - 1:
                siguiente = fin
            else:
                contador_rio[t.traza] += 1
                lugar = f"R_{t.traza.upper()}_{contador_rio[t.traza]:02d}"
                lat, lon = trozo[-1]
                siguiente = _agregar_nodo(
                    g, lugar, CAPA_RIO, nombre=f"Punto del {t.nombre_traza}", tipo="punto_rio",
                    cuenca=t.cuenca, lat=lat, lon=lon, validado="no",
                )
            d = longitud_km(trozo) * t.factor
            g.add_edge(previo, siguiente, distancia_km=d, sentido="aguas_abajo", geometria=trozo, **comunes)
            g.add_edge(siguiente, previo, distancia_km=d, sentido="aguas_arriba", geometria=trozo[::-1], **comunes)
            previo = siguiente

    # Accesos por carretera para acopios y desembarques que no estan sobre una via
    nodos_via = [n for n, a in g.nodes(data=True) if a["capa"] == CAPA_VIA]
    for n, a in list(g.nodes(data=True)):
        if a["capa"] != CAPA_RIO or a["tipo"] not in TIPOS_CON_ACCESO or clave(a["lugar"], CAPA_VIA) in g:
            continue
        cercano = min(nodos_via, key=lambda v: haversine_km(a["lat"], a["lon"], g.nodes[v]["lat"], g.nodes[v]["lon"]))
        b = g.nodes[cercano]
        acceso = _agregar_nodo(g, a["lugar"], CAPA_VIA, **{k: a[k] for k in ("nombre", "tipo", "cuenca", "lat", "lon", "validado")})
        d = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]) * sinuosidad[CAPA_VIA]
        linea = [(a["lat"], a["lon"]), (b["lat"], b["lon"])]
        comunes = {"modo": CAPA_VIA, "traza": "acceso", "cuenca": None, "sentido": None, "etiqueta": "SIMULADO", "fuente": FUENTE_ACCESO}
        g.add_edge(acceso, cercano, distancia_km=d, geometria=linea, **comunes)
        g.add_edge(cercano, acceso, distancia_km=d, geometria=linea[::-1], **comunes)

    # Transbordos en todo lugar con las dos capas
    for n, a in list(g.nodes(data=True)):
        otro = clave(a["lugar"], CAPA_VIA)
        if a["capa"] == CAPA_RIO and otro in g:
            punto = [(a["lat"], a["lon"])]
            comunes = {"modo": "transbordo", "traza": "transbordo", "cuenca": a["cuenca"], "sentido": None,
                       "distancia_km": 0.0, "etiqueta": "SIMULADO", "fuente": FUENTE_TRANSBORDO, "geometria": punto}
            g.add_edge(n, otro, **comunes)
            g.add_edge(otro, n, **comunes)

    g.graph["calibracion"] = _tabla_calibracion(g, objetivos)
    return g


def _tabla_calibracion(g: nx.DiGraph, objetivos: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for m in objetivos.itertuples():
        capa = g.edge_subgraph([(u, v) for u, v, d in g.edges(data=True) if d["modo"] == m.modo])
        km = nx.shortest_path_length(capa, clave(m.origen, m.modo), clave(m.destino, m.modo), weight="distancia_km")
        filas.append(
            {"id": m.id, "modo": m.modo, "origen": m.origen, "destino": m.destino, "km_medido": m.km_medido,
             "km_grafo": km, "error_pct": 100 * (km - m.km_medido) / m.km_medido, "fuente": m.fuente}
        )
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- consultas


def calibracion(g: nx.DiGraph | None = None) -> pd.DataFrame:
    """M01–M04: km medidos frente a km del grafo y error relativo (%)."""
    return (g if g is not None else construir_red()).graph["calibracion"]


def aristas_entre_cuencas(g: nx.DiGraph) -> list[tuple[str, str]]:
    """Aristas de rio que unen nodos de cuencas distintas (debe ser una lista vacia)."""
    return [
        (u, v) for u, v, d in g.edges(data=True)
        if d["modo"] == CAPA_RIO and g.nodes[u]["cuenca"] != g.nodes[v]["cuenca"]
    ]


def opciones_lugares(g: nx.DiGraph) -> dict[str, str]:
    """Nodos con nombre propio (sin punto_rio ni punto_via generados) -> texto para la interfaz."""
    capas = {CAPA_RIO: "río", CAPA_VIA: "carretera"}
    nodos = config.cargar_nodos()
    orden = {lugar: i for i, lugar in enumerate(nodos["id"])}
    elegibles = [n for n, a in g.nodes(data=True) if a["lugar"] in orden]
    elegibles.sort(key=lambda n: (orden[g.nodes[n]["lugar"]], g.nodes[n]["capa"]))
    return {n: f"{g.nodes[n]['nombre']} ({capas[g.nodes[n]['capa']]})" for n in elegibles}


@cache
def subgrafo_modo(g: nx.DiGraph, *modos: str) -> nx.DiGraph:
    """Vista del grafo con solo las aristas de los modos dados (p. ej. solo rio)."""
    return g.edge_subgraph([(u, v) for u, v, d in g.edges(data=True) if d["modo"] in modos])
