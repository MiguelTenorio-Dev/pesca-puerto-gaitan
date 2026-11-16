# Guion de la demostración en vivo (≈ 4 minutos)

**Antes de empezar:**
- abre la app pública 10 minutos antes; si tarda en despertar, recárgala una vez;
- deja una segunda pestaña con «Hoy vs propuesta»;
- **plan B sin internet:** en la terminal, `source .venv/bin/activate && pesca-gaitan` (abre en `localhost:8501`).

## 1. El pescador de hoy (≈ 1,5 min)

1. Barra lateral: deja **los valores de hoy** (solo la plaza activa, aguas bajas, sin hielo a bordo ni camión).
2. Pantalla **«¿A dónde llevo mi pescado?»**: elige **Meta bajo** (o haz clic en el mapa río abajo de Puerto Gaitán), bote **madera a remo**, 20 kg, nevera **dañada**.
3. Lee la tarjeta en voz alta. La idea que hay que transmitir:
   > «El pescado solo se salva si lo sube hasta Puerto Gaitán, pero son 29 km contra la corriente y 14 horas a remo: el viaje le cuesta más de lo que le pagan. Entonces lo deja en San Miguel, espera unos 6 días al comprador y llega dañado.»
4. Señala en el mapa la ruta en **rojo** (contra la corriente) que no conviene.

## 2. El mismo pescador con la propuesta (≈ 1,5 min)

1. Barra lateral: activa **San Miguel** en «Acopios activos».
2. Misma pantalla y mismos datos. Ahora la tarjeta dice:
   > «Lleva tu pescado a San Miguel: 13 km a favor de la corriente, ≈ 2 horas. Allá lo guardan en el cuarto frío, hacen el transbordo y sigue por carretera a la plaza. Te quedan unos $112.000.»
3. Muestra la ruta: **verde** por el río, **gris** por carretera, y el círculo del transbordo.
4. Frase de cierre: «No cambió el río ni el bote: cambió que el pescado no tiene que esperar sin frío».

## 3. Toda la flota y la cartilla (≈ 1 min)

1. Pantalla **«Hoy vs propuesta»**: lee los dos indicadores principales en aguas bajas, el valor perdido (46,1 % → 8,7 %) y las horas hasta la venta (81,7 → 29,7). Las cifras salen de `outputs/resumen_resultados.md`, R6.
2. Señala el aviso: cerca de 2/3 de la mejora salen de **seguir el recomendador**, sin invertir.
3. Baja a **«Cartilla de rutas»** y descarga el **PDF**: «En el río casi no hay señal; esto se imprime y se pega en el acopio».

## Si algo falla

- **La app pública no abre:** pasa al plan B local.
- **El mapa no responde al clic:** usa la lista de lugares.
- **Preguntan por la incertidumbre:** la propuesta tiene VPN positivo en el 52 % de las corridas, por debajo de la regla del 70 % (resumen, R5). Es la mejor opción disponible, pero con riesgo, y depende sobre todo del costo de la energía.
