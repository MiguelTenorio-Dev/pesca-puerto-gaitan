import pandas as pd
import streamlit as st

from pesca import asignacion, config, frio_bimodal, visualizacion
from pesca.app import comun

comun.configurar_pagina("Bimodal y cadena de frío")
escenario = comun.barra_lateral()


@st.cache_data
def precalculado():
    return frio_bimodal.cargar_precalculado()


@st.cache_data
def comparar_zonas(escenario):
    return frio_bimodal.unimodal_vs_bimodal(escenario)


def activar(nuevo) -> None:
    st.session_state["escenario"] = nuevo
    st.rerun()


def millones(cop: float) -> str:
    return f"{asignacion.pesos(cop / 1e6)} M"


st.title("Bimodal y cadena de frío: ¿en qué conviene invertir?")
datos = precalculado()
if datos is None:
    st.error("Faltan los resultados. Córrelos con `python scripts/correr_todo.py --solo r5`.")
    st.stop()

tabla = datos["portafolios"]
resumen = frio_bimodal.resumen_montecarlo(datos["montecarlo"]).set_index("portafolio")
corridas = datos["meta"]["corridas"]
anios = config.parametro("economia.horizonte_anios")
st.markdown(
    "Cada medida se mide igual que en «Centros de acopio»: **cuánto se deja de perder** (pescado dañado + viaje de los "
    f"pescadores) en el mejor reparto de la flota, frente a hoy. El VPN es a {anios} años. "
    f"{comun.etiqueta('SIMULADO')}: todos los costos de las medidas y su efecto."
)

# ---------------------------------------------------------------- 1. rio vs bimodal
st.header("1. ¿Por río a la plaza o por acopio + camión refrigerado?")
st.markdown(
    "Para cada zona: la mejor venta **llevando el pescado por río hasta Puerto Gaitán** frente a la mejor **bimodal**: "
    "río hasta el acopio más conveniente (San Miguel rehabilitado; La Cristalina no tiene acceso por río), transbordo y camión refrigerado."
)
zonas = comparar_zonas(escenario)
emb = st.radio("Embarcación", ["madera_remo", "madera_motor"], horizontal=True, key="emb_bimodal",
               format_func=comun.TEXTO_EMBARCACION.get)
vista = zonas[zonas["embarcacion"] == emb]
st.dataframe(
    vista[["nombre", "destino_rio", "calidad_rio", "neto_rio", "destino_bimodal", "calidad_bimodal", "neto_bimodal", "gana"]],
    hide_index=True, width="stretch",
    column_config={
        "nombre": "zona",
        "destino_rio": "por río",
        "calidad_rio": st.column_config.NumberColumn("calidad (río)", format="%.2f"),
        "neto_rio": st.column_config.NumberColumn("plata neta (río)", format="$ %,.0f"),
        "destino_bimodal": "bimodal",
        "calidad_bimodal": st.column_config.NumberColumn("calidad (bimodal)", format="%.2f"),
        "neto_bimodal": st.column_config.NumberColumn("plata neta (bimodal)", format="$ %,.0f"),
        "gana": "conviene",
    },
)
gana = (vista["gana"] == "bimodal").sum()
st.caption(
    f"Con {comun.TEXTO_EMBARCACION[emb].lower()}, el bimodal conviene en **{gana} de {len(vista)}** zonas. "
    f"Plata neta = lo que le pagan por {config.parametro('poblacion.kg_por_faena'):.0f} kg menos gasolina y tiempo (ida y vuelta). "
    "«no se puede» = el bote no remonta la corriente o la zona está en otra cuenca."
)

# ---------------------------------------------------------------- 2. medidas solas
st.header("2. Cada medida por separado")
solas = [frio_bimodal.clave(pf) for pf in frio_bimodal.medidas_solas()]
por_medida = resumen.loc[[s for s in solas if s in resumen.index]].reset_index()
por_medida["medida"] = por_medida["portafolio"].map(lambda c: " + ".join(frio_bimodal.describir(frio_bimodal.desde_clave(c))))
st.altair_chart(visualizacion.grafico_medidas(por_medida), width="stretch")
st.dataframe(
    por_medida[["portafolio", "medida", "inversion_media", "beneficio_anual_media", "vpn_media", "pct_vpn_positivo"]],
    hide_index=True, width="stretch",
    column_config={
        "portafolio": "código",
        "inversion_media": st.column_config.NumberColumn("inversión", format="$ %,.0f"),
        "beneficio_anual_media": st.column_config.NumberColumn("valor salvado al año", format="$ %,.0f"),
        "vpn_media": st.column_config.NumberColumn(f"VPN a {anios} años", format="$ %,.0f"),
        "pct_vpn_positivo": st.column_config.NumberColumn("% corridas VPN > 0", format="%.0f %%"),
    },
)
st.caption(f"Media e intervalo del 90 % en {corridas} corridas de Monte Carlo (población, parámetros y temporada cambian).")

