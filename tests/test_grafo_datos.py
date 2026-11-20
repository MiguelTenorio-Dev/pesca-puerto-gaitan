from pathlib import Path

import pandas as pd
import pytest

from pesca import config, grafo_datos as gd
from pesca.red import haversine_km, longitud_km

DIR_JUGUETE = Path(__file__).parent / "datos"
RIO, VIAS, PESCA = (DIR_JUGUETE / f"juguete_{n}.kml" for n in ("rio", "vias", "pesca"))
CENTROS_JUGUETE = config.leer_csv_grafo(DIR_JUGUETE / "juguete_centros.csv", config.COLUMNAS_CENTROS)
PASO = config.parametro("grafo.paso_km")


def _juguete(invertir: bool = False):
    lineas = gd.leer_lineas_kml(RIO)
    if invertir:
        for linea in lineas:
            if linea.nombre == "río Uno":
                linea.coords.reverse()
    pueblos, pendientes = gd.lugares(CENTROS_JUGUETE)
    nodos, aristas, mas = gd.construir(lineas, gd.leer_lineas_kml(VIAS), pueblos, gd.zonas_kml(PESCA), PASO)
    return nodos.set_index("id", drop=False), aristas, pendientes + mas


# ---------------------------------------------------------------- KML de juguete


def test_lee_un_linestring_por_traza():
    lineas = gd.leer_lineas_kml(RIO)
    assert [l.nombre for l in lineas] == ["río Uno", "río Dos"]
    assert lineas[0].coords[0] == (4.0, -72.0)
    assert gd.etiqueta(lineas[0].fuente) == "MEDIDO"


def test_vertice_en_la_confluencia():
    nodos, aristas, _ = _juguete()
    conf = nodos[nodos["nombre"].str.startswith("confluencia")]
    assert len(conf) == 1
    assert (conf["lat"].iloc[0], conf["lon"].iloc[0]) == pytest.approx((4.0, -71.95), abs=1e-6)
    # el rio Dos llega a ese vertice
    llegan = aristas[(aristas["tipo"] == "rio") & (aristas["destino"] == conf.index[0])]
    assert len(llegan) == 2


def test_un_vertice_cada_paso():
    _, aristas, _ = _juguete()
    rio = aristas[aristas["tipo"] == "rio"]
    assert len(rio) == 5  # Uno: 5,5 + 5,5 (hasta el pueblo) + 2 × 5,5 ; Dos: 5,5
    assert rio["distancia_km"].max() <= 1.5 * PASO


def test_distancia_es_suma_de_haversine():
    nodos, aristas, _ = _juguete()
    uno = gd.leer_lineas_kml(RIO)[0]
    tramos = aristas[(aristas["tipo"] == "rio") & aristas["origen"].map(nodos["nombre"]).str.contains("Uno|Pueblo")]
    assert tramos["distancia_km"].sum() == pytest.approx(longitud_km(uno.coords), rel=1e-6)
    # los arcos internos (transbordo, espera, venta) tienen d = 0 por definicion (adenda §2.2)
    for a in aristas[aristas["modo"] != "interno"].itertuples():
        o, d = nodos.loc[a.origen], nodos.loc[a.destino]
        assert a.distancia_km >= haversine_km(o.lat, o.lon, d.lat, d.lon) - 1e-4


@pytest.mark.parametrize("invertir", [False, True])
def test_sentido_aguas_abajo_en_el_orden_de_la_traza(invertir):
    nodos, aristas, _ = _juguete(invertir)
    rio = aristas[aristas["tipo"] == "rio"]
    assert (rio["sentido"] == 1).all()
    uno = rio[(rio["origen"].map(nodos["lat"]) == 4.0) & (rio["destino"].map(nodos["lat"]) == 4.0)]
    avanza_al_este = uno["destino"].map(nodos["lon"]) > uno["origen"].map(nodos["lon"])
    assert (avanza_al_este != invertir).all()


def test_zonas_al_punto_del_rio_mas_cercano():
    nodos, aristas, _ = _juguete()
    rios = nodos[nodos["tipo"] == "punto_rio"]
    for z in nodos[nodos["tipo"] == "zona_pesca"].itertuples():
        destino = aristas.loc[aristas["origen"] == z.id, "destino"].item()
        esperado = min(rios.itertuples(), key=lambda r: haversine_km(z.lat, z.lon, r.lat, r.lon)).id
        assert destino == esperado


def test_pueblo_con_embarcadero_via_y_mercado():
    nodos, aristas, pendientes = _juguete()
    assert {"CP01", "E_CP01", "MER_CP01"} <= set(nodos.index)
    tipos = set(aristas.loc[(aristas["origen"] == "CP01") | (aristas["destino"].isin(["CP01", "E_CP01"])), "tipo"])
    assert tipos == {"acceso", "transbordo", "via", "venta"}
    assert "CP02" not in nodos.index
    assert any("Pueblo Sin Mapa" in p for p in pendientes)


