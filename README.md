# Atlas Global de Desastres

Aplicación web interactiva que visualiza, explora y analiza espacialmente la
ocurrencia de desastres naturales a nivel mundial, con énfasis en México, a
partir del conjunto de datos **EM-DAT** (CRED) integrado con indicadores
socioeconómicos del **Banco Mundial (WDI)**, datos de incendios de **CONAFOR**,
la base histórica de **CENAPRED** para el detalle estatal de México y series de
contexto de **Our World in Data (OWID)**.

* **Asignatura:** Análisis y exploración de datos
* **Profesor:** PhD. Fernando Pech-May
* **Institución:** Instituto Tecnológico Superior de los Ríos
* **Carrera:** Ingeniería en Sistemas Computacionales

---

## Estado de las actividades

| # | Actividad | Estado | Entregable |
|---|-----------|--------|------------|
| 1 | Limpieza, depuración y agregación de datos | ✅ Completada | Notebook + dataset integrado + EDA |
| 2 | Integración del mapa base y límites territoriales | ✅ Completada | Notebook + app de muestra |
| 3 | **Capa de visualización temática** | ✅ **Completada** | Notebook + `app/` + GeoJSON + pipeline |
| 4 | **Filtros y controles interactivos** | ✅ **Completada** | Panel de filtros + globo + capa de incendios |
| 5 | **Panel de información y visualizaciones por país** | ✅ **Completada** | Notebook 06 + modal ampliado (indicadores, cobertura y gráficas) |
| 5·M | **México por estados (CENAPRED)** | ✅ **Completada** | Pestaña México + vista estatal + notebook 05 |
| 6 | **Integración de la interfaz de usuario** | ✅ **Completada** | Notebook 07 + `ui_shell.js` + auditoría automática |
| 7 | Validación de resultados | ⏳ Pendiente | — |

---

## Actividad 1 — Limpieza, depuración y agregación

El notebook `notebooks/01_actividad1_preprocesamiento_eda.ipynb` documenta el
proceso completo sobre los 10,907 registros y 69 columnas de EM-DAT:

| Etapa | Contenido |
|-------|-----------|
| 1 | Carga, auditoría de calidad y primeras gráficas exploratorias |
| 2 | Tratamiento de valores faltantes y reporte de disponibilidad |
| 3 | Revisión de tipos, fechas y coordenadas |
| 4 | Integración geográfica con Natural Earth (175 unidades, 220 territorios) |
| 5 | Validación temporal e integridad del conjunto |
| 6 | Codificación, escalado y balanceo + validación de la integración WDI |

**Decisiones relevantes de la Etapa 6:**

* **Codificación:** `Tipo_codigo` (entero estable) y one-hot para el grupo del
  desastre. El catálogo se guarda en `resultados/tablas/catalogo_tipos_desastre.csv`.
* **Escalado:** versión min-max y logarítmica de fallecidos, afectados y daño,
  con evidencia gráfica de por qué la escala logarítmica representa mejor los
  eventos extremos.
* **Balanceo:** se documenta el desbalance entre tipos (razón mayoritaria /
  minoritaria) y se justifica **no aplicarlo**, porque el atlas es descriptivo.
  Se advierte que un modelo futuro debería usar pesos por clase antes que
  eliminar registros.
* **Integración socioeconómica:** PIB, población y superficie del Banco Mundial,
  con el PIB convertido a pesos mexicanos en el pipeline.

---

## Actividad 3 — Capa de visualización temática

La Actividad 3 diseña e implementa una **capa temática sobre el mapa 3D** que
representa las variables de desastres mediante cuatro recursos visuales:

| Recurso visual | Implementación técnica | Variable de ejemplo |
|----------------|------------------------|---------------------|
| **Coloración** | Capa `fill` con expresión de color interpolada | Número de desastres |
| **Intensidad de color** | Ajuste de saturación de la rampa (control deslizante) | — |
| **Elevación** | Capa `fill-extrusion` sobre el globo: prisma con altura ∝ valor | Fallecidos |
| **Deformación de la superficie** | `fill-extrusion` con base y altura en relieve continuo | Personas afectadas |