# ---------------------------------------------------------------- 3. combinadas
st.header("3. Medidas combinadas según el presupuesto")
presupuestos = config.parametro("inversiones.presupuestos_cop")
presupuesto = st.radio("Presupuesto de la alcaldía (inversión inicial)", presupuestos, horizontal=True,
                       index=len(presupuestos) - 1, key="presupuesto", format_func=millones)
elegido = datos["meta"]["recomendados"][str(int(presupuesto))]
fila = tabla.set_index("portafolio").loc[elegido]
portafolio = frio_bimodal.desde_clave(elegido)

with st.container(border=True):
    if not portafolio:
        st.markdown("#### Portafolio recomendado: **no invertir**")
        st.caption("Con este presupuesto ninguna combinación tiene VPN positivo.")
    else:
        st.markdown("#### Portafolio recomendado")
        st.markdown("\n".join(f"- {m}" for m in frio_bimodal.describir(portafolio)))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Inversión", millones(fila["inversion"]))
        c2.metric("Valor salvado al año", millones(fila["beneficio_anual"]))
        c3.metric(f"VPN a {anios} años", millones(fila["vpn"]))
        c4.metric("kg más vendidos al día", f"{fila['kg_salvados_dia']:.0f}")
        if elegido in resumen.index:
            r = resumen.loc[elegido]
            st.caption(
                f"Monte Carlo: VPN medio {millones(r['vpn_media'])} (90 %: {millones(r['vpn_p5'])} a {millones(r['vpn_p95'])}); "
                f"VPN > 0 en el {r['pct_vpn_positivo']:.0f} % de las corridas."
            )
        st.altair_chart(visualizacion.grafico_combinado(frio_bimodal.pasos_combinados(tabla, portafolio)), width="stretch")
        st.caption("Cada barra es lo que suma esa medida a las anteriores. Si una medida suma poco, es porque otra ya resolvió lo mismo.")
        if st.button("Usar este portafolio en el escenario", key="usar_portafolio"):
            activar(frio_bimodal.escenario_con(escenario, portafolio))

# ---------------------------------------------------------------- 4. Pareto
st.header("4. Todas las combinaciones: frontera de Pareto")
recomendados = list(datos["meta"]["recomendados"].values())
st.altair_chart(visualizacion.grafico_pareto(tabla, presupuestos, recomendados), width="stretch")
st.caption(
    f"Cada punto es una de las {len(tabla)} combinaciones de I1–I7. La **frontera** (azul) son las que no tienen otra más "
    "barata que salve lo mismo o más. Las líneas punteadas son los presupuestos; en naranja, la recomendada para cada uno "
    "(la de mayor VPN que cabe). Calculado con la población de ejemplo."
)
pareto = tabla[tabla["pareto"]].sort_values("inversion").assign(
    medidas=lambda d: d["portafolio"].map(lambda c: " + ".join(frio_bimodal.describir(frio_bimodal.desde_clave(c))) or "nada"))
columnas = ["portafolio", "medidas", "inversion", "operacion_anual", "beneficio_anual", "vpn", "kg_salvados_dia"]
st.dataframe(pareto[columnas], hide_index=True, width="stretch",
             column_config={c: st.column_config.NumberColumn(format="$ %,.0f")
                            for c in ("inversion", "operacion_anual", "beneficio_anual", "vpn")})
st.download_button("⬇ Descargar todas las combinaciones (CSV)", tabla.to_csv(index=False).encode("utf-8"),
                   file_name="portafolios_r5.csv", mime="text/csv")

with st.expander("¿Qué hace cada medida en el modelo?"):
    st.dataframe(pd.DataFrame([
        {"código": "I1", "medida": "Cajas térmicas", "efecto": "Todo pescador con nevera buena: el hielo dura 48 h en vez de 12 h"},
        {"código": "I2", "medida": "Fábrica de hielo", "efecto": "Hielo a bordo: el pescado va a 4 °C en el río (exige I1)"},
        {"código": "I3a / I3b", "medida": "Rehabilitar San Miguel / La Cristalina", "efecto": "Acopio con cuarto frío; sigue por carretera. La Cristalina no tiene acceso por río"},
        {"código": "I4", "medida": "Acopio nuevo", "efecto": frio_bimodal.texto_acopio_nuevo()},
        {"código": "I5:N", "medida": "Camión refrigerado con ruta", "efecto": "Lleva lo de los acopios a 4 °C y recoge en los desembarques cada N días: la espera baja de ~6 días a (N+1)/2"},
        {"código": "I6", "medida": "Subsidio de motor", "efecto": "La mitad del motor para parte de los botes a remo; el pescador paga la gasolina"},
        {"código": "I7", "medida": "Mejorar el desembarque", "efecto": "Donde la señora: todo cabe en el congelador y no hay cortes de luz"},
    ]), hide_index=True, width="stretch")
