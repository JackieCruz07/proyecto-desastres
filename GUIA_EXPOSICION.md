# Guía de exposición — Atlas Global de Desastres

> **Cómo usar esta guía**
> 1. Memoriza la frase de la sección 1 y las siete estaciones de la sección 2.
> 2. Aprende de memoria la tabla de cifras de la sección 6 (son las que te van a preguntar).
> 3. Ensaya el guion de 3 minutos (sección 10) y repasa las 20 preguntas (sección 11).
>
> Con eso puedes sostener una exposición de 5 minutos y un interrogatorio de 10.

---

## 1. La frase que resume todo

> «El Atlas Global de Desastres es una aplicación web que convierte **10,907 desastres** registrados entre **2000 y 2026** en un **globo 3D interactivo**: cada país se colorea y se eleva según su impacto, todos los montos están en **pesos mexicanos** y al abrir un país aparece un panel con sus indicadores, su posición mundial y sus desastres más graves.»

Tres verbos para recordarlo: **limpio → agrego → muestro**.

La idea de fondo: *no se trata de graficar un archivo de Excel, se trata de construir un pipeline reproducible que va del dato crudo a una decisión visual.*

---

## 2. El mapa mental: una fábrica de datos en 7 estaciones

Imagina una línea de producción. En cada estación el dato cambia de forma y **nunca se pierde la trazabilidad**.

| # | Estación | Qué entra | Qué se hace | Qué sale |
|---|----------|-----------|-------------|----------|
| 1 | **Limpieza** | EM-DAT crudo (Excel/CSV) | Se revisan faltantes, tipos, fechas, coordenadas y duplicados | `EMDAT_integrado_WDI_validado.csv` · 10,907 filas × 69 columnas |
| 2 | **Geografía** | Dataset limpio + Natural Earth | Se unen por código ISO; alias y fusiones documentadas | 175 unidades cartográficas, 168 con datos |
| 3 | **Economía** | Banco Mundial (WDI) | PIB, población y superficie; PIB per cápita, densidad y conversión a MXN | `paises_socio.json` · 267 países |
| 4 | **Agregación** | Eventos + geografía + economía | Se agrupa por país: eventos, fallecidos, afectados, daño, promedios y rankings | `paises.geojson` · `metadatos.json` |
| 5 | **Capa 3D** | GeoJSON agregado | Color por una variable, altura por otra, más la deformación del relieve | Globo con `fill` + `fill-extrusion` |
| 6 | **Filtros** | `filtros.json` (eventos por año y tipo, por país) | El navegador recalcula totales al mover los controles | Mapa y KPIs actualizados sin recargar |
| 7 | **Panel por país** | `eventos_pais.json`, `owid.json`, `incendios_mexico.json` | KPIs, rankings, 3 gráficas, comparación de periodos y bloques de México/OWID | Modal detallado por país |

**Frase para el profesor:** «El notebook y los módulos de `src/` producen archivos ya listos; la aplicación solo los dibuja. Esa separación es lo que hace el proyecto reproducible y rápido.»

---

## 3. Las cinco fuentes de datos

| Fuente | Qué aporta | Cifras que debes citar |
|--------|------------|------------------------|
| **EM-DAT** (CRED / UCLouvain) | Base principal de desastres | 10,907 eventos · 220 países · 14 tipos · 2000–2026 |
| **Natural Earth 110m** | Límites territoriales para pintar el mapa | 175 unidades cartográficas |
| **WDI / Banco Mundial** | PIB, población y superficie | 267 países con población; 264 con PIB; 262 con superficie |
| **Our World in Data (OWID)** | Contexto y validación externa | 229 países; México 15,516,081 afectados |
| **CONAFOR** | Incendios forestales de México | 74,853 incendios · 7,285,908 ha · 2015–2025 |

**Fuente descartada (y por qué):** los atlas de riesgos estatales no se pudieron usar porque no existe una fuente nacional homogénea y descargable para los 32 estados. Se dice así, con transparencia, y se sustituye por CONAFOR y OWID.

---

## 4. El dataset en 7 cifras

