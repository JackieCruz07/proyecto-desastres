# Actividad 3 — Capa de visualización temática

Documentación técnica de la aplicación web desarrollada para la Actividad 3
del proyecto **Atlas Global de Desastres**.

> El reporte formal en LaTeX de esta actividad se ubica en
> `reportes/actividad3/` y toma como insumo las capturas generadas con
> `python -m src.capturas`.

---

## 1. Objetivo de la actividad

Diseñar e implementar la capa de visualización temática sobre el mapa 3D,
incorporando recursos visuales como coloración, intensidad de color,
elevación y deformación de la superficie para representar las variables
seleccionadas.

## 2. Correspondencia requisito → implementación

| Requisito (enunciado) | Implementación | Archivo |
|-----------------------|----------------|---------|
| Coloración | Rampa de color interpolada por variable | `app/js/capa_tematica.js` (`expresionColor`) |
| Intensidad de color | Control de saturación + `aplicarIntensidad()` | `app/js/escalas.js` |
| Elevación | `fill-extrusion` con altura ∝ valor | `app/js/capa_tematica.js` (`alturaTerritorio`) |
| Deformación de la superficie | `fill-extrusion` en relieve continuo | `app/js/capa_tematica.js` (`alturaTerritorio`) |
| Selección de variables | Dos selectores (color y altura) | `app/index.html` y `app/js/app.js` |
| Mapa 3D | Globo MapLibre + proyección plana | `app/js/app.js` (`crearMapa`, `cambiarProyeccion`) |
| GeoJSON | Capa personalizada generada en Python | `src/capa_tematica.py` |

## 3. Arquitectura de la capa temática

```
EMDAT_integrado_WDI_validado.csv        Natural Earth 110m (.shp)
                │                                  │
                └──────────┬───────────────────────┘
                           ▼
              src/capa_tematica.py
              ├── agregar_indicadores()   → totales y promedios por país
              ├── preparar_mapa()         → fusiones CYN→CYP, SOL→SOM
              ├── nombre_en_espanol()     → etiquetas en español
              └── construir_metadatos()   → estadísticos de escala
                           │
             ┌─────────────┴──────────────┐
             ▼                            ▼
   app/datos/paises.geojson     app/datos/metadatos.json
             │                            │
             └─────────────┬──────────────┘
                           ▼
                  app/ (MapLibre GL JS)
      ┌────────────────────┼────────────────────┐
      ▼                    ▼                    ▼
 relleno-coloreado   relleno-relieve      leyenda / ficha
   (coloración)      (elevación/deform.)   (interfaz)
```

## 4. Recursos visuales

### 4.1 Coloración
Cada territorio recibe un color interpolado en 12 paradas sobre una rampa
perceptual propia de la variable (`YlOrRd`, `Reds`, `Blues`, `Viridis`,
`Magma`, `Teal`). Los territorios sin datos usan un color neutro
(`#1c2740`) para distinguirlos de un valor cero.

### 4.2 Intensidad de color
El control «Intensidad del color» mezcla cada color con su luminancia
gris, de modo que a 0 % se obtiene una escala casi monocromática y a
100 % la rampa completa. Esto permite regular la carga visual del mapa.

### 4.3 Elevación
Se implementa con una capa `fill-extrusion`. La altura, en metros, crece
de forma proporcional al valor normalizado de la variable de altura, con
una base mínima de 4 000 m para que todos los territorios sean visibles:

```
altura = base + t · alturaMáxima      (t ∈ [0, 1])
```

### 4.4 Deformación de la superficie
Variante del mismo recurso en la que el relieve es más continuo y con
menor altura máxima, generando la sensación de una superficie ondulada en
lugar de prismas altos:

```
altura = 8 000 + t · (alturaMáxima · 0.42)
```

### 4.5 Escalas
Las variables con rangos de varios órdenes de magnitud (fallecidos,
afectados, daño económico) usan **escala logarítmica** por defecto. El
máximo se acota al percentil 99 para que un valor extremo aislado no
aplaste el resto de la escala.

## 5. Interacción

* **Hover** → tooltip con los cuatro indicadores principales.
* **Clic** → selección del territorio, resaltado del borde y ficha lateral
  con seis métricas y la observación de calidad del dato.
* **Globo / Plano** → alterna la proyección sin recargar la página.
* **Controles** → variable de color, variable de altura, recurso 3D,
  intensidad, altura máxima, escala y visibilidad de territorios sin datos.

## 6. Cifras de la capa

* Eventos EM-DAT procesados: **10 907**
* Unidades cartográficas: **175**
* Territorios con indicadores: **168**
* Periodo: **2000–2026**
* Tamaño del GeoJSON: ≈ **0.5 MB**

## 7. Cómo reproducir

```bash
pip install -r requirements.txt
python -m src.capa_tematica          # genera GeoJSON y metadatos
cd app && python -m http.server 8000 # sirve la aplicación
python -m src.capturas               # capturas para el reporte
```
