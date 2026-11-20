"""Ubicacion de los acopios sobre el grafo v4 (adenda §4): p-mediana sobre vertices que son centros poblados.

- candidatos: regla de §4.1 con el motivo de cada exclusion;
- c_ij (§4.2): ΔQ de la zona i al acopio j (Dijkstra por capas, en hielo) + ΔQ de la espera en el cuarto frio
  de j + ΔQ de j a la plaza (Dijkstra desde (j, frio)); promedio sobre la flota y el estado de las neveras;
- p-mediana (§4.3) por enumeracion exacta, ILP (PuLP/CBC) y busqueda local Teitz–Bart (§4.4), con el gap;
- referencias (§4.6): p-mediana libre sobre los puntos del rio, centroide y acopios actuales;
- viabilidad (§4.7) y sensibilidad (§4.8).

Nota de diseño: el costo de la ida depende de la hora (el hielo se acaba), asi que la ida se calcula
con Dijkstra hacia adelante desde cada zona (una corrida da el costo a todos los j). La vuelta a la plaza
va en frio, que no depende de la hora, y se calcula una vez por candidato.
"""

from __future__ import annotations

import itertools
import math
from functools import cache

import networkx as nx
import numpy as np
import pandas as pd

from pesca import busqueda, config, grafo, montecarlo, pesos
from pesca.degradacion import precio_base
from pesca.red import haversine_km

SIN_DESTINO = "sin_destino"
DIAS_ANIO = 365


# ---------------------------------------------------------------- datos


def zonas(g: nx.DiGraph) -> list[str]:
    """Origenes de pescado: zonas de pesca y comunidades pescadoras."""
    return sorted(n for n, a in g.nodes(data=True) if a["tipo"] in ("zona_pesca", "comunidad"))


@cache
def _demanda_v31() -> pd.Series:
    from pesca import ubicacion

    return ubicacion.demanda()


def pesos_zonas(g: nx.DiGraph) -> pd.Series:
    """w_i en kg/dia [SIMULADO]: peso_kg_dia del CSV o, si falta, la poblacion de pescadores de la v3.1."""
    demanda = _demanda_v31()
    w = {}
    for i in zonas(g):
        dato = g.nodes[i].get("peso_kg_dia")
        if dato is not None and not (isinstance(dato, float) and math.isnan(dato)):
            w[i] = float(dato)
        else:
            w[i] = float(demanda.get(f"{i}@rio", demanda.mean()))
    return pd.Series(w, name="kg_dia")


TIPOS_IDA = {"rio", "acceso", "transbordo"}


def grafo_ida(g: nx.DiGraph) -> nx.DiGraph:
    """Lo que recorre el pescador con su bote: rio y accesos, y el transbordo para dejar el lote en el pueblo."""
    return g.edge_subgraph([(u, v) for u, v, a in g.edges(data=True) if a["tipo"] in TIPOS_IDA]).copy()


def entrada(g: nx.DiGraph, j: str) -> str:
    return j + grafo.ENTRA if j + grafo.ENTRA in g else j


def salida(g: nx.DiGraph, j: str) -> str:
    return j + grafo.SALE if j + grafo.SALE in g else j


# ---------------------------------------------------------------- candidatos (§4.1)


def candidatos(
    centros: pd.DataFrame, g: nx.DiGraph, p_min: float | None = None, criterio_acceso: str | None = None
) -> tuple[list[str], pd.DataFrame]:
    """C y la tabla de todos los centros con su motivo de exclusion (vacio si entra)."""
    p = config.parametro
    p_min = p("acopios_grafo.p_min_habitantes") if p_min is None else p_min
    criterio_acceso = criterio_acceso or p("acopios_grafo.criterio_acceso")
    acepta = {"si"} if criterio_acceso == "estricto" else {"si", "por_confirmar"}
    origenes = zonas(g)
    filas, elegidos = [], []
    for c in centros.itertuples():
        motivos, confirmar = [], False
        if c.clase_dane not in ("cabecera", "centro_poblado"):
            motivos.append("no es cabecera ni centro poblado")
        if c.habitantes_2018 < p_min:
            motivos.append(f"{c.habitantes_2018} habitantes < P_min = {p_min:g}")
        if not (c.acceso_rio in acepta or c.acceso_via in acepta):
            motivos.append("sin acceso confirmado por río ni por vía")
        if pd.isna(c.lat) or pd.isna(c.lon):
            motivos.append("sin coordenadas")
        elif entrada(g, c.id) not in g:
            motivos.append("no está colgado del grafo")
        elif not any(busqueda.bfs(g, z, entrada(g, c.id)).alcanzable for z in origenes):
            motivos.append("inalcanzable desde las zonas de pesca (BFS)")
        if not motivos:
            elegidos.append(c.id)
            confirmar = c.validado != "si" or "por_confirmar" in (c.acceso_rio, c.acceso_via, c.energia)
        filas.append(
            {
                "id": c.id, "nombre": c.nombre, "habitantes_2018": c.habitantes_2018, "acceso_rio": c.acceso_rio,
                "acceso_via": c.acceso_via, "candidato": not motivos, "motivo": "; ".join(motivos),
                "marca": "[CONFIRMAR]" if confirmar else "",
            }
        )
    return elegidos, pd.DataFrame(filas)