El usuario puede **seleccionar simultáneamente dos variables** (una para el
color y otra para la altura), tal como pide el enunciado del proyecto.

### Organización de la entrega

La Actividad 3 sigue la misma forma de trabajo de las Actividades 1 y 2:

* **Notebook narrador:** `notebooks/03_actividad3_capa_tematica.ipynb`
  ejecuta el motor paso a paso y presenta la evidencia (tablas, controles de
  integridad, gráficas y estadísticos).
* **Motor reutilizable:** `src/capa_tematica.py` hace el trabajo pesado
  (agregación, integración geográfica y exportación), de modo que el notebook
  y cualquier otra herramienta consuman la misma lógica sin duplicar código.
* **Aplicación web:** `app/` dibuja la capa en 3D sobre el globo de MapLibre GL.

### Variables temáticas disponibles

* Número de desastres (`eventos`)
* Fallecidos totales (`fallecidos`)
* Personas afectadas (`afectados`)
* Daño económico ajustado (`dano_ajustado`)
* Fallecidos promedio por evento (`prom_fallecidos`)
* Afectados promedio por evento (`prom_afectados`)

### Tecnologías

* **Frontend:** HTML5, CSS3 y **JavaScript vanilla** (ES6, sin frameworks).
* **Visualización 3D:** MapLibre GL JS (globo 3D, elevación y relieve).
* **Backend / pipeline:** Python (pandas, GeoPandas, NumPy).
* **Formato de la capa personalizada:** GeoJSON.

> Plotly/Dash (usado en la Actividad 2) solo permite coloración; MapLibre GL
> permite además **elevación y deformación reales en 3D**, por lo que es el
> motor de la capa temática.

---

## Actividad 4 — Filtros y controles interactivos

El panel lateral organiza los controles en cuatro pestañas:

| Pestaña | Controles |
|---------|-----------|
| **Resumen** | Indicadores del mapa (territorios, cobertura, máximo y mediana), ficha del territorio seleccionado y paleta temática |
| **Filtros** | Rango de años (2000–2026), tipo de desastre (14 tipos), aplicar al mapa y restablecer |
| **Capa** | Variable de color, variable de altura, recurso 3D (elevación / deformación / ninguno), intensidad de la rampa, altura del relieve, escala y capa de incendios de CONAFOR |
| **México** | Resumen CENAPRED, acceso al mapa por estados y las cuatro fichas de desastres |

Todos los filtros se aplican **en el navegador** sobre la capa ya agregada: al
mover el rango de años o cambiar el tipo de desastre, el mapa y los KPIs se
recalculan sin volver a descargar datos.

### Comportamiento relevante

* **Comparación de periodos.** Al filtrar un rango de años, el panel compara
  ese periodo con el anterior de la misma duración. Si no existe un periodo
  anterior completo dentro de 2000–2026, divide el rango seleccionado en dos
  mitades y lo indica en el título.
* **Capa de incendios.** Se dibujan los incendios de 50 ha o más registrados
  por CONAFOR (2015–2025) como puntos; el detalle por estado y causa se muestra
  en el panel de México.
* **Doble clic en un país.** Abre el panel detallado con 9 KPIs, indicadores de
  impacto relativo, posición mundial en eventos/fallecidos/afectados/daño,
  cuatro gráficas (evolución, impacto humano, daño y tipos), cobertura de los
  datos, comparación de periodos, los eventos más relevantes y, para México, el
  bloque de incendios y el contexto de OWID.
* **Vista de México.** La pestaña México abre el mapa estatal con filtros,
  panel por entidad y las cuatro fichas; se detalla en la sección siguiente.

### Actividad 5 — Panel de información y visualizaciones por país

El modal `#modal-pais` se abre con doble clic en un país (o desde la ficha
lateral) y se alimenta de `app/datos/eventos_pais.json` (10,907 eventos en 220
territorios), `app/datos/paises_socio.json` (267 países con PIB, población,
superficie y densidad) y `app/datos/filtros.json`. El notebook
`notebooks/06_actividad5_panel_pais.ipynb` define y audita todos los
indicadores.

#### Variables e indicadores

