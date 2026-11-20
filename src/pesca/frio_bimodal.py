"""Rutas bimodales, cadena de frio e inversion (R5).

Cada medida I1–I7 es un cambio del Escenario (escenario_con). Su valor es el costo que evita en el reparto
optimo de la flota (asignacion.problema_transporte: valor perdido + viaje) frente al reparto optimo de hoy,
igual que en R4. Se enumeran todos los portafolios, se arma la frontera de Pareto (inversion vs valor salvado)
y para cada presupuesto se recomienda el de mayor VPN entre los que caben.

- I1 cajas termicas: todo pescador con nevera buena.
- I2 fabrica de hielo (exige I1): hielo a bordo, el rio va a 4 °C.
- I3a / I3b: rehabilitar San Miguel / La Cristalina (antes Puente Arimena; costos de R4).
- I4: acopio nuevo en el mejor centro poblado que todavia no es acopio (p-mediana sobre pueblos, modo agregar k = 1).
  Si todos los pueblos candidatos ya son acopio, I4 no esta disponible y no entra a los portafolios.
- I5:N: camion refrigerado que lleva los acopios y recoge en los desembarques cada N dias.
- I6: subsidio de motor para parte de los botes a remo.
- I7: desembarque de la señora mejorado (todo cabe en el congelador y no hay cortes de luz).
"""

from __future__ import annotations

import itertools
import json
from functools import cache

import networkx as nx
import numpy as np
import pandas as pd

from pesca import asignacion, busqueda, cadena_actual, config, montecarlo, poblacion, red, transporte, ubicacion
from pesca.escenario import Escenario

NOMBRE_MEDIDA = {
    "I1": "Cajas térmicas con hielo",
    "I2": "Fábrica de hielo (hielo a bordo)",
    "I3a": "Rehabilitar San Miguel",
    "I3b": "Rehabilitar La Cristalina",
    "I4": "Acopio en el Manacacías (reemplaza a La Cristalina)",
    "I5": "Camión refrigerado con ruta",
    "I6": "Subsidio de motor",
    "I7": "Mejorar el desembarque de la señora",
    "I8": "Puntos fríos en pueblos de la ruta (La Cristalina y los que elija el algoritmo)",
}
# Medidas que ya no se ofrecen (decision del equipo, 20 nov): la solucion es mover y mejorar los acopios.
# I3b: La Cristalina pasa a ser punto frio; I7: el desembarque de la señora no es solucion.
RETIRADAS = {"I3b", "I7"}
ACOPIO_DE = {"I3a": "A02", "I3b": "A03"}
SEPARADOR = "+"
HOY = "hoy"
DIAS_ANIO = ubicacion.DIAS_ANIO

ARCHIVO_PORTAFOLIOS = "r5_portafolios.csv"
ARCHIVO_MONTECARLO = "r5_montecarlo.csv"
ARCHIVO_META = "r5_meta.json"


# ---------------------------------------------------------------- portafolios


def codigo_camion(n: int) -> str:
    return f"I5:{n}"


def ciclo_camion(portafolio: frozenset[str]) -> int | None:
    """N del camion (I5:N) o None si el portafolio no lo incluye."""
    ciclos = [int(m.split(":")[1]) for m in portafolio if m.startswith("I5:")]
    if len(ciclos) > 1:
        raise ValueError(f"El portafolio tiene más de un ciclo de camión: {sorted(portafolio)}")
    return ciclos[0] if ciclos else None


def validar(portafolio: frozenset[str]) -> None:
    conocidas = set(NOMBRE_MEDIDA) - {"I5"}
    for m in portafolio:
        if m not in conocidas and not m.startswith("I5:"):
            raise ValueError(f"Medida desconocida: {m}")
    if portafolio & RETIRADAS:
        raise ValueError(f"Medidas retiradas (la solución es mover y mejorar los acopios): {sorted(portafolio & RETIRADAS)}")
    if "I2" in portafolio and "I1" not in portafolio:
        raise ValueError("I2 (fábrica de hielo) exige I1 (cajas térmicas): sin cajas el hielo no dura")
    ciclo_camion(portafolio)


