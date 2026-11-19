# KML del grafo

Deja aquí los KML que el equipo trace en Google Earth:

- `rio.kml`: un LineString por río (Meta, Manacacías, Yucao…), dibujado **de aguas arriba a aguas abajo**. Si alguno quedó al revés, pasa su nombre con `--invertir`.
- `vias.kml`: un LineString por carretera.
- `pesca.kml`: un punto (Placemark) por zona de pesca.

Luego, desde la raíz del repo:

```
python scripts/kml_a_grafo.py --rio src/pesca/datos/grafo/kml/rio.kml \
    --vias src/pesca/datos/grafo/kml/vias.kml --pesca src/pesca/datos/grafo/kml/pesca.kml
```

Eso reemplaza `nodos.csv` y `aristas.csv` (hoy son el esqueleto SIMULADO, que se regenera con `--esqueleto`).