| Bloque | Indicadores |
|--------|-------------|
| **Información general** | Población, superficie, PIB, PIB por habitante y densidad |
| **Desastres** | Eventos, años con registros, fallecidos, afectados y daño económico |
| **Impacto relativo** | Afectados por 100 mil habitantes, daño sobre el PIB anual, fallecidos por evento, daño por evento, daño por afectado y eventos por año |
| **Rankings mundiales** | Posición en eventos, fallecidos, afectados y daño |
| **Calidad** | Cobertura de fallecidos, afectados y daño; cobertura temporal; completitud promedio y nivel |

#### Visualizaciones

* **Evolución temporal** de eventos y fallecidos, con ejes separados.
* **Impacto humano por año**: barras de fallecidos y línea de afectados.
* **Daño económico por año**, en pesos mexicanos.
* **Distribución por tipo** con selector de medida: eventos, fallecidos,
  afectados o daño.
* **Comparación de periodos** de la misma duración.
* **Eventos destacados** por impacto humano y por daño.
* **Bloques de México (CONAFOR)** y **OWID** como contexto externo.

#### Adaptación a los datos disponibles

La disponibilidad se calcula sobre los eventos crudos: un `null` de EM-DAT
significa **no reportado**, no cero. El panel aplica estas reglas:

* Si falta población o PIB en el WDI (17 territorios, p. ej. Taiwán), los
  ratios dependientes se muestran como **«Sin datos»** y se indica qué falta.
* Si el periodo y el tipo no tienen eventos, los promedios y las gráficas
  muestran un **aviso de vacío**; el KPI de eventos queda en 0.
* Si no hay fallecidos, afectados o daño reportados, el KPI y los ratios
  correspondientes se muestran como **«Sin datos»**, nunca como cero.
* La **cobertura por campo** y la **completitud promedio** acompañan a los
  promedios; una cobertura baja se marca como tal.
* 52 territorios de EM-DAT no tienen polígono en el GeoJSON: no aparecen en el
  mapa y el panel se abre solo para los 168 territorios dibujables con eventos.

#### Cifras de la auditoría (2000–2026)

| Indicador | Valor |
|-----------|------:|
| Territorios en EM-DAT | 220 |
| Territorios con población y PIB para ratios | 201 |
| Cobertura mediana de fallecidos | 61.5 % |
| Cobertura mediana de afectados | 86.3 % |
| Cobertura mediana de daño | 17.2 % |
| Cobertura temporal mediana | 63.0 % |
| Completitud promedio mediana | 55.2 % |
| Calidad alta / media / baja | 26 / 161 / 33 |

#### Evidencia generada

* `notebooks/06_actividad5_panel_pais.ipynb` (ejecutado).
* `resultados/tablas/actividad5_cobertura_pais.csv`
* `resultados/tablas/actividad5_indicadores_pais.csv`
* `resultados/graficas/actividad5_panel_completitud.png`
* `resultados/graficas/actividad5_panel_cobertura_campos.png`
* `resultados/graficas/actividad5_panel_dano_pib.png`

> La vista mundial usa EM-DAT y la vista estatal de México usa CENAPRED. No se
> suman porque las metodologías y los universos de eventos son distintos.

---

## México por estados — CENAPRED (ampliación)

La vista mundial usa EM-DAT y trata a México como un solo país. Para que México
**destaque** con información detallada por entidades, se integró la *Base
histórica de impacto socioeconómico 2000–2024* de **CENAPRED / Atlas Nacional
de Riesgos** y se construyó una vista propia con las 32 entidades.

### Qué incluye

* **Pestaña México** en el panel, con resumen, accesos y las cuatro fichas.
* **Vista de pantalla completa** con mapa coroplético de los 32 estados
  (MapLibre GL).
* **Filtros** de variable (daños, defunciones, afectados, eventos, viviendas),
  rango de años (2000–2024) y tipo de fenómeno.
* **Panel estatal** con participación nacional, KPIs, lugar nacional y los
  eventos más costosos del filtro; al elegir un estado se coloca al frente.
* **Cuatro fichas** de desastres con descripción, métricas, fuente y un botón
  para centrar el estado en el mapa.

### Cifras (2000–2024, solo fenómenos naturales)

