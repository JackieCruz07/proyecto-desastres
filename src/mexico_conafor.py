"""
Datos de incendios forestales de México (CONAFOR).

El enunciado pide complementar EM-DAT con datos públicos del gobierno de
México (CONAFOR, atlas de riesgos, atlas de inundaciones, entre otros) y
analizarlos para quedarse con los mejores conjuntos.

De los conjuntos disponibles se conservaron los dos de CONAFOR porque son
los únicos con registros a nivel de evento y coordenadas:

* estadisticasincendiosforestales2015-2024.csv → 67,837 incendios
* 2025_Incendios_forestales.csv               →  7,016 incendios

Los atlas de riesgos e inundaciones se revisaron y se descartaron para
esta entrega: se publican por estado en PDF y shapefiles sin una API
estable, así que no permiten un pipeline reproducible como el resto.

Salidas
-------
app/datos/incendios_mexico.json          resúmenes por año, estado y causa
app/datos/incendios_puntos.geojson       puntos de incendios >= 50 ha
resultados/tablas/incendios_por_estado.csv
resultados/graficas/mexico/*.png

Uso:
    python -m src.mexico_conafor
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import (  # noqa: E402
    APP_DATOS,
    DATOS_ORIGINALES,
    RESULTADOS_GRAFICAS,
    RESULTADOS_TABLAS,
)

ARCHIVO_HISTORICO = DATOS_ORIGINALES / "estadisticasincendiosforestales2015-2024.csv"
ARCHIVO_2025 = DATOS_ORIGINALES / "2025_Incendios_forestales.csv"

# Solo se dibujan en el mapa los incendios que alcanzaron este tamaño.
UMBRAL_MAPA_HA = 50

COLORES = {
    "purpura": "#4C1D95",
    "rosa": "#FA8A9A",
    "amarillo": "#FFB71B",
    "rojo": "#EE3E29",
    "texto": "#2B2340",
}


# ---------------------------------------------------------------------------
# 1. NORMALIZACIÓN
# ---------------------------------------------------------------------------

def _grados_a_decimal(grados, minutos, segundos, signo: float = 1.0) -> pd.Series:
    """Convierte grados, minutos y segundos a grados decimales."""
    return signo * (
        pd.to_numeric(grados, errors="coerce")
        + pd.to_numeric(minutos, errors="coerce") / 60
        + pd.to_numeric(segundos, errors="coerce") / 3600
    )


def cargar_historico() -> pd.DataFrame:
    """Lee el archivo 2015-2024 y homologa sus columnas."""
    datos = pd.read_csv(ARCHIVO_HISTORICO, low_memory=False)
    return pd.DataFrame(
        {
            "anio": pd.to_numeric(datos["anio"], errors="coerce"),
            "entidad": datos["Entidad"],
            "municipio": datos["Municipio"],
            "lat": pd.to_numeric(datos["latitud"], errors="coerce"),
            "lon": pd.to_numeric(datos["longitud"], errors="coerce"),
            "hectareas": pd.to_numeric(datos["Total_hectareas"], errors="coerce"),
            "causa": datos["Causa"],
            "fecha": datos["Fecha_Inicio"],
        }
    )


def cargar_2025() -> pd.DataFrame:
    """Lee el archivo 2025, que trae las coordenadas en grados/minutos/segundos."""
    datos = pd.read_csv(ARCHIVO_2025, low_memory=False)
    return pd.DataFrame(
        {
            "anio": pd.to_numeric(datos["anio"], errors="coerce"),
            "entidad": datos["entidad"],
            "municipio": datos["municipio"],
            "lat": _grados_a_decimal(
                datos["latitud_grados"], datos["latitud_minutos"], datos["latitud_segundos"]
            ),
            "lon": _grados_a_decimal(
                datos["longitud_grados"],
                datos["longitud_minutos"],
                datos["longitud_segundos"],
                signo=-1.0,
            ),
            "hectareas": pd.to_numeric(datos["total_ha"], errors="coerce"),
            "causa": datos["posible_causa"],
            "fecha": datos["fecha_inicio"],
        }
    )


def cargar() -> pd.DataFrame:
    """Une ambos archivos y limpia los registros incompletos."""
    datos = pd.concat([cargar_historico(), cargar_2025()], ignore_index=True)

    datos["anio"] = datos["anio"].fillna(0).astype(int)
    datos = datos[datos["anio"] > 0]

    datos["entidad"] = (
        datos["entidad"].astype("string").str.strip().fillna("Sin entidad")
    )
    datos["causa"] = (
        datos["causa"].astype("string").str.strip().fillna("No especificada")
    )
    datos["hectareas"] = pd.to_numeric(datos["hectareas"], errors="coerce").fillna(0)

    # Coordenadas fuera de México se descartan para el mapa (no el resumen).
    datos["coord_valida"] = (
        datos["lat"].between(14, 33) & datos["lon"].between(-119, -86)
    )
    return datos


# ---------------------------------------------------------------------------
# 2. RESÚMENES
# ---------------------------------------------------------------------------

def construir_resumen(datos: pd.DataFrame) -> dict:
    """Construye los resúmenes anual, por estado y por causa."""
    anual = (
        datos.groupby("anio")
        .agg(incendios=("hectareas", "size"), hectareas=("hectareas", "sum"))
        .reset_index()
    )
    estados = (
        datos.groupby("entidad")
        .agg(incendios=("hectareas", "size"), hectareas=("hectareas", "sum"))
        .sort_values("hectareas", ascending=False)
        .reset_index()
    )
    causas = (
        datos.groupby("causa")
        .agg(incendios=("hectareas", "size"))
        .sort_values("incendios", ascending=False)
        .head(8)
        .reset_index()
    )

    # Series por año para que el panel pueda responder al filtro de periodo.
    estados_anual = []
    for entidad, grupo in datos.groupby("entidad"):
        serie = grupo.groupby("anio").agg(
            incendios=("hectareas", "size"), hectareas=("hectareas", "sum")
        )
        estados_anual.append(
            [
                str(entidad),
                [
                    [int(anio), int(fila["incendios"]), round(float(fila["hectareas"]), 1)]
                    for anio, fila in serie.iterrows()
                ],
            ]
        )
    estados_anual.sort(key=lambda x: -sum(f[2] for f in x[1]))

    causas_anual = []
    for causa in causas["causa"]:
        serie = datos[datos["causa"] == causa].groupby("anio").size()
        causas_anual.append(
            [
                str(causa),
                [[int(anio), int(total)] for anio, total in serie.items()],
            ]
        )

    return {
        "meta": {
            "fuente": "CONAFOR — Coordinación General de Conservación y Restauración",
            "archivos": [ARCHIVO_HISTORICO.name, ARCHIVO_2025.name],
            "periodo": [int(datos["anio"].min()), int(datos["anio"].max())],
            "umbral_mapa_ha": UMBRAL_MAPA_HA,
            "nota": (
                "Se descartaron los atlas de riesgos e inundaciones porque se "
                "publican en PDF y shapefiles por estado, sin una fuente "
                "reproducible a nivel nacional."
            ),
        },
        "total": {
            "incendios": int(len(datos)),
            "hectareas": round(float(datos["hectareas"].sum()), 1),
        },
        "anual": [
            [int(f["anio"]), int(f["incendios"]), round(float(f["hectareas"]), 1)]
            for _, f in anual.iterrows()
        ],
        "estados": [
            [str(f["entidad"]), int(f["incendios"]), round(float(f["hectareas"]), 1)]
            for _, f in estados.iterrows()
        ],
        "causas": [
            [str(f["causa"]), int(f["incendios"])] for _, f in causas.iterrows()
        ],
        "estados_anual": estados_anual,
        "causas_anual": causas_anual,
    }


def construir_puntos(datos: pd.DataFrame) -> dict:
    """Genera un GeoJSON con los incendios grandes, listo para el mapa."""
    grandes = datos[
        (datos["hectareas"] >= UMBRAL_MAPA_HA) & datos["coord_valida"]
    ].copy()

    caracteristicas = []
    for _, fila in grandes.iterrows():
        caracteristicas.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(float(fila["lon"]), 4), round(float(fila["lat"]), 4)],
                },
                "properties": {
                    "a": int(fila["anio"]),
                    "h": round(float(fila["hectareas"]), 1),
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "metadata": {
            "fuente": "CONAFOR",
            "umbral_ha": UMBRAL_MAPA_HA,
            "n": len(caracteristicas),
        },
        "features": caracteristicas,
    }


# ---------------------------------------------------------------------------
# 3. GRÁFICAS DE EVIDENCIA
# ---------------------------------------------------------------------------

def _estilo() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#D9D2E9",
            "axes.labelcolor": COLORES["texto"],
            "text.color": COLORES["texto"],
            "xtick.color": COLORES["texto"],
            "ytick.color": COLORES["texto"],
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def graficar(resumen: dict, carpeta: Path) -> None:
    """Genera las figuras de la Actividad 1 para los datos de CONAFOR."""
    carpeta.mkdir(parents=True, exist_ok=True)
    _estilo()

    anios = [f[0] for f in resumen["anual"]]
    incendios = [f[1] for f in resumen["anual"]]
    hectareas = [f[2] for f in resumen["anual"]]

    # 1. Incendios por año.
    figura, eje = plt.subplots(figsize=(10, 4.5))
    eje.bar(anios, incendios, color=COLORES["rosa"], width=0.7)
    eje.set_title("Incendios forestales registrados en México por año (CONAFOR)")
    eje.set_xlabel("Año")
    eje.set_ylabel("Incendios")
    eje.set_xticks(anios)
    figura.tight_layout()
    figura.savefig(carpeta / "01_incendios_por_anio.png", dpi=150)
    plt.close(figura)

    # 2. Superficie afectada por año.
    figura, eje = plt.subplots(figsize=(10, 4.5))
    eje.bar(anios, hectareas, color=COLORES["amarillo"], width=0.7)
    eje.set_title("Superficie afectada por incendios forestales en México")
    eje.set_xlabel("Año")
    eje.set_ylabel("Hectáreas")
    eje.set_xticks(anios)
    figura.tight_layout()
    figura.savefig(carpeta / "02_hectareas_por_anio.png", dpi=150)
    plt.close(figura)

    # 3. Hectáreas por estado (10 principales).
    estados = resumen["estados"][:10][::-1]
    figura, eje = plt.subplots(figsize=(10, 5))
    eje.barh(
        [e[0] for e in estados],
        [e[2] for e in estados],
        color=COLORES["purpura"],
    )
    eje.set_title("Superficie afectada por estado (10 principales, 2015-2025)")
    eje.set_xlabel("Hectáreas")
    figura.tight_layout()
    figura.savefig(carpeta / "03_hectareas_por_estado.png", dpi=150)
    plt.close(figura)

    # 4. Causas.
    causas = resumen["causas"][:8][::-1]
    figura, eje = plt.subplots(figsize=(10, 4.5))
    eje.barh([c[0] for c in causas], [c[1] for c in causas], color=COLORES["rojo"])
    eje.set_title("Principales causas de incendios forestales en México")
    eje.set_xlabel("Incendios")
    figura.tight_layout()
    figura.savefig(carpeta / "04_causas.png", dpi=150)
    plt.close(figura)


# ---------------------------------------------------------------------------
# 4. EJECUCIÓN
# ---------------------------------------------------------------------------

def main() -> None:
    print("Leyendo incendios forestales de CONAFOR…")
    datos = cargar()
    print(f"  Registros: {len(datos):,}")
    print(f"  Periodo: {int(datos['anio'].min())}–{int(datos['anio'].max())}")

    resumen = construir_resumen(datos)
    ruta_resumen = APP_DATOS / "incendios_mexico.json"
    with open(ruta_resumen, "w", encoding="utf-8") as archivo:
        json.dump(resumen, archivo, ensure_ascii=False, separators=(",", ":"))
    print(f"  Resumen: {ruta_resumen}")

    puntos = construir_puntos(datos)
    ruta_puntos = APP_DATOS / "incendios_puntos.geojson"
    with open(ruta_puntos, "w", encoding="utf-8") as archivo:
        json.dump(puntos, archivo, ensure_ascii=False, separators=(",", ":"))
    print(f"  Puntos (>= {UMBRAL_MAPA_HA} ha): {ruta_puntos} ({len(puntos['features']):,})")

    RESULTADOS_TABLAS.mkdir(parents=True, exist_ok=True)
    tabla = pd.DataFrame(
        resumen["estados"], columns=["estado", "incendios", "hectareas"]
    )
    ruta_tabla = RESULTADOS_TABLAS / "incendios_por_estado.csv"
    tabla.to_csv(ruta_tabla, index=False, encoding="utf-8-sig")
    print(f"  Evidencia: {ruta_tabla}")

    graficar(resumen, RESULTADOS_GRAFICAS / "mexico")
    print(f"  Gráficas: {RESULTADOS_GRAFICAS / 'mexico'}")

    print("\nListo. Datos de CONAFOR preparados.")


if __name__ == "__main__":
    main()
