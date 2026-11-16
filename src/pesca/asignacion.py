"""Recomendador "¿A donde llevo mi pescado?" y problema de transporte de toda la flota (R3).

Formas de vender que se comparan para un pescador:
- plaza: por rio hasta el malecon de Puerto Gaitan y venta el mismo dia;
- desembarque: dejarlo donde la señora (o en San Miguel sin frio, o en el cruce del Vichada)
  y esperar al comprador, que lo lleva por carretera;
- acopio activo (bimodal): por rio hasta el acopio, cuarto frio, transbordo y carretera hasta la plaza.
Se recomienda la que deja mas plata neta: lo que le pagan (kg × precio base × factor de precio,
especificacion §1) menos lo que le cuesta el viaje por rio (gasolina y tiempo, ida y vuelta).
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
    costo_viaje: float = 0.0  # gasolina + tiempo del pescador, ida y vuelta por rio (COP)
    cop_neto: float = 0.0  # lo que le pagan menos el costo del viaje


@dataclass(frozen=True, eq=False)
class Recomendacion:
    origen: str
    embarcacion: str
    kg: float
    nevera: str
    mejor: Opcion | None
    alternativas: tuple[Opcion, ...]
    explicacion: str


def costo_viaje(km_rio: float, horas_rio: float, embarcacion: str) -> float:
    """Lo que le cuesta al pescador ir y volver por rio: gasolina (solo con motor) y su tiempo."""
    p = config.parametro
    gasolina = km_rio * p("pescador.cop_por_km_motor") if embarcacion.endswith("_motor") else 0.0
    return p("pescador.factor_regreso") * (gasolina + horas_rio * p("pescador.cop_por_hora"))


def dias_espera_esperados(escenario: Escenario | None = None) -> float:
    """Dias que espera en promedio un lote: quien recoge pasa cada L dias y el lote llega en cualquier dia.

    Hoy es el comprador, L ~ U{min..max}; con la ruta del camion refrigerado (I5), L = N.
    """
    if escenario is not None and escenario.ciclo_camion_dias is not None:
        return (escenario.ciclo_camion_dias + 1) / 2
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
    candidatos += [("acopio", a) for a in sorted(escenario.acopios_nuevos)]
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


def _dijkstra(memo: dict | None, g: nx.DiGraph, origen: str, destino: str, perfil: transporte.Perfil,
              criterio: str) -> busqueda.ResultadoBusqueda:
    """Dijkstra propio con memoria opcional (una por corrida de Monte Carlo: los parametros no cambian dentro)."""
    clave = (id(g), origen, destino, perfil, criterio)
    if memo is not None and clave in memo:
        return memo[clave]
    r = busqueda.dijkstra(g, origen, destino, transporte.peso(perfil, criterio))
    if memo is not None:
        memo[clave] = r
    return r


def _pierna_carretera(destino_rio: str, perfil_via: transporte.Perfil, grafo: nx.DiGraph,
                      memo: dict | None) -> tuple[tuple[str, ...], pd.DataFrame]:
    """Del desembarque o acopio hasta la plaza por carretera.

    Si el lugar no tiene nodo vial (acopio nuevo en un punto del rio), se agrega un transbordo y
    un acceso estimado hasta el punto vial mas cercano.
    """
    via_g = red.subgrafo_modo(grafo, red.CAPA_VIA, "transbordo")
    if red.clave(grafo.nodes[destino_rio]["lugar"], red.CAPA_VIA) in grafo:
        viaje = _dijkstra(memo, via_g, destino_rio, PLAZA, perfil_via, "tiempo")
        return viaje.ruta, transporte.tramos_ruta(grafo, viaje.ruta, perfil_via)
    cercano, km = red.acceso_vial(destino_rio, grafo)
    viaje = _dijkstra(memo, via_g, cercano, PLAZA, perfil_via, "tiempo")
    nombre = grafo.nodes[destino_rio]["nombre"]
    estimados = []
    for datos, hasta in (({"modo": "transbordo", "distancia_km": 0.0, "sentido": None}, nombre),
                         ({"modo": red.CAPA_VIA, "distancia_km": km, "sentido": None}, grafo.nodes[cercano]["nombre"])):
        estimados.append({"desde": nombre, "hasta": hasta, "modo": datos["modo"], "sentido": None, "km": datos["distancia_km"],
                          "horas": transporte.tiempo_h(datos, perfil_via), "perdida": transporte.perdida(datos, perfil_via),
                          "fuente": red.FUENTE_ACCESO})
    tramos = pd.concat([pd.DataFrame(estimados), transporte.tramos_ruta(grafo, viaje.ruta, perfil_via)], ignore_index=True)
    return (destino_rio, *viaje.ruta), tramos


def _evaluar(tipo: str, destino: str, origen: str, perfil: transporte.Perfil, kg: float, hielo_h: float,
             escenario: Escenario, grafo: nx.DiGraph, memo: dict | None = None) -> Opcion:
    p = config.parametro
    nombre = grafo.nodes[red.clave(destino, red.CAPA_RIO)]["nombre"]
    if tipo == "plaza":
        nombre = grafo.nodes[PLAZA]["nombre"]
    elif destino in escenario.acopios_nuevos:
        nombre = f"Acopio nuevo ({nombre})"
    destino_rio = red.clave(destino, red.CAPA_RIO)
    if grafo.nodes[origen]["cuenca"] != grafo.nodes[destino_rio]["cuenca"]:
        return Opcion(tipo, destino, nombre, False, "No hay paso por agua: está en otra cuenca")

    rio_g = red.subgrafo_modo(grafo, red.CAPA_RIO)
    viaje_rio = _dijkstra(memo, rio_g, origen, destino_rio, perfil, "perdida")
    if not viaje_rio.alcanzable:
        return Opcion(tipo, destino, nombre, False, transporte.motivo_infactible(rio_g, origen, destino_rio, perfil))

    sitio = _sitio(tipo, destino, escenario)
    refrigerado = tipo == "acopio" and escenario.camion_refrigerado
    # Con la ruta del camion (I5), en los desembarques recoge el camion refrigerado en vez del comprador
    ruta_camion = sitio in ("senora", "sin_frio") and escenario.ciclo_camion_dias is not None
    vehiculo = "camion_refrigerado" if refrigerado or ruta_camion else "comprador_carro"
    perfil_via = dataclasses.replace(perfil, vehiculo=vehiculo)
    ruta_via, tramos_via = _pierna_carretera(destino_rio, perfil_via, grafo, memo)
    tramos = pd.concat([transporte.tramos_ruta(grafo, viaje_rio.ruta, perfil), tramos_via], ignore_index=True)
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
        estado_via = dg.REFRIGERADO if ruta_camion else dg.AMBIENTE
        espera_h = dias_espera_esperados(escenario) * cadena_actual.HORAS_DIA
        icopor = lote_hasta_el_destino()
        dg.poner_hielo(icopor, p("cadena_actual.horas_hielo_desborde"))
        dg.avanzar(icopor, espera_h, "espera", dg.ICOPOR_HIELO)
        v_icopor = dg.valor_lote(carretera(icopor, estado_via))
        if sitio == "senora":
            # Desembarque mejorado (I7): todo cabe en el congelador y no hay cortes de luz
            prob = 1.0 if escenario.desembarque_mejorado else prob_congelador(escenario.desembarque_senora, escenario.temporada)
            congelado = lote_hasta_el_destino()
            dg.congelar(congelado)
            falla = 0.0 if escenario.desembarque_mejorado else min(espera_h, horas_falla_esperadas(dias_espera_esperados(escenario)))
            dg.avanzar(congelado, falla, "espera", dg.FALLA)
            dg.avanzar(congelado, espera_h - falla, "espera", dg.CONGELADO)
            v_cong = dg.valor_lote(carretera(congelado, estado_via))
            valores = [(prob, v_cong), (1 - prob, v_icopor)]
            cop_cong, cop_icop = v_cong["cop_recibido"] / kg, v_icopor["cop_recibido"] / kg
        else:
            valores = [(1.0, v_icopor)]

    def esperado(clave: str) -> float:
        return sum(w * v[clave] for w, v in valores)

    km_rio = tramos.loc[tramos["modo"] == red.CAPA_RIO, "km"].sum()
    km_contra = tramos.loc[tramos["sentido"] == "aguas_arriba", "km"].sum()
    gasto = costo_viaje(km_rio, horas_rio, perfil.embarcacion)
    return Opcion(
        tipo=tipo,
        destino=destino,
        nombre=nombre,
        factible=True,
        ruta=viaje_rio.ruta + ruta_via[1:],
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
        costo_viaje=gasto,
        cop_neto=esperado("cop_recibido") - gasto,
    )


def recomendar(origen: str, embarcacion: str, kg: float, escenario: Escenario, nevera: str = "deteriorada",
               memo: dict | None = None) -> Recomendacion:
    """Compara todas las formas de vender desde `origen` (nodo@rio) y recomienda la que deja mas plata.

    `memo` guarda las rutas ya calculadas (util para repetir muchas recomendaciones con los mismos parametros).
    """
    grafo = red.construir_red()
    if origen not in grafo or grafo.nodes[origen]["capa"] != red.CAPA_RIO:
        raise ValueError(f"El origen debe ser un nodo de río: {origen}")
    if kg <= 0:
        raise ValueError("Los kg deben ser positivos")
    perfil = transporte.Perfil.desde_escenario(escenario, embarcacion)
    hielo_h = horas_hielo(nevera)
    opciones = [_evaluar(t, d, origen, perfil, kg, hielo_h, escenario, grafo, memo) for t, d in _destinos(origen, escenario, grafo)]
    factibles = sorted((o for o in opciones if o.factible), key=lambda o: (o.cop_neto, o.calidad), reverse=True)
    orden = factibles + [o for o in opciones if not o.factible]
    mejor = factibles[0] if factibles else None
    rec = Recomendacion(origen, embarcacion, kg, nevera, mejor, tuple(orden), "")
    return dataclasses.replace(rec, explicacion=explicar(rec))


# ---------------------------------------------------------------- explicacion


def pesos(cop: float) -> str:
    """$145.000 (separador de miles con punto, como en Colombia); -$28.066 si es negativo."""
    signo = "-" if round(cop) < 0 else ""
    return f"{signo}$" + f"{abs(cop):,.0f}".replace(",", ".")


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


def _que_gastas(embarcacion: str) -> str:
    return "en gasolina y tiempo" if embarcacion.endswith("_motor") else "en tiempo"


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
        partes.append(
            f"Llega con calidad {numero(m.calidad, 2)} (de 0 a 1) y te pagan cerca de **{pesos(m.cop_total)}**; "
            f"el viaje ida y vuelta te cuesta unos {pesos(m.costo_viaje)} {_que_gastas(rec.embarcacion)}, "
            f"así que te quedan **{pesos(m.cop_neto)}**."
        )
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


def _poblacion_y_oferta(escenario: Escenario, pob: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict[str, float]]:
    if pob is None:
        pob = cadena_actual.corrida_ejemplo(escenario).poblacion
    if escenario.subsidio_motor:
        pob = poblacion.aplicar_subsidio_motor(pob)
    act = poblacion.actividad_diagnostico()
    oferta = dict(zip(pob["id"], pob["kg_por_faena"] * pob["p_faena_pico"] * act))
    return pob, oferta


def _nevera(pesc, escenario: Escenario) -> str:
    return "buena" if pesc.nevera_buena or escenario.cajas_termicas else "deteriorada"


def capacidad_acopio_kg_dia(acopio: str) -> float:
    """kg por dia que pasan por el cuarto frio de un acopio (capacidad / dias que se queda el pescado)."""
    p = config.parametro
    kg = p(CAPACIDAD_ACOPIO[acopio]) if acopio in CAPACIDAD_ACOPIO else p("acopios.capacidad_nuevo_kg")
    return kg / (p("acopios.horas_espera_acopio") / 24)


def problema_transporte(escenario: Escenario, pob: pd.DataFrame | None = None, memo: dict | None = None,
                        con_hoy: bool = True) -> dict:
    """Reparto optimo de toda la flota entre las formas de vender, con capacidades y sin_destino.

    El costo de cada opcion por kg = valor perdido + costo del viaje del pescador repartido en los kg de su faena.
    Devuelve flujos (pescador, destino, kg_dia, costo_kg, cop_kg), uso de cada destino, costo optimo y costo de hoy.
    `pob` permite usar otra poblacion (Monte Carlo) y `memo` reutilizar rutas entre escenarios.
    """
    p = config.parametro
    p0 = dg.precio_base()
    pob, oferta = _poblacion_y_oferta(escenario, pob)
    # kg/dia que caben en los congeladores de la señora; con el desembarque mejorado (I7) cabe todo
    capacidad_congelador = None if escenario.desembarque_mejorado else (
        p("cadena_actual.n_congeladores") * p("cadena_actual.kg_por_congelador")
        / (sum(p("cadena_actual.ciclo_comprador_dias").values()) / 2)
    )
    costos, capacidades, opciones, nombres, valores = {}, {}, {}, {}, {}
    for pesc in pob.itertuples():
        rec = recomendar(pesc.ubicacion, pesc.embarcacion, pesc.kg_por_faena, escenario, _nevera(pesc, escenario), memo)
        for o in rec.alternativas:
            if not o.factible:
                continue
            viaje_kg = o.costo_viaje / pesc.kg_por_faena
            if o.prob_congelador is not None:  # la señora: congelador (con capacidad) o icopor
                partes = {":congelador": (o.cop_kg_congelador, capacidad_congelador), ":icopor": (o.cop_kg_icopor, None)}
            elif o.tipo == "acopio":
                partes = {"": (o.cop_kg, capacidad_acopio_kg_dia(o.destino))}
            elif o.tipo == "plaza":
                partes = {"": (o.cop_kg, p("acopios.capacidad_plaza_kg_dia"))}
            else:
                partes = {"": (o.cop_kg, None)}
            for sufijo, (cop_kg, cap) in partes.items():
                d = _clave_destino(o, sufijo)
                costos[(pesc.id, d)] = p0 - cop_kg + viaje_kg
                valores[(pesc.id, d)] = cop_kg
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
            "costo_kg": costos.get((pescador, d), p0),
            "cop_kg": valores.get((pescador, d), 0.0),
            **detalle_opcion(o),
        })
    tabla = pd.DataFrame(filas).merge(pob[["id", "zona", "embarcacion", "sitio"]], left_on="pescador", right_on="id").drop(columns="id")
    uso = tabla.groupby(["destino", "destino_nombre"], as_index=False)["kg_dia"].sum()
    uso["capacidad_kg_dia"] = uso["destino"].map(lambda d: capacidades.get(d))
    uso["pct_uso"] = 100 * uso["kg_dia"] / uso["capacidad_kg_dia"]
    return {
        "flujos": tabla,
        "uso": uso,
        "costo_optimo_dia": costo,
        "costo_hoy_dia": costo_hoy(escenario, pob) if con_hoy else None,
        "kg_dia": sum(oferta.values()),
        "kg_sin_destino": tabla.loc[tabla["destino"] == SIN_DESTINO, "kg_dia"].sum(),
        "valor_posible_dia": p0 * sum(oferta.values()),
    }


def asignacion_hoy(escenario: Escenario, pob: pd.DataFrame | None = None) -> pd.DataFrame:
    """Cada pescador en su desembarque habitual de hoy (si no puede remontar, el centro alcanzable mas cercano)."""
    hoy = Escenario.base().con(desembarque_senora=escenario.desembarque_senora, temporada=escenario.temporada)
    pob, oferta = _poblacion_y_oferta(hoy, pob)
    filas = []
    for pesc in pob.itertuples():
        rec = recomendar(pesc.ubicacion, pesc.embarcacion, pesc.kg_por_faena, hoy, _nevera(pesc, hoy))
        habitual = next((o for o in rec.alternativas if o.destino == pesc.desembarque and o.factible), None)
        o = habitual if habitual is not None else rec.mejor
        filas.append({"pescador": pesc.id, "destino": o.destino if o else SIN_DESTINO, "kg_dia": oferta[pesc.id],
                      "cop_kg": o.cop_kg if o else 0.0, "viaje_kg": o.costo_viaje / pesc.kg_por_faena if o else 0.0,
                      **detalle_opcion(o)})
    return pd.DataFrame(filas)


def detalle_opcion(o: Opcion | None) -> dict:
    """Ruta, km, horas y calidad de la forma de vender elegida (vacio si el pescado no tiene destino)."""
    if o is None:
        return {"ruta": (), "km_rio": 0.0, "km_via": 0.0, "horas_hasta_venta": float("nan"), "calidad": 0.0}
    return {"ruta": o.ruta, "km_rio": o.km_rio, "km_via": o.km_via, "horas_hasta_venta": o.horas_hasta_venta,
            "calidad": o.calidad}


def costo_hoy(escenario: Escenario, pob: pd.DataFrame | None = None) -> float:
    """COP perdidos por dia con la asignacion de hoy (valor perdido + costo del viaje)."""
    hoy = asignacion_hoy(escenario, pob)
    return float((hoy["kg_dia"] * (dg.precio_base() - hoy["cop_kg"] + hoy["viaje_kg"])).sum())


def flujos_por_arista(tabla: pd.DataFrame) -> dict[tuple[str, str], float]:
    """kg/dia por arista de la red segun el reparto (para el mapa)."""
    salida: dict[tuple[str, str], float] = {}
    for fila in tabla.itertuples():
        for u, v in zip(fila.ruta, fila.ruta[1:]):
            salida[(u, v)] = salida.get((u, v), 0.0) + fila.kg_dia
    return salida
