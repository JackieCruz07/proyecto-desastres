# Atlas Global de Desastres

Aplicación web interactiva que visualiza, explora y analiza espacialmente la
ocurrencia de desastres naturales a nivel mundial, con énfasis en México, a
partir del conjunto de datos **EM-DAT** (CRED) integrado con indicadores
socioeconómicos del **Banco Mundial (WDI)**, datos de incendios de **CONAFOR**
y series de contexto de **Our World in Data (OWID)**.

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
| 5 | Panel de información y visualizaciones por país | 🟡 En curso | Modal por país (KPIs, rankings, gráficas) |
| 6 | Integración de la interfaz de usuario | ⏳ Pendiente | — |
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

El panel lateral organiza los controles en tres pestañas:

| Pestaña | Controles |
|---------|-----------|
| **Resumen** | Indicadores del mapa (territorios, cobertura, máximo y mediana), ficha del territorio seleccionado y paleta temática |
| **Filtros** | Rango de años (2000–2026), tipo de desastre (14 tipos), aplicar al mapa y restablecer |
| **Capa** | Variable de color, variable de altura, recurso 3D (elevación / deformación / ninguno), intensidad de la rampa, altura del relieve, escala y capa de incendios de CONAFOR |

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
* **Doble clic en un país.** Abre el panel detallado con 9 KPIs, posición
  mundial en eventos/víctimas/daño, tres gráficas (evolución, tipos e impacto),
  comparación de periodos, los eventos más relevantes y, para México, el bloque
  de incendios y el contexto de OWID.

### Panel detallado por país (avance de la Actividad 5)

El modal se alimenta de `app/datos/eventos_pais.json` (10,907 eventos en 220
territorios) y de `app/datos/paises_socio.json` (267 países con PIB, población,
superficie y densidad). Incluye:

* **9 KPIs:** eventos, fallecidos, afectados, daño, PIB, población, PIB per
  cápita, superficie y densidad.
* **Rankings mundiales** de eventos, víctimas y daño sobre 220 territorios.
* **Gráficas:** evolución anual, distribución por tipo y eventos de mayor
  impacto.
* **Eventos destacados** ordenados por impacto humano (fallecidos + afectados)
  y por daño económico.
* **Bloque México:** superficie afectada y causas de incendios por estado.
* **Bloque OWID:** afectados y eventos por tamaño, como validación externa.

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
│   ├── index.html               Interfaz, pestañas y modal por país
│   ├── css/estilos.css          Identidad visual completa
│   ├── js/
│   │   ├── config.js            Rutas, paletas y vista inicial del globo
│   │   ├── escalas.js           Escalas de color (lineal/log) e interpolación
│   │   ├── leyenda.js           Leyenda temática dinámica
│   │   ├── estado.js            Barra de estado y tarjetas
│   │   ├── diccionario_desastres.js  Nombres de desastres en español
│   │   ├── capa_tematica.js     Capas 3D (color, elevación, deformación)
│   │   └── app.js               Orquestador: filtros, modal, rankings, incendios
│   └── datos/
│       ├── paises.geojson       Capa agregada (175 unidades cartográficas)
│       ├── metadatos.json       Variables y estadísticos globales
│       ├── filtros.json         Catálogo de años y tipos para los controles
│       ├── paises_socio.json    PIB, población y superficie por país (267)
│       ├── eventos_pais.json    Eventos por país (10,907 en 220 territorios)
│       ├── owid.json            Contexto OWID por país
│       ├── incendios_mexico.json    Incendios CONAFOR por año, estado y causa
│       └── incendios_puntos.geojson Incendios de 50 ha o más
├── datos/
│   ├── originales/              Fuentes crudas (EM-DAT, WDI, CONAFOR, OWID)
│   ├── procesados/              Dataset limpio e integrado
│   └── geograficos/             Natural Earth 110m (límites territoriales)
├── notebooks/
│   ├── 01_actividad1_preprocesamiento_eda.ipynb
│   ├── 02_actividad2_mapa_base.ipynb
│   ├── 03_actividad3_capa_tematica.ipynb
│   └── 04_actividad4_filtros_controles.ipynb
├── src/                         Código fuente del pipeline
│   ├── config.py                Rutas centralizadas y tipo de cambio
│   ├── moneda.py                Conversión de montos a pesos mexicanos
│   ├── integracion_paises.py    PIB, población y superficie (WDI)
│   ├── capa_tematica.py         Construcción de la capa temática
│   ├── detalle_pais.py          Eventos por país para el modal
│   ├── mexico_conafor.py        Incendios de México (CONAFOR)
│   ├── owid.py                  Contexto y validación con OWID
│   ├── generar_filtros.py       Catálogo de filtros
│   ├── diccionario_desastres.py Nombres de desastres en español
│   ├── servir_app.py            Servidor local de la aplicación
│   └── capturas.py              Generación de capturas (reporte)
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
```

Esto produce `paises.geojson`, `metadatos.json`, `filtros.json`,
`paises_socio.json`, `eventos_pais.json`, `owid.json`, `incendios_mexico.json`,
`incendios_puntos.geojson` y la evidencia tabular en `resultados/tablas/`.

> Todos los montos se convierten a **pesos mexicanos en el pipeline**, con el
> tipo de cambio fijo de `src/config.py`. El navegador nunca hace conversiones
> de moneda.

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

### 4. Generar las capturas del reporte (opcional)

Las capturas ya vienen incluidas en `resultados/graficas/capa_tematica/`, por
lo que **no es necesario regenerarlas**. Solo hay que repetir este paso si se
modifica algo visual en la aplicación:

```bash
pip install playwright
playwright install chromium
python -m src.capturas
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
| **Natural Earth** | Límites territoriales (110m Admin 0 Countries) |

### Validación cruzada

* México: **171 eventos** en EM-DAT y **1.60 billones de pesos** de daño acumulado.
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
