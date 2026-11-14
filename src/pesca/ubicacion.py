"""Centros de acopio (R4): viabilidad de los actuales y reubicacion con p-mediana.

(a) Viabilidad: Monte Carlo del reparto optimo de la flota (asignacion.problema_transporte) con y sin
    cada acopio rehabilitado. El beneficio es el costo que se evita (valor perdido + viaje); los costos
    son la rehabilitacion, la operacion y la energia (explicita: fue la razon del abandono de San Miguel).
    Regla: vale la pena si VPN > 0 en al menos umbral_vpn_positivo de las corridas.
(b) Reubicacion: p-mediana (PuLP/CBC) sobre los puntos del rio, en dos modos: mover los 3 acopios
    o mantener los actuales y agregar k.
"""

from __future__ import annotations

import json

import networkx as nx
import numpy as np
import pandas as pd

from pesca import asignacion, config, montecarlo, poblacion, red, transporte
from pesca.escenario import Escenario

ESCENARIOS = {
    "base": frozenset({"A01"}),
    "A02": frozenset({"A01", "A02"}),
    "A03": frozenset({"A01", "A03"}),
    "todos": frozenset({"A01", "A02", "A03"}),
}
NOMBRE_ESCENARIO = {"A02": "San Miguel", "A03": "Puente Arimena", "todos": "Los tres (Puerto Gaitán + San Miguel + Puente Arimena)"}
COSTOS = {
    "A02": ("economia.rehabilitacion_san_miguel_cop", "economia.operacion_anual_san_miguel_cop", "economia.kwh_dia_san_miguel"),
    "A03": ("economia.rehabilitacion_puente_arimena_cop", "economia.operacion_anual_puente_arimena_cop", "economia.kwh_dia_puente_arimena"),
}
DIAS_ANIO = 365
# La plaza (A01) en la red de rio es el malecon; los acopios actuales en el rio
ACTUALES = {"D_MALECON@rio": "A01", "A02@rio": "A02", "A03@rio": "A03"}

ARCHIVO_VIABILIDAD = "r4_viabilidad.csv"
ARCHIVO_PMEDIANA = "r4_pmediana.json"
ARCHIVO_META = "r4_meta.json"


# ---------------------------------------------------------------- (a) viabilidad


def factor_anualidad(tasa: float, anios: int) -> float:
    """Σ_{t=1..n} 1/(1+tasa)^t."""
    return sum(1 / (1 + tasa) ** t for t in range(1, anios + 1))


def vpn(inversion: float, flujo_anual: float, anios: int, tasa: float) -> float:
    """Valor presente neto de una inversion con un flujo anual constante."""
    return -inversion + flujo_anual * factor_anualidad(tasa, anios)


def vale_la_pena(vpns: pd.Series) -> tuple[bool, float]:
    """Regla de decision: VPN > 0 en al menos umbral_vpn_positivo de las corridas."""
    fraccion = float((vpns > 0).mean())
    return fraccion >= config.parametro("economia.umbral_vpn_positivo"), fraccion


def costos_acopios(acopios: frozenset[str]) -> tuple[float, float, float]:
    """(inversion, operacion anual sin energia, kWh por dia) de rehabilitar estos acopios."""
    p = config.parametro
    inversion = sum(p(COSTOS[a][0]) for a in acopios)
    operacion = sum(p(COSTOS[a][1]) for a in acopios)
    kwh = sum(p(COSTOS[a][2]) for a in acopios)
    return inversion, operacion, kwh


def _kg_vendibles(resultado: dict) -> float:
    f = resultado["flujos"]
    return float(f.loc[(f["destino"] != asignacion.SIN_DESTINO) & (f["cop_kg"] > 0), "kg_dia"].sum())


