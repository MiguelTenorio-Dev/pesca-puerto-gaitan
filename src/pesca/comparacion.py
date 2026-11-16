"""Hoy vs propuesta, cartilla de rutas y resumen de resultados (R6).

Hoy y la propuesta se comparan con la misma base que R3–R5 (valores esperados del recomendador):
- hoy: cada pescador en su desembarque habitual (asignacion.asignacion_hoy);
- propuesta: reparto optimo de la flota con el portafolio elegido (propuesta.portafolio en el yaml).
El diagnostico de R2 es otra cosa: la simulacion dia a dia del ciclo del comprador.
"""

from __future__ import annotations

import io
import json
import textwrap

import numpy as np
import pandas as pd

from pesca import asignacion, busqueda, cadena_actual, config, degradacion as dg, frio_bimodal, red, transporte, ubicacion
from pesca.escenario import Escenario

TEMPORADAS = ("aguas_bajas", "aguas_altas")
TEXTO_TEMPORADA = {"aguas_bajas": "Aguas bajas (verano)", "aguas_altas": "Aguas altas (invierno)"}
TEXTO_BOTE = {"madera_remo": "Madera a remo", "madera_motor": "Madera con motor",
              "aluminio_remo": "Aluminio a remo", "aluminio_motor": "Aluminio con motor"}
LADOS = ("hoy", "propuesta")
TEXTO_ALGORITMO = {"dijkstra": "Dijkstra", "a_estrella": "A*", "bfs": "BFS"}
EMBARCACION_ALGORITMOS = "madera_motor"  # la del laboratorio de algoritmos de la app
# Sitio de cada desembarque o acopio para colorear el mapa (visualizacion.COLOR_SITIO)
SITIO_MAPA = {"D_MALECON": "malecon", "A02": "san_miguel", "A03": "vichada"}

ARCHIVO_PESCADORES = "r6_pescadores.csv"
ARCHIVO_CARTILLA = "r6_cartilla.csv"
ARCHIVO_FLUJOS = "r6_flujos.json"
ARCHIVO_PDF = "cartilla_rutas.pdf"
ARCHIVO_RESUMEN = "resumen_resultados.md"


def portafolio_propuesta() -> frozenset[str]:
    return frozenset(config.parametro("propuesta.portafolio"))


def escenario_propuesta(base: Escenario) -> Escenario:
    return frio_bimodal.escenario_con(base, portafolio_propuesta())


# ---------------------------------------------------------------- hoy vs propuesta


def _por_pescador_un_lado(filas: pd.DataFrame, p0: float, nombres: dict[str, str]) -> pd.DataFrame:
    """Agrega por pescador (un pescador puede repartir su pescado entre destinos): sumas y promedios por kg."""
    f = filas.copy()
    f["cop_dia"] = f["kg_dia"] * f["cop_kg"]
    f["viaje_dia"] = f["kg_dia"] * f["viaje_kg"]
    f["kg_perdidos_dia"] = f["kg_dia"] * (f["cop_kg"] <= 0)
    vendidos = f["cop_kg"] > 0
    salida = []
    for pescador, sub in f.groupby("pescador", sort=False):
        kg = sub["kg_dia"].sum()
        ok = sub[vendidos.loc[sub.index]]
        w = ok["kg_dia"] / ok["kg_dia"].sum() if len(ok) else None
        principal = sub.loc[sub["kg_dia"].idxmax(), "destino"]
        salida.append({
            "pescador": pescador,
            "vende_en": nombres.get(principal, principal),
            "kg_dia": kg,
            "cop_dia": sub["cop_dia"].sum(),
            "viaje_dia": sub["viaje_dia"].sum(),
            "neto_dia": sub["cop_dia"].sum() - sub["viaje_dia"].sum(),
            "pct_valor_perdido": 100 * (1 - sub["cop_dia"].sum() / (p0 * kg)),
            "kg_perdidos_dia": sub["kg_perdidos_dia"].sum(),
            "calidad": float((w * ok["calidad"]).sum()) if w is not None else 0.0,
            "horas": float((w * ok["horas_hasta_venta"]).sum()) if w is not None else np.nan,
            "km_rio": float((w * ok["km_rio"]).sum()) if w is not None else 0.0,
            "km_via": float((w * ok["km_via"]).sum()) if w is not None else 0.0,
        })
    return pd.DataFrame(salida)


