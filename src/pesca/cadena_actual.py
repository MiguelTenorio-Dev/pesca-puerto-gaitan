"""Simulacion de la cadena de hoy (R2), pescador por pescador.

zona de pesca → rio (icopor) → desembarque → espera hasta que llega el comprador → carretera → plaza.

Sitios de desembarque:
- malecon: venta el mismo dia en la plaza (sin espera);
- senora: congeladores horizontales con capacidad fija; lo que no cabe va a icopor; cortes de luz;
- san_miguel y vichada: sin frio (el cuarto frio de San Miguel no se usa): espera en icopor.
Un ciclo dura lo que tarda el comprador (7–15 dias). Las horas de rio y de carretera salen
de Dijkstra (Fase 1) sobre la red calibrada.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field

import networkx as nx
import numpy as np
import pandas as pd

from pesca import busqueda, config, degradacion as dg, montecarlo, poblacion, red, transporte
from pesca.escenario import Escenario

PASO_ESCALA = 0.05
HORAS_DIA = 24
DESTINO_PLAZA = "A01@via"
EMBARCACION_REFERENCIA = "madera_motor"  # la carretera no depende del bote

ARCHIVO_CORRIDAS = "r2_corridas.csv"
ARCHIVO_ZONAS = "r2_zonas.csv"
ARCHIVO_META = "r2_meta.json"


def escenario_hoy(escenario: Escenario) -> Escenario:
    """El diagnostico es la situacion de hoy: sin hielo a bordo, camion refrigerado ni medidas de R5."""
    return escenario.con(hielo_a_bordo=False, camion_refrigerado=False, cajas_termicas=False, ciclo_camion_dias=None,
                         desembarque_mejorado=False, subsidio_motor=False, inversiones=frozenset())


def grafo_vigente() -> nx.DiGraph:
    """Red con la escala de sinuosidad vigente (redondeada para reutilizar la cache)."""
    escala = round(round(config.parametro("rio.escala_sinuosidad") / PASO_ESCALA) * PASO_ESCALA, 2)
    return red.construir_red(escala)


class Tiempos:
    """Horas y rutas de rio y de carretera de una corrida (con cache por consulta)."""

    def __init__(self, grafo: nx.DiGraph, escenario: Escenario):
        self.grafo = grafo
        self.escenario = escenario
        self.rio_g = red.subgrafo_modo(grafo, red.CAPA_RIO)
        self.via_g = red.subgrafo_modo(grafo, red.CAPA_VIA, "transbordo")
        self._rio: dict[tuple[str, str, str], busqueda.ResultadoBusqueda] = {}
        self._via: dict[str, busqueda.ResultadoBusqueda] = {}

    def perfil(self, embarcacion: str) -> transporte.Perfil:
        return transporte.Perfil.desde_escenario(self.escenario, embarcacion)

    def rio(self, ubicacion: str, desembarque: str, embarcacion: str) -> busqueda.ResultadoBusqueda:
        k = (ubicacion, desembarque, embarcacion)
        if k not in self._rio:
            w = transporte.peso(self.perfil(embarcacion), "tiempo")
            self._rio[k] = busqueda.dijkstra(self.rio_g, ubicacion, red.clave(desembarque, red.CAPA_RIO), w)
        return self._rio[k]

    def carretera(self, desembarque: str) -> busqueda.ResultadoBusqueda:
        if desembarque not in self._via:
            w = transporte.peso(self.perfil(EMBARCACION_REFERENCIA), "tiempo")
            self._via[desembarque] = busqueda.dijkstra(self.via_g, red.clave(desembarque, red.CAPA_RIO), DESTINO_PLAZA, w)
        return self._via[desembarque]


@dataclass
class Corrida:
    escenario: Escenario
    poblacion: pd.DataFrame
    lotes: pd.DataFrame
    inventario: pd.DataFrame  # dia a dia del congelador de la señora
    ciclos: dict[str, int]
    kg_mes: dict[str, float]  # kg esperados por sitio en un mes tipico fuera de veda
    capacidad_kg: float
    tiempos: Tiempos = field(repr=False)


def _kg_mes(pob: pd.DataFrame) -> dict[str, float]:
    m = poblacion.meses()
    dias_mes = float(m.loc[~m["veda"], "dias"].mean())
    diario = (pob["kg_por_faena"] * pob["p_faena_pico"]).groupby(pob["sitio"]).sum()
    act = poblacion.actividad_diagnostico()
    return {s: float(diario.get(s, 0.0) * act * dias_mes) for s in poblacion.SITIOS}


def _horas_falla(cortes: np.ndarray, desde: int) -> float:
    """Horas a T ambiente de los cortes de luz mas largos que horas_descongelacion."""
    umbral = config.parametro("cadena_actual.horas_descongelacion")
    return float(np.clip(cortes[desde:] - umbral, 0, None).sum())


def simular_corrida(rng: np.random.Generator, escenario: Escenario) -> Corrida:
    """Un ciclo de recogida de la señora en un mes tipico fuera de veda, con todos los pescadores.

    Todos los sitios se muestrean en los mismos dias; cada sitio espera a su propio comprador.
    Si el bote no puede remontar hasta su desembarque habitual, el pescador vende en el centro
    mas cercano que si alcanza por rio (rio abajo).
    """
    p = config.parametro
    esc = escenario_hoy(escenario)
    grafo = grafo_vigente()
    pob = poblacion.generar_poblacion(rng, esc.desembarque_senora, grafo)
    tiempos = Tiempos(grafo, esc)
    act = poblacion.actividad_diagnostico()

    ciclo, ciclo_sm = p("cadena_actual.ciclo_comprador_dias"), p("cadena_actual.ciclo_comprador_san_miguel_dias")
    ciclos = {
        "senora": int(rng.integers(ciclo["min"], ciclo["max"] + 1)),
        "vichada": int(rng.integers(ciclo["min"], ciclo["max"] + 1)),
        "san_miguel": int(rng.integers(ciclo_sm["min"], ciclo_sm["max"] + 1)),
    }
    largo = ciclos["senora"]
    hay_corte = rng.random(largo) < p("cadena_actual.p_corte_dia")
    duracion = rng.uniform(p("cadena_actual.horas_corte")["min"], p("cadena_actual.horas_corte")["max"], size=largo)
    cortes = np.where(hay_corte, duracion, 0.0)
    capacidad = p("cadena_actual.n_congeladores") * p("cadena_actual.kg_por_congelador")
    centros = _centros_de_venta(pob, esc.desembarque_senora)
    probabilidad = pob["p_faena_pico"].to_numpy() * act

    filas, inventario = [], []
    kg_congelado = kg_icopor = 0.0
    for d in range(largo):
        salen = pob[rng.random(len(pob)) < probabilidad]
        for i in rng.permutation(len(salen)):
            pesc = salen.iloc[i]
            lote, venta, desembarque = _llevar_al_desembarque(pesc, centros, tiempos)
            if venta is None:
                filas.append(_fila(lote, pesc, desembarque, None, d, "no_llego"))
                continue
            if venta == "malecon":
                _ir_a_la_plaza(lote, desembarque, tiempos)
                filas.append(_fila(lote, pesc, desembarque, venta, d, "directo"))
                continue
            dias_espera = ciclos[venta] - d % ciclos[venta]
            for parte, donde in _almacenar(lote, venta, capacidad - kg_congelado):
                if donde == "congelador":
                    kg_congelado += parte.kg
                    falla = _horas_falla(cortes, d)
                    dg.avanzar(parte, falla, "espera", dg.FALLA)
                    dg.avanzar(parte, dias_espera * HORAS_DIA - falla, "espera", dg.CONGELADO)
                else:
                    if venta == "senora":
                        kg_icopor += parte.kg
                    dg.avanzar(parte, dias_espera * HORAS_DIA, "espera", dg.ICOPOR_HIELO)
                _ir_a_la_plaza(parte, desembarque, tiempos)
                filas.append(_fila(parte, pesc, desembarque, venta, d, donde))
        inventario.append(
            {"dia": d + 1, "kg_congelado": kg_congelado, "kg_icopor": kg_icopor, "capacidad_kg": capacidad, "corte_h": cortes[d]}
        )

    lotes = pd.DataFrame(filas)
    return Corrida(esc, pob, lotes, pd.DataFrame(inventario), ciclos, _kg_mes(pob), capacidad, tiempos)


def _centros_de_venta(pob: pd.DataFrame, desembarque_senora: str) -> dict[str, str]:
    """Lugares donde hoy se puede entregar pescado -> sitio que lo maneja."""
    centros = {**{v: k for k, v in poblacion.DESEMBARQUE_FIJO.items()}, desembarque_senora: "senora"}
    centros.update({d: "vichada" for d in config.parametro("poblacion.desembarque_vichada").values()})
    return centros


def _llevar_al_desembarque(pesc: pd.Series, centros: dict[str, str], tiempos: Tiempos) -> tuple[dg.Lote, str | None, str]:
    """Faena y viaje por rio. Devuelve el lote, el sitio donde se vende y el desembarque.

    Si el bote no puede remontar hasta su desembarque habitual, va al centro mas cercano (en
    horas) que si alcanza. Si no alcanza ninguno, el lote no llega (sitio None).
    """
    lote = dg.Lote(kg=pesc["kg_por_faena"], hielo_restante_h=pesc["horas_hielo"])
    dg.avanzar(lote, config.parametro("degradacion.horas_faena"), "faena", dg.ICOPOR_HIELO)
    viaje = tiempos.rio(pesc["ubicacion"], pesc["desembarque"], pesc["embarcacion"])
    desembarque, venta = pesc["desembarque"], pesc["sitio"]
    if not viaje.alcanzable:
        opciones = [(tiempos.rio(pesc["ubicacion"], c, pesc["embarcacion"]), c) for c in centros if c != desembarque]
        opciones = [(v, c) for v, c in opciones if v.alcanzable]
        if not opciones:
            lote.no_llego = True
            return lote, None, desembarque
        viaje, desembarque = min(opciones, key=lambda x: x[0].costo)
        venta = centros[desembarque]
    dg.avanzar(lote, viaje.costo, "rio", dg.ICOPOR_HIELO)
    return lote, venta, desembarque


def _almacenar(lote: dg.Lote, sitio: str, libre_kg: float) -> list[tuple[dg.Lote, str]]:
    """Donde la señora llena el congelador (FIFO) y desborda a icopor; en los demas sitios, icopor."""
    hielo = config.parametro("cadena_actual.horas_hielo_desborde")
    partes = []
    if sitio == "senora" and libre_kg > 0:
        dentro = copy.deepcopy(lote)
        dentro.kg = min(lote.kg, libre_kg)
        dg.congelar(dentro)
        partes.append((dentro, "congelador"))
        lote.kg -= dentro.kg
    if lote.kg > 1e-9:
        dg.poner_hielo(lote, hielo)
        partes.append((lote, "icopor"))
    return partes


def _ir_a_la_plaza(lote: dg.Lote, desembarque: str, tiempos: Tiempos) -> None:
    viaje = tiempos.carretera(desembarque)
    if config.parametro("cadena_actual.comprador_trae_hielo"):
        dg.poner_hielo(lote, config.parametro("degradacion.horas_hielo_nevera_nueva"))
        dg.avanzar(lote, viaje.costo, "carretera", dg.ICOPOR_HIELO)
    else:
        dg.avanzar(lote, viaje.costo, "carretera", dg.AMBIENTE)


def _fila(lote: dg.Lote, pesc: pd.Series, desembarque: str, venta: str | None, dia: int, almacen: str) -> dict:
    return {
        "pescador": pesc["id"],
        "sitio": pesc["sitio"],  # sitio habitual: define el peso del lote en el volumen del mes
        "sitio_venta": venta,
        "zona": pesc["zona"],
        "desembarque": desembarque,
        "desviado": desembarque != pesc["desembarque"],
        "embarcacion": pesc["embarcacion"],
        "dia": dia + 1,
        "almacen": almacen,
        "no_llego": lote.no_llego,
        **dg.valor_lote(lote),
    }


# ---------------------------------------------------------------- indicadores


def _ponderar(corrida: Corrida) -> pd.DataFrame:
    """Lotes con el peso que lleva cada sitio a su volumen de un mes tipico."""
    lotes = corrida.lotes.copy()
    kg_sim = lotes.groupby("sitio")["kg"].sum()
    lotes["peso"] = lotes["sitio"].map(lambda s: corrida.kg_mes[s] / kg_sim[s] if kg_sim.get(s, 0) > 0 else 0.0)
    return lotes


def resumir_corrida(corrida: Corrida) -> tuple[dict, pd.DataFrame]:
    """Indicadores de la corrida (mes tipico) y resumen por zona."""
    L = _ponderar(corrida)
    w = L["peso"]
    kg = (w * L["kg"]).sum()
    cop = {c: (w * L[c]).sum() for c in ["cop_posible", "cop_recibido", "cop_perdido", *[f"cop_{e}" for e in dg.ETAPAS_COP]]}
    senora = L[L["sitio_venta"] == "senora"]
    rio = cop["cop_rio"]
    espera = cop["cop_espera"] + cop[f"cop_{dg.CONGELACION_LENTA}"]
    llegaron = L[~L["no_llego"]]
    ind = {
        "kg_mes": kg,
        "calidad_media": (w * L["kg"] * L["calidad"]).sum() / kg,
        "pct_valor_perdido": 100 * cop["cop_perdido"] / cop["cop_posible"],
        "cop_perdidos_mes": cop["cop_perdido"],
        "kg_rechazados_mes": (w * L["kg"] * (L["factor_precio"] == 0)).sum(),
        "pct_desborde_senora": 100 * senora.loc[senora["almacen"] == "icopor", "kg"].sum() / senora["kg"].sum() if len(senora) else 0.0,
        "pct_no_remontan": 100 * (w * L["kg"] * L["no_llego"]).sum() / kg,
        "pct_desviados": 100 * (w * L["kg"] * L["desviado"]).sum() / kg,
        "horas_rio_media": (llegaron["peso"] * llegaron["kg"] * llegaron["horas_rio"]).sum() / (llegaron["peso"] * llegaron["kg"]).sum(),
        "razon_espera_rio": espera / rio if rio > 0 else np.inf,
        "espera_mayor_que_rio": bool(espera > rio),
        "ciclo_dias": corrida.ciclos["senora"],
        "precio_base": cop["cop_posible"] / kg,
        **{f"cop_kg_{e}": cop[f"cop_{e}"] / kg for e in dg.ETAPAS_COP},
        "cop_kg_recibido": cop["cop_recibido"] / kg,
    }
    zonas = (
        L.assign(kg_w=w * L["kg"], q_w=w * L["kg"] * L["calidad"], posible_w=w * L["cop_posible"], perdido_w=w * L["cop_perdido"])
        .groupby("zona")[["kg_w", "q_w", "posible_w", "perdido_w"]]
        .sum()
    )
    por_zona = pd.DataFrame(
        {
            "kg_mes": zonas["kg_w"],
            "calidad_media": zonas["q_w"] / zonas["kg_w"],
            "pct_valor_perdido": 100 * zonas["perdido_w"] / zonas["posible_w"],
        }
    ).reset_index()
    return ind, por_zona


def por_pescador(corrida: Corrida) -> pd.DataFrame:
    """Una fila por pescador: km por rio y carretera, horas, % contra corriente, calidad, precio y perdida por etapa."""
    L = corrida.lotes
    filas = []
    for pesc in corrida.poblacion.itertuples():
        mios = L[L["pescador"] == pesc.id]
        fila = {"pescador": pesc.id, "sitio": pesc.sitio, "zona": pesc.zona, "desembarque": pesc.desembarque,
                "embarcacion": pesc.embarcacion, "nevera_buena": pesc.nevera_buena, "faenas": int(mios["dia"].nunique())}
        destino = mios["desembarque"].mode().iloc[0] if len(mios) else pesc.desembarque
        fila["vende_en"] = destino
        viaje = corrida.tiempos.rio(pesc.ubicacion, destino, pesc.embarcacion)
        if viaje.alcanzable:
            rio = transporte.resumen_ruta(corrida.tiempos.grafo, viaje.ruta, corrida.tiempos.perfil(pesc.embarcacion))
            via = transporte.resumen_ruta(corrida.tiempos.grafo, corrida.tiempos.carretera(destino).ruta,
                                          corrida.tiempos.perfil(pesc.embarcacion))
            fila.update(km_rio=rio["km"], km_carretera=via["km_via"], pct_contra_corriente=rio["pct_contra_corriente"])
        if len(mios):
            kg = mios["kg"].sum()
            fila.update(
                kg=kg,
                horas_totales=(mios[[f"horas_{e}" for e in dg.ETAPAS]].sum(axis=1) * mios["kg"]).sum() / kg,
                calidad=(mios["calidad"] * mios["kg"]).sum() / kg,
                precio_cop_kg=mios["cop_recibido"].sum() / kg,
                cop_perdidos=mios["cop_perdido"].sum(),
                **{f"cop_{e}": mios[f"cop_{e}"].sum() for e in dg.ETAPAS_COP},
            )
        filas.append(fila)
    return pd.DataFrame(filas)


def flujos(corrida: Corrida) -> dict[tuple[str, str], float]:
    """kg por arista de los recorridos de hoy (rio de cada pescador y carretera del comprador)."""
    llegaron = corrida.lotes[~corrida.lotes["no_llego"]]
    kg_viaje = llegaron.groupby(["pescador", "desembarque"])["kg"].sum()
    kg_desemb = llegaron.groupby("desembarque")["kg"].sum()
    pob = corrida.poblacion.set_index("id")
    salida: dict[tuple[str, str], float] = {}

    def sumar(ruta, kg):
        for u, v in zip(ruta, ruta[1:]):
            salida[(u, v)] = salida.get((u, v), 0.0) + kg

    for (pescador, desembarque), kg in kg_viaje.items():
        pesc = pob.loc[pescador]
        sumar(corrida.tiempos.rio(pesc["ubicacion"], desembarque, pesc["embarcacion"]).ruta, kg)
    for desembarque, kg in kg_desemb.items():
        sumar(corrida.tiempos.carretera(desembarque).ruta, kg)
    return salida


# ---------------------------------------------------------------- Monte Carlo y sensibilidad


def corrida_ejemplo(escenario: Escenario) -> Corrida:
    """Una corrida con los valores base y la semilla fija (la que se muestra en la pantalla)."""
    return simular_corrida(np.random.default_rng(config.parametro("general.semilla")), escenario)


def correr_montecarlo(escenario: Escenario, n: int | None = None, semilla: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """n corridas con parametros muestreados. Devuelve (indicadores por corrida, zonas por corrida)."""
    n = n if n is not None else config.parametro("montecarlo.corridas_r2")
    semilla = semilla if semilla is not None else config.parametro("general.semilla")

    def corrida(i: int, rng: np.random.Generator):
        ind, zon = resumir_corrida(simular_corrida(rng, escenario))
        return {"corrida": i, **ind}, zon.assign(corrida=i)

    resultados = montecarlo.correr(corrida, n, semilla)
    return pd.DataFrame([r[0] for r in resultados]), pd.concat([r[1] for r in resultados], ignore_index=True)


INDICADORES = (
    "calidad_media", "pct_valor_perdido", "cop_perdidos_mes", "kg_rechazados_mes", "pct_desborde_senora",
    "pct_no_remontan", "pct_desviados", "horas_rio_media", "razon_espera_rio", "kg_mes", "precio_base",
    *[f"cop_kg_{e}" for e in dg.ETAPAS_COP], "cop_kg_recibido",
)


def resumen(corridas: pd.DataFrame) -> pd.DataFrame:
    """Media e intervalo del 90 % de cada indicador."""
    filas = {c: montecarlo.resumir(corridas[c].replace(np.inf, np.nan).dropna()) for c in INDICADORES}
    tabla = pd.DataFrame(filas).T
    tabla.loc["espera_mayor_que_rio"] = [100 * corridas["espera_mayor_que_rio"].mean(), np.nan, np.nan]
    return tabla


def sensibilidad(corridas: pd.DataFrame, temporada: str) -> pd.DataFrame:
    """Indicadores clave por candidata del desembarque de la señora (mismas muestras de Monte Carlo)."""
    filas = []
    for candidata, sub in corridas[corridas["temporada"] == temporada].groupby("candidata"):
        r = resumen(sub)
        filas.append(
            {
                "candidata": candidata,
                **{f"{c}_{k}": r.at[c, k] for c in ("calidad_media", "pct_valor_perdido", "horas_rio_media", "razon_espera_rio") for k in ("media", "p5", "p95")},
                "pct_corridas_espera_mayor": r.at["espera_mayor_que_rio", "media"],
            }
        )
    return pd.DataFrame(filas)


def veredicto_sensibilidad(tabla: pd.DataFrame) -> tuple[bool, str]:
    """¿Cambia la conclusion (la espera pesa mas que el rio) segun donde este la señora?"""
    mayoria = tabla["pct_corridas_espera_mayor"] >= 50
    rango = tabla["pct_valor_perdido_media"].max() - tabla["pct_valor_perdido_media"].min()
    if mayoria.all() or not mayoria.any():
        sentido = "pesa más" if mayoria.all() else "pesa menos"
        return False, (
            f"La ubicación **no cambia** la conclusión: en las {len(tabla)} candidatas la espera {sentido} que el río. "
            f"El valor perdido varía {rango:.1f} puntos entre candidatas."
        )
    return True, (
        f"La ubicación **sí cambia** la conclusión: en {int(mayoria.sum())} de {len(tabla)} candidatas la espera pesa más "
        f"que el río. El valor perdido varía {rango:.1f} puntos entre candidatas."
    )


def precalcular(n: int | None = None) -> None:
    """Monte Carlo para cada candidata y temporada → datos/precalculado/r2_*."""
    base = Escenario.base()
    corridas, zonas = [], []
    for temporada in sorted(config.TEMPORADAS):
        for candidata in config.parametro("cadena_actual.candidatas_desembarque_senora"):
            esc = base.con(temporada=temporada, desembarque_senora=candidata)
            ind, zon = correr_montecarlo(esc, n)
            etiqueta = {"candidata": candidata, "temporada": temporada}
            corridas.append(ind.assign(**etiqueta))
            zonas.append(zon.assign(**etiqueta))
            print(f"  r2 {temporada} {candidata}: {len(ind)} corridas")
    config.DIR_PRECALCULADO.mkdir(parents=True, exist_ok=True)
    tabla = pd.concat(corridas, ignore_index=True)
    tabla.to_csv(config.DIR_PRECALCULADO / ARCHIVO_CORRIDAS, index=False, float_format="%.6g")
    z = pd.concat(zonas, ignore_index=True)
    resumen_zonas = (
        z.groupby(["temporada", "candidata", "zona"])
        .agg(
            kg_mes=("kg_mes", "mean"),
            calidad_media=("calidad_media", "mean"),
            pct_valor_perdido=("pct_valor_perdido", "mean"),
            pct_valor_perdido_p5=("pct_valor_perdido", lambda s: np.percentile(s, montecarlo.PERCENTIL_BAJO)),
            pct_valor_perdido_p95=("pct_valor_perdido", lambda s: np.percentile(s, montecarlo.PERCENTIL_ALTO)),
        )
        .reset_index()
    )
    resumen_zonas.to_csv(config.DIR_PRECALCULADO / ARCHIVO_ZONAS, index=False, float_format="%.6g")
    meta = {"corridas": int(tabla.groupby(["temporada", "candidata"]).size().iloc[0]), "semilla": config.parametro("general.semilla")}
    (config.DIR_PRECALCULADO / ARCHIVO_META).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def cargar_precalculado() -> dict | None:
    """Resultados de precalcular(), o None si no existen todavia."""
    archivos = [config.DIR_PRECALCULADO / a for a in (ARCHIVO_CORRIDAS, ARCHIVO_ZONAS, ARCHIVO_META)]
    if not all(a.is_file() for a in archivos):
        return None
    return {
        "corridas": pd.read_csv(archivos[0]),
        "zonas": pd.read_csv(archivos[1]),
        "meta": json.loads(archivos[2].read_text(encoding="utf-8")),
    }


TEXTO_ETAPA = {
    "faena": "faena",
    "rio": "río",
    "espera": "espera",
    "congelacion_lenta": "congelación lenta",
    "carretera": "carretera",
}


def pasos_cascada(tabla: pd.DataFrame) -> list[dict]:
    """Pasos de la cascada COP/kg a partir de resumen(): valor posible → perdidas por etapa → valor recibido."""
    def paso(etapa, fila, tipo):
        return {"etapa": etapa, "valor": tabla.at[fila, "media"], "p5": tabla.at[fila, "p5"], "p95": tabla.at[fila, "p95"], "tipo": tipo}

    orden = ("faena", "rio", "espera", "congelacion_lenta", "carretera")
    return [
        paso("valor posible", "precio_base", "total"),
        *[paso(f"− {TEXTO_ETAPA[e]}", f"cop_kg_{e}", "perdida") for e in orden],
        paso("valor recibido", "cop_kg_recibido", "total"),
    ]
