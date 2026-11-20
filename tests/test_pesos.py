import pytest

from pesca import config, grafo, pesos

M04, M03 = pesos.arco_ejemplo_m04(), pesos.arco_ejemplo_m03()
REMO_BAJAS = pesos.Condiciones(bote="madera_remo", temporada="aguas_bajas", nevera="buena")
TOL = 0.001


# ---------------------------------------------------------------- ejemplo §3.8 (prueba 4)


def test_remo_aguas_bajas_velocidad_y_tiempo():
    v, factible, _ = pesos.velocidad_efectiva(M04, REMO_BAJAS)
    assert factible and v == pytest.approx(2.0)
    assert pesos.tiempo_arco(M04, REMO_BAJAS) == pytest.approx(20.825, abs=TOL)


@pytest.mark.parametrize("nevera, dq", [("buena", 0.1134), ("deteriorada", 0.4978)])
def test_perdida_segun_la_nevera(nevera, dq):
    resultado = pesos.costo_arco(M04, "hielo", 0.0, REMO_BAJAS.con(nevera=nevera))
    assert resultado[0] == pytest.approx(dq, abs=TOL)
    assert resultado[2] == "hielo"


def test_sin_hielo_se_pierde_todo():
    dq = pesos.costo_arco(M04, "hielo", 0.0, REMO_BAJAS.con(nevera="sin_hielo"))[0]
    assert dq >= 1
    assert max(0.0, 1 - dq) == 0


def test_remo_aguas_altas_infactible_con_motivo():
    cond = REMO_BAJAS.con(temporada="aguas_altas")
    v, factible, motivo = pesos.velocidad_efectiva(M04, cond)
    assert not factible and v is None
    assert "contra la corriente" in motivo and "0 km/h" in motivo
    assert pesos.costo_arco(M04, "hielo", 0.0, cond) is None
    assert pesos.peso(M04, "calidad", cond=cond) is None


def test_motor_aguas_altas():
    dq, tau, _ = pesos.costo_arco(M04, "hielo", 0.0, pesos.Condiciones(bote="madera_motor", temporada="aguas_altas", nevera="deteriorada"))
    assert tau == pytest.approx(3.786, abs=TOL)
    assert dq == pytest.approx(0.0206, abs=TOL)
    dq, tau, _ = pesos.costo_arco(M04, "hielo", 0.0, pesos.Condiciones(bote="aluminio_motor", temporada="aguas_altas"))
    assert tau == pytest.approx(1.735, abs=TOL) and dq == pytest.approx(0.0094, abs=TOL)


def test_camion_refrigerado_por_carretera():
    dq, tau, capa = pesos.costo_arco(M03, "frio", 0.0, REMO_BAJAS)
    assert tau == pytest.approx(1.111, abs=TOL)
    assert dq == pytest.approx(0.0061, abs=TOL)
    assert capa == "frio"


def test_transbordo():
    arco = {"tipo": "transbordo", "modo": "interno", "d_km": 0.0, "sentido": 0}
    dq, tau, _ = pesos.costo_arco(arco, "hielo", 0.0, REMO_BAJAS)
    assert tau == config.parametro("rio.tiempo_transbordo_h")
    assert dq == pytest.approx(0.0027, abs=TOL)


# ---------------------------------------------------------------- reglas del peso


def test_el_hielo_se_acaba_a_mitad_de_un_arco():
    # nevera deteriorada (H = 12 h) y el arco empieza a las 10 h: 2 h con hielo y el resto a temperatura ambiente
    cond = REMO_BAJAS.con(nevera="deteriorada")
    tau = pesos.tiempo_arco(M04, cond)
    esperado = (2 * pesos.rrs(4) + (tau - 2) * pesos.rrs(32)) / 360
    assert pesos.costo_arco(M04, "hielo", 10.0, cond)[0] == pytest.approx(esperado)
    # llegar mas tarde nunca cuesta menos (FIFO, adenda §3.7)
    costos = [pesos.costo_arco(M04, "hielo", t, cond)[0] for t in range(0, 40, 2)]
    assert costos == sorted(costos)


def test_la_capa_solo_pasa_de_hielo_a_frio_en_una_espera_con_equipo():
    espera = {"tipo": "espera", "modo": "interno", "d_km": 0.0, "sentido": 0, "centro": "CP03"}
    con_frio = REMO_BAJAS.con(acopios=frozenset({"CP03"}))
    assert pesos.capa_nueva(espera, "hielo", con_frio) == "frio"
    assert pesos.capa_nueva(espera, "hielo", REMO_BAJAS.con(acopios=frozenset())) == "hielo"
    assert pesos.capa_nueva(espera, "frio", con_frio) == "frio"
    assert pesos.capa_nueva(M04, "hielo", con_frio) == "hielo"
    assert pesos.capa_nueva(espera, "hielo", REMO_BAJAS.con(acopios=frozenset(), camion_refrigerado=True)) == "frio"