# ---------------------------------------------------------------- c_ij (§4.2)


def _combinaciones() -> list[tuple[str, str, float]]:
    """(bote, nevera, peso) de la flota y las neveras [SIMULADO]."""
    p = config.parametro
    buena = p("cadena_actual.fraccion_nevera_buena")
    return [
        (bote, nevera, w_b * w_n)
        for bote, w_b in p("flota.mezcla").items()
        for nevera, w_n in (("buena", buena), ("deteriorada", 1 - buena))
    ]


def tramos_costo(g: nx.DiGraph, i: str, destinos: list[str], cond: pesos.Condiciones) -> dict[str, dict]:
    """Para una condicion: ΔQ de ida (hielo), espera (frio) y vuelta a la plaza (frio) para cada j."""
    p = config.parametro
    mercado = grafo.mercados(g)[0]
    ida_cond = cond.con(acopios=frozenset(), camion_refrigerado=False)
    gc_ida = pesos.expandir_capas(_ida_cache(g), ida_cond)
    if (i, "hielo") not in gc_ida:
        return dict.fromkeys(destinos)
    w, t, previo = busqueda.dijkstra_todos(gc_ida, (i, "hielo"), pesos.funcion_costo(ida_cond))
    salida_tabla = {}
    for j in destinos:
        estado = (entrada(g, j), "hielo")
        if estado not in w:
            salida_tabla[j] = None
            continue
        vuelta = _vuelta(g, j, cond, mercado)
        tiene_plaza = any(g.nodes[m].get("centro_id") == j for m in grafo.mercados(g))
        espera = 0.0 if tiene_plaza else pesos.perdida(p("acopios.horas_espera_acopio"), "frio", 0.0, cond)
        salida_tabla[j] = {
            "ida": w[estado], "espera": espera, "vuelta": vuelta, "camino": busqueda.camino_hasta(previo, estado),
            "horas": t[estado],
        }
    return salida_tabla


def _vuelta(g: nx.DiGraph, j: str, cond: pesos.Condiciones, mercado: str) -> float:
    """ΔQ de j a la plaza viajando en frio (camion refrigerado por via o bote con hielo suficiente por rio)."""
    if salida(g, j) == mercado or any(g.nodes[m].get("centro_id") == j for m in grafo.mercados(g)):
        return 0.0
    return _vuelta_cache(g, salida(g, j), cond.con(acopios=frozenset({j})), mercado)


_CACHE_VUELTA: dict = {}
_CACHE_IDA: dict = {}


def _ida_cache(g: nx.DiGraph) -> nx.DiGraph:
    if id(g) not in _CACHE_IDA:
        _CACHE_IDA[id(g)] = grafo_ida(g)
    return _CACHE_IDA[id(g)]


def _vuelta_cache(g, origen, cond, mercado) -> float:
    """Dijkstra desde (j, frio) a la plaza; se guarda salvo dentro de un Monte Carlo (parametros muestreados)."""
    clave = (id(g), origen, cond)
    if config._SOBRESCRITOS.get() or clave not in _CACHE_VUELTA:
        gc = pesos.expandir_capas(g, cond)
        r = busqueda.dijkstra_capas(gc, (origen, "frio"), {(mercado, c) for c in pesos.CAPAS}, pesos.funcion_costo(cond))
        if config._SOBRESCRITOS.get():
            return r.costo
        _CACHE_VUELTA[clave] = r.costo
    return _CACHE_VUELTA[clave]


