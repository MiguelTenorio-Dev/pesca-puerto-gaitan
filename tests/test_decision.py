from pesca import comparacion, config, decision
from pesca.escenario import Escenario


def test_recorrido_de_cinco_pasos_con_ejemplo_numerico():
    pasos = decision.recorrido(Escenario.base())
    assert [p["n"] for p in pasos] == [1, 2, 3, 4, 5]
    for p in pasos:
        assert any(ch.isdigit() for ch in p["ejemplo"]), p["titulo"]
        assert (config.DIR_APP / p["pagina"]).is_file(), p["pagina"]


def test_el_recorrido_cambia_con_el_escenario():
    bajas = decision.recorrido(Escenario.base())[2]["ejemplo"]
    altas = decision.recorrido(Escenario.base().con(temporada="aguas_altas"))[2]["ejemplo"]
    assert "0,4978" in bajas
    assert "infactible" in altas


def test_resumen_tiene_la_seccion_del_grafo():
    texto = decision.texto_resumen_grafo()
    for clave in ("## Grafo y acopios", "Calibración", "M04", "enumeracion", "ilp", "busqueda_local", "Costo de exigir pueblos", "Centroide"):
        assert clave in texto


def test_resumen_versionado_al_dia():
    """outputs/resumen_resultados.md se regenera con `python scripts/correr_todo.py --solo resumen`."""
    if config.DIR_REPO is None:
        return
    archivo = (config.DIR_REPO / "outputs" / comparacion.ARCHIVO_RESUMEN).read_text(encoding="utf-8")
    assert decision.texto_resumen_grafo() in archivo