def _nombres_destinos(base: Escenario) -> dict[str, str]:
    g = red.construir_red()
    nombres = {n: a["nombre"] for n, a in g.nodes(data=True) if a["capa"] == red.CAPA_RIO}
    lugares = {a["lugar"]: a["nombre"] for _, a in g.nodes(data=True)}
    nombres.update(lugares)
    nombres[asignacion.PLAZA_RIO] = g.nodes[asignacion.PLAZA]["nombre"]
    nombres[asignacion.SIN_DESTINO] = "Sin destino (se pierde)"
    return nombres


def comparar(base: Escenario, pob: pd.DataFrame | None = None) -> dict:
    """Hoy vs propuesta para una poblacion: tabla por pescador, flujos para el mapa y desembarques a marcar."""
    pob = pob if pob is not None else cadena_actual.corrida_ejemplo(base).poblacion
    p0 = dg.precio_base()
    hoy = asignacion.asignacion_hoy(base, pob)
    prop = asignacion.problema_transporte(escenario_propuesta(base), pob, con_hoy=False)["flujos"]
    prop = prop.assign(viaje_kg=prop["costo_kg"] - p0 + prop["cop_kg"])
    # Los destinos del reparto vienen como "tipo:lugar[:parte]"; se deja solo el lugar
    prop["destino"] = prop["destino"].map(lambda d: d.split(":")[1] if ":" in d else d)
    nombres = _nombres_destinos(base)
    lados = {"hoy": _por_pescador_un_lado(hoy, p0, nombres), "propuesta": _por_pescador_un_lado(prop, p0, nombres)}
    # El reparto va en decimas de kg (min_cost_flow): los kg del pescador se toman de hoy
    tabla = lados["hoy"].merge(lados["propuesta"].drop(columns="kg_dia"), on="pescador", suffixes=("_hoy", "_propuesta"))
    tabla = pob[["id", "sitio", "zona", "embarcacion"]].rename(columns={"id": "pescador"}).merge(tabla, on="pescador")
    tabla.insert(0, "temporada", base.temporada)
    nuevo = frio_bimodal.acopio_nuevo_r4()
    marcar = {"hoy": {lugar: SITIO_MAPA.get(lugar, "senora") for lugar in hoy["destino"].unique() if lugar != asignacion.SIN_DESTINO},
              "propuesta": {lugar: SITIO_MAPA.get(lugar, "acopio" if lugar == nuevo else "senora")
                            for lugar in prop["destino"].unique() if lugar != asignacion.SIN_DESTINO}}
    return {"tabla": tabla, "flujos": {"hoy": asignacion.flujos_por_arista(hoy), "propuesta": asignacion.flujos_por_arista(prop)},
            "marcar": marcar}


def descomponer_mejora(costo_hoy: float, costo_optimo_hoy: float, valor_salvado_inversion: float) -> dict[str, float]:
    """Mejora por dia = seguir el recomendador con los acopios de hoy (R3) + lo que agrega la inversion (R5).

    costo = valor perdido + viaje; la propuesta cuesta costo_optimo_hoy - valor_salvado_inversion.
    """
    recomendador = costo_hoy - costo_optimo_hoy
    return {"recomendador": recomendador, "inversion": valor_salvado_inversion, "total": recomendador + valor_salvado_inversion}


def partes_de_la_mejora(mejora_neta_dia: float, valor_salvado_inversion: float) -> dict[str, float]:
    """Separa la mejora de la flota en lo que da seguir el recomendador y lo que agrega la inversion."""
    return {"recomendador": mejora_neta_dia - valor_salvado_inversion, "inversion": valor_salvado_inversion,
            "total": mejora_neta_dia}