def clave(portafolio: frozenset[str]) -> str:
    """Texto estable de un portafolio, p. ej. 'I1+I2+I5:3'; el vacio es 'hoy'."""
    return SEPARADOR.join(sorted(portafolio)) if portafolio else HOY


def desde_clave(texto: str) -> frozenset[str]:
    return frozenset() if texto == HOY else frozenset(texto.split(SEPARADOR))


def describir(portafolio: frozenset[str]) -> list[str]:
    """Nombres para la interfaz, p. ej. 'Camión refrigerado con ruta (cada 3 días)'."""
    salida = []
    for m in sorted(portafolio):
        if m.startswith("I5:"):
            n = int(m.split(":")[1])
            salida.append(f"{NOMBRE_MEDIDA['I5']} ({'todos los días' if n == 1 else f'cada {n} días'})")
        else:
            salida.append(NOMBRE_MEDIDA[m])
    return salida


def enumerar_portafolios() -> list[frozenset[str]]:
    """Todas las combinaciones validas: I2 solo con I1 y a lo sumo un ciclo de camion."""
    opciones_hielo = [(), ("I1",), ("I1", "I2")]
    opciones_camion = [()] + [(codigo_camion(n),) for n in config.parametro("inversiones.ciclos_camion_dias")]
    binarias = ["I3a", *(["I4"] if acopio_nuevo() else []), "I6", "I8"]
    portafolios = []
    for hielo in opciones_hielo:
        for camion in opciones_camion:
            for elegidas in itertools.product((False, True), repeat=len(binarias)):
                extra = tuple(m for m, si in zip(binarias, elegidas) if si)
                portafolios.append(frozenset(hielo + camion + extra))
    return portafolios


def medidas_solas() -> list[frozenset[str]]:
    """Cada medida sola (I2 va con I1, que exige) y cada ciclo del camion."""
    solas = [frozenset({"I1"}), frozenset({"I1", "I2"}), frozenset({"I3a"}), frozenset({"I8"})]
    solas += [frozenset({"I4"})] if acopio_nuevo() else []
    solas += [frozenset({codigo_camion(n)}) for n in config.parametro("inversiones.ciclos_camion_dias")]
    return solas + [frozenset({"I6"})]


# ---------------------------------------------------------------- efecto en el escenario


@cache
def _analisis_grafo() -> dict:
    from pesca import acopios

    return acopios.analizar()


def pueblo_nuevo() -> str | None:
    """Punto del Manacacias del grafo v4 donde va el acopio que reemplaza a La Cristalina (busqueda exhaustiva)."""
    return _analisis_grafo()["manacacias"]["punto"]


@cache
def acopio_nuevo() -> str | None:
    """Punto del rio de la red de simulacion frente al acopio del Manacacias (I4)."""
    punto = pueblo_nuevo()
    if punto is None:
        return None
    a = _analisis_grafo()["grafo"].nodes[punto]
    return red.separar(red.nodo_rio_mas_cercano(a["lat"], a["lon"]))[0]


# Pueblos del grafo v4 -> lugares de la red de simulacion (los que existen en ella)
LUGAR_DE_PUEBLO = {"CP01": "A01", "CP02": "A03", "CP03": "A02", "C01": "C01"}


@cache
def puntos_frios() -> tuple[frozenset[str], frozenset[str]]:
    """(lugares de la red de simulacion, pueblos del grafo v4) de los puntos frios: La Cristalina y los elegidos."""
    todos = frozenset(_analisis_grafo()["puntos_frios"]["todos"])
    return frozenset(LUGAR_DE_PUEBLO[x] for x in todos if x in LUGAR_DE_PUEBLO), todos


def texto_acopio_nuevo() -> str:
    an = _analisis_grafo()
    m = an["manacacias"]
    return (f"Cuarto frío junto al Manacacías ({m['pueblo']}, [CONFIRMAR]) en {m['nombre']}, el mejor punto del río según la "
            f"búsqueda exhaustiva; reemplaza al acopio de La Cristalina")


