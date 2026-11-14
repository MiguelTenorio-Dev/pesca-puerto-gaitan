import numpy as np
import pandas as pd
import pytest

from pesca import cadena_actual as ca, config, degradacion as dg
from pesca.escenario import Escenario

BASE = Escenario.base()


def _corrida(semilla=42, **valores):
    with config.sobrescribir(valores):
        return ca.simular_corrida(np.random.default_rng(semilla), BASE)


def test_el_congelador_nunca_supera_la_capacidad():
    for semilla in range(10):
        c = _corrida(semilla)
        assert (c.inventario["kg_congelado"] <= c.capacidad_kg + 1e-9).all()
    c = _corrida()
    assert c.inventario["kg_icopor"].iloc[-1] > 0  # con el volumen base hay desborde
    congelado = c.lotes[(c.lotes["sitio"] == "senora") & (c.lotes["almacen"] == "congelador")]["kg"].sum()
    assert congelado == pytest.approx(min(c.capacidad_kg, c.lotes.loc[c.lotes["sitio"] == "senora", "kg"].sum()))


def test_sin_cortes_no_hay_falla():
    c = _corrida(**{"cadena_actual.p_corte_dia": 0.0})
    congelador = c.lotes[c.lotes["almacen"] == "congelador"]
    assert len(congelador) and (congelador["perdida_espera"] == 0).all()


def test_con_cortes_largos_hay_falla():
    c = _corrida(**{"cadena_actual.p_corte_dia": 1.0, "cadena_actual.horas_corte": {"min": 12.0, "max": 12.0}})
    congelador = c.lotes[c.lotes["almacen"] == "congelador"]
    assert (congelador["perdida_espera"] > 0).all()


def test_el_malecon_no_espera():
    malecon = _corrida().lotes.query("sitio == 'malecon'")
    assert len(malecon)
    assert set(malecon["almacen"]) <= {"directo", "no_llego"}
    assert (malecon["horas_espera"] == 0).all()


def test_misma_semilla_mismo_resultado():
    pd.testing.assert_frame_equal(_corrida(3).lotes, _corrida(3).lotes)


def test_sin_subregistro_no_llega_nada_a_la_senora():
    c = _corrida(**{"volumen.factor_subregistro": 1.0})
    assert not (c.lotes["sitio"] == "senora").any()


def test_etapas_suman_el_total_por_lote():
    L = _corrida().lotes
    etapas = L[[f"cop_{e}" for e in dg.ETAPAS_COP]].sum(axis=1)
    assert np.allclose(etapas, L["cop_perdido"])


def test_cascada_cierra():
    ind, _ = ca.resumir_corrida(_corrida())
    perdidas = sum(ind[f"cop_kg_{e}"] for e in dg.ETAPAS_COP)
    assert ind["precio_base"] - perdidas == pytest.approx(ind["cop_kg_recibido"])


def test_kg_del_mes_tipico_coinciden_con_la_poblacion():
    c = _corrida()
    ind, zonas = ca.resumir_corrida(c)
    assert ind["kg_mes"] == pytest.approx(sum(c.kg_mes.values()))
    assert zonas["kg_mes"].sum() == pytest.approx(ind["kg_mes"])


def test_monte_carlo_con_intervalos():
    corridas, zonas = ca.correr_montecarlo(BASE, n=15)
    r = ca.resumen(corridas)
    for c in ca.INDICADORES:
        assert r.at[c, "p5"] <= r.at[c, "media"] <= r.at[c, "p95"], c
    assert 0 <= r.at["espera_mayor_que_rio", "media"] <= 100
    assert set(zonas["corrida"]) == set(range(15))
    # Reproducible
    pd.testing.assert_frame_equal(corridas, ca.correr_montecarlo(BASE, n=15)[0])


def test_sensibilidad_cuatro_candidatas():
    tablas = []
    for candidata in config.parametro("cadena_actual.candidatas_desembarque_senora"):
        ind, _ = ca.correr_montecarlo(BASE.con(desembarque_senora=candidata), n=5)
        tablas.append(ind.assign(candidata=candidata, temporada="aguas_bajas"))
    sens = ca.sensibilidad(pd.concat(tablas), "aguas_bajas")
    assert len(sens) == 4
    cambia, texto = ca.veredicto_sensibilidad(sens)
    assert isinstance(cambia, bool) and "conclusión" in texto


def test_veredicto():
    def tabla(pcts):
        return pd.DataFrame({"pct_corridas_espera_mayor": pcts, "pct_valor_perdido_media": [50.0] * len(pcts)})

    assert ca.veredicto_sensibilidad(tabla([90, 80, 70, 95]))[0] is False
    assert ca.veredicto_sensibilidad(tabla([10, 20, 30, 40]))[0] is False
    assert ca.veredicto_sensibilidad(tabla([90, 20, 70, 95]))[0] is True


def test_diagnostico_no_usa_hielo_ni_camion():
    hoy = ca.escenario_hoy(BASE.con(hielo_a_bordo=True, camion_refrigerado=True))
    assert not hoy.hielo_a_bordo and not hoy.camion_refrigerado


def test_precalculado_completo():
    datos = ca.cargar_precalculado()
    assert datos is not None, "Corre python scripts/correr_todo.py --solo r2"
    c = datos["corridas"]
    assert set(c["candidata"]) == set(config.parametro("cadena_actual.candidatas_desembarque_senora"))
    assert set(c["temporada"]) == config.TEMPORADAS
    assert c.groupby(["temporada", "candidata"]).size().eq(datos["meta"]["corridas"]).all()