def _corrida_viabilidad(i: int, rng: np.random.Generator) -> list[dict]:
    p = config.parametro
    temporada = "aguas_altas" if rng.random() < p("economia.fraccion_aguas_altas") else "aguas_bajas"
    base = Escenario.base().con(temporada=temporada)
    pob = poblacion.generar_poblacion(rng, base.desembarque_senora, red.construir_red())
    memo: dict = {}
    res = {
        nombre: asignacion.problema_transporte(base.con(acopios_activos=acopios), pob, memo, con_hoy=False)
        for nombre, acopios in ESCENARIOS.items()
    }
    tasa, anios = p("economia.tasa_descuento"), p("economia.horizonte_anios")
    af = factor_anualidad(tasa, anios)
    filas = []
    for nombre in ("A02", "A03", "todos"):
        acopios = ESCENARIOS[nombre] - {"A01"}
        inversion, operacion, kwh = costos_acopios(acopios)
        energia = kwh * DIAS_ANIO * p("economia.cop_kwh")
        evitado = res["base"]["costo_optimo_dia"] - res[nombre]["costo_optimo_dia"]
        beneficio = evitado * p("volumen.dias_pesca_anio")
        uso = res[nombre]["uso"]
        en_acopios = uso[uso["destino"].isin([f"acopio:{a}" for a in acopios])]["kg_dia"].sum()
        capacidad = sum(asignacion.capacidad_acopio_kg_dia(a) for a in acopios)
        filas.append({
            "corrida": i,
            "acopio": nombre,
            "temporada": temporada,
            "costo_evitado_dia": evitado,
            "beneficio_anual": beneficio,
            "kg_salvados_dia": _kg_vendibles(res[nombre]) - _kg_vendibles(res["base"]),
            "kg_dia_acopio": en_acopios,
            "uso_pct": 100 * en_acopios / capacidad,
            "inversion": inversion,
            "operacion_anual": operacion,
            "energia_anual": energia,
            "vpn": vpn(inversion, beneficio - operacion - energia, anios, tasa),
            "vpn_sin_energia": vpn(inversion, beneficio - operacion, anios, tasa),
            "vp_energia_por_cop_kwh": kwh * DIAS_ANIO * af,
        })
    return filas


def viabilidad(n: int | None = None, semilla: int | None = None) -> pd.DataFrame:
    """Monte Carlo de la viabilidad de rehabilitar San Miguel, Puente Arimena y los tres."""
    n = n if n is not None else config.parametro("montecarlo.corridas_r4")
    semilla = semilla if semilla is not None else config.parametro("general.semilla")
    resultados = montecarlo.correr(_corrida_viabilidad, n, semilla)
    return pd.DataFrame([fila for filas in resultados for fila in filas])


def resumen_viabilidad(tabla: pd.DataFrame) -> pd.DataFrame:
    """Por acopio: VPN (media e IC 90 %), % de corridas con VPN > 0, veredicto y punto de equilibrio de la energia."""
    filas = []
    for acopio, sub in tabla.groupby("acopio", sort=False):
        pasa, fraccion = vale_la_pena(sub["vpn"])
        r_vpn = montecarlo.resumir(sub["vpn"])
        filas.append({
            "acopio": acopio,
            "nombre": NOMBRE_ESCENARIO[acopio],
            "vale_la_pena": pasa,
            "pct_vpn_positivo": 100 * fraccion,
            "vpn_media": r_vpn["media"], "vpn_p5": r_vpn["p5"], "vpn_p95": r_vpn["p95"],
            **{f"{c}_{k}": v for c in ("kg_salvados_dia", "beneficio_anual", "uso_pct", "energia_anual")
               for k, v in montecarlo.resumir(sub[c]).items()},
            # Tarifa de energia con la que el VPN medio llega a 0
            "equilibrio_cop_kwh": sub["vpn_sin_energia"].mean() / sub["vp_energia_por_cop_kwh"].mean(),
        })
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- (b) p-mediana


def candidatos(grafo: nx.DiGraph | None = None) -> list[str]:
    """Puntos del rio (candidatos de §4.4) y los acopios actuales en el rio."""
    grafo = grafo if grafo is not None else red.construir_red()
    puntos = sorted(n for n, a in grafo.nodes(data=True) if a["tipo"] == "punto_rio")
    return [*ACTUALES, *puntos]


