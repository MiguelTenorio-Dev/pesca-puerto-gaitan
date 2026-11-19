"""Datos del grafo de la adenda v4: KML → nodos.csv y aristas.csv, esqueleto SIMULADO y esquema.

Construccion (adenda §2.3, pasos 1–5):
1. trazas del rio y de las vias (LineString de Google Earth); el rio, de aguas arriba a aguas abajo;
2. un vertice en cada extremo, en cada confluencia o cruce y frente a cada pueblo que se cuelga;
   entre esos, uno cada ~paso_km;
3. distancia_km de cada arco = suma de haversine entre los vertices de la traza;
4. cada centro poblado (o comunidad) con acceso por rio recibe un embarcadero y un transbordo;
   con acceso por via, un arco a la red vial; la cabecera recibe el mercado;
5. cada zona de pesca recibe un arco de acceso al punto del rio mas cercano.
Un tramo de rio se guarda una vez, con sentido +1 (aguas abajo): el constructor del grafo crea el inverso.

Cada fila lleva fuente = "ETIQUETA: detalle", con ETIQUETA en config.ETIQUETAS.
"""

from __future__ import annotations

import argparse
import math
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import networkx as nx
import pandas as pd

from pesca import config
from pesca.red import _cortar, haversine_km, longitud_km

TIPOS_NODO = {"zona_pesca", "punto_rio", "embarcadero", "centro_poblado", "punto_via", "desembarque", "comunidad", "mercado"}
MODO_DE_ARCO = {"rio": "rio", "acceso": "rio", "transbordo": "interno", "via": "via", "espera": "interno", "venta": "interno"}
CLASES_DANE = {"cabecera", "centro_poblado"}
SI_NO = {"si", "no"}
ACCESOS = {"si", "no", "por_confirmar"}
CUENCAS = {"meta", "vichada", "por_confirmar"}
RANGO_LAT, RANGO_LON = (2.0, 7.0), (-75.0, -69.0)
ORDEN_ETIQUETAS = ["MEDIDO", "DATO", "OFICIAL", "CALIBRADO", "SIMULADO", "CONFIRMAR"]

# Rios de cada cuenca (CLAUDE.md); se reconocen por el nombre de la traza
CUENCA_RIO = {"meta": "meta", "manacacias": "meta", "yucao": "meta", "planas": "vichada", "muco": "vichada", "guarrojo": "vichada"}

# Lugares de distancias_medidas.csv -> id del pueblo en el grafo v4
LUGARES_MEDIDOS = {"yucao_pueblo": "C01", "san_miguel": "CP03", "puerto_gaitan": "CP01"}

# Esqueleto SIMULADO: lo minimo de rios.csv, vias.csv y nodos.csv (v3.1) para reproducir M01–M04
ESQUELETO_RIOS = {"meta": ("C01", "A02"), "manacacias": ("D_MALECON", "X01")}
ESQUELETO_VIAS = ("via_yucao", "via_san_miguel")
# Vias sin traza en vias.csv: linea recta entre dos centros poblados (la sinuosidad la pone el escalado)
ESQUELETO_VIAS_RECTAS = {"vía Puerto Gaitán–La Cristalina": ("CP01", "CP02")}
ESQUELETO_ZONAS = ("P01", "P02")

FUENTE_INTERNO = "SIMULADO: arco interno (d = 0); el tiempo sale de parametros.yaml"
FUENTE_ACCESO_ZONA = "SIMULADO: línea recta al punto del río más cercano"
FUENTE_ENLACE_VIA = "SIMULADO: línea recta del pueblo al punto de la vía más cercano"


@dataclass
class Linea:
    """Traza de un rio o de una via: nombre, vertices (lat, lon) y fuente de las filas que genera."""

    nombre: str
    coords: list[tuple[float, float]]
    fuente: str


# ---------------------------------------------------------------- utilidades


def etiqueta(fuente: object) -> str:
    """Etiqueta de una fuente "ETIQUETA: detalle"."""
    return str(fuente).split(":", 1)[0].strip()