def totales(tabla: pd.DataFrame) -> pd.DataFrame:
    """Indicadores de toda la flota antes y despues: sumas por dia y promedios ponderados por kg vendidos."""
    p0 = dg.precio_base()
    filas = {}
    for lado in LADOS:
        kg = tabla["kg_dia"].sum()
        vendidos = tabla["kg_dia"] - tabla[f"kg_perdidos_dia_{lado}"]
        w = vendidos / vendidos.sum()
        filas[lado] = {
            "kg_dia": kg,
            "cop_dia": tabla[f"cop_dia_{lado}"].sum(),
            "neto_dia": tabla[f"neto_dia_{lado}"].sum(),
            "pct_valor_perdido": 100 * (1 - tabla[f"cop_dia_{lado}"].sum() / (p0 * kg)),
            "kg_perdidos_dia": tabla[f"kg_perdidos_dia_{lado}"].sum(),
            "calidad": float((w * tabla[f"calidad_{lado}"]).sum()),
            "horas": float((w * tabla[f"horas_{lado}"].fillna(0)).sum()),
            "km_rio": float((w * tabla[f"km_rio_{lado}"]).sum()),
        }
    t = pd.DataFrame(filas)
    t["diferencia"] = t["propuesta"] - t["hoy"]
    return t


# ---------------------------------------------------------------- cartilla


def _como_llegar(o: asignacion.Opcion) -> str:
    contra = o.km_rio * o.pct_contra_corriente / 100
    if contra < 0.05:
        sentido = "río abajo (a favor de la corriente)"
    elif o.km_rio - contra < 0.05:
        sentido = "río arriba (contra la corriente)"
    else:
        sentido = f"{o.km_rio - contra:.0f} km a favor y {contra:.0f} km contra la corriente"
    horas_rio = o.tramos.loc[o.tramos["modo"] == red.CAPA_RIO, "horas"].sum()
    texto = f"Por el río {o.km_rio:.0f} km, {sentido}, ≈ {asignacion.numero(horas_rio)} h"
    if o.tipo == "plaza":
        return texto + ". Vende ese mismo día en la plaza."
    if o.tipo == "acopio":
        vehiculo = "camión refrigerado" if o.vehiculo == "camion_refrigerado" else "carro"
        return texto + f". Déjalo en el cuarto frío; sigue en {vehiculo} a la plaza ({o.km_via:.0f} km)."
    return texto + f". Espera ≈ {o.horas_espera / 24:.0f} días al comprador."


def cartilla(base: Escenario | None = None) -> pd.DataFrame:
    """Una fila por zona × embarcacion × temporada: a donde llevar el pescado con la propuesta y como."""
    base = base if base is not None else Escenario.base()
    kg = config.parametro("poblacion.kg_por_faena")
    nevera = config.parametro("propuesta.nevera_cartilla")
    nodos = config.cargar_nodos()
    zonas = nodos[nodos["tipo"].isin(["zona_pesca", "comunidad"])]
    filas = []
    for temporada in TEMPORADAS:
        esc = escenario_propuesta(base.con(temporada=temporada))
        for z in zonas.itertuples():
            for bote in TEXTO_BOTE:
                rec = asignacion.recomendar(red.clave(z.id, red.CAPA_RIO), bote, kg, esc, nevera)
                m = rec.mejor
                fila = {"zona": z.id, "lugar": z.nombre, "temporada": TEXTO_TEMPORADA[temporada], "bote": TEXTO_BOTE[bote]}
                if m is None:
                    fila.update(lleva_a="No hay ruta posible con este bote", como="", horas=np.nan, te_quedan_cop=np.nan,
                                calidad=np.nan, aviso="Busca quién te lleve con motor")
                else:
                    aviso = []
                    if m.pct_contra_corriente > 0:
                        aviso.append(f"{m.km_rio * m.pct_contra_corriente / 100:.0f} km contra la corriente")
                    if m.tipo == "acopio":
                        aviso.append("transbordo en el acopio")
                    if m.cop_total <= 0:
                        aviso.append("llega dañado: lleva hielo")
                    fila.update(lleva_a=m.nombre, como=_como_llegar(m), horas=m.horas_viaje, te_quedan_cop=m.cop_neto,
                                calidad=m.calidad, aviso="; ".join(aviso))
                filas.append(fila)
    return pd.DataFrame(filas)