def _temporadas(temporada: str | None) -> list[tuple[str, float]]:
    """Una temporada, o las dos ponderadas por fraccion_aguas_altas: un acopio se ubica para todo el año."""
    if temporada is not None:
        return [(temporada, 1.0)]
    altas = config.parametro("economia.fraccion_aguas_altas")
    return [("aguas_altas", altas), ("aguas_bajas", 1 - altas)]


def matriz_costos(g: nx.DiGraph, cands: list[str], temporada: str | None = None, bote: str | None = None) -> pd.DataFrame:
    """c_ij: fraccion del lote que se pierde si la zona i entrega en j y el lote sigue a la plaza.

    Promedio ponderado sobre la flota, las neveras y las dos temporadas (o un solo bote o una sola temporada si se
    pide). En aguas altas un bote a remo no remonta el Meta: por eso la temporada pesa en donde va un acopio.
    Tope 1 (se pierde todo).
    """
    tope = config.parametro("acopios_grafo.costo_sin_destino")
    combos = [(b, n, t, w * wt) for b, n, w in _combinaciones() if bote is None or b == bote for t, wt in _temporadas(temporada)]
    total = sum(w for *_, w in combos)
    c = pd.DataFrame(0.0, index=zonas(g), columns=cands)
    for b, nevera, temporada_combo, peso_combo in combos:
        cond = pesos.Condiciones(bote=b, temporada=temporada_combo, nevera=nevera)
        for i in c.index:
            tramos = tramos_costo(g, i, cands, cond)
            for j in cands:
                x = tramos[j]
                valor = tope if x is None else min(tope, x["ida"] + x["espera"] + x["vuelta"])
                c.at[i, j] += peso_combo / total * valor
    return c


# ---------------------------------------------------------------- p-mediana (§4.3–4.4)


def f(c: pd.DataFrame, w: pd.Series, abiertos) -> float:
    """Σ_i w_i min_{j∈S} c_ij (kg equivalentes perdidos por dia)."""
    abiertos = list(abiertos)
    if not abiertos:
        return float((w * config.parametro("acopios_grafo.costo_sin_destino")).sum())
    return float((w * c[abiertos].min(axis=1)).sum())


def p_mediana_enumeracion(c: pd.DataFrame, w: pd.Series, p: int, fijos: tuple = ()) -> dict:
    """Evalua todas las combinaciones: el optimo garantizado (la referencia)."""
    libres = [j for j in c.columns if j not in fijos]
    if not len(fijos) <= p <= len(c.columns):
        raise ValueError(f"p = {p} no es posible con {len(fijos)} fijos y {len(c.columns)} candidatos")
    mejor = None
    evaluadas = 0
    for extra in itertools.combinations(libres, p - len(fijos)):
        s = (*fijos, *extra)
        valor = f(c, w, s)
        evaluadas += 1
        if mejor is None or valor < mejor[1] - 1e-12:
            mejor = (tuple(sorted(s)), valor)
    return {"metodo": "enumeracion", "S": mejor[0], "f": mejor[1], "evaluadas": evaluadas}


def p_mediana_ilp(c: pd.DataFrame, w: pd.Series, p: int, fijos: tuple = (), capacidad: pd.Series | None = None) -> dict:
    """Formulacion de §4.3 con PuLP/CBC; con `capacidad` agrega Σ_i w_i x_ij <= K_j y_j."""
    try:
        import pulp
    except ImportError as e:  # pragma: no cover
        raise ImportError("La p-mediana ILP necesita PuLP: pip install pulp") from e
    prob = pulp.LpProblem("p_mediana_grafo", pulp.LpMinimize)
    I, J = list(c.index), list(c.columns)
    y = {j: pulp.LpVariable(f"y_{k}", cat="Binary") for k, j in enumerate(J)}
    x = {(i, j): pulp.LpVariable(f"x_{a}_{b}", 0, 1) for a, i in enumerate(I) for b, j in enumerate(J)}
    prob += pulp.lpSum(w[i] * c.at[i, j] * x[i, j] for i in I for j in J)
    for i in I:
        prob += pulp.lpSum(x[i, j] for j in J) == 1
        for j in J:
            prob += x[i, j] <= y[j]
    prob += pulp.lpSum(y.values()) == p
    for j in fijos:
        prob += y[j] == 1
    if capacidad is not None:
        for j in J:
            prob += pulp.lpSum(w[i] * x[i, j] for i in I) <= float(capacidad.get(j, math.inf) if not math.isnan(capacidad.get(j, math.inf)) else 1e12) * y[j]
    estado = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[estado] != "Optimal":
        return {"metodo": "ilp", "S": (), "f": math.inf, "estado": pulp.LpStatus[estado]}
    s = tuple(sorted(j for j in J if y[j].value() > 0.5))
    return {"metodo": "ilp", "S": s, "f": float(pulp.value(prob.objective)), "estado": "Optimal"}