| Dato | Valor | Por qué importa |
|------|-------|-----------------|
| Eventos | **10,907** | Es el tamaño de la base y la unidad de todo el análisis |
| Variables | **69** | Incluye fechas, geografía, impacto humano y daño económico |
| Países / territorios | **220** | Es el universo de EM-DAT |
| Tipos de desastre | **14** | Permite el filtro por tipo |
| Periodo | **2000–2026** | 27 años de registro homogéneo |
| Unidades en el mapa | **175** (168 con datos) | Es lo que Natural Earth 110m permite dibujar |
| Eventos agregados al mapa | **10,627** | Los otros 280 son territorios que no existen en esa capa (Hong Kong, Comoras, Tonga…) y **no se reasignan** para no inventar |

---

## 5. Recorrido paso a paso (lo que debes poder contar)

### 5.1 Limpieza (Actividad 1)

- Se conserva el archivo original y se trabaja sobre una copia.
- Se mide el faltante por columna: el daño económico solo existe en **30.4 %** de los eventos (3,312 de 10,907). **No se inventan datos**: se documenta y se advierte que los totales de daño son un **mínimo**.
- Se revisan tipos (fechas como texto), fechas imposibles (inicio después del fin), coordenadas fuera de rango y montos negativos.
- Se detectan 3 casos de fechas sospechosas y se marcan con banderas (`Requiere_revision_temporal`), sin borrar registros.
- Resultado: **10,907 filas × 69 columnas**, sin duplicados de `DisNo.`.

### 5.2 Integración geográfica

- La unión se hace por **código ISO de 3 letras**.
- Se documentan dos alias: **PSE → PSX** (Palestina) y **SSD → SDS** (Sudán del Sur).
- Dos fusiones cartográficas: **Chipre del Norte → Chipre** y **Somalilandia → Somalia**, sin sumar indicadores.
- Siete territorios se conservan **sin datos** (Sahara Occidental, Islas Malvinas, Groenlandia, etc.) y se pintan con un color neutro.
- Regla de oro del proyecto: **«sin datos» no significa «sin desastres»**; significa que EM-DAT no registró eventos que cumplieran sus criterios.

### 5.3 Integración socioeconómica

- PIB (`NY.GDP.MKTP.CD`), población (`SP.POP.TOTL`) y superficie (`AG.SRF.TOTL.K2`) del Banco Mundial.
- Se calculan dos indicadores derivados: **PIB per cápita** y **densidad de población**.
- **Toda la conversión a pesos se hace en el pipeline**, con un tipo de cambio fijo de **20.8 MXN/USD**. El navegador nunca convierte moneda.
- Ejemplo de México: PIB **38.07 billones MXN**, población **130,861,007**, superficie **1,957,194 km²**, densidad **66.9 hab/km²**, PIB per cápita **290,951 MXN**.

### 5.4 Agregación temática

Por cada país se calculan seis variables:

| Variable | Qué es | Escala sugerida |
|----------|--------|-----------------|
| `eventos` | Número de desastres | lineal |
| `fallecidos` | Suma de muertes | logarítmica |
| `afectados` | Suma de personas afectadas | logarítmica |
| `dano_ajustado` | Daño económico en MXN | logarítmica |
| `prom_fallecidos` | Muertes por evento | logarítmica |
| `prom_afectados` | Afectados por evento | logarítmica |

También se guardan los **estadísticos** (mínimo, mediana, p95, máximo) para construir la leyenda y los cortes de color sin recalcular en el navegador.

### 5.5 La capa 3D

- **Color:** una capa `fill` con una expresión de interpolación sobre la variable elegida.
- **Altura:** una capa `fill-extrusion` cuyo `fill-extrusion-height` depende de otra variable.
- **Deformación:** la misma extrusión, pero con base y altura continuas, se ve como relieve y no como bloques.
- El usuario puede combinar **dos variables a la vez** (por ejemplo, color = eventos, altura = fallecidos), que es justo lo que pide el enunciado.
- La **intensidad** de la rampa se ajusta con un control deslizante (mezcla cada color hacia su versión desaturada).

### 5.6 Filtros y controles (Actividad 4)