def cartilla_pdf(tabla: pd.DataFrame) -> bytes:
    """PDF para imprimir: una pagina por zona con letra grande."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    kg = config.parametro("poblacion.kg_por_faena")
    columnas = ["Temporada", "Bote", "Lleva tu pescado a", "Cómo llegar", "≈ horas", f"Te quedan\n({kg:.0f} kg)", "Ojo"]
    anchos = [0.11, 0.10, 0.16, 0.32, 0.07, 0.10, 0.14]
    envolver = [14, 14, 22, 48, 6, 12, 18]
    salida = io.BytesIO()
    with PdfPages(salida) as pdf:
        for zona, sub in tabla.groupby("zona", sort=False):
            fig = plt.figure(figsize=(11.69, 8.27))  # A4 horizontal
            fig.text(0.04, 0.95, f"Cartilla de rutas: {sub['lugar'].iloc[0]}", fontsize=20, weight="bold")
            fig.text(0.04, 0.915, "¿A dónde llevo mi pescado? Con San Miguel y el acopio nuevo funcionando.", fontsize=12)
            celdas = []
            for f in sub.itertuples():
                valores = [f.temporada, f.bote, f.lleva_a, f.como,
                           "" if pd.isna(f.horas) else asignacion.numero(f.horas),
                           "" if pd.isna(f.te_quedan_cop) else asignacion.pesos(f.te_quedan_cop), f.aviso]
                celdas.append(["\n".join(textwrap.wrap(str(v), n)) or "" for v, n in zip(valores, envolver)])
            ax = fig.add_axes([0.03, 0.08, 0.94, 0.8])
            ax.axis("off")
            t = ax.table(cellText=celdas, colLabels=columnas, colWidths=anchos, loc="upper center", cellLoc="left")
            t.auto_set_font_size(False)
            t.set_fontsize(9)
            for (fila, _), celda in t.get_celld().items():
                celda.set_height(0.105 if fila > 0 else 0.06)
                if fila == 0:
                    celda.set_text_props(weight="bold")
                    celda.set_facecolor("#e8eef8")
            fig.text(0.04, 0.03, "Valores SIMULADOS (proyecto universitario). Rutas aproximadas: pregunta en el acopio antes de salir.",
                     fontsize=9, style="italic")
            pdf.savefig(fig)
            plt.close(fig)
    return salida.getvalue()


# ---------------------------------------------------------------- precalculo


def precalcular() -> None:
    """Hoy vs propuesta (dos temporadas) y la cartilla → datos/precalculado/r6_*."""
    config.DIR_PRECALCULADO.mkdir(parents=True, exist_ok=True)
    tablas, flujos = [], {}
    for temporada in TEMPORADAS:
        r = comparar(Escenario.base().con(temporada=temporada))
        tablas.append(r["tabla"])
        flujos[temporada] = {lado: {"|".join(k): v for k, v in r["flujos"][lado].items()} for lado in LADOS}
        flujos[temporada]["marcar"] = r["marcar"]
    pd.concat(tablas).to_csv(config.DIR_PRECALCULADO / ARCHIVO_PESCADORES, index=False, float_format="%.6g")
    (config.DIR_PRECALCULADO / ARCHIVO_FLUJOS).write_text(json.dumps(flujos, ensure_ascii=False), encoding="utf-8")
    cart = cartilla()
    cart.to_csv(config.DIR_PRECALCULADO / ARCHIVO_CARTILLA, index=False, float_format="%.6g")
    (config.DIR_PRECALCULADO / ARCHIVO_PDF).write_bytes(cartilla_pdf(cart))
    print(f"  r6: {len(tablas[0])} pescadores × {len(TEMPORADAS)} temporadas; cartilla de {len(cart)} filas")


def cargar_precalculado() -> dict | None:
    archivos = [config.DIR_PRECALCULADO / a for a in (ARCHIVO_PESCADORES, ARCHIVO_CARTILLA, ARCHIVO_FLUJOS, ARCHIVO_PDF)]
    if not all(a.is_file() for a in archivos):
        return None
    crudo = json.loads(archivos[2].read_text(encoding="utf-8"))
    flujos = {t: {**{lado: {tuple(k.split("|")): v for k, v in d[lado].items()} for lado in LADOS}, "marcar": d["marcar"]}
              for t, d in crudo.items()}
    return {"pescadores": pd.read_csv(archivos[0]), "cartilla": pd.read_csv(archivos[1]), "flujos": flujos,
            "cartilla_pdf": archivos[3].read_bytes()}


# ---------------------------------------------------------------- resumen de resultados


def _m(cop: float) -> str:
    return f"{cop / 1e6:,.1f} M".replace(",", "X").replace(".", ",").replace("X", ".")


def _n(x: float, d: int = 1) -> str:
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _ic(r: dict, f=_n) -> str:
    return f"{f(r['media'])} (90 %: {f(r['p5'])} a {f(r['p95'])})"


def texto_resumen() -> str:
    """Cifras clave de R1–R6, solo de lo precalculado (mas el reparto de R3, que es liviano)."""
    p = config.parametro
    lineas = ["# Resumen de resultados", "",
              "Generado por `python scripts/correr_todo.py`. El informe toma sus cifras solo de aquí. "
              "Etiquetas: **MEDIDO** (Google Earth/KML), **OFICIAL** (SEPEC, SIPSA), **SIMULADO** (supuestos del proyecto, §10). "
              "Las cifras con Monte Carlo se dan como media e intervalo del 90 %.", ""]

    # R1
    g = red.construir_red()
    cal = red.calibracion(g)
    lineas += ["## R1. Red y calibración [MEDIDO → CALIBRADO]", "", "| ruta | modo | km medidos | km del grafo | error |", "|---|---|---|---|---|"]
    lineas += [f"| {c.id} | {c.modo} | {_n(c.km_medido, 2)} | {_n(c.km_grafo, 2)} | {_n(c.error_pct, 3)} % |" for c in cal.itertuples()]
    s = g.graph["sinuosidad"]
    lineas += ["", f"Sinuosidad calibrada: río {_n(s['rio'], 2)}, carretera {_n(s['via'], 2)}. "
               f"Grafo: {g.number_of_nodes()} nodos, {g.number_of_edges()} aristas.", ""]
    perfil = transporte.Perfil.desde_escenario(Escenario.base(), EMBARCACION_ALGORITMOS)
    comp = busqueda.comparar(g, busqueda.pares_comparacion(), perfil)
    lineas += [f"Dijkstra vs A* vs BFS ({TEXTO_BOTE[EMBARCACION_ALGORITMOS].lower()}, aguas bajas, peso = pérdida de calidad):", "",
               "| ruta | algoritmo | nodos explorados | tramos | % peor que Dijkstra |", "|---|---|---|---|---|"]
    for c in comp.itertuples():
        lineas.append(f"| {c.par} | {TEXTO_ALGORITMO[c.algoritmo]} | {c.nodos_explorados} | {c.tramos} | {_n(max(c.pct_peor_que_dijkstra, 0.0), 1)} % |")
    total = comp.groupby("algoritmo")["nodos_explorados"].sum()
    peor = comp[comp["algoritmo"] == "bfs"]["pct_peor_que_dijkstra"]
    lineas += ["", f"Nodos explorados en total: Dijkstra {total['dijkstra']}, A* {total['a_estrella']} "
               f"({_n(100 * (1 - total['a_estrella'] / total['dijkstra']), 0)} % menos), BFS {total['bfs']}. "
               f"A* da siempre el mismo costo que Dijkstra; BFS (menos tramos) queda en promedio {_n(peor.mean(), 1)} % peor "
               f"(máximo {_n(peor.max(), 1)} %).", ""]

    # R2
    r2 = cadena_actual.cargar_precalculado()
    base = p("escenario_base.desembarque_senora")
    lineas += [f"## R2. Diagnóstico de hoy [SIMULADO, {r2['meta']['corridas']} corridas por candidata y temporada]", "",
               f"Candidata base del desembarque de la señora: {base}.", "",
               "| indicador | aguas bajas | aguas altas |", "|---|---|---|"]
    res = {t: cadena_actual.resumen(r2["corridas"][(r2["corridas"]["candidata"] == base) & (r2["corridas"]["temporada"] == t)])
           for t in TEMPORADAS}
    for ind, texto, f in [("calidad_media", "calidad media (0–1)", lambda x: _n(x, 2)),
                          ("pct_valor_perdido", "% del valor perdido", _n),
                          ("cop_perdidos_mes", "COP perdidos al mes", _m),
                          ("precio_base", "precio base (COP/kg)", lambda x: _n(x, 0)),
                          ("cop_kg_faena", "COP/kg perdidos en la faena", lambda x: _n(x, 0)),
                          ("cop_kg_rio", "COP/kg perdidos en el río", lambda x: _n(x, 0)),
                          ("cop_kg_espera", "COP/kg perdidos en la espera", lambda x: _n(x, 0)),
                          ("cop_kg_congelacion_lenta", "COP/kg perdidos por congelación lenta", lambda x: _n(x, 0)),
                          ("cop_kg_carretera", "COP/kg perdidos en la carretera", lambda x: _n(x, 0)),
                          ("cop_kg_recibido", "COP/kg que recibe el pescador", lambda x: _n(x, 0)),
                          ("razon_espera_rio", "espera / río (veces)", lambda x: _n(x, 0))]:
        lineas.append(f"| {texto} | " + " | ".join(_ic(res[t].loc[ind].to_dict(), f) for t in TEMPORADAS) + " |")
    lineas.append("| % corridas con espera > río | " + " | ".join(f"{_n(res[t].at['espera_mayor_que_rio', 'media'], 1)} %" for t in TEMPORADAS) + " |")
    for t in TEMPORADAS:
        lineas += ["", f"Sensibilidad a la ubicación de la señora, {TEXTO_TEMPORADA[t].lower()}: "
                   + cadena_actual.veredicto_sensibilidad(cadena_actual.sensibilidad(r2["corridas"], t))[1].replace("**", "")]
    lineas.append("")

    # R3
    pt = asignacion.problema_transporte(Escenario.base())
    lineas += ["## R3. Recomendador y reparto óptimo [SIMULADO, población de ejemplo, aguas bajas]", "",
               f"- Pérdida + viaje con lo que hacen hoy: {_m(pt['costo_hoy_dia'])} COP/día.",
               f"- Con el reparto óptimo (mismos acopios de hoy): {_m(pt['costo_optimo_dia'])} COP/día "
               f"({_n(100 * (1 - pt['costo_optimo_dia'] / pt['costo_hoy_dia']), 0)} % menos).",
               f"- kg sin destino posible: {_n(pt['kg_sin_destino'], 1)} de {_n(pt['kg_dia'], 0)} kg/día.", ""]

    # R4
    r4 = ubicacion.cargar_precalculado()
    umbral = 100 * p("economia.umbral_vpn_positivo")
    lineas += [f"## R4. Acopios [SIMULADO, {r4['meta']['corridas']} corridas]", "",
               f"Regla: vale la pena si VPN > 0 en al menos el {umbral:.0f} % de las corridas.", "",
               "| acopio | VPN a 5 años | % VPN > 0 | veredicto |", "|---|---|---|---|"]
    for f in ubicacion.resumen_viabilidad(r4["viabilidad"]).itertuples():
        lineas.append(f"| {f.nombre} | {_m(f.vpn_media)} (90 %: {_m(f.vpn_p5)} a {_m(f.vpn_p95)}) | {f.pct_vpn_positivo:.0f} % | "
                      f"{'vale la pena' if f.vale_la_pena else 'no vale la pena'} |")
    k1 = next(r for r in r4["pmediana"]["resultados"] if r["modo"] == "agregar" and r["k"] == 1)
    lineas += ["", f"p-mediana: con los 3 acopios de hoy, {_m(r4['pmediana']['costo_actuales_dia'])} COP/día; "
               f"agregando uno en {', '.join(a['lugar'] for a in k1['acopios'] if not a['actual'])}, {_m(k1['costo_dia'])} COP/día.", ""]

    # R5
    r5 = frio_bimodal.cargar_precalculado()
    tabla5 = r5["portafolios"].set_index("portafolio")
    mc5 = frio_bimodal.resumen_montecarlo(r5["montecarlo"]).set_index("portafolio")
    lineas += [f"## R5. Bimodal, frío e inversión [SIMULADO, {r5['meta']['corridas']} corridas]", "",
               "| presupuesto | recomendado | inversión | valor salvado al año | VPN a 5 años | % VPN > 0 |", "|---|---|---|---|---|---|"]
    for b, pf in r5["meta"]["recomendados"].items():
        fila, m = tabla5.loc[pf], mc5.loc[pf]
        lineas.append(f"| {_m(float(b))} | {' + '.join(frio_bimodal.describir(frio_bimodal.desde_clave(pf))) or 'nada'} | "
                      f"{_m(fila['inversion'])} | {_m(m['beneficio_anual_media'])} (90 %: {_m(m['beneficio_anual_p5'])} a {_m(m['beneficio_anual_p95'])}) | "
                      f"{_m(m['vpn_media'])} | {m['pct_vpn_positivo']:.0f} % |")
    lineas += ["", "Cada medida sola:", "", "| medida | inversión | valor salvado al año | VPN a 5 años | % VPN > 0 |", "|---|---|---|---|---|"]
    for pf in frio_bimodal.medidas_solas():
        c = frio_bimodal.clave(pf)
        m = mc5.loc[c]
        lineas.append(f"| {' + '.join(frio_bimodal.describir(pf))} | {_m(m['inversion_media'])} | {_m(m['beneficio_anual_media'])} | "
                      f"{_m(m['vpn_media'])} | {m['pct_vpn_positivo']:.0f} % |")
    lineas.append("")

    # R6
    r6 = cargar_precalculado()
    prop = frio_bimodal.clave(portafolio_propuesta())
    lineas += ["## R6. Hoy vs propuesta [SIMULADO, población de ejemplo]", "",
               f"Propuesta: {' + '.join(frio_bimodal.describir(portafolio_propuesta()))}, con los pescadores siguiendo el recomendador.", ""]
    for t in TEMPORADAS:
        tot = totales(r6["pescadores"][r6["pescadores"]["temporada"] == t])
        lineas += [f"**{TEXTO_TEMPORADA[t]}**", "", "| indicador | hoy | propuesta |", "|---|---|---|"]
        for ind, texto, f in [("cop_dia", "COP recibidos al día", asignacion.pesos),
                              ("neto_dia", "COP netos al día (menos el viaje)", asignacion.pesos),
                              ("pct_valor_perdido", "% del valor perdido", _n), ("kg_perdidos_dia", "kg perdidos al día", _n),
                              ("calidad", "calidad media (0–1)", lambda x: _n(x, 2)), ("horas", "horas hasta la venta", _n),
                              ("km_rio", "km por río", _n)]:
            lineas.append(f"| {texto} | {f(tot.at[ind, 'hoy'])} | {f(tot.at[ind, 'propuesta'])} |")
        lineas.append("")
    partes = descomponer_mejora(pt["costo_hoy_dia"], pt["costo_optimo_dia"], tabla5.at[prop, "valor_salvado_dia"])
    lineas += [f"En aguas bajas, la mejora de {asignacion.pesos(partes['total'])}/día se reparte así: "
               f"{asignacion.pesos(partes['recomendador'])}/día por solo seguir el recomendador (R3, sin invertir) y "
               f"{asignacion.pesos(partes['inversion'])}/día por la inversión (R5).", ""]
    if prop in mc5.index:
        m = mc5.loc[prop]
        lineas += [f"Valor salvado al año con la propuesta (Monte Carlo de R5): {_m(m['beneficio_anual_media'])} "
                   f"(90 %: {_m(m['beneficio_anual_p5'])} a {_m(m['beneficio_anual_p95'])}); VPN {_m(m['vpn_media'])}, "
                   f"positivo en el {m['pct_vpn_positivo']:.0f} % de las corridas (la regla de R4 pide {umbral:.0f} %).", ""]
    return "\n".join(lineas)


def escribir_resumen() -> None:
    destino = (config.DIR_REPO / "outputs") if config.DIR_REPO is not None else config.DIR_PRECALCULADO
    destino.mkdir(parents=True, exist_ok=True)
    (destino / ARCHIVO_RESUMEN).write_text(texto_resumen(), encoding="utf-8")
    print(f"  resumen: {destino / ARCHIVO_RESUMEN}")