| Indicador | Valor |
|-----------|-------|
| Registros naturales | 4,182 |
| Filas estado-evento | 4,195 (32 estados) |
| Defunciones | 5,181 |
| Población afectada | 59,761,863 |
| Daños | **687.0 mil millones de pesos** |
| Viviendas dañadas | 2,576,168 |

### Estados con mayor daño acumulado

| Lugar | Estado | Daños (mil M MXN) | Participación |
|------:|--------|------------------:|--------------:|
| 1 | Guerrero | 131.1 | 19.1 % |
| 2 | Veracruz | 80.0 | 11.6 % |
| 3 | Tabasco | 71.9 | 10.5 % |
| 4 | Chiapas | 56.2 | 8.2 % |
| 5 | Ciudad de México | 45.3 | 6.6 % |

### Los cuatro desastres destacados

| Desastre | Año | Estado | Daños (mil M MXN) | Defunciones | % del daño estatal |
|----------|----:|--------|------------------:|------------:|-------------------:|
| Huracán Otis | 2023 | Guerrero | 84.2 | 52 | 64.2 % |
| Sismo del 19S | 2017 | Ciudad de México | 44.0 | 228 | 97.1 % |
| Inundación de Tabasco 2007 | 2007 | Tabasco | 31.9 | 0 | 44.3 % |
| Inundación de Tabasco 2020 | 2020 | Tabasco | 13.6 | 10 | 18.9 % |

### Decisiones metodológicas

* **Solo fenómenos naturales:** clasificaciones *Hidrometeorológico*,
  *Geológico* y *Sanitario*. Se excluyen sociorganizativos y químicos.
* **Incendios forestales:** se consultan en la capa de CONAFOR para no
  duplicar el mismo fenómeno.
* **Montos en pesos:** CENAPRED ya reporta en MXN; **no** se aplica tipo de
  cambio.
* **Registros multiestado:** 11 filas se reparten en partes iguales entre los
  estados mencionados (0.3 % de los registros).
* **Menciones nacionales:** 4 filas (`Todo el país`, `Varios Estados`) no se
  pueden ubicar en un mapa estatal; se excluyen del mapa (6.2 mil M MXN, 121
  defunciones y 508 mil afectados) y se documentan en el notebook.
* **Comparación con EM-DAT:** no son comparables. EM-DAT reporta ~1.60 billones
  de pesos para México; CENAPRED reporta 687 mil M para fenómenos naturales.
  Cambian cobertura, clasificación y metodología, por eso la vista mundial usa
  EM-DAT y la estatal usa CENAPRED.

### Cómo regenerarlo

```bash
python -m src.mexico_estados       # JSON estatal + GeoJSON + tabla resumen
```

El notebook `notebooks/05_actividad5_mexico_estados.ipynb` documenta la fuente,
la limpieza, la homologación, los agregados, las fichas y la validación. Las
gráficas quedan en `resultados/graficas/mexico/`.

---

## Actividad 6 — Integración de la interfaz de usuario

La Actividad 6 une el mapa 3D, la capa temática, los filtros, los controles y
el panel por país en una sola experiencia. **No rediseña la apariencia**: el
panel lateral, la paleta y los componentes visuales se conservan; se añade la
capa que coordina las piezas.

### Cómo se integra

El módulo `app/js/ui_shell.js` escucha los eventos que emite `app.js` y
mantiene un estado de interfaz único:

| Evento | Efecto en la interfaz |
|--------|------------------------|
| `atlas:filtros` | Chips de filtros activos, barra de sincronización y anuncio accesible |
| `atlas:seleccion` | Ficha del país, pestaña Resumen, enlace profundo y anuncio |
| `atlas:modal` | Aviso de apertura/cierre y gestión de foco |
| `atlas:proyeccion` | Persistencia globo/plano y actualización de la dirección |
| `atlas:pestana` | Persistencia de la pestaña y enlace profundo |
| `atlas:mexico` | Dirección `#mexico=1` y anuncio de la vista estatal |
| `atlas:listo` | Restaura la vista guardada y valida el estado inicial |

Otras piezas de la integración:

* **Buscador de países** con navegación por teclado (`↑`, `↓`, `Enter`,
  `Esc`) y centrado del mapa sobre el territorio elegido.