def p_mediana_busqueda_local(c: pd.DataFrame, w: pd.Series, p: int, fijos: tuple = (), reinicios: int | None = None,
                             semilla: int | None = None) -> dict:
    """Teitz–Bart: estado = conjunto S de p candidatos; vecino = cambiar un j de S por un k fuera de S.

    Inicio voraz y reinicios aleatorios. Es heuristica: el gap contra la enumeracion se reporta aparte.
    """
    reinicios = config.parametro("acopios_grafo.reinicios_busqueda_local") if reinicios is None else reinicios
    semilla = config.parametro("general.semilla") if semilla is None else semilla
    rng = np.random.default_rng(semilla)
    J = list(c.columns)
    libres = [j for j in J if j not in fijos]

    def mejorar(s: set) -> set:
        actual = f(c, w, s)
        hubo = True
        while hubo:
            hubo = False
            for j in sorted(s - set(fijos)):
                for k in sorted(set(J) - s):
                    nuevo = (s - {j}) | {k}
                    valor = f(c, w, nuevo)
                    if valor < actual - 1e-12:
                        s, actual, hubo = nuevo, valor, True
                        break
                if hubo:
                    break
        return s

    voraz = set(fijos)
    while len(voraz) < p:
        voraz.add(min((j for j in libres if j not in voraz), key=lambda j: f(c, w, voraz | {j})))
    mejor = mejorar(voraz)
    for _ in range(reinicios):
        azar = set(fijos) | set(rng.choice(libres, size=p - len(fijos), replace=False).tolist()) if p > len(fijos) else set(fijos)
        s = mejorar(azar)
        if f(c, w, s) < f(c, w, mejor) - 1e-12:
            mejor = s
    return {"metodo": "busqueda_local", "S": tuple(sorted(mejor)), "f": f(c, w, mejor), "reinicios": reinicios}


def tres_metodos(c: pd.DataFrame, w: pd.Series, p: int, fijos: tuple = ()) -> pd.DataFrame:
    """Enumeracion, ILP y Teitz–Bart para el mismo p, con el gap contra la enumeracion."""
    filas = [p_mediana_enumeracion(c, w, p, fijos), p_mediana_ilp(c, w, p, fijos), p_mediana_busqueda_local(c, w, p, fijos)]
    tabla = pd.DataFrame(filas)[["metodo", "S", "f"]]
    referencia = tabla.at[0, "f"]
    tabla["gap_pct"] = 100 * (tabla["f"] - referencia) / referencia if referencia > 0 else 0.0
    return tabla


def voronoi(c: pd.DataFrame, abiertos) -> pd.Series:
    """Area de influencia: cada zona va al acopio abierto con menor c_ij (las distancias ya son Dijkstra)."""
    return c[list(abiertos)].idxmin(axis=1)


def codo(curva: pd.DataFrame) -> int:
    """El menor p tal que abrir un acopio mas baja f menos que umbral_codo · f(1)."""
    umbral = config.parametro("acopios_grafo.umbral_codo") * curva["f"].iloc[0]
    for k in range(len(curva) - 1):
        if curva["f"].iloc[k] - curva["f"].iloc[k + 1] < umbral:
            return int(curva["p"].iloc[k])
    return int(curva["p"].iloc[-1])


# ---------------------------------------------------------------- referencias (§4.6)