def demanda(escenario: Escenario | None = None) -> pd.Series:
    """kg/dia de cada ubicacion de pescadores (poblacion de ejemplo, mes tipico fuera de veda)."""
    from pesca import cadena_actual

    esc = escenario if escenario is not None else Escenario.base()
    pob = cadena_actual.corrida_ejemplo(esc).poblacion
    kg = pob["kg_por_faena"] * pob["p_faena_pico"] * poblacion.actividad_diagnostico()
    return kg.groupby(pob["ubicacion"]).sum().sort_index()


def matriz_costos(origenes: list[str], cands: list[str], escenario: Escenario | None = None) -> pd.DataFrame:
    """c_ij: COP perdidos por kg (valor perdido + viaje) si el pescador de i lleva su pescado a un acopio en j.

    Promedio sobre la mezcla de embarcaciones y el estado de las neveras. Un acopio en j funciona como
    los acopios activos del recomendador (cuarto frio + transbordo + carretera); el malecon es la plaza.
    """
    p = config.parametro
    grafo = red.construir_red()
    puntos = [red.separar(j)[0] for j in cands if j not in ACTUALES]
    esc = (escenario if escenario is not None else Escenario.base()).con(acopios_nuevos=frozenset(puntos))
    p0 = asignacion.dg.precio_base()
    kg = p("poblacion.kg_por_faena")
    f_buena = p("cadena_actual.fraccion_nevera_buena")
    neveras = {"buena": f_buena, "deteriorada": 1 - f_buena}
    memo: dict = {}
    c = pd.DataFrame(0.0, index=origenes, columns=cands)
    for emb, w_emb in p("flota.mezcla").items():
        perfil = transporte.Perfil.desde_escenario(esc, emb)
        for nevera, w_nev in neveras.items():
            hielo = asignacion.horas_hielo(nevera)
            for i in origenes:
                for j in cands:
                    lugar = red.separar(j)[0]
                    tipo = "plaza" if j == "D_MALECON@rio" else "acopio"
                    o = asignacion._evaluar(tipo, lugar, i, perfil, kg, hielo, esc, grafo, memo)
                    costo = p0 - o.cop_kg + o.costo_viaje / kg if o.factible else p0
                    c.at[i, j] += w_emb * w_nev * costo
    return c


def p_mediana(w: pd.Series, c: pd.DataFrame, p: int, fijos: tuple[str, ...] = ()) -> dict:
    """Abre p acopios (incluidos los fijos) que minimizan Σ w_i c_ij x_ij. Resuelve con PuLP/CBC."""
    import pulp

    if not len(fijos) <= p <= len(c.columns):
        raise ValueError(f"p = {p} no es posible con {len(fijos)} fijos y {len(c.columns)} candidatos")
    prob = pulp.LpProblem("p_mediana", pulp.LpMinimize)
    jj = list(c.columns)
    ii = list(w.index)
    y = {j: pulp.LpVariable(f"y_{k}", cat="Binary") for k, j in enumerate(jj)}
    x = {(i, j): pulp.LpVariable(f"x_{a}_{b}", lowBound=0, upBound=1) for a, i in enumerate(ii) for b, j in enumerate(jj)}
    prob += pulp.lpSum(w[i] * c.at[i, j] * x[i, j] for i in ii for j in jj)
    for i in ii:
        prob += pulp.lpSum(x[i, j] for j in jj) == 1
        for j in jj:
            prob += x[i, j] <= y[j]
    prob += pulp.lpSum(y.values()) == p
    for j in fijos:
        prob += y[j] == 1
    estado = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[estado] != "Optimal":
        raise RuntimeError(f"La p-mediana no encontró óptimo: {pulp.LpStatus[estado]}")
    abiertos = [j for j in jj if y[j].value() > 0.5]
    asignacion_ij = {i: max(abiertos, key=lambda j: x[i, j].value()) for i in ii}
    return {"abiertos": abiertos, "asignacion": asignacion_ij, "costo_dia": float(pulp.value(prob.objective))}