def test_main_escribe_csv_validos(tmp_path):
    codigo = gd.main(
        ["--rio", str(RIO), "--vias", str(VIAS), "--pesca", str(PESCA), "--invertir", "río Dos",
         "--centros", str(DIR_JUGUETE / "juguete_centros.csv"), "--salida", str(tmp_path)]
    )
    assert codigo == 0
    nodos = config.leer_csv_grafo(tmp_path / "nodos.csv", config.COLUMNAS_NODOS_GRAFO)
    aristas = config.leer_csv_grafo(tmp_path / "aristas.csv", config.COLUMNAS_ARISTAS)
    assert gd.validar_esquema(nodos, aristas, CENTROS_JUGUETE) == []
    assert (nodos["tipo"] == "zona_pesca").sum() == 2


def test_invertir_un_rio_que_no_existe_falla(tmp_path):
    with pytest.raises(SystemExit):
        gd.main(["--rio", str(RIO), "--invertir", "río Tres", "--salida", str(tmp_path)])


# ---------------------------------------------------------------- esquema de los archivos del paquete

CENTROS = config.cargar_centros_poblados()
NODOS = config.cargar_nodos_grafo()
ARISTAS = config.cargar_aristas()
PLANTILLA_NODOS = config.leer_csv_grafo(config.DIR_GRAFO / "plantilla_nodos.csv", config.COLUMNAS_NODOS_GRAFO)
PLANTILLA_ARISTAS = config.leer_csv_grafo(config.DIR_GRAFO / "plantilla_aristas.csv", config.COLUMNAS_ARISTAS)

TABLAS = {
    "centros_poblados": (CENTROS, gd.validar_centros),
    "nodos": (NODOS, gd.validar_nodos),
    "aristas": (ARISTAS, gd.validar_aristas),
    "plantilla_nodos": (PLANTILLA_NODOS, gd.validar_nodos),
    "plantilla_aristas": (PLANTILLA_ARISTAS, gd.validar_aristas),
}


@pytest.mark.parametrize("nombre", TABLAS)
def test_esquema_de_cada_archivo(nombre):
    tabla, validar = TABLAS[nombre]
    assert validar(tabla) == []
    assert tabla["id"].is_unique
    assert tabla["fuente"].map(gd.etiqueta).isin({"MEDIDO", "DATO", "OFICIAL", "CALIBRADO", "SIMULADO", "CONFIRMAR"}).all()
    if "lat" in tabla:
        assert tabla["lat"].dropna().between(2, 7).all()
        assert tabla["lon"].dropna().between(-75, -69).all()


def test_plantillas_tienen_una_fila_de_ejemplo():
    assert len(PLANTILLA_NODOS) == 1 and len(PLANTILLA_ARISTAS) == 1


def test_esquema_del_grafo_completo():
    assert gd.validar_esquema(NODOS, ARISTAS, CENTROS) == []


@pytest.mark.parametrize(
    "dano, error",
    [
        (lambda n: n.assign(lat=n["lat"].where(n.index != 0, 10.0)), "lat fuera"),
        (lambda n: n.assign(lon=n["lon"].where(n.index != 0, -80.0)), "lon fuera"),
        (lambda n: n.assign(fuente=n["fuente"].where(n.index != 0, "INVENTADO: x")), "etiqueta válida"),
        (lambda n: n.assign(id=n["id"].where(n.index != 1, n["id"].iloc[0])), "ids repetidos"),
        (lambda n: n.assign(tipo=n["tipo"].where(n.index != 0, "acopio")), "tipos de nodo"),
        (lambda n: n.drop(columns="notas"), "columnas"),
    ],
)
def test_el_esquema_detecta_errores(dano, error):
    assert any(error in e for e in gd.validar_nodos(dano(NODOS)))


def test_el_esquema_detecta_arcos_mal_formados():
    malos = ARISTAS.assign(sentido=ARISTAS["sentido"].where(ARISTAS.index != 0, 2))
    assert any("sentido" in e for e in gd.validar_aristas(malos))
    suelto = ARISTAS.assign(destino=ARISTAS["destino"].where(ARISTAS.index != 0, "NO_EXISTE"))
    assert any("NO_EXISTE" in e for e in gd.validar_esquema(NODOS, suelto))


# ---------------------------------------------------------------- centros poblados


def test_centros_poblados_del_dane():
    poblacion = dict(zip(CENTROS["nombre"], CENTROS["habitantes_2018"]))
    assert poblacion == {
        "Puerto Gaitán": 20659, "La Cristalina": 904, "San Miguel": 569, "Domo Planas": 446,
        "San Pedro de Arimena": 235, "El Porvenir": 209, "Puente Arimena": 207, "Murujuy": 76, "Puerto Trujillo": 58,
    }
    # validados: los que tienen coordenada medida en KML (rutas del equipo y el malecon)
    assert set(CENTROS.loc[CENTROS["validado"] == "si", "nombre"]) == {
        "Puerto Gaitán", "La Cristalina", "Domo Planas", "San Pedro de Arimena", "El Porvenir"}
    assert (CENTROS["fuente"] == "OFICIAL: DANE CNPV 2018, vía citypopulation.de").all()


