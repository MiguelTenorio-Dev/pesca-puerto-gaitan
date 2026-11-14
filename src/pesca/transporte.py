"""Velocidades, tiempos y costos de cada arista segun la embarcacion, el vehiculo y la corriente.

El peso de busqueda devuelve None si la arista es infactible (misma convencion de NetworkX):
aguas arriba con velocidad efectiva <= v_minima el bote no avanza.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import networkx as nx
import pandas as pd

from pesca import config, red
from pesca.degradacion import rrs
from pesca.escenario import Escenario

CRITERIOS = ("perdida", "tiempo", "distancia")
TIPOS_ORIGEN = ("zona_pesca", "comunidad", "desembarque")

Peso = Callable[[str, str, dict], float | None]


def embarcaciones() -> list[str]:
    return list(config.cargar_parametros()["embarcaciones"])


@dataclass(frozen=True)
class Perfil:
    """Con que se viaja y a que temperatura va el pescado en cada modo."""

    embarcacion: str
    vehiculo: str
    corriente_kmh: float
    t_rio_c: float
    t_via_c: float

    def __post_init__(self) -> None:
        if self.embarcacion not in embarcaciones():
            raise ValueError(f"Embarcación desconocida: {self.embarcacion}")
        if self.vehiculo not in config.cargar_parametros()["vehiculos"]:
            raise ValueError(f"Vehículo desconocido: {self.vehiculo}")

    @classmethod
    def desde_escenario(cls, escenario: Escenario, embarcacion: str) -> Perfil:
        p = config.parametro
        t_amb, t_frio = p("degradacion.t_ambiente_c"), p("degradacion.t_frio_c")
        return cls(
            embarcacion=embarcacion,
            vehiculo="camion_refrigerado" if escenario.camion_refrigerado else "comprador_carro",
            corriente_kmh=escenario.corriente_kmh(),
            t_rio_c=t_frio if escenario.hielo_a_bordo else t_amb,
            t_via_c=t_frio if escenario.camion_refrigerado else t_amb,
        )

    @property
    def v_bote_kmh(self) -> float:
        return config.parametro(f"embarcaciones.{self.embarcacion}")

    @property
    def v_vehiculo_kmh(self) -> float:
        return config.parametro(f"vehiculos.{self.vehiculo}")

    @property
    def v_max_kmh(self) -> float:
        """La mayor velocidad efectiva posible en cualquier arista (para la heuristica de A*)."""
        return max(self.v_bote_kmh + self.corriente_kmh, self.v_vehiculo_kmh)

    @property
    def rrs_min(self) -> float:
        """La menor tasa de deterioro posible en cualquier arista (para la heuristica de A*)."""
        return min(rrs(self.t_rio_c), rrs(self.t_via_c))


# ---------------------------------------------------------------- costo por arista


def velocidad_efectiva(datos: dict, perfil: Perfil) -> tuple[float | None, str]:
    """Velocidad en km/h, o None con el motivo si el tramo es infactible."""
    if datos["modo"] == red.CAPA_VIA:
        return perfil.v_vehiculo_kmh, ""
    if datos["modo"] != red.CAPA_RIO:
        raise ValueError(f"Una arista de {datos['modo']} no tiene velocidad")
    c = perfil.corriente_kmh
    v = perfil.v_bote_kmh + c if datos["sentido"] == "aguas_abajo" else perfil.v_bote_kmh - c
    v_minima = config.parametro("rio.v_minima_kmh")
    if v <= v_minima:
        texto = perfil.embarcacion.replace("_", " a ")
        return None, (
            f"Contra la corriente ({c:g} km/h), un bote de {texto} avanza a {v:g} km/h: "
            f"no alcanza el mínimo de {v_minima:g} km/h"
        )
    return v, ""


def tiempo_h(datos: dict, perfil: Perfil) -> float | None:
    if datos["modo"] == "transbordo":
        return config.parametro("rio.tiempo_transbordo_h")
    v, _ = velocidad_efectiva(datos, perfil)
    return None if v is None else datos["distancia_km"] / v


def temperatura_c(datos: dict, perfil: Perfil) -> float:
    return perfil.t_via_c if datos["modo"] == red.CAPA_VIA else perfil.t_rio_c


def perdida(datos: dict, perfil: Perfil) -> float | None:
    """Fraccion de la vida util que se consume en la arista: horas × RRS(T) / VU0."""
    t = tiempo_h(datos, perfil)
    if t is None:
        return None
    return t * rrs(temperatura_c(datos, perfil)) / config.parametro("degradacion.vu0_h")


def peso(perfil: Perfil, criterio: str = "perdida") -> Peso:
    """Funcion de peso (u, v, datos) -> costo o None, para las busquedas propias y para networkx."""
    if criterio not in CRITERIOS:
        raise ValueError(f"Criterio desconocido: {criterio}")

    def funcion(u: str, v: str, datos: dict) -> float | None:
        if criterio == "perdida":
            return perdida(datos, perfil)
        t = tiempo_h(datos, perfil)
        if t is None:
            return None
        return t if criterio == "tiempo" else datos["distancia_km"]

    return funcion


def heuristica(grafo: nx.DiGraph, destino: str, perfil: Perfil, criterio: str = "perdida") -> Callable[[str], float]:
    """Cota inferior admisible del costo restante hasta `destino`.

    linea recta / v_max (× RRS_min / VU0 si el criterio es la perdida). Como cada arista mide
    al menos la linea recta entre sus extremos, ningun camino es mas corto que la linea recta,
    ninguna arista es mas rapida que v_max y ninguna se deteriora menos que con RRS_min.
    """
    fin = grafo.nodes[destino]
    if criterio == "distancia":
        escala = 1.0
    elif criterio == "tiempo":
        escala = 1.0 / perfil.v_max_kmh
    else:
        escala = perfil.rrs_min / (perfil.v_max_kmh * config.parametro("degradacion.vu0_h"))

    def h(nodo: str) -> float:
        a = grafo.nodes[nodo]
        return red.haversine_km(a["lat"], a["lon"], fin["lat"], fin["lon"]) * escala

    return h


# ---------------------------------------------------------------- rutas


def tramos_ruta(grafo: nx.DiGraph, ruta: tuple[str, ...], perfil: Perfil) -> pd.DataFrame:
    """Una fila por arista de la ruta, con modo, sentido, km, horas y perdida."""
    filas = []
    for u, v in zip(ruta, ruta[1:]):
        d = grafo.edges[u, v]
        filas.append(
            {
                "desde": grafo.nodes[u]["nombre"],
                "hasta": grafo.nodes[v]["nombre"],
                "modo": d["modo"],
                "sentido": d["sentido"],
                "km": d["distancia_km"],
                "horas": tiempo_h(d, perfil),
                "perdida": perdida(d, perfil),
                "fuente": d["fuente"],
            }
        )
    return pd.DataFrame(filas, columns=["desde", "hasta", "modo", "sentido", "km", "horas", "perdida", "fuente"])


def resumen_ruta(grafo: nx.DiGraph, ruta: tuple[str, ...], perfil: Perfil) -> dict:
    """km por modo, horas, % contra corriente y calidad del viaje (solo el viaje)."""
    t = tramos_ruta(grafo, ruta, perfil)
    km_rio = t.loc[t["modo"] == red.CAPA_RIO, "km"].sum()
    km_contra = t.loc[t["sentido"] == "aguas_arriba", "km"].sum()
    perdida_total = t["perdida"].sum()
    return {
        "km": t["km"].sum(),
        "km_rio": km_rio,
        "km_via": t.loc[t["modo"] == red.CAPA_VIA, "km"].sum(),
        "horas": t["horas"].sum(),
        "pct_contra_corriente": 100 * km_contra / km_rio if km_rio > 0 else 0.0,
        "transbordos": int((t["modo"] == "transbordo").sum()),
        "perdida": perdida_total,
        "calidad_viaje": max(0.0, 1 - perdida_total),
    }


def motivo_infactible(grafo: nx.DiGraph, origen: str, destino: str, perfil: Perfil) -> str:
    """Explica por que no hay ruta factible: sin conexion, o el primer tramo que no se puede remontar."""
    from pesca import busqueda

    estructural = busqueda.bfs(grafo, origen, destino)
    if not estructural.alcanzable:
        return "No hay conexión ni por río ni por carretera"
    for u, v in zip(estructural.ruta, estructural.ruta[1:]):
        d = grafo.edges[u, v]
        if d["modo"] == red.CAPA_RIO:
            v_ef, motivo = velocidad_efectiva(d, perfil)
            if v_ef is None:
                return motivo
    return "No hay una ruta factible con esta embarcación"


def matriz_origen_acopio(escenario: Escenario, criterio: str = "perdida") -> pd.DataFrame:
    """Matriz origen × acopio × embarcacion con la mejor ruta segun `criterio`.

    La calidad es solo la del viaje; la Fase 2 suma la faena y la espera.
    """
    from pesca import busqueda

    grafo = red.construir_red()
    nodos = config.cargar_nodos()
    origenes = nodos[nodos["tipo"].isin(TIPOS_ORIGEN)]
    acopios = nodos[nodos["tipo"] == "acopio"]
    filas = []
    for emb in embarcaciones():
        perfil = Perfil.desde_escenario(escenario, emb)
        w = peso(perfil, criterio)
        for o in origenes.itertuples():
            inicio = red.clave(o.id, red.CAPA_RIO)
            for a in acopios.itertuples():
                destinos = [red.clave(a.id, c) for c in (red.CAPA_RIO, red.CAPA_VIA) if red.clave(a.id, c) in grafo]
                mejor = min((busqueda.dijkstra(grafo, inicio, d, w) for d in destinos), key=lambda r: r.costo)
                fila = {
                    "origen": o.id,
                    "origen_nombre": o.nombre,
                    "acopio": a.id,
                    "acopio_nombre": a.nombre,
                    "activo": a.id in escenario.acopios_activos,
                    "embarcacion": emb,
                    "factible": mejor.alcanzable,
                    "motivo": "",
                }
                if mejor.alcanzable:
                    fila.update(resumen_ruta(grafo, mejor.ruta, perfil))
                else:
                    fila["motivo"] = motivo_infactible(grafo, inicio, destinos[0], perfil)
                filas.append(fila)
    return pd.DataFrame(filas)