def costo_con(w: pd.Series, c: pd.DataFrame, abiertos: list[str]) -> float:
    """Costo por dia si cada demanda va al mejor de los acopios abiertos."""
    return float((w * c[abiertos].min(axis=1)).sum())


def _describir(grafo: nx.DiGraph, nodo: str) -> dict:
    a = grafo.nodes[nodo]
    lugar = ACTUALES.get(nodo, a["lugar"])
    trazas = {d["traza"] for _, _, d in grafo.out_edges(nodo, data=True) if d["modo"] == red.CAPA_RIO}
    return {"nodo": nodo, "lugar": lugar, "actual": nodo in ACTUALES,
            "nombre": grafo.nodes[red.clave(lugar, red.CAPA_VIA)]["nombre"] if nodo in ACTUALES else a["nombre"],
            "rio": ", ".join(sorted(trazas)), "lat": a["lat"], "lon": a["lon"]}


def reubicar() -> dict:
    """Codo (mover: p = 1…p_max) y modo agregar (mantener los 3 actuales + k), con la poblacion de ejemplo."""
    grafo = red.construir_red()
    w = demanda()
    cands = candidatos(grafo)
    c = matriz_costos(list(w.index), cands)
    resultados = []
    for p in range(1, config.parametro("ubicacion.p_max_codo") + 1):
        resultados.append({"modo": "mover", "p": p, "k": None, **p_mediana(w, c, p)})
    fijos = tuple(ACTUALES)
    for k in range(1, config.parametro("ubicacion.k_max_agregar") + 1):
        resultados.append({"modo": "agregar", "p": len(fijos) + k, "k": k, **p_mediana(w, c, len(fijos) + k, fijos)})
    for r in resultados:
        r["acopios"] = [_describir(grafo, j) for j in r["abiertos"]]
    return {
        "resultados": resultados,
        "costo_actuales_dia": costo_con(w, c, list(ACTUALES)),
        "demanda": {i: float(v) for i, v in w.items()},
    }


# ---------------------------------------------------------------- precalculo


def precalcular(n: int | None = None) -> None:
    """Viabilidad (Monte Carlo) y p-mediana → datos/precalculado/r4_*."""
    config.DIR_PRECALCULADO.mkdir(parents=True, exist_ok=True)
    tabla = viabilidad(n)
    tabla.to_csv(config.DIR_PRECALCULADO / ARCHIVO_VIABILIDAD, index=False, float_format="%.6g")
    print(f"  r4 viabilidad: {tabla['corrida'].nunique()} corridas")
    pm = reubicar()
    (config.DIR_PRECALCULADO / ARCHIVO_PMEDIANA).write_text(json.dumps(pm, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  r4 p-mediana: {len(pm['resultados'])} resoluciones")
    meta = {"corridas": int(tabla["corrida"].nunique()), "semilla": config.parametro("general.semilla")}
    (config.DIR_PRECALCULADO / ARCHIVO_META).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def cargar_precalculado() -> dict | None:
    archivos = [config.DIR_PRECALCULADO / a for a in (ARCHIVO_VIABILIDAD, ARCHIVO_PMEDIANA, ARCHIVO_META)]
    if not all(a.is_file() for a in archivos):
        return None
    return {
        "viabilidad": pd.read_csv(archivos[0]),
        "pmediana": json.loads(archivos[1].read_text(encoding="utf-8")),
        "meta": json.loads(archivos[2].read_text(encoding="utf-8")),
    }


def escenario_con_propuesta(escenario: Escenario, acopios: list[dict]) -> Escenario:
    """Activa en el escenario los acopios de una propuesta (los actuales en acopios_activos, los nuevos aparte)."""
    actuales = {a["lugar"] for a in acopios if a["actual"]}
    nuevos = {a["lugar"] for a in acopios if not a["actual"]}
    return escenario.con(acopios_activos=frozenset(escenario.acopios_activos | actuales | {"A01"}),
                         acopios_nuevos=frozenset(nuevos))