def escenario_con(base: Escenario, portafolio: frozenset[str]) -> Escenario:
    """El escenario base con las medidas del portafolio encendidas."""
    validar(portafolio)
    ciclo = ciclo_camion(portafolio)
    acopios = set(base.acopios_activos) | {ACOPIO_DE[m] for m in portafolio if m in ACOPIO_DE}
    nuevos = set(base.acopios_nuevos) | ({acopio_nuevo()} if "I4" in portafolio else set())
    return base.con(
        acopios_activos=frozenset(acopios),
        acopios_nuevos=frozenset(nuevos),
        cajas_termicas=base.cajas_termicas or "I1" in portafolio,
        hielo_a_bordo=base.hielo_a_bordo or "I2" in portafolio,
        camion_refrigerado=base.camion_refrigerado or ciclo is not None,
        ciclo_camion_dias=ciclo if ciclo is not None else base.ciclo_camion_dias,
        subsidio_motor=base.subsidio_motor or "I6" in portafolio,
        desembarque_mejorado=base.desembarque_mejorado,
        puntos_frios=frozenset(base.puntos_frios | (puntos_frios()[0] if "I8" in portafolio else set())),
        puntos_frios_grafo=frozenset(base.puntos_frios_grafo | (puntos_frios()[1] if "I8" in portafolio else set())),
        inversiones=frozenset(base.inversiones | portafolio),
    )


# ---------------------------------------------------------------- costos


def paradas_camion(escenario: Escenario) -> list[str]:
    """Lugares donde recoge el camion: desembarques (señora, San Miguel o cruces del Vichada) y acopios activos."""
    paradas = {escenario.desembarque_senora, "A02", *config.parametro("poblacion.desembarque_vichada").values()}
    paradas |= set(escenario.acopios_activos) | set(escenario.acopios_nuevos)
    return sorted(paradas - {asignacion.ACOPIO_PLAZA})


def km_ruta_camion(escenario: Escenario, grafo: nx.DiGraph | None = None) -> float:
    """Circuito por carretera plaza → paradas → plaza, por vecino mas cercano (Dijkstra propio por distancia)."""
    grafo = grafo if grafo is not None else red.construir_red()
    via = red.subgrafo_modo(grafo, red.CAPA_VIA, "transbordo")
    peso = transporte.peso(transporte.Perfil.desde_escenario(escenario, "madera_motor"), "distancia")

    def entrada(lugar: str) -> tuple[str, float]:
        """Nodo vial de la parada y km de acceso estimado si no esta sobre una via (acopio nuevo)."""
        if red.clave(lugar, red.CAPA_RIO) not in grafo:  # acopio solo por carretera (La Cristalina)
            return red.clave(lugar, red.CAPA_VIA), 0.0
        return red.acceso_vial(red.clave(lugar, red.CAPA_RIO), grafo)

    def km(a: str, b: str) -> float:
        return busqueda.dijkstra(via, a, b, peso).costo

    pendientes = {lugar: entrada(lugar) for lugar in paradas_camion(escenario)}
    actual, total = asignacion.PLAZA, 0.0
    while pendientes:
        lugar = min(pendientes, key=lambda x: km(actual, pendientes[x][0]))
        nodo, acceso = pendientes.pop(lugar)
        total += km(actual, nodo) + 2 * acceso
        actual = nodo
    return total + km(actual, asignacion.PLAZA)


