import streamlit as st
from streamlit_folium import st_folium

from pesca import asignacion, comparacion, config, frio_bimodal, red, visualizacion
from pesca.app import comun

comun.configurar_pagina("Hoy vs propuesta")
escenario = comun.barra_lateral()


@st.cache_data
def precalculado():
    return comparacion.cargar_precalculado()


@st.cache_data
def precalculado_r5():
    return frio_bimodal.cargar_precalculado()


st.title("Hoy vs propuesta")
datos = precalculado()
r5 = precalculado_r5()
if datos is None or r5 is None:
    st.error("Faltan los resultados. Córrelos con `python scripts/correr_todo.py --solo r5` y `--solo r6`.")
    st.stop()

portafolio = comparacion.portafolio_propuesta()
clave = frio_bimodal.clave(portafolio)
st.markdown(
    "**La propuesta:** " + " + ".join(frio_bimodal.describir(portafolio))
    + ", con cada pescador llevando su pescado a donde le recomienda «¿A dónde llevo mi pescado?»."
)
temporada = st.radio("Temporada", comparacion.TEMPORADAS, horizontal=True, key="temporada_r6",
                     index=comparacion.TEMPORADAS.index(escenario.temporada), format_func=comparacion.TEXTO_TEMPORADA.get)
tabla = datos["pescadores"][datos["pescadores"]["temporada"] == temporada]
tot = comparacion.totales(tabla)

# ---------------------------------------------------------------- indicadores
st.header("Lo que cambia para los pescadores")
c1, c2, c3 = st.columns(3)
c1.metric("Plata que les queda al día (toda la flota)", asignacion.pesos(tot.at["neto_dia", "propuesta"]),
          delta=f"{asignacion.pesos(tot.at['neto_dia', 'diferencia'])} frente a hoy")
c1.caption(f"Hoy: {asignacion.pesos(tot.at['neto_dia', 'hoy'])}. Lo que les pagan menos gasolina y tiempo.")
c2.metric("Valor que se pierde", f"{tot.at['pct_valor_perdido', 'propuesta']:.0f} %",
          delta=f"{tot.at['pct_valor_perdido', 'diferencia']:.0f} puntos", delta_color="inverse")
c2.caption(f"Hoy: {tot.at['pct_valor_perdido', 'hoy']:.0f} %.")
c3.metric("kg que se botan al día", f"{tot.at['kg_perdidos_dia', 'propuesta']:.0f} kg",
          delta=f"{tot.at['kg_perdidos_dia', 'diferencia']:.0f} kg", delta_color="inverse")
c3.caption(f"Hoy: {tot.at['kg_perdidos_dia', 'hoy']:.0f} kg de {tot.at['kg_dia', 'hoy']:.0f} kg al día.")
c1, c2, c3 = st.columns(3)
c1.metric("Calidad media al vender", asignacion.numero(tot.at["calidad", "propuesta"], 2),
          delta=asignacion.numero(tot.at["calidad", "diferencia"], 2))
c1.caption(f"Hoy: {asignacion.numero(tot.at['calidad', 'hoy'], 2)} (de 0 a 1).")
c2.metric("Horas desde que sale hasta que se vende", f"{tot.at['horas', 'propuesta']:.0f} h",
          delta=f"{tot.at['horas', 'diferencia']:.0f} h", delta_color="inverse")
c2.caption(f"Hoy: {tot.at['horas', 'hoy']:.0f} h (la espera al comprador).")
fila5 = r5["portafolios"].set_index("portafolio").loc[clave]
mc = frio_bimodal.resumen_montecarlo(r5["montecarlo"]).set_index("portafolio")
c3.metric("Inversión de la alcaldía", f"{asignacion.pesos(fila5['inversion'] / 1e6)} M")
if clave in mc.index:
    m = mc.loc[clave]
    c3.caption(f"VPN a {config.parametro('economia.horizonte_anios')} años: {asignacion.pesos(m['vpn_media'] / 1e6)} M; "
               f"positivo en el {m['pct_vpn_positivo']:.0f} % de las corridas.")

if temporada == config.parametro("escenario_base.temporada"):  # R5 se calculo en la temporada base
    partes = comparacion.partes_de_la_mejora(tot.at["neto_dia", "diferencia"], fila5["valor_salvado_dia"])
    st.info(
        f"De la mejora, **{asignacion.pesos(partes['recomendador'])}/día** se logran solo con que cada pescador siga el "
        f"recomendador, sin invertir nada; la inversión agrega **{asignacion.pesos(partes['inversion'])}/día**."
    )
