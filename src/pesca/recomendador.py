"""Asignacion con capacidades y recomendador "¿A dónde llevo mi pescado?" sobre el grafo v4 (adenda §5, R3).

- flujo_minimo: networkx.min_cost_flow con costo round(1e4 · c_ij), kg enteros y un destino "sin_destino";
- comparar_con_voronoi: donde el reparto con capacidades se aparta del acopio mas cercano;
- recomendar: compara ir directo a la plaza, dejarlo en un pueblo y esperar al comprador, y llevarlo a un
  acopio con frio (que sigue en camion refrigerado). Gana la que deja mas plata neta al pescador.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import networkx as nx
import pandas as pd

from pesca import acopios, busqueda, config, grafo, pesos
from pesca.degradacion import factor_precio, precio_base

ESCALA_COSTO = 10_000
SUMIDERO = "sumidero"
TEXTO_TIPO = {"plaza": "por río a la plaza", "acopio": "a un acopio con frío", "esperar": "dejarlo y esperar al comprador"}


# ---------------------------------------------------------------- flujo de costo minimo (§5)


def flujo_minimo(c: pd.DataFrame, w: pd.Series, capacidad: pd.Series, abiertos) -> pd.DataFrame:
    """Reparto de los kg de cada zona entre los acopios abiertos sin pasar su capacidad.

    min_cost_flow solo acepta enteros: costo = round(1e4 · c_ij) y kg redondeados. Lo que no cabe va a
    sin_destino con el costo de perder todo el lote (y un poco mas, para que se use solo si no hay lugar).
    """
    abiertos = list(abiertos)
    kg = w.round().astype(int)
    total = int(kg.sum())
    tope = config.parametro("acopios_grafo.costo_sin_destino")
    red = nx.DiGraph()
    red.add_node(SUMIDERO, demand=total)
    for i, oferta in kg.items():
        red.add_node(("zona", i), demand=-int(oferta))
        for j in abiertos:
            red.add_edge(("zona", i), ("acopio", j), weight=round(ESCALA_COSTO * c.at[i, j]), capacity=int(oferta))
        red.add_edge(("zona", i), ("acopio", acopios.SIN_DESTINO), weight=round(ESCALA_COSTO * tope) + 1, capacity=int(oferta))
    for j in abiertos:
        k = capacidad.get(j, math.nan)
        red.add_edge(("acopio", j), SUMIDERO, weight=0, capacity=total if pd.isna(k) else int(k))
    red.add_edge(("acopio", acopios.SIN_DESTINO), SUMIDERO, weight=0, capacity=total)
    flujo = nx.min_cost_flow(red)
    filas = [
        {"zona": u[1], "destino": v[1], "kg_dia": kg_flujo, "c_ij": c.at[u[1], v[1]] if v[1] in c.columns else tope}
        for u, salientes in flujo.items() if u != SUMIDERO and u[0] == "zona"
        for v, kg_flujo in salientes.items() if kg_flujo > 0
    ]
    return pd.DataFrame(filas, columns=["zona", "destino", "kg_dia", "c_ij"])


def comparar_con_voronoi(c: pd.DataFrame, w: pd.Series, capacidad: pd.Series, abiertos) -> pd.DataFrame:
    """Por zona: su acopio mas cercano (Voronoi) y a donde la manda el flujo con capacidades."""
    vor = acopios.voronoi(c, abiertos)
    flujo = flujo_minimo(c, w, capacidad, abiertos)
    filas = []
    for i in c.index:
        sub = flujo[flujo["zona"] == i]
        destinos = ", ".join(f"{d} ({kg} kg)" for d, kg in zip(sub["destino"], sub["kg_dia"]))
        filas.append({"zona": i, "voronoi": vor[i], "con_capacidad": destinos, "difiere": set(sub["destino"]) != {vor[i]}})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- recomendador


@dataclass
class Opcion:
    tipo: str  # plaza, acopio o esperar
    destino: str  # centro poblado
    nombre: str
    factible: bool
    motivo: str = ""
    dq: float = math.inf
    calidad: float = 0.0
    factor: float = 0.0
    cop_kg: float = 0.0
    valor: float = 0.0
    costo_viaje: float = 0.0
    neto: float = -math.inf
    horas: float = math.inf
    km_rio: float = 0.0
    km_contra: float = 0.0
    camino: tuple = ()  # nodos del grafo base, de la zona a la plaza
    sentidos: list = field(default_factory=list)  # (u, v, modo, sentido) de cada tramo, para el mapa
    texto: list = field(default_factory=list)


@dataclass
class Recomendacion:
    origen: str
    bote: str
    kg: float
    nevera: str
    opciones: list
    mejor: Opcion | None


def _ruta_base(gc: nx.DiGraph, camino: tuple) -> tuple:
    return tuple(n for n, _ in camino)


def _tramos(g: nx.DiGraph, camino: tuple) -> list:
    return [(u, v, g.edges[u, v]["modo"], g.edges[u, v]["sentido"]) for u, v in zip(camino, camino[1:])]


def _vuelta(g: nx.DiGraph, j: str, cond: pesos.Condiciones, capa: str, t0: float):
    """De la salida del pueblo j a la plaza: en frio (camion refrigerado) o en hielo (carro del comprador)."""
    mercado = grafo.mercados(g)[0]
    gc = pesos.expandir_capas(g, cond)
    return busqueda.dijkstra_capas(gc, (acopios.salida(g, j), capa), {(mercado, c) for c in pesos.CAPAS},
                                   pesos.funcion_costo(cond), t0)


def _opcion(g, gc_ida, origen, j, tipo, cond, kg) -> Opcion:
    """Una forma de vender: ida por agua hasta j y, segun el tipo, vender, guardar en frio o esperar."""
    p = config.parametro
    nombre = g.nodes[acopios.entrada(g, j)]["nombre"]
    ida_cond = cond.con(acopios=frozenset(), camion_refrigerado=False)
    estado = {(acopios.entrada(g, j), c) for c in pesos.CAPAS}
    if (origen, "hielo") not in gc_ida:
        return Opcion(tipo, j, nombre, False, "el origen no está sobre el río")
    ida = busqueda.dijkstra_capas(gc_ida, (origen, "hielo"), estado, pesos.funcion_costo(ida_cond))
    if not ida.alcanzable:
        motivo = "no se llega por río con este bote" if any(acopios.entrada(g, j) == n for n, _ in gc_ida.nodes) else "no tiene acceso por río"
        return Opcion(tipo, j, nombre, False, motivo)
    camino = _ruta_base(gc_ida, ida.camino)
    dq, horas = ida.costo, ida.horas
    if tipo == "acopio":
        espera_h = p("acopios.horas_espera_acopio")
        dq += pesos.perdida(espera_h, "frio", horas, cond)
        vuelta = _vuelta(g, j, cond.con(acopios=frozenset({j})), "frio", horas + espera_h)
    elif tipo == "esperar":
        ciclo = p("cadena_actual.ciclo_comprador_dias")
        espera_h = 24 * (ciclo["min"] + ciclo["max"]) / 2
        dq += pesos.perdida(espera_h, "hielo", horas, cond)
        vuelta = _vuelta(g, j, cond.con(acopios=frozenset(), camion_refrigerado=False), "hielo", horas + espera_h)
    else:
        vuelta = _vuelta(g, j, cond.con(acopios=frozenset(), camion_refrigerado=False), "hielo", horas)
    if not vuelta.alcanzable:
        return Opcion(tipo, j, nombre, False, "no hay cómo seguir a la plaza")
    dq += vuelta.costo
    # la ida termina en j:entra y la vuelta sale de j:sale (el arco de espera los une)
    completo = camino + tuple(n for n, _ in vuelta.camino if n != camino[-1])
    tramos = _tramos(g, completo)
    km_rio = sum(g.edges[u, v]["d_km"] for u, v, modo, _ in _tramos(g, camino) if modo == "rio")
    km_contra = sum(g.edges[u, v]["d_km"] for u, v, modo, s in _tramos(g, camino) if modo == "rio" and s == -1)
    q = max(0.0, 1 - dq)
    fp = factor_precio(q)
    cop_kg = precio_base() * fp
    from pesca.asignacion import costo_viaje

    viaje = costo_viaje(km_rio, ida.horas, cond.bote)
    return Opcion(
        tipo, j, nombre, True, dq=dq, calidad=q, factor=fp, cop_kg=cop_kg, valor=kg * cop_kg, costo_viaje=viaje,
        neto=kg * cop_kg - viaje, horas=ida.horas, km_rio=km_rio, km_contra=km_contra, camino=completo,
        sentidos=tramos, texto=grafo.ruta_a_texto(g, completo),
    )


def recomendar(origen: str, bote: str, kg: float, cond: pesos.Condiciones, g: nx.DiGraph | None = None) -> Recomendacion:
    """Compara todas las formas de vender y recomienda la que deja mas plata neta."""
    g = g if g is not None else grafo.construir_grafo()
    cond = cond.con(bote=bote)
    gc_ida = pesos.expandir_capas(acopios.grafo_ida(g), cond.con(acopios=frozenset(), camion_refrigerado=False))
    plaza = next(g.nodes[m]["centro_id"] for m in grafo.mercados(g))
    centros = sorted({a["centro_id"] for _, a in g.nodes(data=True) if a["tipo"] == "centro_poblado"})
    opciones = [_opcion(g, gc_ida, origen, plaza, "plaza", cond, kg)]
    for j in centros:
        if j == plaza:
            continue
        tipo = "acopio" if j in cond.acopios or cond.camion_refrigerado else "esperar"
        opciones.append(_opcion(g, gc_ida, origen, j, tipo, cond, kg))
    factibles = [o for o in opciones if o.factible]
    mejor = max(factibles, key=lambda o: o.neto) if factibles else None
    return Recomendacion(origen, bote, kg, cond.nevera, opciones, mejor)


# ---------------------------------------------------------------- explicacion


def _pesos(cop: float) -> str:
    return f"${cop:,.0f}".replace(",", ".")


def _km(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _q(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def explicar(rec: Recomendacion) -> str:
    """Explicacion en lenguaje sencillo: a donde, por que, la corriente y el transbordo."""
    m = rec.mejor
    if m is None:
        return "Con este bote no hay cómo llegar a vender: revisa la temporada o busca un bote con motor."
    partes = []
    if m.tipo == "plaza":
        partes.append(f"**Llévalo directo a la plaza de Puerto Gaitán.**")
    elif m.tipo == "acopio":
        partes.append(f"**Llévalo al acopio de {m.nombre}.** Allí lo dejas en el cuarto frío (transbordo) y sigue en camión refrigerado a la plaza.")
    else:
        partes.append(f"**Déjalo en {m.nombre} y espera al comprador.** Es lo menos malo, pero se daña mientras esperas.")
    if m.km_rio > 0:
        if m.km_contra > 0:
            partes.append(f"Por el río son {_km(m.km_rio)} km, {_km(m.km_contra)} de ellos **contra la corriente**, unas {_km(m.horas)} horas.")
        else:
            partes.append(f"Por el río son {_km(m.km_rio)} km **a favor de la corriente** o sin corriente, unas {_km(m.horas)} horas.")
    partes.append(f"Llega con calidad {_q(m.calidad)} y te pagan el {100 * m.factor:.0f} % del precio: {_pesos(m.cop_kg)} por kg, "
                  f"{_pesos(m.valor)} por {rec.kg:g} kg, menos {_pesos(m.costo_viaje)} del viaje = **{_pesos(m.neto)}**.")
    otras = [o for o in rec.opciones if o is not m]
    for o in otras:
        if not o.factible:
            partes.append(f"{TEXTO_TIPO[o.tipo].capitalize()} ({o.nombre}): no se puede, {o.motivo}.")
        elif o.tipo == "plaza" and o.km_contra > 0:
            partes.append(f"Ir directo a la plaza son {_km(o.km_contra)} km contra la corriente: llegaría con calidad {_q(o.calidad)} y te dejaría {_pesos(o.neto)}.")
        else:
            partes.append(f"{TEXTO_TIPO[o.tipo].capitalize()} ({o.nombre}): calidad {_q(o.calidad)}, te dejaría {_pesos(o.neto)}.")
    return "\n\n".join(partes)


def tabla_opciones(rec: Recomendacion) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"opción": TEXTO_TIPO[o.tipo], "destino": o.nombre, "se puede": o.factible, "calidad": o.calidad if o.factible else None,
             "% del precio": 100 * o.factor if o.factible else None, "neto COP": o.neto if o.factible else None,
             "km por río": o.km_rio if o.factible else None, "km contra corriente": o.km_contra if o.factible else None,
             "motivo": o.motivo}
            for o in rec.opciones
        ]
    )