- **Periodo:** dos deslizadores (año inicial y final) entre 2000 y 2026.
- **Tipo de desastre:** catálogo de 14 tipos; «Todos los tipos» por defecto.
- **Recurso 3D:** elevación, deformación o ninguno.
- **Escala:** automática, lineal o logarítmica.
- **Capas complementarias:** incendios de CONAFOR (puntos de 50 ha o más) y territorios con indicadores.
- **Todo se recalcula en el navegador**: `filtros.json` ya trae los eventos resumidos por país, año y tipo (no los 10,907 registros completos), así que mover un control es instantáneo.
- **Comparación de periodos:** si existe un periodo anterior completo, se compara contra él; si no, se dividen las dos mitades del rango (el título lo dice). Ejemplo real de México: **2010–2019 vs 2000–2009** → 65 vs 64 eventos (+1.6 %), 1,259 vs 744 fallecidos (+69.2 %), 7,304,753 vs 6,768,415 afectados (+7.9 %), 781.6 vs 455.0 mil millones MXN (+71.8 %).

### 5.7 Panel por país (avance de la Actividad 5)

- **9 KPIs:** población, superficie, PIB, PIB per cápita, densidad, eventos, fallecidos, afectados y daño.
- **Rankings mundiales** sobre 220 territorios: eventos, víctimas (fallecidos + afectados) y daño.
- **Tres gráficas:** evolución anual, distribución por tipo y eventos de mayor impacto.
- **Comparación de periodos** y **listas de eventos** (impacto humano y daño económico).
- **Bloque México:** incendios por estado y por causa.
- **Bloque OWID:** afectados y eventos por tamaño, como validación externa.

---

## 6. Las cifras que tienes que saber

### 6.1 Mundo (2000–2026)

| Indicador | Valor | Cómo leerlo |
|-----------|-------|-------------|
| Eventos | **10,907** | — |
| Fallecidos | **1,737,592** | ≈ 1.74 millones |
| Afectados | **4,903,433,684** | ≈ 4.9 mil millones de personas |
| Daño económico | **108.2 billones MXN** | 1 billón = 1,000,000 de millones |
| Eventos con daño reportado | **30.4 %** | Por eso el total es un mínimo |
| Tipo más frecuente | **Inundación (39.4 %)** | 4,294 eventos |
| Segundo tipo | **Tormenta (26.9 %)** | 2,930 eventos |
| Tercero | **Epidemia (8.2 %)** | 895 eventos |

### 6.2 Países líderes

| Ranking | País | Valor |
|---------|------|-------|
| Más eventos | China | 675 |
| | Estados Unidos | 660 |
| | India | 436 |
| | Indonesia | 425 |
| | Filipinas | 406 |
| Mayor daño | Estados Unidos | 43.6 billones MXN |
| | China | 15.4 billones MXN |
| | Japón | 12.5 billones MXN |

### 6.3 México

| Indicador | Valor |
|-----------|-------|
| Eventos | **171** |
| Fallecidos | **2,631** |
| Afectados | **15,538,601** |
| Daño económico | **1.60 billones MXN** |
| PIB | **38.07 billones MXN** |
| Población | **130,861,007** |
| Superficie | **1,957,194 km²** |
| Densidad | **66.9 hab/km²** |
| PIB per cápita | **290,951 MXN** |
| Posición mundial | **#11 eventos · #35 víctimas · #10 daño** (de 220) |
| Tipos más frecuentes | Tormenta 84 · Inundación 50 · Terremoto 15 |

### 6.4 CONAFOR (México, 2015–2025)

| Indicador | Valor |
|-----------|-------|
| Incendios | **74,853** |
| Superficie afectada | **7,285,908 ha** (≈ 3.7 % del territorio nacional) |
| Puntos dibujados | **14,052** (los de 50 ha o más) |
| Estado con más superficie | **Guerrero** (979,268 ha) |
| Estado con más incendios | **Jalisco** (9,180) |
| Causa más frecuente | **Intencional** (13,379) |
| Segunda causa | Actividades agrícolas (11,720) |

### 6.5 Validación