def test_congelado_no_se_deteriora():
    assert pesos.perdida(100.0, "congelado", 0.0, REMO_BAJAS) == 0


def test_asimetria_san_miguel_puerto_gaitan():
    g = grafo.construir_grafo()
    for bote in config.cargar_parametros()["embarcaciones"]:
        cond = REMO_BAJAS.con(bote=bote)
        for u, v, a in g.edges(data=True):
            if a["tipo"] == "rio" and a["sentido"] == 1:
                assert pesos.tiempo_arco(g.edges[v, u], cond) > pesos.tiempo_arco(a, cond)


def test_pesos_no_negativos_en_todos_los_arcos_y_criterios():
    g = grafo.construir_grafo()
    for bote in config.cargar_parametros()["embarcaciones"]:
        for temporada in config.TEMPORADAS:
            cond = pesos.Condiciones(bote=bote, temporada=temporada, acopios=frozenset({"CP01", "CP03"}))
            for *_, a in g.edges(data=True):
                for criterio in pesos.CRITERIOS:
                    for capa in pesos.CAPAS:
                        w = pesos.peso(a, criterio, capa, 5.0, cond)
                        assert w is None or w >= 0, (a["id"], criterio)


def test_ningun_numero_simulado_en_el_codigo():
    # los numeros del modelo se leen del yaml: cambiar el yaml cambia el peso
    with config.sobrescribir({"degradacion.vu0_h": 720.0}):
        dq = pesos.costo_arco(M04, "hielo", 0.0, REMO_BAJAS)[0]
    assert dq == pytest.approx(0.1134 / 2, abs=TOL)
    with config.sobrescribir({"embarcaciones.madera_remo": 6.0}):
        assert pesos.tiempo_arco(M04, REMO_BAJAS) == pytest.approx(41.65 / 4)


def test_grafo_por_capas():
    g = grafo.construir_grafo()
    cond = REMO_BAJAS.con(acopios=frozenset({"CP03"}), temporada="aguas_altas")
    gc = pesos.expandir_capas(g, cond)
    assert gc.number_of_nodes() == len(pesos.CAPAS_GRAFO) * g.number_of_nodes()
    assert not any(capa == "congelado" for _, capa in gc.nodes)
    # aguas altas a remo: no hay arcos de rio aguas arriba
    assert not any(a["tipo"] == "rio" and a["sentido"] == -1 for *_, a in gc.edges(data=True))
    # la espera de San Miguel lleva de hielo a frio; nunca hay un arco de frio a hielo
    assert gc.has_edge(("CP03:entra", "hielo"), ("CP03:sale", "frio"))
    assert not any(u[1] == "frio" and v[1] == "hielo" for u, v in gc.edges)


def test_explicar_arco_muestra_los_numeros():
    texto = "\n".join(pesos.explicar_arco(M04, REMO_BAJAS.con(nevera="deteriorada")))
    assert "20,825" in texto and "0,4978" in texto and "17,64" in texto
    infactible = "\n".join(pesos.explicar_arco(M04, REMO_BAJAS.con(temporada="aguas_altas")))
    assert "Infactible" in infactible


def test_heuristica_admisible_por_construccion():
    cond = pesos.Condiciones(bote="aluminio_motor", temporada="aguas_altas")
    assert pesos.v_max(cond) >= config.parametro("embarcaciones.aluminio_motor") + config.parametro("rio.corriente_aguas_altas_kmh")
    assert pesos.rrs_min() == pytest.approx(1.96)


def test_punto_frio_solo_cambia_la_capa_en_su_pueblo():
    cond = REMO_BAJAS.con(acopios=frozenset(), puntos_frios=frozenset({"C01"}))
    transbordo_yucao = {"tipo": "transbordo", "modo": "interno", "d_km": 0.0, "sentido": 0, "pueblo": "C01"}
    transbordo_otro = {**transbordo_yucao, "pueblo": "CP03"}
    espera_frio = {"tipo": "espera", "modo": "interno", "d_km": 0.0, "sentido": 0, "centro": "C01"}
    assert pesos.capa_nueva(transbordo_yucao, "hielo", cond) == "frio"
    assert pesos.capa_nueva(espera_frio, "hielo", cond) == "frio"
    assert pesos.capa_nueva(transbordo_otro, "hielo", cond) == "hielo"
    assert pesos.capa_nueva(M04, "hielo", cond) == "hielo"  # pasar por el rio frente al pueblo no basta: hay que entrar