def _normalizar(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def cuenca_de(nombre_rio: str) -> str:
    nombre = _normalizar(nombre_rio)
    return next((c for rio, c in CUENCA_RIO.items() if rio in nombre), "por_confirmar")


def _clave(p: tuple[float, float]) -> tuple[float, float]:
    return round(p[0], 6), round(p[1], 6)


def _proyectar(p: tuple[float, float], coords: list[tuple[float, float]]) -> tuple[float, int, tuple[float, float]]:
    """Punto de la polilinea mas cercano a p: (distancia km, segmento, punto). Plano local lat/lon."""
    escala = math.cos(math.radians(p[0]))
    mejor = (math.inf, 0, coords[0])
    for i, (a, b) in enumerate(zip(coords, coords[1:])):
        ax, ay = (a[1] - p[1]) * escala, a[0] - p[0]
        dx, dy = (b[1] - a[1]) * escala, b[0] - a[0]
        largo2 = dx * dx + dy * dy
        t = 0.0 if largo2 == 0 else min(1.0, max(0.0, -(ax * dx + ay * dy) / largo2))
        q = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        d = haversine_km(*p, *q)
        if d < mejor[0]:
            mejor = (d, i, q)
    return mejor


def _insertar(linea: Linea, i: int, q: tuple[float, float], tolerancia_km: float) -> tuple[float, float]:
    """Pone q como vertice del segmento i; si un extremo del segmento esta a <= tolerancia, usa ese extremo."""
    cerca = min(linea.coords[i : i + 2], key=lambda v: haversine_km(*v, *q))
    if haversine_km(*cerca, *q) <= tolerancia_km:
        return cerca
    linea.coords.insert(i + 1, q)
    return q


def _trozos(linea: Linea, cortes: set, paso_km: float) -> list[list[tuple[float, float]]]:
    """Trozos de la traza entre cortes, y cada uno en partes iguales de ~paso_km."""
    salida, actual = [], [linea.coords[0]]
    ultimo = len(linea.coords) - 1
    for j, p in enumerate(linea.coords[1:], 1):
        actual.append(p)
        if j == ultimo or _clave(p) in cortes:
            partes = max(1, round(longitud_km(actual) / paso_km))
            salida.extend(_cortar(actual, partes))
            actual = [p]
    return salida


# ---------------------------------------------------------------- KML


def leer_lineas_kml(ruta: Path) -> list[Linea]:
    """Un LineString por traza, con el nombre de su Placemark."""
    ruta = Path(ruta)
    lineas = []
    for marca in ET.parse(ruta).iter():
        if not marca.tag.endswith("Placemark"):
            continue
        nombre = next((e.text or "" for e in marca if e.tag.endswith("name")), "").strip()
        for geo in marca.iter():
            if not geo.tag.endswith("LineString"):
                continue
            texto = next((e.text or "" for e in geo if e.tag.endswith("coordinates")), "")
            coords = [(float(lat), float(lon)) for lon, lat, *_ in (p.split(",") for p in texto.split())]
            if len(coords) >= 2:
                lineas.append(Linea(nombre or f"traza {len(lineas) + 1}", coords, f"MEDIDO: {ruta.name}"))
    if not lineas:
        raise ValueError(f"{ruta.name}: no tiene ningún LineString con al menos dos puntos")
    return lineas


def zonas_kml(ruta: Path) -> pd.DataFrame:
    """Zonas de pesca desde los puntos de un KML (Z01, Z02, ...)."""
    puntos = config.leer_puntos_kml(Path(ruta))
    return pd.DataFrame(
        {
            "id": [f"Z{i:02d}" for i in range(1, len(puntos) + 1)],
            "nombre": puntos["nombre_kml"],
            "lat": puntos["lat"],
            "lon": puntos["lon"],
            "fuente": [f"DATO: {a}" for a in puntos["archivo"]],
        }
    )


# ---------------------------------------------------------------- construccion


def lugares(centros: pd.DataFrame, comunidades: pd.DataFrame | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Pueblos que se cuelgan del grafo: centros poblados con coordenadas y comunidades.

    Un centro sin coordenadas no entra (adenda §4.1): queda en la lista de pendientes.
    """
    con = centros["lat"].notna() & centros["lon"].notna()
    pendientes = [f"{c.nombre}: sin coordenadas, no entra al grafo" for c in centros[~con].itertuples()]
    filas = [
        {
            "id": c.id, "nombre": c.nombre, "tipo": "centro_poblado", "lat": c.lat, "lon": c.lon,
            "acceso_rio": c.acceso_rio, "acceso_via": c.acceso_via, "clase_dane": c.clase_dane, "validado": c.validado,
            "fuente": "DATO: centros_poblados.csv" if c.validado == "si" else "CONFIRMAR: coordenada de centros_poblados.csv sin validar",
            "notas": c.notas,
        }
        for c in centros[con].itertuples()
    ]
    for c in (comunidades if comunidades is not None else pd.DataFrame()).itertuples():
        filas.append(
            {
                "id": c.id, "nombre": c.nombre, "tipo": "comunidad", "lat": c.lat, "lon": c.lon,
                # M01 y M02 salen de la comunidad por via y por rio
                "acceso_rio": "si", "acceso_via": "si", "clase_dane": None, "validado": "no",
                "fuente": "CONFIRMAR: comunidad de nodos.csv (v3.1); clase DANE por confirmar",
                "notas": "No es candidato a acopio por defecto (adenda §4.1)",
            }
        )
    return pd.DataFrame(filas), pendientes


def _red(lineas: list[Linea], modo: str, pueblos: pd.DataFrame, paso_km: float, prefijo: str):
    """Nodos y arcos de una red (rio o via), y el nodo de la red donde se cuelga cada pueblo."""
    p = config.parametro
    tol_conf, tol_vert = p("grafo.tolerancia_confluencia_km"), p("grafo.tolerancia_vertice_km")
    d_max = p("grafo.distancia_max_pueblo_km")
    lineas = [Linea(l.nombre, list(l.coords), l.fuente) for l in lineas]
    cortes: dict[tuple[float, float], str] = {}
    pendientes: list[str] = []

    # Confluencias (rio) o cruces (via): el extremo de una traza sobre otra traza
    union = "confluencia" if modo == "rio" else "cruce"
    for a in lineas:
        for extremo in (0, -1):
            for b in lineas:
                if b is a:
                    continue
                d, i, q = _proyectar(a.coords[extremo], b.coords)
                if d <= tol_conf:
                    q = _insertar(b, i, q, tol_conf)
                    a.coords[extremo] = q
                    cortes.setdefault(_clave(q), f"{union} de {a.nombre} y {b.nombre}")
                    break

    # Pueblos: un vertice en el punto de la traza mas cercano
    colgados = {}
    for lug in pueblos.itertuples():
        punto = (lug.lat, lug.lon)
        cercanos = [(*_proyectar(punto, l.coords), l) for l in lineas]
        if not cercanos:
            continue
        d, i, q, linea = min(cercanos, key=lambda x: x[0])
        if d > d_max:
            pendientes.append(f"{lug.nombre}: queda a {d:.1f} km de la red de {modo}; no se cuelga")
            continue
        q = _insertar(linea, i, q, tol_vert)
        cortes[_clave(q)] = f"{linea.nombre} frente a {lug.nombre}"
        colgados[lug.id] = _clave(q)

    ids: dict[tuple[float, float], str] = {}
    nodos, arcos = [], []

    def nodo(pt: tuple[float, float], linea: Linea, km: float) -> str:
        k = _clave(pt)
        if k not in ids:
            ids[k] = f"{prefijo}{len(ids) + 1:03d}"
            nodos.append(
                {
                    "id": ids[k], "nombre": cortes.get(k, f"{linea.nombre}, km {km:.1f} de la traza"), "tipo": f"punto_{modo}",
                    "cuenca": cuenca_de(linea.nombre) if modo == "rio" else None, "lat": k[0], "lon": k[1],
                    "centro_id": None, "peso_kg_dia": None, "validado": "no", "fuente": linea.fuente, "notas": None,
                }
            )
        return ids[k]

    for linea in lineas:
        km = 0.0
        for trozo in _trozos(linea, set(cortes), paso_km):
            largo = longitud_km(trozo)
            origen = nodo(trozo[0], linea, km)
            km += largo
            destino = nodo(trozo[-1], linea, km)
            if origen == destino:
                continue
            arcos.append(
                {
                    "origen": origen, "destino": destino, "tipo": modo, "modo": modo, "distancia_km": largo,
                    "sentido": 1 if modo == "rio" else 0, "clase_via": "por_confirmar" if modo == "via" else None,
                    "fuente": linea.fuente, "validado": "no",
                    "notas": f"{linea.nombre}: suma de haversine sobre {len(trozo)} vértices",
                }
            )
    return nodos, arcos, {lid: ids[k] for lid, k in colgados.items()}, pendientes


def construir(
    lineas_rio: list[Linea], lineas_via: list[Linea], pueblos: pd.DataFrame, zonas: pd.DataFrame, paso_km: float
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """nodos.csv y aristas.csv (adenda §2.5) desde las trazas, los pueblos y las zonas de pesca."""
    vacio = pd.DataFrame(columns=["id", "acceso_rio", "acceso_via"])
    pueblos = pueblos if len(pueblos) else vacio
    nodos_r, arcos_r, en_rio, pend_r = _red(lineas_rio, "rio", pueblos[pueblos["acceso_rio"] == "si"], paso_km, "R")
    nodos_v, arcos_v, en_via, pend_v = _red(lineas_via, "via", pueblos[pueblos["acceso_via"] == "si"], paso_km, "V")
    nodos, arcos, pendientes = nodos_r + nodos_v, arcos_r + arcos_v, pend_r + pend_v
    por_id = {n["id"]: n for n in nodos}

    for lug in pueblos.itertuples():
        rio = por_id.get(en_rio.get(lug.id))
        nodos.append(
            {
                "id": lug.id, "nombre": lug.nombre, "tipo": lug.tipo,
                "cuenca": rio["cuenca"] if rio else "por_confirmar", "lat": lug.lat, "lon": lug.lon,
                "centro_id": lug.id, "peso_kg_dia": None, "validado": lug.validado, "fuente": lug.fuente, "notas": lug.notas,
            }
        )
        if rio:
            embarcadero = f"E_{lug.id}"
            nodos.append(
                {
                    "id": embarcadero, "nombre": f"Embarcadero de {lug.nombre}", "tipo": "embarcadero", "cuenca": rio["cuenca"],
                    "lat": rio["lat"], "lon": rio["lon"], "centro_id": lug.id, "peso_kg_dia": None, "validado": "no",
                    "fuente": f"{etiqueta(rio['fuente'])}: punto de la traza más cercano a {lug.nombre}", "notas": None,
                }
            )
            arcos.append(
                {
                    "origen": rio["id"], "destino": embarcadero, "tipo": "acceso", "modo": "rio", "distancia_km": 0.0,
                    "sentido": 0, "clase_via": None, "fuente": rio["fuente"], "validado": "no",
                    "notas": "El embarcadero queda sobre el punto del río más cercano al pueblo",
                }
            )
            arcos.append(
                {
                    "origen": embarcadero, "destino": lug.id, "tipo": "transbordo", "modo": "interno", "distancia_km": 0.0,
                    "sentido": 0, "clase_via": None, "fuente": FUENTE_INTERNO, "validado": "no", "notas": None,
                }
            )
        via = por_id.get(en_via.get(lug.id))
        if via:
            arcos.append(
                {
                    "origen": lug.id, "destino": via["id"], "tipo": "via", "modo": "via",
                    "distancia_km": haversine_km(lug.lat, lug.lon, via["lat"], via["lon"]), "sentido": 0,
                    "clase_via": "por_confirmar", "fuente": FUENTE_ENLACE_VIA, "validado": "no", "notas": None,
                }
            )
        if lug.tipo == "centro_poblado" and lug.clase_dane == "cabecera":
            mercado = f"MER_{lug.id}"
            nodos.append(
                {
                    "id": mercado, "nombre": f"Plaza de mercado de {lug.nombre}", "tipo": "mercado", "cuenca": None,
                    "lat": lug.lat, "lon": lug.lon, "centro_id": lug.id, "peso_kg_dia": None, "validado": lug.validado,
                    "fuente": lug.fuente, "notas": "Destino final de la venta",
                }
            )
            arcos.append(
                {
                    "origen": lug.id, "destino": mercado, "tipo": "venta", "modo": "interno", "distancia_km": 0.0,
                    "sentido": 0, "clase_via": None, "fuente": FUENTE_INTERNO, "validado": "no", "notas": None,
                }
            )

    for z in zonas.itertuples():
        if not nodos_r:
            pendientes.append(f"{z.nombre}: no hay río al que colgar la zona")
            continue
        rio = min(nodos_r, key=lambda n: haversine_km(z.lat, z.lon, n["lat"], n["lon"]))
        nodos.append(
            {
                "id": z.id, "nombre": z.nombre, "tipo": "zona_pesca", "cuenca": rio["cuenca"], "lat": z.lat, "lon": z.lon,
                "centro_id": None, "peso_kg_dia": None, "validado": "no", "fuente": z.fuente, "notas": None,
            }
        )
        arcos.append(
            {
                "origen": z.id, "destino": rio["id"], "tipo": "acceso", "modo": "rio",
                "distancia_km": haversine_km(z.lat, z.lon, rio["lat"], rio["lon"]), "sentido": 0, "clase_via": None,
                "fuente": FUENTE_ACCESO_ZONA, "validado": "no", "notas": None,
            }
        )

    tabla_n = pd.DataFrame(nodos, columns=config.COLUMNAS_NODOS_GRAFO)
    tabla_a = pd.DataFrame(arcos)
    tabla_a.insert(0, "id", [f"T{i:03d}" for i in range(1, len(tabla_a) + 1)])
    return tabla_n, tabla_a.reindex(columns=config.COLUMNAS_ARISTAS), pendientes


# ---------------------------------------------------------------- rutas medidas


def _grafo_tipo(aristas: pd.DataFrame, tipo: str) -> nx.Graph:
    g = nx.Graph()
    for a in aristas[aristas["tipo"] == tipo].itertuples():
        g.add_edge(a.origen, a.destino, km=a.distancia_km, fila=a.Index)
    return g


def nodo_medido(aristas: pd.DataFrame, lugar: str, modo: str) -> str:
    """Nodo de la red donde empieza o termina una ruta medida: el punto del rio frente al pueblo o el pueblo."""
    pueblo = LUGARES_MEDIDOS[lugar]
    if modo == "via":
        return pueblo
    acceso = aristas[(aristas["tipo"] == "acceso") & (aristas["destino"] == f"E_{pueblo}")]
    return acceso["origen"].iloc[0] if len(acceso) else pueblo


def comparar_medidas(aristas: pd.DataFrame) -> pd.DataFrame:
    """km de M01–M04 en el grafo (ruta mas corta dentro de su modo) contra lo medido."""
    filas = []
    for m in config.cargar_distancias_medidas().itertuples():
        g = _grafo_tipo(aristas, m.modo)
        o, d = nodo_medido(aristas, m.origen, m.modo), nodo_medido(aristas, m.destino, m.modo)
        km = nx.shortest_path_length(g, o, d, weight="km") if o in g and d in g and nx.has_path(g, o, d) else math.nan
        filas.append(
            {"id": m.id, "modo": m.modo, "km_medido": float(m.distancia_km), "km_grafo": km, "error_pct": 100 * (km / m.distancia_km - 1)}
        )
    return pd.DataFrame(filas)


def _escalar(aristas: pd.DataFrame, tipo: str) -> None:
    """Escala los arcos de `tipo` para que reproduzcan M01–M04, como la calibracion de red.py.

    Los arcos compartidos por varias rutas medidas usan la sinuosidad comun (acotada para que las
    demas rutas cierren); los exclusivos de una ruta la cierran; los demas usan la sinuosidad comun.
    Ningun factor puede ser menor que 1: cada arco mide al menos la linea recta.
    """
    medidas = config.cargar_distancias_medidas()
    medidas = medidas[medidas["modo"] == tipo]
    g = _grafo_tipo(aristas, tipo)
    km = aristas["distancia_km"].to_dict()
    caminos = {}
    for m in medidas.itertuples():
        ruta = nx.shortest_path(g, nodo_medido(aristas, m.origen, tipo), nodo_medido(aristas, m.destino, tipo), weight="km")
        caminos[m.id] = [g.edges[u, v]["fila"] for u, v in zip(ruta, ruta[1:])]
    uso = Counter(i for c in caminos.values() for i in c)
    s = medidas["distancia_km"].sum() / sum(km[i] for c in caminos.values() for i in c)
    compartido = s
    for m in medidas.itertuples():
        comp = sum(km[i] for i in caminos[m.id] if uso[i] > 1)
        excl = sum(km[i] for i in caminos[m.id] if uso[i] == 1)
        if comp > 0 and excl > 0:
            compartido = min(compartido, (m.distancia_km - excl) / comp)
    factor = {i: compartido if uso[i] > 1 else s for i in aristas.index[aristas["tipo"] == tipo]}
    nota = {i: f"sinuosidad común de {' y '.join(medidas['id'])}" for i in factor}
    for m in medidas.itertuples():
        excl = [i for i in caminos[m.id] if uso[i] == 1]
        if excl:
            fijo = sum(km[i] * factor[i] for i in caminos[m.id] if uso[i] > 1)
            f = (m.distancia_km - fijo) / sum(km[i] for i in excl)
            factor.update({i: f for i in excl})
            nota.update({i: f"cierra {m.id}" for i in excl})
    if min(factor.values()) < 1 - 1e-9:
        raise ValueError(f"Escalar {tipo} pide un factor < 1: las trazas miden más que las rutas medidas")
    for i, f in factor.items():
        if km[i] > 0:
            aristas.at[i, "distancia_km"] = km[i] * f
            aristas.at[i, "notas"] = f"{aristas.at[i, 'notas']}; km × {f:.3f} ({nota[i]})"


# ---------------------------------------------------------------- esqueleto SIMULADO


def _linea_de_traza(trazas: pd.DataFrame, traza: str, archivo: str, desde: str | None = None, hasta: str | None = None) -> Linea:
    filas = trazas[trazas["traza"] == traza].reset_index(drop=True)
    if desde is not None:
        i, j = (filas.index[filas["id_nodo"] == x][0] for x in (desde, hasta))
        filas = filas.iloc[i : j + 1]
    return Linea(filas["nombre"].iloc[0], list(zip(filas["lat"], filas["lon"])), f"SIMULADO: {archivo}, traza aproximada")


def comunidades_v31() -> pd.DataFrame:
    nodos = config.cargar_nodos()
    return nodos[nodos["tipo"] == "comunidad"]


def esqueleto_simulado(centros: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Esqueleto minimo mientras llega el KML: Yucao, Puerto Gaitan, San Miguel y La Cristalina.

    Usa solo coordenadas que ya existen (rios.csv, vias.csv, nodos.csv v3.1 y los puntos KML) y escala
    los km para reproducir M01–M04. Todas las filas quedan SIMULADO y validado = no.
    """
    centros = centros if centros is not None else config.cargar_centros_poblados()
    rios, vias, v31 = config.cargar_rios(), config.cargar_vias(), config.cargar_nodos()
    lineas_rio = [_linea_de_traza(rios, t, "rios.csv", *extremos) for t, extremos in ESQUELETO_RIOS.items()]
    lineas_via = [_linea_de_traza(vias, t, "vias.csv") for t in ESQUELETO_VIAS]
    puntos = centros.set_index("id")
    for nombre, extremos in ESQUELETO_VIAS_RECTAS.items():
        coords = [(puntos.at[c, "lat"], puntos.at[c, "lon"]) for c in extremos]
        lineas_via.append(Linea(nombre, coords, "SIMULADO: línea recta entre centros_poblados.csv, vía sin trazar"))
    zonas = v31[v31["id"].isin(ESQUELETO_ZONAS)][["id", "nombre", "lat", "lon"]].assign(fuente="SIMULADO: nodos.csv (v3.1)")
    pueblos, pendientes = lugares(centros, comunidades_v31())
    nodos, aristas, mas = construir(lineas_rio, lineas_via, pueblos, zonas, config.parametro("grafo.paso_esqueleto_km"))
    for tipo in ("rio", "via"):
        _escalar(aristas, tipo)
    for tabla in (nodos, aristas):
        tabla["fuente"] = [
            f"SIMULADO: esqueleto G1 ({f.split(':', 1)[1].strip() if etiqueta(f) == 'SIMULADO' else f})" for f in tabla["fuente"]
        ]
        tabla["validado"] = "no"
    return nodos, aristas, pendientes + mas


# ---------------------------------------------------------------- esquema


def _comunes(df: pd.DataFrame, columnas: list[str], nombre: str, coordenadas_obligatorias: bool) -> list[str]:
    if list(df.columns) != columnas:
        return [f"{nombre}: columnas {list(df.columns)}, se esperaban {columnas}"]
    errores = []
    if df["id"].isna().any():
        errores.append(f"{nombre}: hay filas sin id")
    repetidos = sorted(set(df["id"][df["id"].duplicated()]))
    if repetidos:
        errores.append(f"{nombre}: ids repetidos {repetidos}")
    malas = df.loc[~df["fuente"].map(etiqueta).isin(config.ETIQUETAS), "id"]
    if len(malas):
        errores.append(f"{nombre}: fuente sin etiqueta válida en {list(malas)}")
    if not df["validado"].isin(SI_NO).all():
        errores.append(f"{nombre}: validado debe ser si o no")
    if "lat" in df:
        for col, (lo, hi) in (("lat", RANGO_LAT), ("lon", RANGO_LON)):
            v = pd.to_numeric(df[col], errors="coerce")
            if (df[col].notna() & v.isna()).any():
                errores.append(f"{nombre}: {col} no numérica")
            fuera = df.loc[v.notna() & ~v.between(lo, hi), "id"]
            if len(fuera):
                errores.append(f"{nombre}: {col} fuera de [{lo}, {hi}] en {list(fuera)}")
            if coordenadas_obligatorias and v.isna().any():
                errores.append(f"{nombre}: {col} vacía en {list(df.loc[v.isna(), 'id'])}")
    return errores


def _numerica_no_negativa(df: pd.DataFrame, col: str, nombre: str, obligatoria: bool) -> list[str]:
    v = pd.to_numeric(df[col], errors="coerce")
    errores = []
    if (df[col].notna() & v.isna()).any() or (obligatoria and v.isna().any()):
        errores.append(f"{nombre}: {col} debe ser un número")
    if (v < 0).any():
        errores.append(f"{nombre}: {col} negativa en {list(df.loc[v < 0, 'id'])}")
    return errores


def validar_centros(centros: pd.DataFrame) -> list[str]:
    errores = _comunes(centros, config.COLUMNAS_CENTROS, "centros_poblados", coordenadas_obligatorias=False)
    if errores and errores[0].startswith("centros_poblados: columnas"):
        return errores
    if not centros["clase_dane"].isin(CLASES_DANE).all():
        errores.append(f"centros_poblados: clase_dane fuera de {sorted(CLASES_DANE)}")
    if not pd.api.types.is_integer_dtype(centros["habitantes_2018"]):
        errores.append("centros_poblados: habitantes_2018 debe ser entero")
    for col in ("acceso_rio", "acceso_via", "energia"):
        if not centros[col].isin(ACCESOS).all():
            errores.append(f"centros_poblados: {col} fuera de {sorted(ACCESOS)}")
    return errores + _numerica_no_negativa(centros, "capacidad_frio_kg", "centros_poblados", obligatoria=False)


def validar_nodos(nodos: pd.DataFrame, nombre: str = "nodos") -> list[str]:
    errores = _comunes(nodos, config.COLUMNAS_NODOS_GRAFO, nombre, coordenadas_obligatorias=True)
    if errores and errores[0].startswith(f"{nombre}: columnas"):
        return errores
    malos = sorted(set(nodos["tipo"]) - TIPOS_NODO)
    if malos:
        errores.append(f"{nombre}: tipos de nodo desconocidos {malos}")
    if not (nodos["cuenca"].isna() | nodos["cuenca"].isin(CUENCAS)).all():
        errores.append(f"{nombre}: cuenca fuera de {sorted(CUENCAS)}")
    return errores + _numerica_no_negativa(nodos, "peso_kg_dia", nombre, obligatoria=False)


def validar_aristas(aristas: pd.DataFrame, nombre: str = "aristas") -> list[str]:
    errores = _comunes(aristas, config.COLUMNAS_ARISTAS, nombre, coordenadas_obligatorias=False)
    if errores and errores[0].startswith(f"{nombre}: columnas"):
        return errores
    malos = sorted(set(aristas["tipo"]) - set(MODO_DE_ARCO))
    if malos:
        errores.append(f"{nombre}: tipos de arco desconocidos {malos}")
    modo_mal = aristas.loc[aristas["modo"] != aristas["tipo"].map(MODO_DE_ARCO), "id"]
    if len(modo_mal):
        errores.append(f"{nombre}: modo que no corresponde al tipo en {list(modo_mal)}")
    errores += _numerica_no_negativa(aristas, "distancia_km", nombre, obligatoria=True)
    if not aristas["sentido"].isin([-1, 0, 1]).all():
        errores.append(f"{nombre}: sentido debe ser -1, 0 o 1")
    sin_rio = aristas.loc[(aristas["sentido"] != 0) & (aristas["tipo"] != "rio"), "id"]
    if len(sin_rio):
        errores.append(f"{nombre}: sentido distinto de 0 en arcos que no son de río {list(sin_rio)}")
    return errores


def validar_esquema(nodos: pd.DataFrame, aristas: pd.DataFrame, centros: pd.DataFrame | None = None) -> list[str]:
    """Todos los errores de esquema del grafo; lista vacia si esta bien."""
    errores = validar_nodos(nodos) + validar_aristas(aristas)
    if errores:
        return errores
    ids = set(nodos["id"])
    sueltos = sorted((set(aristas["origen"]) | set(aristas["destino"])) - ids)
    if sueltos:
        errores.append(f"aristas: origen o destino que no está en nodos {sueltos}")
    if centros is not None:
        errores += validar_centros(centros)
        sin_centro = sorted(set(nodos["centro_id"].dropna()) - set(centros["id"]) - ids)
        if sin_centro:
            errores.append(f"nodos: centro_id desconocido {sin_centro}")
    return errores


# ---------------------------------------------------------------- pantalla y salida


def con_etiqueta(tabla: pd.DataFrame) -> pd.DataFrame:
    """La tabla con la etiqueta de la fuente y su detalle en columnas aparte, al inicio."""
    partes = tabla["fuente"].astype(str).str.split(":", n=1, expand=True)
    salida = tabla.drop(columns="fuente")
    salida.insert(1, "etiqueta", partes[0].str.strip())
    salida.insert(2, "detalle", partes[1].str.strip() if 1 in partes else "")
    return salida


def resumen_fuentes(tablas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Filas por etiqueta de fuente en cada tabla."""
    conteo = {nombre: t["fuente"].map(etiqueta).value_counts() for nombre, t in tablas.items()}
    return pd.DataFrame(conteo).reindex(ORDEN_ETIQUETAS).fillna(0).astype(int)


def escribir(nodos: pd.DataFrame, aristas: pd.DataFrame, salida: Path) -> None:
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    nodos = nodos.assign(lat=nodos["lat"].astype(float).round(6), lon=nodos["lon"].astype(float).round(6))
    aristas = aristas.assign(distancia_km=aristas["distancia_km"].astype(float).round(4), sentido=aristas["sentido"].astype(int))
    nodos.to_csv(salida / "nodos.csv", index=False)
    aristas.to_csv(salida / "aristas.csv", index=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KML de Google Earth → nodos.csv y aristas.csv del grafo (adenda §2.3)")
    parser.add_argument("--rio", type=Path, help="KML con un LineString por río, de aguas arriba a aguas abajo")
    parser.add_argument("--vias", type=Path, help="KML con un LineString por carretera")
    parser.add_argument("--pesca", type=Path, help="KML con un punto por zona de pesca")
    parser.add_argument("--invertir", nargs="*", default=[], help="ríos trazados de aguas abajo a aguas arriba")
    parser.add_argument("--centros", type=Path, default=config.DIR_DATOS / "centros_poblados.csv")
    parser.add_argument("--salida", type=Path, default=config.DIR_GRAFO)
    parser.add_argument("--paso-km", type=float, default=None, help="un vértice cada ~paso km (parametros.yaml)")
    parser.add_argument("--esqueleto", action="store_true", help="sin KML: esqueleto SIMULADO que reproduce M01–M04")
    args = parser.parse_args(argv)

    centros = config.leer_csv_grafo(args.centros, config.COLUMNAS_CENTROS)
    if args.esqueleto:
        nodos, aristas, pendientes = esqueleto_simulado(centros)
    else:
        if args.rio is None:
            parser.error("falta --rio (o usa --esqueleto mientras no haya KML)")
        lineas_rio = leer_lineas_kml(args.rio)
        desconocidos = set(args.invertir) - {l.nombre for l in lineas_rio}
        if desconocidos:
            parser.error(f"--invertir: no hay ríos con esos nombres en el KML: {sorted(desconocidos)}")
        for linea in lineas_rio:
            if linea.nombre in args.invertir:
                linea.coords.reverse()
        lineas_via = leer_lineas_kml(args.vias) if args.vias else []
        zonas = zonas_kml(args.pesca) if args.pesca else pd.DataFrame(columns=["id", "nombre", "lat", "lon", "fuente"])
        pueblos, pendientes = lugares(centros, comunidades_v31())
        paso = args.paso_km or config.parametro("grafo.paso_km")
        nodos, aristas, mas = construir(lineas_rio, lineas_via, pueblos, zonas, paso)
        pendientes += mas

    errores = validar_esquema(nodos, aristas, centros)
    if errores:
        print("El grafo no cumple el esquema:", *errores, sep="\n- ")
        return 1
    escribir(nodos, aristas, args.salida)
    print(f"Escrito en {args.salida}: {len(nodos)} nodos y {len(aristas)} arcos")
    print(nodos["tipo"].value_counts().to_string(), aristas["tipo"].value_counts().to_string(), sep="\n\n")
    print("\nRutas medidas (km):")
    print(comparar_medidas(aristas).round(2).to_string(index=False))
    if pendientes:
        print("\nPendientes:", *pendientes, sep="\n- ")
    return 0