| Comparación | Resultado |
|-------------|-----------|
| Afectados en México (EM-DAT vs OWID) | 15,538,601 vs 15,516,081 → **0.15 % de diferencia** |
| PIB de México (archivo vs módulo) | **38,074,177,670,649 MXN** en ambos |
| Filas del dataset | 10,907 antes y después de la limpieza |
| Duplicados de `DisNo.` | 0 |
| Prueba de la aplicación | 0 errores de JavaScript, 15 capturas |

### 6.6 Cómo se leen los montos en la app

| Sufijo | Significa | Ejemplo |
|--------|-----------|---------|
| `mil` | 1,000 | $950 mil MXN |
| `M` | millón (10⁶) | $4.5 M MXN |
| `MM` | mil millones (10⁹) | $163.8 MM MXN |
| `B` | billón (10¹²) | $1.60 B MXN |

**Consejo:** si te preguntan «¿cuánto es 1.60 B?», responde: «1.60 billones de pesos, es decir, 1,600,000 millones».

---

## 7. Las cinco decisiones que más te van a preguntar

1. **¿Por qué 2000–2026?**
   Porque es el periodo con registro más homogéneo de EM-DAT y evita comparar años con coberturas muy distintas. Son 27 años y 10,907 eventos.

2. **¿Por qué pesos y por qué 20.8?**
   Porque el proyecto se entrega en México y el profesor pidió montos en pesos. El tipo de cambio es fijo **para que la cifra sea reproducible**: si mañana cambia el dólar, la app no cambia de número. La conversión ocurre una sola vez, en `src/moneda.py`.

3. **¿Por qué escala logarítmica?**
   Porque los valores van de 1 a miles de millones. Con escala lineal, un solo evento gigante aplasta a los demás y el mapa se ve casi vacío. El logaritmo reparte mejor los colores y deja ver los países pequeños.

4. **¿Por qué hay territorios «sin datos»?**
   Porque Natural Earth incluye 175 unidades y EM-DAT no registró eventos para todas. Se pintan en color neutro y **no se reasignan** a otro país: eso sería inventar información. «Sin datos» ≠ «sin desastres».

5. **¿Por qué no se aplicó balanceo?**
   Porque el proyecto es **descriptivo**, no entrena un clasificador. Aun así se analizó: la clase mayoritaria es Inundación (4,294) y la minoritaria Incidente con animales (1), una razón de **4,294 a 1**. Si se equilibrara quitando eventos, se perdería el 99.9 % del dataset. Se documentó y se recomendó, para un modelo futuro, usar **pesos por clase** en lugar de borrar registros.

---

## 8. La identidad visual en 30 segundos

- **Paleta:** púrpura `#4C1D95`, rosa `#FA8A9A`, amarillo `#FFB71B`, rojo `#EE3E29`, coral `#FF8A5F`.
- **Tipografía:** **Poppins** para títulos (sustituto libre de la del brand guide) y **Open Sans** para texto.
- **Océano azul** `#1B4576` para separar el planeta del fondo púrpura `#2B1055`; la atmósfera es púrpura `#7C3AED`.
- **Por qué:** un mapa de desastres debe leerse rápido; los tonos cálidos marcan el impacto y el azul frío deja descansar la vista. La app es responsive (escritorio, tableta y móvil).

---

## 9. Cómo se valida que el proyecto está bien

1. **Conteo:** 10,907 filas antes y después; 0 duplicados de `DisNo.`.
2. **Sumas:** los totales del mapa coinciden con los del dataset (México: 171 eventos, $1.60 B MXN).
3. **Fuente externa:** OWID reporta 15,516,081 afectados en México y EM-DAT 15,538,601 → 0.15 % de diferencia.
4. **Coherencia interna:** el PIB de México calculado por el módulo es idéntico al del archivo integrado.
5. **Prueba funcional:** recorrido automatizado con Playwright sobre 15 vistas; **0 errores de página**.

---

## 10. Guion de 3 minutos (para decir, no para leer)