def costos(portafolio: frozenset[str], escenario: Escenario, pob: pd.DataFrame) -> dict[str, float]:
    """Inversion inicial y operacion anual (con energia, combustible y reposicion) del portafolio.

    `escenario` es el escenario con el portafolio aplicado (para la ruta del camion).
    """
    p = config.parametro
    inversion = operacion = kwh_dia = 0.0
    if "I1" in portafolio:
        cajas = len(pob) * p("inversiones.caja_termica_cop")
        inversion += cajas
        operacion += cajas / p("inversiones.vida_caja_anios")
    if "I2" in portafolio:
        inversion += p("inversiones.fabrica_hielo_cop")
        operacion += p("inversiones.operacion_anual_hielo_cop")
        kwh_dia += p("inversiones.kwh_dia_hielo")
    acopios = frozenset(ACOPIO_DE[m] for m in portafolio if m in ACOPIO_DE)
    inv_a, op_a, kwh_a = ubicacion.costos_acopios(acopios)
    inversion, operacion, kwh_dia = inversion + inv_a, operacion + op_a, kwh_dia + kwh_a
    if "I4" in portafolio:
        inversion += p("inversiones.acopio_nuevo_cop")
        operacion += p("inversiones.operacion_anual_acopio_nuevo_cop")
        kwh_dia += p("inversiones.kwh_dia_acopio_nuevo")
    ciclo = ciclo_camion(portafolio)
    km_ruta = 0.0
    if ciclo is not None:
        km_ruta = km_ruta_camion(escenario)
        inversion += p("inversiones.camion_refrigerado_cop")
        viajes = p("volumen.dias_pesca_anio") / ciclo
        operacion += p("inversiones.operacion_anual_camion_cop") + km_ruta * viajes * p("inversiones.camion_cop_km")
    motores = 0
    if "I6" in portafolio:
        motores = int((poblacion.aplicar_subsidio_motor(pob)["embarcacion"] != pob["embarcacion"]).sum())
        inversion += motores * p("inversiones.motor_cop") * p("inversiones.fraccion_subsidio_motor")
    if "I8" in portafolio:
        n_frios = len(puntos_frios()[1])
        inversion += n_frios * p("puntos_frios.inversion_cop")
        operacion += n_frios * p("puntos_frios.operacion_anual_cop")
        kwh_dia += n_frios * p("puntos_frios.kwh_dia")
    energia = kwh_dia * DIAS_ANIO * p("economia.cop_kwh")
    return {"inversion": inversion, "operacion_anual": operacion + energia, "energia_anual": energia,
            "km_ruta_camion": km_ruta, "motores_subsidiados": motores}


# ---------------------------------------------------------------- evaluacion


def evaluar(portafolio: frozenset[str], base: Escenario, pob: pd.DataFrame, costo_base_dia: float,
            kg_base_dia: float, memo: dict | None = None) -> dict:
    """Valor salvado, costos y VPN de un portafolio frente al reparto optimo de hoy."""
    p = config.parametro
    esc = escenario_con(base, portafolio)
    res = asignacion.problema_transporte(esc, pob, memo, con_hoy=False)
    c = costos(portafolio, esc, pob)
    evitado = costo_base_dia - res["costo_optimo_dia"]
    beneficio = evitado * p("volumen.dias_pesca_anio")
    anios, tasa = p("economia.horizonte_anios"), p("economia.tasa_descuento")
    return {
        "portafolio": clave(portafolio),
        "n_medidas": len(portafolio),
        "costo_dia": res["costo_optimo_dia"],
        "valor_salvado_dia": evitado,
        "beneficio_anual": beneficio,
        "kg_salvados_dia": ubicacion._kg_vendibles(res) - kg_base_dia,
        **c,
        "vpn": ubicacion.vpn(c["inversion"], beneficio - c["operacion_anual"], anios, tasa),
    }


def _referencia(base: Escenario, pob: pd.DataFrame, memo: dict) -> tuple[float, float]:
    res = asignacion.problema_transporte(base, pob, memo, con_hoy=False)
    return res["costo_optimo_dia"], ubicacion._kg_vendibles(res)


def tabla_portafolios(base: Escenario | None = None, pob: pd.DataFrame | None = None,
                      portafolios: list[frozenset[str]] | None = None) -> pd.DataFrame:
    """Todos los portafolios evaluados con la poblacion de ejemplo (deterministico)."""
    base = base if base is not None else Escenario.base()
    pob = pob if pob is not None else cadena_actual.corrida_ejemplo(base).poblacion
    portafolios = portafolios if portafolios is not None else enumerar_portafolios()
    memo: dict = {}
    costo_base, kg_base = _referencia(base, pob, memo)
    return pd.DataFrame([evaluar(pf, base, pob, costo_base, kg_base, memo) for pf in portafolios])


def frontera_pareto(tabla: pd.DataFrame) -> pd.Series:
    """True para los portafolios no dominados: ninguno cuesta lo mismo o menos y salva estrictamente mas (o igual y cuesta menos)."""
    inv, val = tabla["inversion"].to_numpy(), tabla["beneficio_anual"].to_numpy()
    no_dominado = []
    for i in range(len(tabla)):
        domina = (inv <= inv[i]) & (val >= val[i]) & ((inv < inv[i]) | (val > val[i]))
        no_dominado.append(not domina.any())
    return pd.Series(no_dominado, index=tabla.index)


