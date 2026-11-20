from streamlit.testing.v1 import AppTest

from pesca import cli, config

PAGINAS = [config.DIR_APP / "Inicio.py", *sorted((config.DIR_APP / "pages").glob("*.py"))]


def test_cli_encuentra_inicio():
    assert cli.RUTA_INICIO.is_file()


def test_paginas_abren_sin_errores():
    for pagina in PAGINAS:
        at = AppTest.from_file(str(pagina), default_timeout=30).run()
        assert not at.exception, f"{pagina.name}: {at.exception}"


def test_barra_lateral_cambia_el_escenario():
    at = AppTest.from_file(str(config.DIR_APP / "Inicio.py"), default_timeout=30).run()
    at.sidebar.toggle[0].set_value(True).run()
    assert at.session_state["escenario"].hielo_a_bordo is True


def test_laboratorio_cambia_de_algoritmo():
    pagina = config.DIR_APP / "pages" / "04_Laboratorio_de_algoritmos.py"
    at = AppTest.from_file(str(pagina), default_timeout=30).run()
    for algoritmo in ("a_estrella", "bfs"):
        at.radio(key="algoritmo").set_value(algoritmo).run()
        assert not at.exception, at.exception



def test_centros_de_acopio_activa_la_propuesta():
    pagina = config.DIR_APP / "pages" / "07_Centros_de_acopio.py"
    at = AppTest.from_file(str(pagina), default_timeout=60).run()
    assert not at.exception, at.exception
    at.button(key="activar_propuesta").click().run()
    assert not at.exception, at.exception
    assert at.session_state["escenario"].acopios_grafo
    assert set(config.parametro("puntos_frios.fijos")) <= at.session_state["escenario"].puntos_frios_grafo


def test_ya_no_estan_el_recomendador_ni_toda_la_flota():
    nombres = {p.name for p in (config.DIR_APP / "pages").glob("*.py")}
    assert not any(n.startswith(("05_", "06_")) for n in nombres)


def test_pesos_carga_el_ejemplo():
    pagina = config.DIR_APP / "pages" / "13_Como_se_calculan_los_pesos.py"
    at = AppTest.from_file(str(pagina), default_timeout=30).run()
    at.button(key="cargar_ejemplo").click().run()
    assert not at.exception, at.exception
    assert any("0,4978" in m.value or "0,1134" in m.value for m in at.markdown)



def test_bimodal_cambia_presupuesto_y_usa_el_portafolio():
    pagina = config.DIR_APP / "pages" / "08_Bimodal_y_cadena_de_frio.py"
    at = AppTest.from_file(str(pagina), default_timeout=120).run()
    assert not at.exception, at.exception
    at.radio(key="emb_bimodal").set_value("madera_motor").run()
    for presupuesto in config.parametro("inversiones.presupuestos_cop"):
        at.radio(key="presupuesto").set_value(presupuesto).run()
        assert not at.exception, at.exception
    at.button(key="usar_portafolio").click().run()
    assert not at.exception, at.exception
    assert at.session_state["escenario"].inversiones


def test_hoy_vs_propuesta_cambia_temporada_y_descarga():
    pagina = config.DIR_APP / "pages" / "09_Hoy_vs_propuesta.py"
    at = AppTest.from_file(str(pagina), default_timeout=60).run()
    assert not at.exception, at.exception
    at.radio(key="temporada_r6").set_value("aguas_altas").run()
    assert not at.exception, at.exception
    at.selectbox(key="zona_cartilla").set_value(at.selectbox(key="zona_cartilla").options[1]).run()
    assert not at.exception, at.exception
