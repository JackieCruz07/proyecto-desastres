# Atlas Global de Desastres

Aplicación web interactiva que visualiza, explora y analiza espacialmente la
ocurrencia de desastres naturales a nivel mundial, con énfasis en México, a
partir del conjunto de datos **EM-DAT** (CRED) integrado con indicadores
socioeconómicos del **Banco Mundial (WDI)**.

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
| 4 | Filtros y controles interactivos | ⏳ Pendiente | — |
| 5 | Panel de información y visualizaciones por país | ⏳ Pendiente | — |
| 6 | Integración de la interfaz de usuario | ⏳ Pendiente | — |
| 7 | Validación de resultados | ⏳ Pendiente | — |

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

## Estructura del proyecto

```
PROYECTO_DESASTRES/
├── app/                         Aplicación web (Actividad 3)
│   ├── index.html               Interfaz principal
│   ├── css/estilos.css          Hoja de estilos
│   ├── js/
│   │   ├── config.js            Configuración y paletas temáticas
│   │   ├── escalas.js           Escalas de color (lineal/log) e interpolación
│   │   ├── leyenda.js           Leyenda temática dinámica
│   │   ├── estado.js            Barra de estado y tarjetas
│   │   ├── capa_tematica.js     Capas 3D (color, elevación, deformación)
│   │   └── app.js               Orquestador e interacción
│   └── datos/
│       ├── paises.geojson       Capa generada (175 territorios)
│       └── metadatos.json       Variables y estadísticos
├── datos/
│   ├── originales/              Fuentes crudas (EM-DAT, WDI, CONAFOR, OWID)
│   ├── procesados/              Dataset limpio e integrado
│   └── geograficos/             Natural Earth 110m (límites territoriales)
├── notebooks/
│   ├── 01_actividad1_preprocesamiento_eda.ipynb
│   ├── 02_actividad2_mapa_base.ipynb
│   └── 03_actividad3_capa_tematica.ipynb
├── src/                         Código fuente del pipeline
│   ├── config.py                Rutas centralizadas
│   ├── capa_tematica.py         Construcción de la capa temática
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

### 2. Generar la capa temática

```bash
python -m src.capa_tematica
```

Esto produce `app/datos/paises.geojson`, `app/datos/metadatos.json` y la
evidencia tabular en `resultados/tablas/resumen_capa_tematica.csv`.

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

* **EM-DAT** — Emergency Events Database (CRED / Université de Louvain).
* **World Development Indicators** y **World Bank Open Data** (Banco Mundial).
* **Our World in Data** (OWID).
* **CONAFOR** y estadísticas de incendios forestales de México.
* **Natural Earth** — límites territoriales (110m Admin 0 Countries).

---

## Licencia y uso académico

Proyecto académico de la asignatura *Análisis y exploración de datos*. El
uso de los datos está sujeto a los términos de cada fuente original.