* **Enlaces profundos** como `#pais=MEX&pestana=filtros&proyeccion=plano`.
* **Persistencia ligera** de pestaña y proyección en `localStorage`.
* **Atajos**: `/` busca, `1`–`4` cambian de pestaña, `G` globo, `P` plano,
  `M` México, `?` abre la ayuda y `Esc` cierra.
* **Accesibilidad**: enlaces para saltar, regiones vivas, foco visible,
  etiquetas ARIA, `prefers-reduced-motion`, contraste AA y tamaños táctiles.
* **Capacidad de respuesta**: en pantallas de hasta 900 px el panel se vuelve
  una hoja inferior colapsable con botón, cierre explícito y foco gestionado.

### Validación automática

`src/validar_ui.py` ejecuta **35 comprobaciones** sobre HTML, CSS y JS:

```bash
python -m src.validar_ui
```

Genera `resultados/tablas/validacion_ui.csv` con los resultados de:

* Coherencia entre los IDs que usa el JavaScript y los del HTML (64 IDs).
* Duplicados, roles de pestaña, paneles, diálogos y referencias ARIA.
* Botones con nombre accesible, campos etiquetados y regiones vivas.
* Emisión y escucha de los 7 eventos de sincronización.
* Presencia de foco visible, movimiento reducido y tamaños táctiles.
* Contraste WCAG AA de los 12 pares de color usados como texto
  (mínimo medido: **4.57:1**).

### Evidencia generada

* `notebooks/07_actividad6_integracion_ui.ipynb` (ejecutado).
* `resultados/tablas/validacion_ui.csv`
* `resultados/graficas/integracion_ui/01_escritorio_resumen.png`
* `resultados/graficas/integracion_ui/02_escritorio_filtros.png`
* `resultados/graficas/integracion_ui/03_escritorio_buscador.png`
* `resultados/graficas/integracion_ui/04_modal_pais.png`
* `resultados/graficas/integracion_ui/05_ayuda_atajos.png`
* `resultados/graficas/integracion_ui/06_movil_mapa.png`
* `resultados/graficas/integracion_ui/07_movil_panel.png`
* `resultados/graficas/integracion_ui/08_mexico_estados.png`
* `resultados/graficas/integracion_ui/contraste_wcag.png`

---

## Identidad visual

La interfaz usa la paleta institucional del brand guide y tipografía
**Poppins** (títulos) y **Open Sans** (texto):

| Color | Uso |
|-------|-----|
| `#4C1D95` púrpura | Color principal, océano del globo, encabezados |
| `#FA8A9A` rosa | Acentos, degradados y series secundarias |
| `#FFB71B` amarillo | Rampa de valores, énfasis y botones |
| `#EE3E29` rojo | Alertas, daño económico y valores altos |
| `#FF8A5F` coral | Transiciones del degradado |
| `#1B4576` azul océano | Agua del globo, para separarla del fondo |
| `#FAF6F1` fondo cálido | Superficie de la interfaz |

El degradado de marca (`#FFB71B → #FA8A9A → #4C1D95`) se usa en el encabezado,
las tarjetas y los títulos del panel. El agua del globo va en azul profundo y el
cielo que rodea al planeta conserva el púrpura de la marca, de modo que el
océano y el fondo se distinguen a primera vista.

---

## Estructura del proyecto