st.caption(
    f"{comun.etiqueta('SIMULADO')}: población de ejemplo y valores esperados del recomendador (la misma base de "
    "«Toda la flota», «Centros de acopio» y «Bimodal»). El diagnóstico simula día a día un ciclo del comprador, por eso "
    "sus cifras de hoy no son idénticas a estas."
)

# ---------------------------------------------------------------- mapa doble
st.header("Por dónde va el pescado")
grafo = red.construir_red()
flujos = datos["flujos"][temporada]
c1, c2 = st.columns(2)
for col, lado, titulo in ((c1, "hoy", "Hoy"), (c2, "propuesta", "Con la propuesta")):
    with col:
        st.subheader(titulo)
        st_folium(visualizacion.mapa_recorridos(grafo, flujos[lado], flujos["marcar"][lado]),
                  height=420, use_container_width=True, returned_objects=[], key=f"mapa_{lado}")
st.caption("Grosor = kg al día. Verde: a favor de la corriente · rojo: en contra · gris punteado: carretera. "
           "Círculos: dónde se deja el pescado (morado = acopio nuevo).")

# ---------------------------------------------------------------- pescador por pescador
st.header("Pescador por pescador")
zonas = sorted(tabla["zona"].unique())
elegidas = st.multiselect("Zonas", zonas, default=zonas, key="zonas_r6")
vista = tabla[tabla["zona"].isin(elegidas)]
columnas = ["pescador", "zona", "embarcacion", "kg_dia", "vende_en_hoy", "vende_en_propuesta",
            "calidad_hoy", "calidad_propuesta", "horas_hoy", "horas_propuesta", "neto_dia_hoy", "neto_dia_propuesta"]
st.dataframe(
    vista[columnas], hide_index=True, width="stretch",
    column_config={
        "embarcacion": "bote", "kg_dia": st.column_config.NumberColumn("kg/día", format="%.1f"),
        "vende_en_hoy": "hoy vende en", "vende_en_propuesta": "con la propuesta",
        "calidad_hoy": st.column_config.NumberColumn("calidad hoy", format="%.2f"),
        "calidad_propuesta": st.column_config.NumberColumn("calidad propuesta", format="%.2f"),
        "horas_hoy": st.column_config.NumberColumn("horas hoy", format="%.0f"),
        "horas_propuesta": st.column_config.NumberColumn("horas propuesta", format="%.0f"),
        "neto_dia_hoy": st.column_config.NumberColumn("le queda hoy (COP/día)", format="$ %,.0f"),
        "neto_dia_propuesta": st.column_config.NumberColumn("le queda con la propuesta", format="$ %,.0f"),
    },
)
st.download_button("⬇ Descargar la tabla (CSV)", vista.to_csv(index=False).encode("utf-8"),
                   file_name=f"hoy_vs_propuesta_{temporada}.csv", mime="text/csv")

# ---------------------------------------------------------------- cartilla
st.header("Cartilla de rutas para imprimir")
st.markdown("En el río casi no hay señal: la cartilla dice, para cada zona y tipo de bote, **a dónde llevar el pescado** "
            "con la propuesta funcionando, en verano y en invierno.")
cart = datos["cartilla"]
zona_c = st.selectbox("Ver la cartilla de", sorted(cart["lugar"].unique()), key="zona_cartilla")
st.dataframe(cart[cart["lugar"] == zona_c][["temporada", "bote", "lleva_a", "como", "horas", "te_quedan_cop", "aviso"]],
             hide_index=True, width="stretch",
             column_config={"lleva_a": "lleva tu pescado a", "como": "cómo llegar",
                            "horas": st.column_config.NumberColumn("≈ horas", format="%.1f"),
                            "te_quedan_cop": st.column_config.NumberColumn(
                                f"te quedan ({config.parametro('poblacion.kg_por_faena'):.0f} kg)", format="$ %,.0f"),
                            "aviso": "ojo"})
c1, c2 = st.columns(2)
c1.download_button("⬇ Cartilla completa (PDF para imprimir)", datos["cartilla_pdf"], file_name="cartilla_rutas.pdf",
                   mime="application/pdf", key="cartilla_pdf")
c2.download_button("⬇ Cartilla completa (CSV)", cart.to_csv(index=False).encode("utf-8"), file_name="cartilla_rutas.csv",
                   mime="text/csv", key="cartilla_csv")
st.caption(f"{comun.etiqueta('SIMULADO')}: {config.parametro('poblacion.kg_por_faena'):.0f} kg por faena y nevera de icopor "
           "deteriorada; las rutas son aproximadas.")