def recomendado(tabla: pd.DataFrame, presupuesto: float) -> pd.Series:
    """El portafolio de mayor VPN cuya inversion cabe en el presupuesto ('hoy' si ninguno tiene VPN > 0)."""
    caben = tabla[tabla["inversion"] <= presupuesto]
    if caben.empty:
        raise ValueError(f"Ningún portafolio cabe en {presupuesto:,.0f} COP")
    return caben.loc[caben["vpn"].idxmax()]


def pasos_combinados(tabla: pd.DataFrame, portafolio: frozenset[str]) -> list[dict]:
    """Hoy → + medida → + medida … (en orden del valor que salva cada medida sola), leidos de la tabla.

    I1 va siempre antes de I2, porque I2 lo exige.
    """
    por_clave = tabla.set_index("portafolio")
    solas = {m: por_clave.at[clave(frozenset({m} | ({"I1"} if m == "I2" else set()))), "beneficio_anual"] for m in portafolio}
    orden = sorted(portafolio, key=lambda m: -solas[m])
    if "I2" in orden and "I1" in orden and orden.index("I2") < orden.index("I1"):
        orden.remove("I1")
        orden.insert(orden.index("I2"), "I1")
    pasos, acumulado = [], frozenset()
    for m in orden:
        acumulado = acumulado | {m}
        fila = por_clave.loc[clave(acumulado)]
        pasos.append({"medida": describir(frozenset({m}))[0], "portafolio": clave(acumulado),
                      "beneficio_anual": float(fila["beneficio_anual"]), "inversion": float(fila["inversion"])})
    return pasos


# ---------------------------------------------------------------- Monte Carlo


def _corrida(i: int, rng: np.random.Generator, portafolios: list[frozenset[str]]) -> list[dict]:
    p = config.parametro
    temporada = "aguas_altas" if rng.random() < p("economia.fraccion_aguas_altas") else "aguas_bajas"
    base = Escenario.base().con(temporada=temporada)
    pob = poblacion.generar_poblacion(rng, base.desembarque_senora, red.construir_red())
    memo: dict = {}
    costo_base, kg_base = _referencia(base, pob, memo)
    return [{"corrida": i, "temporada": temporada, **evaluar(pf, base, pob, costo_base, kg_base, memo)}
            for pf in portafolios]


def montecarlo_portafolios(portafolios: list[frozenset[str]], n: int | None = None,
                           semilla: int | None = None) -> pd.DataFrame:
    """Monte Carlo (mismas muestras para todos los portafolios) de valor salvado y VPN."""
    n = n if n is not None else p_corridas()
    semilla = semilla if semilla is not None else config.parametro("general.semilla")
    resultados = montecarlo.correr(lambda i, rng: _corrida(i, rng, portafolios), n, semilla)
    return pd.DataFrame([fila for filas in resultados for fila in filas])


def p_corridas() -> int:
    return config.parametro("montecarlo.corridas_r5")


def resumen_montecarlo(tabla: pd.DataFrame) -> pd.DataFrame:
    """Por portafolio: media e IC 90 % de valor salvado, VPN y kg salvados, y % de corridas con VPN > 0."""
    filas = []
    for pf, sub in tabla.groupby("portafolio", sort=False):
        filas.append({
            "portafolio": pf,
            "pct_vpn_positivo": 100 * float((sub["vpn"] > 0).mean()),
            **{f"{c}_{k}": v for c in ("beneficio_anual", "vpn", "kg_salvados_dia", "inversion")
               for k, v in montecarlo.resumir(sub[c]).items()},
        })
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- unimodal vs bimodal


