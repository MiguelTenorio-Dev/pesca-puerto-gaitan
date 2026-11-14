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
