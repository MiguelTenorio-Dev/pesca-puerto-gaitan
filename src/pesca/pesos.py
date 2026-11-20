"""Pesos de las aristas del grafo v4 (adenda §3). Funciones puras: todo numero sale de parametros.yaml.

Para un arco e = (u → v), una capa de conservacion y la hora t (horas desde la captura al entrar):
1. velocidad efectiva v_e: rio v_b + σ·c (σ = +1 a favor, −1 en contra); via v_vehiculo·clase·temporada;
   si v_e < v_min el arco es infactible para ese bote y se guarda el motivo;
2. tiempo τ = d / v_e (los arcos internos tienen su propio tiempo: transbordo, espera, venta);
3. capa: solo cambia en el arco de espera de un pueblo con equipo (cuarto frio activo o camion
   refrigerado): hielo → frio. Nunca vuelve de frio a hielo;
4. perdida de calidad ΔQ (§3.5): en hielo, las horas con hielo vigente (H − t) van a T_hielo y el resto a
   T_ambiente; en frio todo va a T_frio; congelado no se deteriora.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import networkx as nx

from pesca import config
from pesca.degradacion import rrs
from pesca.red import haversine_km

CAPAS = ("hielo", "frio", "congelado")
# Capas que recorren el grafo. Congelado no viaja: es una espera en un congelador (cadena de hoy) y ningun
# arco del grafo v4 lleva a esa capa. Si viajara con RRS = 0, la heuristica de A* dejaria de ser admisible.
CAPAS_GRAFO = ("hielo", "frio")
CRITERIOS = ("calidad", "tiempo", "distancia", "saltos", "costo_cop")
NEVERAS = {"buena": "degradacion.horas_hielo_nevera_nueva", "deteriorada": "degradacion.horas_hielo_nevera_deteriorada", "sin_hielo": None}
TEXTO_NEVERA = {"buena": "nevera buena", "deteriorada": "icopor deteriorado", "sin_hielo": "sin hielo"}
# Acopios de la v3.1 (escenario de la barra lateral) -> centros poblados del grafo v4
ACOPIOS_V31 = {"A01": "CP01", "A02": "CP03", "A03": "CP02"}


@dataclass(frozen=True)
class Condiciones:
    """Lo que cambia el peso de un arco: bote, temporada, nevera, acopios con frio y camion."""

    bote: str = "madera_remo"
    temporada: str = "aguas_bajas"
    nevera: str = "deteriorada"
    acopios: frozenset[str] = field(default_factory=lambda: frozenset({"CP01"}))
    camion_refrigerado: bool = False
    espera_h: float | None = None  # None = pesos.espera_h
    puntos_frios: frozenset[str] = field(default_factory=frozenset)  # pueblos donde se recoge hielo nuevo

    def __post_init__(self) -> None:
        if self.bote not in config.cargar_parametros()["embarcaciones"]:
            raise ValueError(f"Embarcación desconocida: {self.bote}")
        if self.temporada not in config.TEMPORADAS:
            raise ValueError(f"Temporada desconocida: {self.temporada}")
        if self.nevera not in NEVERAS:
            raise ValueError(f"Nevera desconocida: {self.nevera}")
        object.__setattr__(self, "acopios", frozenset(self.acopios))
        object.__setattr__(self, "puntos_frios", frozenset(self.puntos_frios))

    def con(self, **cambios) -> Condiciones:
        return replace(self, **cambios)


def condiciones(escenario, bote: str = "madera_remo", nevera: str = "deteriorada") -> Condiciones:
    """Condiciones del grafo v4 a partir del escenario de la barra lateral."""
    acopios = {ACOPIOS_V31[a] for a in escenario.acopios_activos if a in ACOPIOS_V31} | set(escenario.acopios_grafo)
    return Condiciones(
        bote=bote,
        temporada=escenario.temporada,
        nevera="buena" if escenario.hielo_a_bordo else nevera,
        acopios=frozenset(acopios),
        camion_refrigerado=escenario.camion_refrigerado,
        puntos_frios=frozenset(getattr(escenario, "puntos_frios_grafo", frozenset())),
    )


# ---------------------------------------------------------------- parametros


def horas_hielo(nevera: str) -> float:
    """H: horas que dura el hielo desde la captura segun el estado de la nevera."""
    ruta = NEVERAS[nevera]
    return 0.0 if ruta is None else config.parametro(ruta)


def temperatura(capa: str, con_hielo: bool = True) -> float:
    p = config.parametro
    if capa == "hielo":
        return p("pesos.t_hielo_c") if con_hielo else p("degradacion.t_ambiente_c")
    if capa == "frio":
        return p("degradacion.t_frio_c")
    if capa == "congelado":
        return p("degradacion.t_congelado_c")
    raise ValueError(f"Capa desconocida: {capa}")


def vehiculo(capa: str) -> str:
    return config.parametro("pesos.vehiculo_capa")[capa]


def corriente_kmh(temporada: str) -> float:
    return config.parametro(f"rio.corriente_{temporada}_kmh")


def tiempo_interno_h(tipo: str, cond: Condiciones) -> float:
    if tipo == "transbordo":
        return config.parametro("rio.tiempo_transbordo_h")
    if tipo == "espera":
        return cond.espera_h if cond.espera_h is not None else config.parametro("pesos.espera_h")
    return 0.0  # venta


# ---------------------------------------------------------------- pasos 1 a 4


def velocidad_efectiva(arco: dict, cond: Condiciones, capa: str = "hielo") -> tuple[float | None, bool, str]:
    """(v_e, factible, motivo). Para arcos internos v_e es None y siempre son factibles."""
    p = config.parametro
    if arco["modo"] == "rio":
        v_b, c = p(f"embarcaciones.{cond.bote}"), corriente_kmh(cond.temporada)
        sigma = int(arco["sentido"])
        v = v_b + sigma * c
        if v < p("rio.v_minima_kmh"):
            signo = "−" if sigma < 0 else "+"
            return None, False, (
                f"{cond.bote} contra la corriente en {cond.temporada.replace('_', ' ')}: "
                f"{v_b:g} {signo} {c:g} = {v:g} km/h, menos que el mínimo de {p('rio.v_minima_kmh'):g} km/h"
            )
        return v, True, ""
    if arco["modo"] == "via":
        clase = arco.get("clase_via") if isinstance(arco.get("clase_via"), str) else "por_confirmar"
        v = p(f"vehiculos.{vehiculo(capa)}") * p("pesos.factor_clase_via")[clase] * p("pesos.factor_temporada_via")[cond.temporada]
        return v, True, ""
    return None, True, ""


def tiempo_arco(arco: dict, cond: Condiciones, capa: str = "hielo") -> float | None:
    """τ en horas; None si el arco es infactible."""
    v, factible, _ = velocidad_efectiva(arco, cond, capa)
    if not factible:
        return None
    if arco["modo"] == "interno":
        return tiempo_interno_h(arco["tipo"], cond)
    return arco["d_km"] / v


def capa_nueva(arco: dict, capa: str, cond: Condiciones) -> str:
    """La capa solo cambia de hielo a frio, nunca al reves:
    - en el arco de espera de un pueblo con equipo (cuarto frio de un acopio activo, o camion refrigerado);
    - al pasar por un punto frio (transbordo o espera de ese pueblo): se recoge hielo nuevo, que dura mas
      que cualquier tramo que falte, asi que el resto del viaje va como en frio.
    """
    if capa != "hielo":
        return capa
    con_equipo = arco.get("centro") in cond.acopios or cond.camion_refrigerado
    if arco["tipo"] == "espera" and con_equipo:
        return "frio"
    pueblo = arco.get("pueblo") if arco["tipo"] == "transbordo" else arco.get("centro") if arco["tipo"] == "espera" else None
    if pueblo is not None and pueblo in cond.puntos_frios:
        return "frio"
    return capa


def perdida(tau: float, capa: str, t: float, cond: Condiciones) -> float:
    """ΔQ de pasar τ horas en una capa, entrando a la hora t (adenda §3.5)."""
    vu0 = config.parametro("degradacion.vu0_h")
    if capa == "hielo":
        t_h = min(tau, max(0.0, horas_hielo(cond.nevera) - t))
        return (t_h * rrs(temperatura("hielo")) + (tau - t_h) * rrs(temperatura("hielo", con_hielo=False))) / vu0
    return tau * rrs(temperatura(capa)) / vu0


def costo_arco(arco: dict, capa: str, t: float, cond: Condiciones) -> tuple[float, float, str] | None:
    """(ΔQ, τ, capa_nueva) del arco; None si es infactible. El tiempo del arco corre en la capa nueva."""
    nueva = capa_nueva(arco, capa, cond)
    tau = tiempo_arco(arco, cond, nueva)
    if tau is None:
        return None
    return perdida(tau, nueva, t, cond), tau, nueva


def costo_cop(arco: dict, cond: Condiciones) -> float:
    """COP del arco [SIMULADO]: gasolina por km en rio (solo con motor) y camion por km en via."""
    p = config.parametro
    if arco["modo"] == "rio":
        return arco["d_km"] * p("pescador.cop_por_km_motor") if cond.bote.endswith("_motor") else 0.0
    if arco["modo"] == "via":
        return arco["d_km"] * p("inversiones.camion_cop_km")
    return 0.0


def peso(arco: dict, criterio: str, capa: str = "hielo", t: float = 0.0, cond: Condiciones | None = None) -> float | None:
    """w_e segun el criterio (adenda §3.6); None si el arco es infactible."""
    cond = cond or Condiciones()
    if criterio not in CRITERIOS:
        raise ValueError(f"Criterio desconocido: {criterio}")
    costo = costo_arco(arco, capa, t, cond)
    if costo is None:
        return None
    dq, tau, _ = costo
    return {"calidad": dq, "tiempo": tau, "distancia": arco["d_km"], "saltos": 1.0, "costo_cop": costo_cop(arco, cond)}[criterio]


# ---------------------------------------------------------------- grafo por capas


def expandir_capas(g: nx.DiGraph, cond: Condiciones) -> nx.DiGraph:
    """Grafo de busqueda: un nodo (v, capa) por nodo y capa que viaja; los arcos infactibles no entran."""
    gc = nx.DiGraph(capas=CAPAS_GRAFO, condiciones=cond)
    for n, a in g.nodes(data=True):
        for capa in CAPAS_GRAFO:
            gc.add_node((n, capa), **a, capa=capa, base=n)
    for u, v, a in g.edges(data=True):
        for capa in CAPAS_GRAFO:
            nueva = capa_nueva(a, capa, cond)
            tau = tiempo_arco(a, cond, nueva)
            if tau is not None:
                gc.add_edge((u, capa), (v, nueva), **a, tau=tau, capa_origen=capa, capa_destino=nueva)
    return gc


def funcion_costo(cond: Condiciones, criterio: str = "calidad"):
    """costo(u, v, datos, t) -> (w, τ) para las busquedas sobre el grafo por capas."""

    def costo(u, v, datos: dict, t: float) -> tuple[float, float] | None:
        w = peso(datos, criterio, u[1], t, cond)
        return None if w is None else (w, datos["tau"])

    return costo


def v_max(cond: Condiciones) -> float:
    """La mayor velocidad efectiva posible en el escenario (aguas abajo o el vehiculo mas rapido)."""
    p = config.parametro
    rio = p(f"embarcaciones.{cond.bote}") + corriente_kmh(cond.temporada)
    via = max(p(f"vehiculos.{v}") for v in set(p("pesos.vehiculo_capa").values()))
    via *= max(p("pesos.factor_clase_via").values()) * p("pesos.factor_temporada_via")[cond.temporada]
    return max(rio, via)


def rrs_min() -> float:
    """La menor RRS entre las capas que recorren el grafo (hielo, con y sin hielo vigente, y frio)."""
    return min(rrs(temperatura("hielo")), rrs(temperatura("hielo", con_hielo=False)), rrs(temperatura("frio")))


def heuristica(gc: nx.DiGraph, destino: str, cond: Condiciones, criterio: str = "calidad"):
    """h(n) de A* (adenda §3.9): linea recta / v_max × RRS_min / VU0. Admisible: ningun camino es mas
    corto que la linea recta, ninguno va mas rapido que v_max y ninguno se deteriora menos que RRS_min."""
    fin = gc.nodes[(destino, CAPAS[0])]
    escala = {"calidad": rrs_min() / (v_max(cond) * config.parametro("degradacion.vu0_h")), "tiempo": 1 / v_max(cond)}
    if criterio not in escala:
        raise ValueError("A* usa la heurística de calidad o de tiempo")
    k = escala[criterio]

    def h(nodo) -> float:
        a = gc.nodes[nodo]
        return haversine_km(a["lat"], a["lon"], fin["lat"], fin["lon"]) * k

    return h


# ---------------------------------------------------------------- explicacion


def _n(x: float, d: int = 3) -> str:
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def explicar_arco(arco: dict, cond: Condiciones, capa: str = "hielo", t: float = 0.0) -> list[str]:
    """Paso a paso del peso del arco, con la formula y los numeros (para la pantalla)."""
    p = config.parametro
    nueva = capa_nueva(arco, capa, cond)
    pasos = []
    v, factible, motivo = velocidad_efectiva(arco, cond, nueva)
    if arco["modo"] == "rio":
        sigma = int(arco["sentido"])
        sentido = {1: "a favor (σ = +1)", -1: "en contra (σ = −1)", 0: "sin corriente (σ = 0)"}[sigma]
        pasos.append(
            f"1. Velocidad: v_e = v_b + σ·c = {p(f'embarcaciones.{cond.bote}'):g} + ({sigma:+d})·{corriente_kmh(cond.temporada):g}"
            f" = {_n(v, 1) if factible else _n(p(f'embarcaciones.{cond.bote}') + sigma * corriente_kmh(cond.temporada), 1)} km/h ({sentido})"
        )
    elif arco["modo"] == "via":
        pasos.append(f"1. Velocidad: {vehiculo(nueva)} por carretera = {_n(v, 1)} km/h (clase y temporada incluidas)")
    else:
        pasos.append(f"1. Arco interno ({arco['tipo']}): no tiene velocidad, su tiempo es un parámetro")
    if not factible:
        pasos.append(f"**Infactible:** {motivo}. El arco no entra al grafo para este bote.")
        return pasos
    tau = tiempo_arco(arco, cond, nueva)
    if arco["modo"] == "interno":
        pasos.append(f"2. Tiempo: τ = {_n(tau)} h")
    else:
        pasos.append(f"2. Tiempo: τ = d / v_e = {_n(arco['d_km'], 2)} / {_n(v, 1)} = {_n(tau)} h")
    cambio = f" (cambia de {capa} a {nueva}: entra al cuarto frío o al camión)" if nueva != capa else ""
    pasos.append(f"3. Capa: {nueva}{cambio}")
    vu0 = p("degradacion.vu0_h")
    dq = perdida(tau, nueva, t, cond)
    if nueva == "hielo":
        h = horas_hielo(cond.nevera)
        t_h = min(tau, max(0.0, h - t))
        r_h, r_a = rrs(temperatura("hielo")), rrs(temperatura("hielo", con_hielo=False))
        pasos.append(
            f"4. Hielo: H = {_n(h, 1)} h ({TEXTO_NEVERA[cond.nevera]}), t = {_n(t, 2)} h al entrar → "
            f"t_h = min(τ, max(0, H − t)) = {_n(t_h)} h con hielo y {_n(tau - t_h)} h sin hielo"
        )
        pasos.append(
            f"5. ΔQ = [t_h·RRS({temperatura('hielo'):g} °C) + (τ − t_h)·RRS({temperatura('hielo', False):g} °C)] / VU0 = "
            f"[{_n(t_h)}·{_n(r_h, 2)} + {_n(tau - t_h)}·{_n(r_a, 2)}] / {vu0:g} = **{_n(dq, 4)}**"
        )
    else:
        pasos.append(f"4. ΔQ = τ·RRS({temperatura(nueva):g} °C) / VU0 = {_n(tau)}·{_n(rrs(temperatura(nueva)), 2)} / {vu0:g} = **{_n(dq, 4)}**")
    pasos.append(f"Calidad si el lote solo hiciera este tramo: Q = 1 − ΔQ = {_n(max(0.0, 1 - dq), 3)}")
    return pasos


def arco_ejemplo_m04() -> dict:
    """El tramo del ejemplo §3.8: San Miguel → Puerto Gaitán por río, 41,65 km (M04), todo en contra."""
    m04 = config.cargar_distancias_medidas().set_index("id").loc["M04"]
    return {"id": "M04", "d_km": float(m04["distancia_km"]), "tipo": "rio", "modo": "rio", "sentido": -1, "clase_via": None}


def arco_ejemplo_m03() -> dict:
    """San Miguel → Puerto Gaitán por carretera, 38,9 km (M03)."""
    m03 = config.cargar_distancias_medidas().set_index("id").loc["M03"]
    return {"id": "M03", "d_km": float(m03["distancia_km"]), "tipo": "via", "modo": "via", "sentido": 0, "clase_via": None}
