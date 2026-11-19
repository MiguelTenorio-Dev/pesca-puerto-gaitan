"""KML de Google Earth → src/pesca/datos/grafo/nodos.csv y aristas.csv (adenda §2.3).

Uso:
    python scripts/kml_a_grafo.py --rio rio.kml [--vias vias.kml] [--pesca pesca.kml] [--invertir "río Yucao"]
    python scripts/kml_a_grafo.py --esqueleto      # sin KML: esqueleto SIMULADO que reproduce M01–M04
"""

from pesca.grafo_datos import main

if __name__ == "__main__":
    raise SystemExit(main())