def puntos_libres(g: nx.DiGraph, cands: list[str] = ()) -> list[str]:
    """Candidatos de la p-mediana libre (el enfoque de la v3.1): todo punto del rio, mas los pueblos.

    Como incluye a los pueblos, f(S_libre) <= f(S_urbano): es la cota inferior del costo de exigir pueblos.
    """
    return sorted({n for n, a in g.nodes(data=True) if a["tipo"] == "punto_rio"} | set(cands))


def centroide(g: nx.DiGraph, w: pd.Series) -> str:
    """Centroide ponderado de las zonas, llevado al nodo del grafo mas cercano (rio, via o pueblo)."""
    lat = sum(g.nodes[i]["lat"] * w[i] for i in w.index) / w.sum()
    lon = sum(g.nodes[i]["lon"] * w[i] for i in w.index) / w.sum()
    elegibles = [n for n, a in g.nodes(data=True) if a["tipo"] in ("punto_rio", "punto_via") or a.get("parte") == "entra"]
    cercano = min(elegibles, key=lambda n: haversine_km(lat, lon, g.nodes[n]["lat"], g.nodes[n]["lon"]))
    return cercano.split(":")[0]


# ---------------------------------------------------------------- analisis completo


def actuales(cands: list[str]) -> list[str]:
    return [j for j in config.parametro("acopios_grafo.actuales") if j in cands]


def analizar(g: nx.DiGraph | None = None, centros: pd.DataFrame | None = None, temporada: str | None = None) -> dict:
    """Todo lo de §4 para el escenario base: candidatos, c_ij, curva del codo, modos, referencias."""
    g = g if g is not None else grafo.construir_grafo()
    centros = centros if centros is not None else config.cargar_centros_poblados()
    cands, tabla_cands = candidatos(centros, g)
    w = pesos_zonas(g)
    libres = puntos_libres(g, cands)
    c_todo = matriz_costos(g, sorted(set(cands) | set(libres)), temporada)
    c = c_todo[cands]
    curva = pd.DataFrame(
        [{"p": p, **p_mediana_enumeracion(c, w, p)} for p in range(1, len(cands) + 1)]
    )[["p", "S", "f"]]
    p_codo = codo(curva)
    s_estrella = curva.set_index("p").at[p_codo, "S"]
    hoy = actuales(cands)
    agregar = []
    for k in range(1, config.parametro("ubicacion.k_max_agregar") + 1):
        if len(hoy) + k <= len(cands):
            agregar.append({"k": k, **p_mediana_enumeracion(c, w, len(hoy) + k, tuple(hoy))})
    libre = p_mediana_enumeracion(c_todo[libres], w, min(p_codo, len(libres))) if libres else None
    j_centro = centroide(g, w)
    c_centro = matriz_costos(g, [j_centro], temporada) if j_centro not in c_todo.columns else c_todo[[j_centro]]
    return {
        "grafo": g, "candidatos": cands, "tabla_candidatos": tabla_cands, "w": w, "c": c, "c_libres": c_todo[libres],
        "curva": curva, "p_codo": p_codo, "S": s_estrella, "metodos": tres_metodos(c, w, p_codo),
        "actuales": hoy, "f_actuales": f(c, w, hoy), "agregar": pd.DataFrame(agregar),
        "libre": libre, "costo_exigir_pueblos": (f(c, w, s_estrella) - libre["f"]) if libre else math.nan,
        "centroide": j_centro, "f_centroide_p1": f(c_centro, w, [j_centro]), "f_p1": curva["f"].iloc[0],
        "voronoi": voronoi(c, s_estrella),
    }


# ---------------------------------------------------------------- viabilidad (§4.7)

# Costos de cada acopio en parametros.yaml: (inversion, operacion anual, kWh/dia). La Cristalina hereda los
# de Puente Arimena (decision del 19 nov); un pueblo nuevo usa los de un acopio nuevo; la plaza ya funciona.
COSTOS = {
    "CP03": ("economia.rehabilitacion_san_miguel_cop", "economia.operacion_anual_san_miguel_cop", "economia.kwh_dia_san_miguel"),
    "CP02": ("economia.rehabilitacion_puente_arimena_cop", "economia.operacion_anual_puente_arimena_cop", "economia.kwh_dia_puente_arimena"),
}
COSTOS_NUEVO = ("inversiones.acopio_nuevo_cop", "inversiones.operacion_anual_acopio_nuevo_cop", "inversiones.kwh_dia_acopio_nuevo")
PLAZA = "CP01"


