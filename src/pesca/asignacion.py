"""Recomendador "¿A donde llevo mi pescado?" y problema de transporte de toda la flota (R3).

Formas de vender que se comparan para un pescador:
- plaza: por rio hasta el malecon de Puerto Gaitan y venta el mismo dia;
- desembarque: dejarlo donde la señora (o en San Miguel sin frio, o en el cruce del Vichada)
  y esperar al comprador, que lo lleva por carretera;
- acopio activo (bimodal): por rio hasta el acopio, cuarto frio, transbordo y carretera hasta la plaza.
Se recomienda la que deja mas plata (valor = kg × precio base × factor de precio, especificacion §1).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from functools import cache

import networkx as nx
import pandas as pd

from pesca import busqueda, cadena_actual, config, degradacion as dg, poblacion, red, transporte
from pesca.escenario import Escenario

PLAZA_RIO = "D_MALECON"  # Puerto Gaitan por rio
PLAZA = "A01@via"
ACOPIO_PLAZA = "A01"  # la plaza es el acopio de Puerto Gaitan: se vende ahi mismo
NEVERAS = {
    "sin_hielo": None,
    "deteriorada": "degradacion.horas_hielo_nevera_deteriorada",
    "buena": "degradacion.horas_hielo_nevera_nueva",
}
CAPACIDAD_ACOPIO = {"A02": "acopios.capacidad_san_miguel_kg", "A03": "acopios.capacidad_puente_arimena_kg"}
SIN_DESTINO = "sin_destino"
SUMIDERO = "sumidero"
ESCALA_KG = 10  # min_cost_flow solo acepta enteros: el flujo va en decimas de kg


def horas_hielo(nevera: str) -> float:
    if nevera not in NEVERAS:
        raise ValueError(f"Nevera desconocida: {nevera}")
    return 0.0 if NEVERAS[nevera] is None else config.parametro(NEVERAS[nevera])


# ---------------------------------------------------------------- opciones


@dataclass(frozen=True, eq=False)
class Opcion:
    tipo: str  # "plaza" | "desembarque" | "acopio"
    destino: str
    nombre: str
    factible: bool
    motivo: str = ""
    ruta: tuple[str, ...] = ()
    tramos: pd.DataFrame | None = None
    km_rio: float = 0.0
    km_via: float = 0.0
    pct_contra_corriente: float = 0.0
    bimodal: bool = False
    horas_viaje: float = 0.0
    horas_espera: float = 0.0
    horas_hasta_venta: float = 0.0
    calidad: float = 0.0
    cop_kg: float = 0.0
    cop_total: float = 0.0
    cop_perdidos_por_etapa: dict | None = None
    prob_congelador: float | None = None
    cop_kg_congelador: float | None = None  # donde la señora: valor si cabe en el congelador
    cop_kg_icopor: float | None = None  # donde la señora: valor si se desborda a icopor
    vehiculo: str = ""


@dataclass(frozen=True, eq=False)
class Recomendacion:
    origen: str
    embarcacion: str
    kg: float
    nevera: str
    mejor: Opcion | None
    alternativas: tuple[Opcion, ...]
    explicacion: str


def dias_espera_esperados() -> float:
    """Dias que espera en promedio un lote: el comprador llega cada L ~ U{min..max} dias y el lote llega en cualquier dia."""
    ciclo = config.parametro("cadena_actual.ciclo_comprador_dias")
    return ((ciclo["min"] + ciclo["max"]) / 2 + 1) / 2


def horas_falla_esperadas(dias: float) -> float:
    """Horas a T ambiente que se esperan por cortes de luz mas largos que lo que aguanta el congelador."""
    p = config.parametro
    a, b = p("cadena_actual.horas_corte")["min"], p("cadena_actual.horas_corte")["max"]
    u = p("cadena_actual.horas_descongelacion")
    if u <= a:
        exceso = (a + b) / 2 - u
    elif u >= b:
        exceso = 0.0
    else:
        exceso = (b - u) ** 2 / (2 * (b - a))
    return dias * p("cadena_actual.p_corte_dia") * exceso


@cache
def prob_congelador(candidata: str, temporada: str) -> float:
    """Probabilidad de que el lote quepa en el congelador de la señora (Monte Carlo de la Fase 2)."""
    datos = cadena_actual.cargar_precalculado()
    if datos is None:
        corrida = cadena_actual.corrida_ejemplo(Escenario.base().con(desembarque_senora=candidata, temporada=temporada))
        inv = corrida.inventario.iloc[-1]
        total = inv["kg_congelado"] + inv["kg_icopor"]
        return float(inv["kg_congelado"] / total) if total > 0 else 1.0
    c = datos["corridas"]
    sub = c[(c["candidata"] == candidata) & (c["temporada"] == temporada)]
    return float(1 - sub["pct_desborde_senora"].mean() / 100)


def _destinos(origen: str, escenario: Escenario, grafo: nx.DiGraph) -> list[tuple[str, str]]:
    """(tipo, lugar) de cada forma de vender que tiene sentido para este origen."""
    activos = escenario.acopios_activos
    candidatos = [("plaza", PLAZA_RIO), ("desembarque", escenario.desembarque_senora)]
    if "A02" not in activos:
        candidatos.append(("desembarque", "A02"))  # San Miguel hoy: sin frio
    for cruce in config.parametro("poblacion.desembarque_vichada").values():
        if cruce not in activos:
            candidatos.append(("desembarque", cruce))
    candidatos += [("acopio", a) for a in sorted(activos) if a != ACOPIO_PLAZA]
    cuenca = grafo.nodes[origen]["cuenca"]
    # La plaza se muestra siempre (aunque sea de otra cuenca); lo demas, solo en la misma cuenca
    return [(t, l) for t, l in candidatos if t == "plaza" or grafo.nodes[red.clave(l, red.CAPA_RIO)]["cuenca"] == cuenca]


def _sitio(tipo: str, destino: str, escenario: Escenario) -> str:
    if tipo == "plaza":
        return "plaza"
    if tipo == "acopio":
        return "acopio"
    if destino == escenario.desembarque_senora:
        return "senora"
    return "sin_frio"


def _avanzar_rio(lote: dg.Lote, horas: float, escenario: Escenario, etapa: str = "rio") -> None:
    dg.avanzar(lote, horas, etapa, dg.REFRIGERADO if escenario.hielo_a_bordo else dg.ICOPOR_HIELO)


def _evaluar(tipo: str, destino: str, origen: str, perfil: transporte.Perfil, kg: float, hielo_h: float,
             escenario: Escenario, grafo: nx.DiGraph) -> Opcion:
    p = config.parametro
    nombre = grafo.nodes[red.clave(destino, red.CAPA_RIO)]["nombre"]
    if tipo == "plaza":
        nombre = grafo.nodes[PLAZA]["nombre"]
    destino_rio = red.clave(destino, red.CAPA_RIO)
    if grafo.nodes[origen]["cuenca"] != grafo.nodes[destino_rio]["cuenca"]:
        return Opcion(tipo, destino, nombre, False, "No hay paso por agua: está en otra cuenca")

    rio_g = red.subgrafo_modo(grafo, red.CAPA_RIO)
    viaje_rio = busqueda.dijkstra(rio_g, origen, destino_rio, transporte.peso(perfil, "perdida"))
    if not viaje_rio.alcanzable:
        return Opcion(tipo, destino, nombre, False, transporte.motivo_infactible(rio_g, origen, destino_rio, perfil))

    sitio = _sitio(tipo, destino, escenario)
    refrigerado = tipo == "acopio" and escenario.camion_refrigerado
    vehiculo = "camion_refrigerado" if refrigerado else "comprador_carro"
    perfil_via = dataclasses.replace(perfil, vehiculo=vehiculo)
    via_g = red.subgrafo_modo(grafo, red.CAPA_VIA, "transbordo")
    viaje_via = busqueda.dijkstra(via_g, destino_rio, PLAZA, transporte.peso(perfil_via, "tiempo"))

    tramos = pd.concat(
        [transporte.tramos_ruta(grafo, viaje_rio.ruta, perfil), transporte.tramos_ruta(grafo, viaje_via.ruta, perfil_via)],
        ignore_index=True,
    )
    horas_rio = tramos.loc[tramos["modo"] == red.CAPA_RIO, "horas"].sum()
    horas_via = tramos.loc[tramos["modo"] != red.CAPA_RIO, "horas"].sum()
    horas_faena = p("degradacion.horas_faena")

    def lote_hasta_el_destino() -> dg.Lote:
        lote = dg.Lote(kg=kg, hielo_restante_h=hielo_h)
        _avanzar_rio(lote, horas_faena, escenario, "faena")
        _avanzar_rio(lote, horas_rio, escenario)
        return lote

    def carretera(lote: dg.Lote, estado: str) -> dg.Lote:
        dg.avanzar(lote, horas_via, "carretera", estado)
        return lote

    prob = None
    cop_cong = cop_icop = None
    if sitio == "plaza":
        espera_h = 0.0
        valores = [(1.0, dg.valor_lote(carretera(lote_hasta_el_destino(), dg.ICOPOR_HIELO)))]
    elif sitio == "acopio":
        espera_h = p("acopios.horas_espera_acopio")
        lote = lote_hasta_el_destino()
        dg.avanzar(lote, espera_h, "espera", dg.REFRIGERADO)
        valores = [(1.0, dg.valor_lote(carretera(lote, dg.REFRIGERADO if refrigerado else dg.AMBIENTE)))]
    else:
        espera_h = dias_espera_esperados() * cadena_actual.HORAS_DIA
        icopor = lote_hasta_el_destino()
        dg.poner_hielo(icopor, p("cadena_actual.horas_hielo_desborde"))
        dg.avanzar(icopor, espera_h, "espera", dg.ICOPOR_HIELO)
        v_icopor = dg.valor_lote(carretera(icopor, dg.AMBIENTE))
        if sitio == "senora":
            prob = prob_congelador(escenario.desembarque_senora, escenario.temporada)
            congelado = lote_hasta_el_destino()
            dg.congelar(congelado)
            falla = min(espera_h, horas_falla_esperadas(dias_espera_esperados()))
            dg.avanzar(congelado, falla, "espera", dg.FALLA)
            dg.avanzar(congelado, espera_h - falla, "espera", dg.CONGELADO)
            v_cong = dg.valor_lote(carretera(congelado, dg.AMBIENTE))
            valores = [(prob, v_cong), (1 - prob, v_icopor)]
            cop_cong, cop_icop = v_cong["cop_recibido"] / kg, v_icopor["cop_recibido"] / kg
        else:
            valores = [(1.0, v_icopor)]

    def esperado(clave: str) -> float:
        return sum(w * v[clave] for w, v in valores)

    km_rio = tramos.loc[tramos["modo"] == red.CAPA_RIO, "km"].sum()
    km_contra = tramos.loc[tramos["sentido"] == "aguas_arriba", "km"].sum()
    return Opcion(
        tipo=tipo,
        destino=destino,
        nombre=nombre,
        factible=True,
        ruta=viaje_rio.ruta + viaje_via.ruta[1:],
        tramos=tramos,
        km_rio=km_rio,
        km_via=tramos.loc[tramos["modo"] == red.CAPA_VIA, "km"].sum(),
        pct_contra_corriente=100 * km_contra / km_rio if km_rio > 0 else 0.0,
        bimodal=tipo != "plaza",
        horas_viaje=horas_faena + horas_rio + horas_via,
        horas_espera=espera_h,
        horas_hasta_venta=horas_faena + horas_rio + espera_h + horas_via,
        calidad=esperado("calidad"),
        cop_kg=esperado("cop_recibido") / kg,
        cop_total=esperado("cop_recibido"),
        cop_perdidos_por_etapa={e: esperado(f"cop_{e}") for e in dg.ETAPAS_COP},
        prob_congelador=prob,
        cop_kg_congelador=cop_cong,
        cop_kg_icopor=cop_icop,
        vehiculo=vehiculo,
    )


def recomendar(origen: str, embarcacion: str, kg: float, escenario: Escenario, nevera: str = "deteriorada") -> Recomendacion:
    """Compara todas las formas de vender desde `origen` (nodo@rio) y recomienda la que deja mas plata."""
    grafo = red.construir_red()
    if origen not in grafo or grafo.nodes[origen]["capa"] != red.CAPA_RIO:
        raise ValueError(f"El origen debe ser un nodo de río: {origen}")
    if kg <= 0:
        raise ValueError("Los kg deben ser positivos")
    perfil = transporte.Perfil.desde_escenario(escenario, embarcacion)
    hielo_h = horas_hielo(nevera)
    opciones = [_evaluar(t, d, origen, perfil, kg, hielo_h, escenario, grafo) for t, d in _destinos(origen, escenario, grafo)]
    factibles = sorted((o for o in opciones if o.factible), key=lambda o: (o.cop_total, o.calidad), reverse=True)
    orden = factibles + [o for o in opciones if not o.factible]
    mejor = factibles[0] if factibles else None
    rec = Recomendacion(origen, embarcacion, kg, nevera, mejor, tuple(orden), "")
    return dataclasses.replace(rec, explicacion=explicar(rec))


# ---------------------------------------------------------------- explicacion


def pesos(cop: float) -> str:
    """$145.000 (separador de miles con punto, como en Colombia)."""
    return "$" + f"{cop:,.0f}".replace(",", ".")


def numero(x: float, decimales: int = 1) -> str:
    """Numero con coma decimal: 1,9."""
    return f"{x:.{decimales}f}".replace(".", ",")


def _texto_corriente(o: Opcion) -> str:
    contra = o.km_rio * o.pct_contra_corriente / 100
    favor = o.km_rio - contra
    if contra < 0.05:
        return f"{favor:.0f} km **a favor de la corriente**"
    if favor < 0.05:
        return f"{contra:.0f} km **contra la corriente**"
    return f"{favor:.0f} km **a favor** y {contra:.0f} km **contra la corriente**"


def _horas_rio(o: Opcion) -> float:
    return o.tramos.loc[o.tramos["modo"] == red.CAPA_RIO, "horas"].sum()


def explicar(rec: Recomendacion) -> str:
    """Explicacion en lenguaje sencillo: a donde, por donde, corriente, transbordo, cuanto y por que no lo otro."""
    m = rec.mejor
    if m is None:
        motivo = rec.alternativas[0].motivo if rec.alternativas else ""
        return f"Desde aquí no hay ninguna ruta posible con este bote. {motivo}."
    partes = []
    if m.cop_total <= 0:
        partes.append(
            "Con lo que hay hoy, **ninguna opción salva tu pescado**: llega dañado y lo rechazan. "
            f"Lo que menos daño le hace es llevarlo a **{m.nombre}**."
        )
    else:
        partes.append(f"Lleva tu pescado a **{m.nombre}**.")
    partes.append(f"Ve por el río: {_texto_corriente(m)}, unas {numero(_horas_rio(m))} horas.")
    if m.tipo == "plaza":
        partes.append("Desembarca en el malecón y lo vendes el mismo día en la plaza.")
    elif m.tipo == "acopio":
        vehiculo = "camión refrigerado" if m.vehiculo == "camion_refrigerado" else "carro"
        partes.append(
            f"Allá lo guardan en el cuarto frío unas {m.horas_espera:.0f} horas, hacen el **transbordo** "
            f"y sigue en {vehiculo} por **carretera** hasta la plaza ({m.km_via:.0f} km)."
        )
    else:
        partes.append(f"Allá espera unos {m.horas_espera / 24:.0f} días hasta que llegue el comprador.")
        if m.prob_congelador is not None:
            partes.append(f"Hay espacio en el congelador en {round(10 * m.prob_congelador)} de cada 10 viajes; si no, va en icopor.")
    if m.cop_total > 0:
        partes.append(f"Llega con calidad {numero(m.calidad, 2)} (de 0 a 1) y te pagan cerca de **{pesos(m.cop_total)}**.")
    else:
        partes.append(f"Llega con calidad {numero(m.calidad, 2)} (de 0 a 1).")

    plaza = next((o for o in rec.alternativas if o.tipo == "plaza"), None)
    if plaza is not None and plaza is not m:
        if plaza.factible:
            partes.append(
                f"No subas por el río hasta Puerto Gaitán: son {_texto_corriente(plaza)}, {_horas_rio(plaza):.0f} horas"
                + (f", y te pagarían {pesos(plaza.cop_total)}." if plaza.cop_total > 0 else ", y el pescado llega dañado.")
            )
        else:
            partes.append(f"Hasta Puerto Gaitán por río no se puede: {plaza.motivo.lower()}.")
    if rec.nevera != "buena" and m.calidad < config.parametro("precio_calidad.escalones")[0]["calidad_min"]:
        partes.append("Llevar hielo cambia mucho: prueba con una nevera buena.")
    return " ".join(partes)


# ---------------------------------------------------------------- problema de transporte


def resolver_flujo(
    oferta: dict[str, float],
    costos: dict[tuple[str, str], float],
    capacidades: dict[str, float | None],
    costo_sin_destino: dict[str, float],
) -> tuple[dict[tuple[str, str], float], float]:
    """Flujo de costo minimo: cada origen manda su oferta a un destino o a sin_destino.

    `costos` en COP por kg; `capacidades` en kg (None = sin limite). networkx.min_cost_flow
    solo acepta enteros: el flujo se escala a decimas de kg y los costos a COP enteros.
    Devuelve ({(origen, destino): kg}, costo total en COP).
    """
    g = nx.DiGraph()
    unidades = {o: round(kg * ESCALA_KG) for o, kg in oferta.items()}
    total = sum(unidades.values())
    for o, u in unidades.items():
        g.add_node(("o", o), demand=-u)
    g.add_node(SUMIDERO, demand=total)
    for (o, d), c in costos.items():
        g.add_edge(("o", o), ("d", d), weight=round(c))
    for d, cap in capacidades.items():
        if ("d", d) in g:
            atributos = {} if cap is None else {"capacity": round(cap * ESCALA_KG)}
            g.add_edge(("d", d), SUMIDERO, weight=0, **atributos)
    for o in unidades:
        g.add_edge(("o", o), ("d", SIN_DESTINO), weight=round(costo_sin_destino[o]))
    g.add_edge(("d", SIN_DESTINO), SUMIDERO, weight=0)

    flujo = nx.min_cost_flow(g)
    salida = {}
    for (_, o), destinos in ((n, f) for n, f in flujo.items() if isinstance(n, tuple) and n[0] == "o"):
        for (_, d), u in destinos.items():
            if u > 0:
                salida[(o, d)] = u / ESCALA_KG
    costo = sum(kg * (costos[(o, d)] if d != SIN_DESTINO else costo_sin_destino[o]) for (o, d), kg in salida.items())
    return salida, costo


def _clave_destino(o: Opcion, parte: str = "") -> str:
    return f"{o.tipo}:{o.destino}{parte}"


def _poblacion_y_oferta(escenario: Escenario) -> tuple[pd.DataFrame, dict[str, float]]:
    pob = cadena_actual.corrida_ejemplo(escenario).poblacion
    act = poblacion.actividad_diagnostico()
    oferta = dict(zip(pob["id"], pob["kg_por_faena"] * pob["p_faena_pico"] * act))
    return pob, oferta


def _nevera(pesc) -> str:
    return "buena" if pesc.nevera_buena else "deteriorada"


def problema_transporte(escenario: Escenario) -> dict:
    """Reparto optimo de toda la flota entre las formas de vender, con capacidades y sin_destino.

    Devuelve flujos (pescador, destino, kg_dia, cop_kg), uso de cada destino, costo optimo y costo de hoy.
    """
    p = config.parametro
    p0 = dg.precio_base()
    pob, oferta = _poblacion_y_oferta(escenario)
    capacidad_congelador = p("cadena_actual.n_congeladores") * p("cadena_actual.kg_por_congelador") / (
        sum(p("cadena_actual.ciclo_comprador_dias").values()) / 2
    )
    costos, capacidades, opciones, nombres = {}, {}, {}, {}
    for pesc in pob.itertuples():
        rec = recomendar(pesc.ubicacion, pesc.embarcacion, 1.0, escenario, _nevera(pesc))
        for o in rec.alternativas:
            if not o.factible:
                continue
            if o.prob_congelador is not None:  # la señora: congelador (con capacidad) o icopor
                partes = {":congelador": (o.cop_kg_congelador, capacidad_congelador), ":icopor": (o.cop_kg_icopor, None)}
            elif o.tipo == "acopio":
                cap = p(CAPACIDAD_ACOPIO[o.destino]) / (p("acopios.horas_espera_acopio") / 24) if o.destino in CAPACIDAD_ACOPIO else None
                partes = {"": (o.cop_kg, cap)}
            elif o.tipo == "plaza":
                partes = {"": (o.cop_kg, p("acopios.capacidad_plaza_kg_dia"))}
            else:
                partes = {"": (o.cop_kg, None)}
            for sufijo, (cop_kg, cap) in partes.items():
                d = _clave_destino(o, sufijo)
                costos[(pesc.id, d)] = p0 - cop_kg
                capacidades[d] = cap
                opciones[(pesc.id, d)] = o
                nombres[d] = o.nombre + {":congelador": " (congelador)", ":icopor": " (icopor)"}.get(sufijo, "")
    flujos, costo = resolver_flujo(oferta, costos, capacidades, {i: p0 for i in oferta})

    filas = []
    for (pescador, d), kg in flujos.items():
        o = opciones.get((pescador, d))
        filas.append({
            "pescador": pescador,
            "destino": d,
            "destino_nombre": nombres.get(d, "Sin destino (se pierde)"),
            "kg_dia": kg,
            "cop_perdidos_kg": costos.get((pescador, d), p0),
            "ruta": o.ruta if o else (),
        })
    tabla = pd.DataFrame(filas).merge(pob[["id", "zona", "embarcacion", "sitio"]], left_on="pescador", right_on="id").drop(columns="id")
    uso = tabla.groupby(["destino", "destino_nombre"], as_index=False)["kg_dia"].sum()
    uso["capacidad_kg_dia"] = uso["destino"].map(lambda d: capacidades.get(d))
    uso["pct_uso"] = 100 * uso["kg_dia"] / uso["capacidad_kg_dia"]
    return {
        "flujos": tabla,
        "uso": uso,
        "costo_optimo_dia": costo,
        "costo_hoy_dia": costo_hoy(escenario),
        "kg_dia": sum(oferta.values()),
        "kg_sin_destino": tabla.loc[tabla["destino"] == SIN_DESTINO, "kg_dia"].sum(),
        "valor_posible_dia": p0 * sum(oferta.values()),
    }


def asignacion_hoy(escenario: Escenario) -> pd.DataFrame:
    """Cada pescador en su desembarque habitual de hoy (si no puede remontar, el centro alcanzable mas cercano)."""
    hoy = Escenario.base().con(desembarque_senora=escenario.desembarque_senora, temporada=escenario.temporada)
    pob, oferta = _poblacion_y_oferta(escenario)
    filas = []
    for pesc in pob.itertuples():
        rec = recomendar(pesc.ubicacion, pesc.embarcacion, 1.0, hoy, _nevera(pesc))
        habitual = next((o for o in rec.alternativas if o.destino == pesc.desembarque and o.factible), None)
        o = habitual if habitual is not None else rec.mejor
        filas.append({"pescador": pesc.id, "destino": o.destino if o else SIN_DESTINO, "kg_dia": oferta[pesc.id],
                      "cop_kg": o.cop_kg if o else 0.0})
    return pd.DataFrame(filas)


def costo_hoy(escenario: Escenario) -> float:
    """COP perdidos por dia con la asignacion de hoy."""
    hoy = asignacion_hoy(escenario)
    return float((hoy["kg_dia"] * (dg.precio_base() - hoy["cop_kg"])).sum())


def flujos_por_arista(tabla: pd.DataFrame) -> dict[tuple[str, str], float]:
    """kg/dia por arista de la red segun el reparto (para el mapa)."""
    salida: dict[tuple[str, str], float] = {}
    for fila in tabla.itertuples():
        for u, v in zip(fila.ruta, fila.ruta[1:]):
            salida[(u, v)] = salida.get((u, v), 0.0) + fila.kg_dia
    return salida