```
PROYECTO_DESASTRES/
├── app/                         Aplicación web
│   ├── index.html               Interfaz, pestañas, modal por país y vista México
│   ├── css/estilos.css          Identidad visual completa
│   ├── js/
│   │   ├── config.js            Rutas, paletas y vista inicial del globo
│   │   ├── escalas.js           Escalas de color (lineal/log) e interpolación
│   │   ├── leyenda.js           Leyenda temática dinámica
│   │   ├── estado.js            Barra de estado y tarjetas
│   │   ├── diccionario_desastres.js  Nombres de desastres en español
│   │   ├── capa_tematica.js     Capas 3D (color, elevación, deformación)
│   │   ├── mexico_estados.js    Vista estatal: mapa, filtros, panel y fichas
│   │   ├── app.js               Orquestador: filtros, modal, indicadores y rankings
│   │   └── ui_shell.js          Integración: eventos, chips, buscador, atajos y móvil
│   └── datos/
│       ├── paises.geojson       Capa agregada (175 unidades cartográficas)
│       ├── metadatos.json       Variables y estadísticos globales
│       ├── filtros.json         Catálogo de años y tipos para los controles
│       ├── paises_socio.json    PIB, población y superficie por país (267)
│       ├── eventos_pais.json    Eventos por país (10,907 en 220 territorios)
│       ├── owid.json            Contexto OWID por país
│       ├── incendios_mexico.json    Incendios CONAFOR por año, estado y causa
│       ├── incendios_puntos.geojson Incendios de 50 ha o más
│       ├── mexico_estados.json  Indicadores estatales CENAPRED (32 estados)
│       └── estados_mexico.geojson   Polígonos de los 32 estados (clave ISO)
├── datos/
│   ├── originales/              Fuentes crudas (EM-DAT, WDI, CONAFOR, OWID, CENAPRED)
│   ├── procesados/              Dataset limpio e integrado
│   └── geograficos/             Natural Earth 110m y GeoJSON de los estados
├── notebooks/
│   ├── 01_actividad1_preprocesamiento_eda.ipynb
│   ├── 02_actividad2_mapa_base.ipynb
│   ├── 03_actividad3_capa_tematica.ipynb
│   ├── 04_actividad4_filtros_controles.ipynb
│   ├── 05_actividad5_mexico_estados.ipynb
│   ├── 06_actividad5_panel_pais.ipynb
│   └── 07_actividad6_integracion_ui.ipynb
├── src/                         Código fuente del pipeline
│   ├── config.py                Rutas centralizadas y tipo de cambio
│   ├── moneda.py                Conversión de montos a pesos mexicanos
│   ├── integracion_paises.py    PIB, población y superficie (WDI)
│   ├── capa_tematica.py         Construcción de la capa temática
│   ├── detalle_pais.py          Eventos por país para el modal
│   ├── mexico_conafor.py        Incendios de México (CONAFOR)
│   ├── mexico_estados.py        Impacto estatal de México (CENAPRED)
│   ├── owid.py                  Contexto y validación con OWID
│   ├── generar_filtros.py       Catálogo de filtros
│   ├── diccionario_desastres.py Nombres de desastres en español
│   ├── servir_app.py            Servidor local de la aplicación
│   ├── capturas.py              Generación de capturas (reporte)
│   ├── validar_ui.py            Auditoría de accesibilidad e integración
│   └── capturas_ui.py           Capturas de la interfaz integrada (Actividad 6)
├── resultados/                  Evidencia: tablas, gráficas y capturas
└── reportes/                    Reportes de cada actividad
```

---

## Instalación y uso

### 1. Requisitos

```bash
pip install -r requirements.txt
```

### 2. Regenerar los datos de la aplicación

Cada módulo es independiente y escribe sus archivos en `app/datos/`:

```bash
python -m src.integracion_paises   # PIB, población y superficie (WDI)
python -m src.capa_tematica        # capa agregada + metadatos
python -m src.generar_filtros      # catálogo de años y tipos
python -m src.detalle_pais         # eventos por país (modal)
python -m src.owid                 # contexto de OWID
python -m src.mexico_conafor       # incendios de México (CONAFOR)
python -m src.mexico_estados       # impacto estatal de México (CENAPRED)
```

Esto produce `paises.geojson`, `metadatos.json`, `filtros.json`,
`paises_socio.json`, `eventos_pais.json`, `owid.json`, `incendios_mexico.json`,
`incendios_puntos.geojson`, `mexico_estados.json`, `estados_mexico.geojson` y
la evidencia tabular en `resultados/tablas/`.

> Todos los montos se convierten a **pesos mexicanos en el pipeline**, con el
> tipo de cambio fijo de `src/config.py`. El navegador nunca hace conversiones
> de moneda.

El notebook `06_actividad5_panel_pais.ipynb` no genera datos para la app: audita
la cobertura de los campos y calcula los indicadores derivados que el modal
resuelve en el navegador. Para reproducirlo:

```bash
jupyter nbconvert --to notebook --execute --inplace notebooks/06_actividad5_panel_pais.ipynb
```