> «Este es el Atlas Global de Desastres. Trabaja con 10,907 desastres registrados por EM-DAT entre 2000 y 2026 en 220 países, y los combina con el PIB, la población y la superficie del Banco Mundial. Todo el proceso está en un notebook y en módulos de Python: primero limpio los datos, luego los uno con la geografía por código ISO, después agrego los indicadores económicos y finalmente resumo cada país.
>
> El resultado es un globo 3D. El color representa una variable y la altura otra; se pueden combinar, por ejemplo, color por número de desastres y altura por fallecidos. Los filtros de año y tipo se recalculan en el navegador, sin servidor, porque los datos ya vienen resumidos.
>
> Al hacer doble clic en un país se abre su panel: nueve indicadores, su posición mundial, la evolución de sus desastres, la comparación con el periodo anterior y sus eventos más graves. En México, además, se muestran los incendios de CONAFOR: 74,853 incendios y 7.3 millones de hectáreas entre 2015 y 2025.
>
> Un dato que me gusta citar: México tiene 171 desastres, 15.5 millones de afectados y 1.60 billones de pesos en daños; es el lugar 11 del mundo en número de eventos y el 10 en daño económico. Y para comprobar que los datos son consistentes, comparé los afectados con Our World in Data: la diferencia es de 0.15 %.»

---

## 11. Las 20 preguntas probables (y sus respuestas)

**1. ¿Por qué EM-DAT y no otra base?**
Porque es el estándar académico, tiene criterios de inclusión homogéneos y cubre 1900–2026. Su límite es el subregistro en países con menos capacidad de reporte; por eso se complementa con OWID y CONAFOR, y se advierte en la nota metodológica.

**2. ¿Qué criterios usa EM-DAT para registrar un desastre?**
Al menos 10 muertos, 100 afectados, declaración de emergencia o solicitud de ayuda internacional. Eso explica por qué faltan eventos pequeños.

**3. ¿Por qué hay 220 países en los datos y solo 175 en el mapa?**
Porque 220 es el universo de códigos ISO de EM-DAT y 175 es lo que la capa Natural Earth 110m dibuja. La diferencia son territorios pequeños o dependientes que no están en esa versión.

**4. ¿Entonces el mapa pierde eventos?**
Sí, 280 de 10,907 (2.6 %). Se conservan en el dataset y en el panel por país, pero no se pintan para no asignarlos a otro territorio sin evidencia.

**5. ¿Por qué México es #10 en daño y #35 en víctimas?**
Porque son dos cosas distintas: el daño mide pérdidas económicas y México ha tenido eventos muy costosos (sismos, huracanes); las víctimas suman fallecidos y afectados, donde otros países con sequías o inundaciones masivas tienen cifras mayores.

**6. ¿Cómo evitas que un evento extremo arruine el mapa?**
Con escala logarítmica y con estadísticos robustos: la leyenda usa la mediana y el percentil 95, no solo el máximo.

**7. ¿Qué significa «daño ajustado»?**
Que EM-DAT ya corrigió la inflación y lo expresó en dólares de 2024; después el pipeline lo convierte a pesos con 20.8.

**8. ¿Por qué solo 30 % de los eventos tiene daño?**
Porque reportar pérdidas es voluntario y muchos países no lo hacen. Se conserva el dato faltante y se advierte que cualquier total de daño es un **mínimo**, no el total real.

**9. ¿El mapa está en tiempo real?**
No. Es un corte histórico 2000–2026 preparado con anticipación. «Tiempo real» sería otra arquitectura (API y base de datos).

**10. ¿Cómo funcionan los filtros sin servidor?**
`filtros.json` guarda los eventos ya resumidos por país, año y tipo. Al mover el control, el navegador suma esos valores y actualiza colores, alturas y KPIs en milisegundos.

**11. ¿Cómo se calcula la comparación de periodos?**
Se busca el periodo anterior de la misma duración. Si no existe completo dentro de 2000–2026, se dividen las dos mitades del rango y se avisa en el título; por eso a veces se lee «2000–2013 contra 2014–2026».

**12. ¿Por qué a veces el daño sube mucho y los eventos casi no cambian?**
Porque el daño depende de uno o dos eventos costosos y de la cobertura de reporte, no solo de la cantidad. Es una limitación de la fuente, no del cálculo.