def test_tres_centros_con_coordenadas_y_ningun_acceso_inventado():
    con = CENTROS.dropna(subset=["lat"])
    assert set(con["nombre"]) == {"Puerto Gaitán", "San Miguel", "La Cristalina", "Domo Planas", "San Pedro de Arimena", "El Porvenir"}
    centros = CENTROS.set_index("nombre")
    assert centros.at["La Cristalina", "acceso_rio"] == "no"  # confirmado por el equipo
    # acceso por rio solo donde hay ruta por agua medida; Domo Planas solo tiene ruta por tierra
    assert centros.at["Domo Planas", "acceso_rio"] == "por_confirmar"
    otros = CENTROS[CENTROS["lat"].isna() & (CENTROS["nombre"] != "Puente Arimena")]
    assert (otros[["acceso_rio", "acceso_via"]] == "por_confirmar").all().all()
    assert otros["capacidad_frio_kg"].isna().all()
    # la energia se supone en todos (SIMULADO, decision del equipo del 19 nov)
    assert (CENTROS["energia"] == "si").all()


# ---------------------------------------------------------------- esqueleto SIMULADO


def test_esqueleto_todo_simulado_y_sin_validar():
    # todo es SIMULADO salvo las zonas de pesca (estimaciones del equipo con imagenes) y los pueblos que el
    # equipo confirmo (La Cristalina): esos son DATO
    # zonas y pueblos confirmados: DATO; trazas KML del equipo: MEDIDO; lo demas: SIMULADO
    confirmados = set(CENTROS.loc[CENTROS["validado"] == "si", "id"])
    # (la plaza de mercado toma la fuente de su pueblo)
    dato = (NODOS["tipo"] == "zona_pesca") | NODOS["id"].isin(confirmados) | ((NODOS["tipo"] == "mercado") & NODOS["centro_id"].isin(confirmados))
    assert (NODOS.loc[dato, "fuente"].map(gd.etiqueta) == "DATO").all()
    assert set(NODOS.loc[~dato, "fuente"].map(gd.etiqueta)) <= {"SIMULADO", "MEDIDO"}
    assert set(ARISTAS["fuente"].map(gd.etiqueta)) == {"SIMULADO", "MEDIDO"}
    medidos = ARISTAS[ARISTAS["fuente"].map(gd.etiqueta) == "MEDIDO"]
    assert medidos["fuente"].str.contains("rutas que faltan").all()
    for tabla in (NODOS, ARISTAS):
        assert (tabla["validado"] == "no").all()


def test_esqueleto_cuenca_del_meta():
    v31 = config.cargar_nodos()
    zonas_meta = set(v31.loc[(v31["tipo"] == "zona_pesca") & (v31["cuenca"] == "meta"), "id"])
    assert set(NODOS.loc[NODOS["tipo"] == "zona_pesca", "id"]) == zonas_meta
    assert (NODOS.loc[NODOS["tipo"] == "punto_rio", "cuenca"] == "meta").all()
    assert {"Puerto Gaitán", "San Miguel", "La Cristalina", "pueblo Yucao"} <= set(NODOS["nombre"])
    # La Cristalina no tiene acceso por rio: no tiene embarcadero
    assert "E_CP02" not in set(NODOS["id"])


def test_esqueleto_arcos_no_mas_cortos_que_la_linea_recta():
    nodos = NODOS.set_index("id")
    for a in ARISTAS[ARISTAS["modo"] != "interno"].itertuples():
        o, d = nodos.loc[a.origen], nodos.loc[a.destino]
        assert a.distancia_km >= haversine_km(o.lat, o.lon, d.lat, d.lon) - 1e-4, a.id


def test_esqueleto_reproduce_lo_medido():
    tabla = gd.comparar_medidas(ARISTAS)
    assert {f"M{i:02d}" for i in range(1, 11)} == set(tabla["id"])
    tolerancia = config.parametro("red.tolerancia_calibracion")
    medicion = tabla[tabla["manda"] == "medición"]
    assert (medicion["error_pct"].abs() <= 100 * tolerancia).all(), tabla
    # donde manda el KML la diferencia con la medicion a mano es chica (M04: la traza mide un poco menos)
    assert (tabla["error_pct"].abs() <= 3).all(), tabla


def test_esqueleto_versionado_es_el_que_genera_el_codigo(tmp_path):
    nodos, aristas, _ = gd.esqueleto_simulado()
    gd.escribir(nodos, aristas, tmp_path)
    for archivo in ("nodos.csv", "aristas.csv"):
        assert (tmp_path / archivo).read_text() == (config.DIR_GRAFO / archivo).read_text(), archivo


def test_resumen_de_fuentes():
    resumen = gd.resumen_fuentes({"centros": CENTROS, "nodos": NODOS, "aristas": ARISTAS})
    assert resumen.loc["OFICIAL", "centros"] == 9
    assert resumen.loc[["SIMULADO", "DATO", "MEDIDO"], "nodos"].sum() == len(NODOS)
    assert resumen.loc["DATO", "nodos"] >= (NODOS["tipo"] == "zona_pesca").sum()
    assert list(resumen.index) == gd.ORDEN_ETIQUETAS
    tabla = gd.con_etiqueta(NODOS)
    assert list(tabla.columns[1:3]) == ["etiqueta", "detalle"]