def costos(j: str) -> tuple[float, float, float]:
    if j == PLAZA:
        return 0.0, 0.0, 0.0
    return tuple(config.parametro(r) for r in COSTOS.get(j, COSTOS_NUEVO))


def capacidad(centros: pd.DataFrame) -> pd.Series:
    return centros.set_index("id")["capacidad_frio_kg"]


def metricas_area(g: nx.DiGraph, asignacion: pd.Series, w: pd.Series, temporada: str | None = None) -> pd.DataFrame:
    """km, horas y % del recorrido contra la corriente de cada area, ponderados por kg (bote mas comun)."""
    p = config.parametro
    bote = max(p("flota.mezcla"), key=p("flota.mezcla").get)
    cond = pesos.Condiciones(bote=bote, temporada=temporada or p("escenario_base.temporada"))
    gc = pesos.expandir_capas(g, cond.con(acopios=frozenset()))
    filas = []
    for i, j in asignacion.items():
        r = busqueda.dijkstra_capas(gc, (i, "hielo"), {(entrada(g, j), x) for x in pesos.CAPAS}, pesos.funcion_costo(cond.con(acopios=frozenset())))
        contra = sum(gc.edges[u, v]["d_km"] for u, v in zip(r.camino, r.camino[1:]) if gc.edges[u, v]["sentido"] == -1)
        filas.append({"zona": i, "acopio": j, "kg_dia": w[i], "km": r.km, "horas": r.horas, "km_contra": contra})
    t = pd.DataFrame(filas)
    agrupado = t.groupby("acopio").apply(
        lambda d: pd.Series({
            "kg_dia": d["kg_dia"].sum(),
            "km_prom": np.average(d["km"], weights=d["kg_dia"]),
            "horas_prom": np.average(d["horas"], weights=d["kg_dia"]),
            "pct_contra": 100 * (d["km_contra"] * d["kg_dia"]).sum() / max((d["km"] * d["kg_dia"]).sum(), 1e-9),
        }),
        include_groups=False,
    )
    return agrupado


def viabilidad(analisis: dict, abiertos=None, mc: pd.DataFrame | None = None) -> pd.DataFrame:
    """Por acopio: carga contra capacidad, perdida evitada f(S∖j) − f(S), metricas del area y VPN."""
    from pesca.ubicacion import vale_la_pena, vpn

    p = config.parametro
    g, c, w = analisis["grafo"], analisis["c"], analisis["w"]
    abiertos = list(abiertos if abiertos is not None else analisis["S"])
    asign = voronoi(c, abiertos)
    area = metricas_area(g, asign, w)
    k = capacidad(config.cargar_centros_poblados())
    f_s = f(c, w, abiertos)
    tasa, anios = p("economia.tasa_descuento"), p("economia.horizonte_anios")
    filas = []
    for j in abiertos:
        carga = float(w[asign == j].sum())
        evitada = f([] if False else c, w, [x for x in abiertos if x != j]) - f_s
        inversion, operacion, kwh = costos(j)
        beneficio = evitada * precio_base() * p("volumen.dias_pesca_anio")
        energia = kwh * DIAS_ANIO * p("economia.cop_kwh")
        fila = {
            "acopio": j, "nombre": g.nodes[entrada(g, j)]["nombre"], "kg_dia": carga, "capacidad_kg": k.get(j, math.nan),
            "uso_pct": 100 * carga / k[j] if j in k and k[j] > 0 else math.nan,
            "perdida_evitada_kg_dia": evitada, "beneficio_anual": beneficio, "inversion": inversion,
            "vpn": vpn(inversion, beneficio - operacion - energia, anios, tasa) if j != PLAZA else math.nan,
            **(area.loc[j].to_dict() if j in area.index else {}),
        }
        if mc is not None and j in set(mc["acopio"]):
            v = mc.loc[mc["acopio"] == j, "vpn"]
            ok, frac = vale_la_pena(v)
            fila.update(vpn_p5=float(np.percentile(v, 5)), vpn_p95=float(np.percentile(v, 95)), pct_vpn_positivo=100 * frac,
                        veredicto="vale la pena" if ok else "no vale la pena")
        elif j == PLAZA:
            fila["veredicto"] = "ya funciona (la plaza)"
        filas.append(fila)
    return pd.DataFrame(filas)