**13. ¿Qué es exactamente la deformación?**
Es una extrusión continua: la base y la altura siguen el valor de la variable, así que el país se ve como relieve. La elevación normal son prismas; la deformación es la misma técnica con transición suave.

**14. ¿Por qué un globo y no un mapa plano?**
Porque el globo no deforma las áreas y da la sensación 3D que pide el proyecto. Aun así existe el botón **Plano** (Mercator) para comparar y para quien prefiera leer el mundo completo.

**15. ¿Cómo validaste los datos?**
Con cinco comprobaciones: conteo de filas, duplicados, sumas contra el dataset, comparación externa con OWID y una prueba automatizada de la interfaz. Todas dieron positivo.

**16. ¿Por qué no hay un modelo que prediga desastres?**
Porque el objetivo es **descriptivo y exploratorio**: mostrar dónde y cuándo ocurren. Predecir exigiría otra unidad de análisis, variables climáticas y una validación temporal distinta.

**17. ¿Por qué no balanceaste las clases si lo pide la actividad?**
Se analizó y se documentó. El balanceo aplica a modelos de clasificación; aquí se describe el universo completo. Equilibrar implicaría borrar el 99.9 % de los eventos.

**18. ¿Qué pasa si el tipo de cambio cambia?**
Nada dentro de la app: la conversión ya está hecha y documentada. Para actualizarla se cambia una constante y se vuelve a correr el pipeline.

**19. ¿Por qué el océano es azul si la marca es púrpura?**
Porque el azul separa el agua del fondo púrpura y hace que el planeta se lea como planeta. El cielo y la atmósfera conservan el púrpura de la marca; el azul solo se usa en el agua.

**20. ¿Qué mejorarías con más tiempo?**
Imputar el daño con un modelo documentado, sumar más fuentes nacionales, cachear la app para uso sin internet, agregar pruebas automáticas de datos y mejorar la accesibilidad (lectores de pantalla y navegación por teclado).

---

## 12. Trampas al exponer (evítalas)

| No digas | Di |
|----------|-----|
| «10,907 países» | «10,907 eventos en 220 países» |
| «1.60 B son 1.60 mil millones» | «1.60 B son 1.60 billones = 1,600,000 millones» |
| «El mapa predice» | «El mapa describe y compara» |
| «Los datos están en tiempo real» | «Es un corte histórico 2000–2026» |
| «El daño total del mundo es 108 billones» (sin aclarar) | «Es el daño **reportado**, un mínimo: solo 30 % de los eventos lo tiene» |
| «México es el país 11 del mundo» (sin contexto) | «México es el lugar 11 en **número de eventos** de 220» |
| «Los territorios grises no tienen desastres» | «No tienen datos registrados en EM-DAT para ese periodo» |

---

## 13. Glosario mínimo

- **Evento / desastre:** un registro de EM-DAT con un `DisNo.` único.
- **ISO:** código de tres letras del país (MEX, USA, BRA).
- **Agregación:** resumir muchos eventos en un valor por país.
- **GeoJSON:** formato de datos geográficos que entiende el mapa.
- **fill / fill-extrusion:** capa plana y capa con altura en MapLibre.
- **Escala logarítmica:** comprime los valores grandes para que todos se vean.
- **p95:** valor que deja por debajo al 95 % de los datos; se usa para que un caso extremo no deforme la leyenda.
- **Pipeline:** la cadena de pasos que va del dato crudo al archivo final.

---

## 14. Demostración en 6 clics (para el día de la exposición)

1. Abrir la app (`python -m src.servir_app`).
2. Clic en **México** → se llena la ficha del territorio.
3. **Doble clic** en México → se abre el panel con los 9 KPIs y los rankings.
4. Pestaña **Filtros** → mover a 2010–2019 → «Aplicar los filtros al mapa».
5. Volver a abrir México → bajar hasta **«Periodo actual contra periodo anterior»**.
6. Pestaña **Capa** → activar **Incendios forestales de México** → hacer zoom a México.

**Cierre sugerido:** «Con esto se ve el ciclo completo: el dato se limpia, se integra, se resume, se pinta y se explica. No es solo un mapa bonito: es un pipeline reproducible que cualquiera puede volver a correr.»