El notebook de la Actividad 6 audita la integración y la accesibilidad:

```bash
jupyter nbconvert --to notebook --execute --inplace notebooks/07_actividad6_integracion_ui.ipynb
```

### 3. Ejecutar la aplicación web

La aplicación consume el GeoJSON con `fetch`, por lo que debe servirse por HTTP
(no abrir `index.html` directamente con `file://`):

```bash
python -m src.servir_app          # abre el navegador automáticamente
```

o manualmente:

```bash
cd app
python -m http.server 8000
```

Luego abre <http://localhost:8000> en el navegador.

### 4. Validar la interfaz y generar capturas (opcional)

La auditoría de accesibilidad e integración se puede repetir en cualquier
momento:

```bash
python -m src.validar_ui
```

Las capturas ya vienen incluidas en `resultados/graficas/capa_tematica/` y
`resultados/graficas/integracion_ui/`, por lo que **no es necesario
regenerarlas**. Solo hay que repetir este paso si se modifica algo visual:

```bash
pip install playwright
playwright install chromium
python -m src.capturas          # capa temática (Actividad 3)
python -m src.capturas_ui       # interfaz integrada (Actividad 6)
```

---

## Metodología de integración geográfica

Heredada de la Actividad 2 y aplicada en `src/capa_tematica.py`:

* **Equivalencias de código:** `PSE → PSX` (Estado de Palestina),
  `SSD → SDS` (Sudán del Sur).
* **Fusiones cartográficas:** Chipre del Norte (`CYN`) se integra con Chipre
  (`CYP`); Somalilandia (`SOL`) con Somalia (`SOM`), sin sumar indicadores.
* **Territorios sin indicadores** (`SAH`, `FLK`, `GRL`, `ATF`, `BRN`, `ATA`,
  `KOS`): se conservan sin datos para no atribuir eventos de un territorio a
  otro sin evidencia.

La ausencia de indicadores **no** implica ausencia de desastres: refleja que
EM-DAT no registra eventos que cumplan sus criterios de inclusión para ese
territorio en el periodo analizado.

---

## Fuentes de datos

| Fuente | Uso en el proyecto |
|--------|--------------------|
| **EM-DAT** (CRED / UCLouvain) | Base principal: 10,907 eventos, 2000–2026, 220 territorios |
| **World Development Indicators** (Banco Mundial) | PIB, población y superficie por país; insumos de PIB per cápita y densidad |
| **Our World in Data** (OWID) | Contexto y validación externa de afectados y eventos por tamaño |
| **CONAFOR** | Incendios forestales de México 2015–2025: puntos, superficie, causas y estados |
| **CENAPRED / Atlas Nacional de Riesgos** | Impacto socioeconómico de desastres en México 2000–2024, por estado y municipio (MXN) |
| **Natural Earth** | Límites territoriales (110m Admin 0 Countries) |

### Validación cruzada

* México: **171 eventos** en EM-DAT y **1.60 billones de pesos** de daño acumulado.
* México en CENAPRED: **4,182 registros naturales**, **5,181 defunciones** y
  **687.0 mil M MXN** en las 32 entidades (2000–2024). No se suma con EM-DAT:
  son fuentes y metodologías distintas.
* Afectados en México: **15,538,601** (EM-DAT) frente a **15,516,081** (OWID),
  una diferencia de 0.15 % que respalda la integración.
* PIB de México: **38.07 billones de pesos** (WDI 2024 × tipo de cambio del proyecto).
* Incendios: **74,853** registros de CONAFOR, de los cuales **14,052** superan
  las 50 ha y se dibujan en el mapa.

### Fuentes revisadas y descartadas

Los **atlas de riesgos** estatales y municipales se revisaron, pero no se
incorporaron: no existe una fuente nacional homogénea, descargable y
reproducible que cubra los 32 estados con la misma metodología. En su lugar se
usaron **CONAFOR** (incendios de México) y **OWID** (contexto y validación),
que sí permiten reconstruir el pipeline de forma transparente.

---

## Licencia y uso académico

Proyecto académico de la asignatura *Análisis y exploración de datos*. El
uso de los datos está sujeto a los términos de cada fuente original.