def montecarlo_viabilidad(abiertos, n: int | None = None, semilla: int | None = None) -> pd.DataFrame:
    """VPN de cada acopio con los parametros muestreados (regla: VPN > 0 en ≥ umbral de las corridas)."""
    from pesca.ubicacion import vpn

    n = n if n is not None else config.parametro("acopios_grafo.corridas_montecarlo")
    semilla = semilla if semilla is not None else config.parametro("general.semilla")
    g = grafo.construir_grafo()
    w = pesos_zonas(g)
    abiertos = list(abiertos)

    def corrida(i: int, rng: np.random.Generator) -> list[dict]:
        p = config.parametro
        temporada = "aguas_altas" if rng.random() < p("economia.fraccion_aguas_altas") else "aguas_bajas"
        c = matriz_costos(g, abiertos, temporada)
        f_s = f(c, w, abiertos)
        filas = []
        for j in abiertos:
            if j == PLAZA:
                continue
            evitada = f(c, w, [x for x in abiertos if x != j]) - f_s
            inversion, operacion, kwh = costos(j)
            beneficio = evitada * precio_base() * p("volumen.dias_pesca_anio")
            energia = kwh * DIAS_ANIO * p("economia.cop_kwh")
            flujo = beneficio - operacion - energia
            filas.append({"corrida": i, "acopio": j, "temporada": temporada, "perdida_evitada_kg_dia": evitada,
                          "vpn": vpn(inversion, flujo, p("economia.horizonte_anios"), p("economia.tasa_descuento"))})
        return filas

    columnas = ["corrida", "acopio", "temporada", "perdida_evitada_kg_dia", "vpn"]
    return pd.DataFrame([fila for filas in montecarlo.correr(corrida, n, semilla) for fila in filas], columns=columnas)


# ---------------------------------------------------------------- sensibilidad (§4.8)


def sensibilidad(analisis: dict) -> pd.DataFrame:
    """Repite la eleccion de S* (cada caso con su propio codo) variando P_min, el acceso, la temporada y el bote."""
    p = config.parametro
    g, w, s_base = analisis["grafo"], analisis["w"], analisis["S"]
    centros = config.cargar_centros_poblados()
    casos = [("P_min", x, {"p_min": x}) for x in p("acopios_grafo.p_min_sensibilidad")]
    casos += [("criterio_acceso", x, {"criterio_acceso": x}) for x in ("estricto", "permisivo")]
    casos += [("temporada", x, {"temporada": x}) for x in sorted(config.TEMPORADAS)]
    casos += [("embarcacion", x, {"bote": x}) for x in p("flota.mezcla")]
    filas = []
    for variable, valor, kw in casos:
        cands, _ = candidatos(centros, g, kw.get("p_min"), kw.get("criterio_acceso"))
        c = matriz_costos(g, cands, kw.get("temporada"), kw.get("bote"))
        curva = pd.DataFrame([{"p": k, **p_mediana_enumeracion(c, w, k)} for k in range(1, len(cands) + 1)])
        pp = codo(curva)
        r = curva.set_index("p").loc[pp]
        filas.append({"variable": variable, "valor": str(valor), "candidatos": len(cands), "p": pp, "S": r["S"], "f": r["f"],
                      "cambia": tuple(sorted(r["S"])) != tuple(sorted(s_base))})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- precalculo


def precalcular(n: int | None = None) -> None:
    analisis = analizar()
    mc = montecarlo_viabilidad(analisis["S"], n)
    destino = config.DIR_PRECALCULADO
    destino.mkdir(parents=True, exist_ok=True)
    mc.to_csv(destino / "g5_viabilidad_mc.csv", index=False)
    sensibilidad(analisis).assign(S=lambda d: d["S"].map(" ".join)).to_csv(destino / "g5_sensibilidad.csv", index=False)


def cargar_precalculado() -> dict | None:
    destino = config.DIR_PRECALCULADO
    if not (destino / "g5_viabilidad_mc.csv").is_file():
        return None
    sens = pd.read_csv(destino / "g5_sensibilidad.csv")
    sens["S"] = sens["S"].map(lambda s: tuple(str(s).split()))
    return {"mc": pd.read_csv(destino / "g5_viabilidad_mc.csv"), "sensibilidad": sens}
