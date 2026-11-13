# Proyecto Universitario: Optimización y Sostenibilidad de la Cadena de Pesca en Puerto Gaitán

<rol_del_agente>
Eres un Principal Engineer y experto en ciencia de datos, teoría de grafos y optimización logística. Tu tarea es escribir el código para este proyecto desde cero. Lee todo este documento para entender el contexto. Antes de escribir código, mapea la topología, planifica la arquitectura y haz preguntas si encuentras ambigüedades. No modifiques ni crees archivos sin antes aprobar el plan.
</rol_del_agente>

<contexto_academico_y_problema>
El proyecto busca resolver una problemática real de las comunidades de pescadores en Puerto Gaitán (Meta, Colombia). Actualmente, la cadena de valor pesquera es insostenible:
- Hay periodos de veda (mayo a julio) donde los pescadores no pueden pescar y dependen de subsidios (muchas veces reclamados por falsos pescadores).
- Hay pérdida de biodiversidad por sobrepesca de especies de alto valor comercial, ignorando otras.
- Existe una degradación acelerada del producto (pescado) debido a la ausencia de una red de frío y tiempos de traslado largos y desconocidos.
- Las condiciones del agua están afectadas por agricultura, minería e hidrocarburos.
- El objetivo a nivel social es aumentar el empleo y los ingresos de los pescadores, mejorando su cadena de comercialización y evitando que los intermediarios mayoristas se aprovechen de la degradación rápida del producto.
</contexto_academico_y_problema>

<topologia_y_datos_del_grafo>
Se debe modelar la situación como un problema de transporte y teoría de grafos.

**Nodos de Extracción (Zonas de Pesca 'P'):**
- Río Meta (Cuenca principal, alta concentración).
- Río Manacacias (Zona de altísimo impacto y concentración de pesca).
- Río Yucao.
- Río Guarrojo.
- Río Muco.
- Otros: Río Planas, Caños menores (Canalete, Cañomorroco, Maiciana, Guiva, Chayva).

**Nodos de Acopio (Destinos 'A'):**
- Puerto Gaitán: Centro principal (plaza de mercado con ~8 negocios con refrigeración).
- San Miguel: Cuarto frío (4m³) actualmente inutilizado/inmantenible.
- Puente Arimena: Cuarto frío pequeño (no se usa actualmente).
- *Nota:* Múltiples zonas reportan ausencia total de infraestructura (sin muelles ni cuartos fríos).

**Aristas (Rutas) y Variables de Peso:**
- **Distancia y Tiempo:** No hay datos reales. El código deberá generar datos simulados/aleatorios realistas para las distancias entre las zonas de pesca y los centros de acopio.
- **Modificadores de Velocidad (Transporte):** El único medio es acuático. Las embarcaciones tienen 9 metros de eslora. 
  - Material: Madera (tradicional, lenta) vs. Aluminio/Fibra de vidrio (ligeras, rápidas).
  - Propulsión: A remo (muy lento) vs. Motor pequeño (rápido).
- **Función Objetivo (Degradación):** El peso/costo principal de la ruta es el "tiempo de degradación". Sin cadena de frío, la carga bacteriana aumenta rápidamente, devaluando el precio que paga el mayorista. La vida útil máxima de algunas especies (ej. cachama) en condiciones ideales es de 15 días, pero al sol en una canoa, es de horas.
</topologia_y_datos_del_grafo>

<requerimientos_funcionales>
El sistema / código a desarrollar debe realizar las siguientes simulaciones basadas en el grafo:

1. **Mapeo Inicial:** Crear el grafo base que conecte las zonas de pesca (Ríos) con los centros de acopio existentes, simulando distancias y tiempos de viaje según el tipo de transporte.
2. **Asignación Óptima:** Determinar cuáles son los centros de acopio más eficientes para cada pescador dependiendo de su zona de extracción para minimizar el tiempo de traslado (y por ende, la degradación).
3. **Factibilidad de San Miguel:** Simular si vale la pena y es matemáticamente factible recuperar el centro de acopio de San Miguel basándose en las distancias.
4. **Reubicación y Nuevos Acopios:** Calcular y proponer las ubicaciones/coordenadas más óptimas a lo largo del río para instalar nuevos centros de acopio que reduzcan significativamente los tiempos de viaje.
5. **Solución para Veda (Criaderos):** Integrar a la simulación una forma de identificar las zonas óptimas, ambiental y legalmente viables, para ubicar "enjambres de criaderos" (piscicultura sostenible en jaulas) que den sustento a los pescadores en época de veda (mayo-julio) sin afectar el río.
6. **Alcaldía y Ornamentación:** Simular cómo la inversión de la alcaldía en embalses u ornamentación optimizada en puntos clave mejoraría los tiempos de mantenimiento y refrigeración del pescado.
</requerimientos_funcionales>

<stack_tecnologico>
A definir por el Principal Engineer, pero se sugiere utilizar un entorno robusto para análisis de grafos y simulación (Ej. Python con NetworkX, Pandas y Matplotlib/Folium para visualización, o una solución interactiva web si se requiere interfaz visual).
</stack_tecnologico>