def unimodal_vs_bimodal(escenario: Escenario, embarcaciones: tuple[str, ...] = ("madera_remo", "madera_motor")) -> pd.DataFrame:
    """Por zona y embarcacion: la mejor venta por rio a la plaza frente al mejor acopio + camion refrigerado.

    El lado bimodal activa San Miguel y La Cristalina con camion refrigerado sobre el escenario dado.
    """
    bimodal = escenario.con(acopios_activos=frozenset(escenario.acopios_activos | {"A02", "A03"}), camion_refrigerado=True)
    kg = config.parametro("poblacion.kg_por_faena")
    nodos = config.cargar_nodos()
    zonas = nodos[nodos["tipo"].isin(["zona_pesca", "comunidad"])]
    filas = []
    for z in zonas.itertuples():
        for emb in embarcaciones:
            uni = _mejor(asignacion.recomendar(red.clave(z.id, red.CAPA_RIO), emb, kg, escenario), "plaza")
            bi = _mejor(asignacion.recomendar(red.clave(z.id, red.CAPA_RIO), emb, kg, bimodal), "acopio")
            filas.append({
                "zona": z.id, "nombre": z.nombre, "cuenca": z.cuenca, "embarcacion": emb,
                **_columnas(uni, "rio"), **_columnas(bi, "bimodal"),
                "gana": _ganador(uni, bi),
            })
    return pd.DataFrame(filas)


def _mejor(rec: asignacion.Recomendacion, tipo: str) -> asignacion.Opcion | None:
    opciones = [o for o in rec.alternativas if o.factible and o.tipo == tipo]
    return max(opciones, key=lambda o: o.cop_neto) if opciones else None


def _columnas(o: asignacion.Opcion | None, sufijo: str) -> dict:
    if o is None:
        return {f"destino_{sufijo}": "no se puede", f"calidad_{sufijo}": np.nan, f"horas_{sufijo}": np.nan,
                f"neto_{sufijo}": np.nan}
    return {f"destino_{sufijo}": o.nombre, f"calidad_{sufijo}": o.calidad, f"horas_{sufijo}": o.horas_hasta_venta,
            f"neto_{sufijo}": o.cop_neto}


def _ganador(uni: asignacion.Opcion | None, bi: asignacion.Opcion | None) -> str:
    if uni is None and bi is None:
        return "ninguna"
    if bi is None:
        return "río"
    if uni is None:
        return "bimodal"
    return "bimodal" if bi.cop_neto > uni.cop_neto else "río"


# ---------------------------------------------------------------- precalculo


def precalcular(n: int | None = None) -> None:
    """Todos los portafolios (poblacion de ejemplo) y Monte Carlo de hoy, medidas solas y recomendados."""
    config.DIR_PRECALCULADO.mkdir(parents=True, exist_ok=True)
    tabla = tabla_portafolios()
    tabla["pareto"] = frontera_pareto(tabla)
    tabla.to_csv(config.DIR_PRECALCULADO / ARCHIVO_PORTAFOLIOS, index=False, float_format="%.6g")
    print(f"  r5 portafolios: {len(tabla)}")
    presupuestos = config.parametro("inversiones.presupuestos_cop")
    elegidos = {float(b): recomendado(tabla, b)["portafolio"] for b in presupuestos}
    candidatos = [frozenset(), *medidas_solas()]
    # la propuesta del equipo tambien pasa por el Monte Carlo, la recomiende o no el VPN
    for pf in [frozenset(config.parametro("propuesta.portafolio")), *map(desde_clave, elegidos.values())]:
        if pf not in candidatos:
            candidatos.append(pf)
    mc = montecarlo_portafolios(candidatos, n)
    mc.to_csv(config.DIR_PRECALCULADO / ARCHIVO_MONTECARLO, index=False, float_format="%.6g")
    print(f"  r5 Monte Carlo: {mc['corrida'].nunique()} corridas × {len(candidatos)} portafolios")
    meta = {"corridas": int(mc["corrida"].nunique()), "semilla": config.parametro("general.semilla"),
            "recomendados": {str(int(b)): pf for b, pf in elegidos.items()}}
    (config.DIR_PRECALCULADO / ARCHIVO_META).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def cargar_precalculado() -> dict | None:
    archivos = [config.DIR_PRECALCULADO / a for a in (ARCHIVO_PORTAFOLIOS, ARCHIVO_MONTECARLO, ARCHIVO_META)]
    if not all(a.is_file() for a in archivos):
        return None
    return {
        "portafolios": pd.read_csv(archivos[0]),
        "montecarlo": pd.read_csv(archivos[1]),
        "meta": json.loads(archivos[2].read_text(encoding="utf-8")),
    }
