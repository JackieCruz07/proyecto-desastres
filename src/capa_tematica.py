"""
Preparación de la capa de visualización temática (Actividad 3).

Este módulo transforma el dataset integrado y validado de la Actividad 1
en los archivos que consumirá la aplicación web:

    app/datos/paises.geojson   → límites territoriales + indicadores
    app/datos/metadatos.json   → descripción de variables y estadísticos
    resultados/resumen_capa_tematica.csv → evidencia tabular de la entrega

Recursos preparados para la capa temática
-----------------------------------------
* Coloración:            variable por país disponible como atributo geojson.
* Intensidad de color:   estadísticos (percentiles) para construir escalas.
* Elevación:             mismos atributos listos para fill-extrusion.
* Deformación de la superficie: valores normalizables para el relieve.

Moneda
------
Los montos económicos se leen del dataset ya convertido a pesos mexicanos
por `src.moneda` (tipo de cambio fijo 1 USD = 20.8 MXN).

Decisiones de integración geográfica (heredadas de la Actividad 2)
-------------------------------------------------------------------
* PSE → PSX  (Estado de Palestina)   SSD → SDS  (Sudán del Sur)
* CYN se fusiona con CYP (Chipre); SOL se fusiona con SOM (Somalilandia).
* SAH, FLK, GRL, ATF, BRN, ATA, CYN, SOL y KOS se conservan SIN indicadores
  para no atribuir eventos de un territorio a otro sin evidencia.

Uso:
    python -m src.capa_tematica
    (también puede ejecutarse directamente: python src/capa_tematica.py)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

# Permite ejecutar el archivo directamente sin instalar el paquete src.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import (  # noqa: E402
    APP_DATOS,
    DATASET_INTEGRADO,
    MAPA_SHP,
    RESULTADOS,
    RESULTADOS_TABLAS,
    TIPO_CAMBIO_MXN,
    asegurar_carpetas,
)
from src.integracion_paises import construir_tabla as construir_tabla_socio  # noqa: E402

# ---------------------------------------------------------------------------
# 1. DICCIONARIO DE VARIABLES TEMÁTICAS
# ---------------------------------------------------------------------------
# Cada variable define cómo se calcula desde el dataset y cómo debe
# formatearse/escalarse en la interfaz. Las claves son las que usa el
# frontend (app/js) para referenciar la propiedad del GeoJSON.

VARIABLES = {
    "eventos": {
        "etiqueta": "Número de desastres",
        "descripcion": "Total de eventos EM-DAT registrados por territorio.",
        "unidad": "eventos",
        "formato": "entero",
        "escala_sugerida": "lineal",
        "categoria": "recuento",
    },
    "fallecidos": {
        "etiqueta": "Fallecidos totales",
        "descripcion": "Suma de víctimas mortales registradas (Total Deaths).",
        "unidad": "personas",
        "formato": "entero",
        "escala_sugerida": "log",
        "categoria": "impacto humano",
    },
    "afectados": {
        "etiqueta": "Personas afectadas",
        "descripcion": "Suma de población afectada (Total Affected).",
        "unidad": "personas",
        "formato": "entero",
        "escala_sugerida": "log",
        "categoria": "impacto humano",
    },
    "dano_ajustado": {
        "etiqueta": "Daño económico ajustado",
        "descripcion": (
            "Suma de daños totales ajustados por inflación "
            "(Total Damage, Adjusted), expresada en pesos mexicanos."
        ),
        "unidad": "MXN",
        "formato": "moneda",
        "escala_sugerida": "log",
        "categoria": "impacto económico",
    },
    "prom_fallecidos": {
        "etiqueta": "Fallecidos promedio por evento",
        "descripcion": "Total de fallecidos dividido entre el número de eventos.",
        "unidad": "personas/evento",
        "formato": "decimal",
        "escala_sugerida": "log",
        "categoria": "intensidad",
    },
    "prom_afectados": {
        "etiqueta": "Afectados promedio por evento",
        "descripcion": "Total de afectados dividido entre el número de eventos.",
        "unidad": "personas/evento",
        "formato": "decimal",
        "escala_sugerida": "log",
        "categoria": "intensidad",
    },
}

# equivalencias código EM-DAT → código cartográfico (Actividad 2)
EQUIVALENCIAS_ISO = {
    "PSE": "PSX",  # Estado de Palestina
    "SSD": "SDS",  # Sudán del Sur
}

# territorios fusionados en la cartografía (Actividad 2)
FUSIONES = {"CYN": "CYP", "SOL": "SOM"}

# territorios conservados sin indicadores, con la observación documentada
SIN_INDICADORES = {
    "SAH": "No se asignan eventos de Marruecos o Mauritania sin confirmación "
           "de que corresponden al Sáhara Occidental.",
    "FLK": "No se identificaron registros directos por nombre en EM-DAT.",
    "GRL": "No se confirmó un desglose independiente de Dinamarca para "
           "Groenlandia.",
    "ATF": "No se identificaron registros independientes en EM-DAT.",
    "BRN": "No se identificaron coincidencias directas de código en EM-DAT.",
    "ATA": "No se identificaron registros directos en EM-DAT.",
    "CYN": "EM-DAT registra datos nacionales de Chipre sin desglose para el norte.",
    "SOL": "No se confirmaron indicadores independientes de Somalilandia.",
    "KOS": "No se asignan automáticamente los totales de Serbia.",
}

SIN_REGISTROS = (
    "EM-DAT no registra eventos que cumplan sus criterios de inclusión "
    "para este territorio en el periodo consultado."
)

# ---------------------------------------------------------------------------
# 2. NOMBRES EN ESPAÑOL
# ---------------------------------------------------------------------------

EXCEPCIONES = {
    "CYP": "Chipre",
    "SOM": "Somalia",
    "KOS": "Kosovo",
    "SAH": "Sáhara Occidental",
    "CYN": "Chipre del Norte",
    "SOL": "Somalilandia",
    "FLK": "Islas Malvinas",
    "GRL": "Groenlandia",
    "ATF": "Tierras Australes y Antárticas Francesas",
    "BRN": "Brunéi",
    "ATA": "Antártida",
    "SCG": "Serbia y Montenegro (histórico)",
    "PSX": "Estado de Palestina",
    "SDS": "Sudán del Sur",
}

NOMBRES_PERSONALIZADOS = {
    "United States of America": "Estados Unidos",
    "Russia": "Rusia",
    "South Korea": "Corea del Sur",
    "North Korea": "Corea del Norte",
    "Ivory Coast": "Costa de Marfil",
    "Dem. Rep. Congo": "República Democrática del Congo",
    "Congo": "República del Congo",
    "Czechia": "Chequia",
    "Taiwan": "Taiwán",
    "Vatican": "Ciudad del Vaticano",
    "Türkiye": "Turquía",
}


def nombre_en_espanol(codigo: str, nombre_original: str) -> str:
    """Traduce el nombre de un territorio al español.

    Prioridad: excepciones manuales → pycountry + Babel →
    nombres personalizados por nombre original → nombre original.
    """
    from babel import Locale
    import pycountry

    if codigo in EXCEPCIONES:
        return EXCEPCIONES[codigo]

    pais = pycountry.countries.get(alpha_3=codigo)
    if pais:
        traduccion = Locale("es").territories.get(pais.alpha_2)
        if traduccion:
            return traduccion

    return NOMBRES_PERSONALIZADOS.get(nombre_original, nombre_original)


# ---------------------------------------------------------------------------
# 3. AGREGACIÓN DE EM-DAT POR TERRITORIO
# ---------------------------------------------------------------------------

def agregar_indicadores(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega los eventos EM-DAT a un registro por territorio.

    Devuelve una tabla con los indicadores crudos que alimentan la
    capa temática (recuentos, totales, promedios y cobertura del daño).
    """
    datos = df.copy()
    datos["ISO_mapa"] = (
        datos["ISO"].astype(str).str.strip().replace(EQUIVALENCIAS_ISO)
    )

    columna_dano = "Total Damage, Adjusted ('000 MXN)"

    agregado = (
        datos.groupby("ISO_mapa", as_index=False)
        .agg(
            eventos=("DisNo.", "count"),
            fallecidos=("Total Deaths", "sum"),
            afectados=("Total Affected", "sum"),
            dano_miles=("Total Damage, Adjusted ('000 MXN)", "sum"),
            eventos_con_dano=(columna_dano, "count"),
            tipos_distintos=("Disaster Type", "nunique"),
        )
        .rename(columns={"ISO_mapa": "codigo"})
    )

    # Daño económico en MXN (el dataset lo almacena en miles de pesos).
    agregado["dano_ajustado"] = (agregado["dano_miles"] * 1000).round(0)
    agregado = agregado.drop(columns=["dano_miles"])

    # Promedios por evento.
    agregado["prom_fallecidos"] = (
        agregado["fallecidos"] / agregado["eventos"]
    ).round(2)
    agregado["prom_afectados"] = (
        agregado["afectados"] / agregado["eventos"]
    ).round(2)

    # Porcentaje de eventos con dato de daño disponible (transparencia).
    agregado["cobertura_dano"] = (
        100 * agregado["eventos_con_dano"] / agregado["eventos"]
    ).round(1)
    agregado = agregado.drop(columns=["eventos_con_dano"])

    # Nulos explícitos para columnas cuyo dato puede no existir.
    for columna in ("fallecidos", "afectados", "dano_ajustado"):
        agregado[columna] = agregado[columna].fillna(0)

    return agregado


# ---------------------------------------------------------------------------
# 4. CARTOGRAFÍA
# ---------------------------------------------------------------------------

def preparar_mapa() -> gpd.GeoDataFrame:
    """Carga los límites territoriales y aplica las fusiones de la Actividad 2.

    CYN (Chipre del Norte) se fusiona con CYP y SOL (Somalilandia) con SOM,
    de modo que la geometría final contiene 175 unidades cartográficas sin
    códigos duplicados.
    """
    mapa = gpd.read_file(MAPA_SHP)

    # Columnas mínimas necesarias para la capa temática.
    mapa = mapa[["ADMIN", "ADM0_A3", "CONTINENT", "geometry"]].copy()
    mapa["ADM0_A3"] = mapa["ADM0_A3"].astype(str).str.strip()

    mapa["Codigo_mapa"] = mapa["ADM0_A3"].replace(FUSIONES)

    mapa_final = mapa.dissolve(
        by="Codigo_mapa",
        as_index=False,
        aggfunc={"ADMIN": "first", "CONTINENT": "first"},
    ).rename(columns={"Codigo_mapa": "codigo"})

    # Nombres corregidos de las unidades fusionadas.
    mapa_final.loc[mapa_final["codigo"] == "CYP", "ADMIN"] = "Cyprus"
    mapa_final.loc[mapa_final["codigo"] == "SOM", "ADMIN"] = "Somalia"

    return mapa_final


# ---------------------------------------------------------------------------
# 5. ENSAMBLADO DE LA CAPA TEMÁTICA
# ---------------------------------------------------------------------------

def construir_capa(df: pd.DataFrame) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Une la cartografía con los indicadores agregados.

    Devuelve la capa geográfica lista para exportarse como GeoJSON y la
    tabla de indicadores (para evidencia tabular en resultados/).
    """
    mapa_final = preparar_mapa()
    agregado = agregar_indicadores(df)

    capa = mapa_final.merge(agregado, on="codigo", how="left")

    # --- indicadores socioeconómicos del Banco Mundial -------------------
    socio = construir_tabla_socio()[
        ["poblacion", "superficie_km2", "pib_mxn", "pib_pc_mxn", "densidad", "anio_socio"]
    ]
    capa = capa.merge(socio, left_on="codigo", right_index=True, how="left")

    # Posición de cada territorio en los rankings mundiales.
    capa["victimas"] = capa["fallecidos"].fillna(0) + capa["afectados"].fillna(0)
    capa["rank_eventos"] = capa["eventos"].rank(ascending=False, method="min")
    capa["rank_victimas"] = capa["victimas"].rank(ascending=False, method="min")
    capa["rank_dano"] = capa["dano_ajustado"].rank(ascending=False, method="min")

    # --- disponibilidad de datos (documentada en la Actividad 2) ---------
    capa["disponibilidad"] = "Con indicadores asociados"
    capa["observacion"] = (
        "Indicadores asociados mediante el código geográfico EM-DAT."
    )

    sin_datos = capa["eventos"].isna()
    capa.loc[sin_datos, "disponibilidad"] = "Sin registros asociados"
    capa.loc[sin_datos, "observacion"] = SIN_REGISTROS

    for codigo, observacion in SIN_INDICADORES.items():
        filtro = capa["codigo"] == codigo
        capa.loc[filtro, "disponibilidad"] = "Sin indicadores directos"
        capa.loc[filtro, "observacion"] = observacion

    # --- nombres en español ---------------------------------------------
    capa["nombre"] = [
        nombre_en_espanol(codigo, admin)
        for codigo, admin in zip(capa["codigo"], capa["ADMIN"])
    ]

    # --- propiedades finales del GeoJSON --------------------------------
    columnas_salida = [
        "codigo", "nombre", "ADMIN", "CONTINENT",
        "disponibilidad", "observacion",
        *VARIABLES.keys(),
        "tipos_distintos", "cobertura_dano",
        "poblacion", "superficie_km2", "pib_mxn", "pib_pc_mxn", "densidad",
        "anio_socio", "rank_eventos", "rank_victimas", "rank_dano",
        "geometry",
    ]
    capa = capa[columnas_salida].rename(
        columns={
            "ADMIN": "nombre_original",
            "CONTINENT": "continente",
            "tipos_distintos": "tipos_desastre",
        }
    )

    # Orden estable y tipos numéricos consistentes.
    for variable in VARIABLES:
        capa[variable] = pd.to_numeric(capa[variable], errors="coerce")

    capa = capa.sort_values("nombre").reset_index(drop=True)

    tabla = capa.drop(columns="geometry")
    return capa, tabla


# ---------------------------------------------------------------------------
# 6. METADATOS PARA EL FRONTEND
# ---------------------------------------------------------------------------

def calcular_estadisticos(serie: pd.Series) -> dict:
    """Estadísticos por variable para construir escalas y leyendas.

    Se calculan únicamente sobre los territorios con valor disponible.
    """
    valores = serie.dropna()
    valores = valores[valores >= 0]

    if valores.empty:
        return {"n": 0}

    percentiles = np.percentile(valores, [50, 75, 90, 95, 99])
    return {
        "n": int(valores.size),
        "min": float(valores.min()),
        "p50": float(percentiles[0]),
        "p75": float(percentiles[1]),
        "p90": float(percentiles[2]),
        "p95": float(percentiles[3]),
        "p99": float(percentiles[4]),
        "max": float(valores.max()),
        "media": float(valores.mean()),
    }


def construir_metadatos(capa: gpd.GeoDataFrame, df: pd.DataFrame) -> dict:
    """Genera el archivo de metadatos que consume la aplicación web."""
    variables = {}
    for clave, definicion in VARIABLES.items():
        variables[clave] = {
            **definicion,
            "estadisticos": calcular_estadisticos(capa[clave]),
        }

    anios = pd.to_numeric(df["Start Year"], errors="coerce").dropna()

    return {
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fuente": (
            "EM-DAT (CRED/Université de Louvain) integrado con "
            "World Development Indicators — archivo: "
            "EMDAT_integrado_WDI_validado.csv"
        ),
        "cartografia": "Natural Earth 110m Admin 0 Countries",
        "moneda": {
            "codigo": "MXN",
            "nombre": "Peso mexicano",
            "tipo_cambio_usd": TIPO_CAMBIO_MXN,
            "nota": (
                "Los montos del dataset se convirtieron de USD a MXN con un "
                "tipo de cambio fijo de 1 USD = "
                f"{TIPO_CAMBIO_MXN} MXN."
            ),
        },
        "n_eventos": int(len(df)),
        "n_territorios": int(len(capa)),
        "periodo": {
            "inicio": int(anios.min()),
            "fin": int(anios.max()),
        },
        "variables": variables,
        "socio": {
            "poblacion": {"etiqueta": "Población", "unidad": "habitantes"},
            "superficie_km2": {"etiqueta": "Superficie", "unidad": "km²"},
            "pib_mxn": {"etiqueta": "PIB", "unidad": "MXN"},
            "pib_pc_mxn": {"etiqueta": "PIB por habitante", "unidad": "MXN"},
            "densidad": {"etiqueta": "Densidad de población", "unidad": "hab/km²"},
            "anio_socio": {"etiqueta": "Año de referencia", "unidad": "año"},
        },
        "fuentes_complementarias": [
            "World Bank — World Development Indicators (PIB, población y superficie)",
            "Our World in Data (contexto y validación)",
            "CONAFOR (incendios forestales de México)",
        ],
    }


# ---------------------------------------------------------------------------
# 7. EJECUCIÓN
# ---------------------------------------------------------------------------

def main() -> None:
    asegurar_carpetas()

    print("Leyendo dataset integrado…")
    df = pd.read_csv(DATASET_INTEGRADO, low_memory=False)
    print(f"  Eventos: {len(df):,} | Territorios EM-DAT: {df['ISO'].nunique()}")

    print("Construyendo la capa temática…")
    capa, tabla = construir_capa(df)
    con_datos = int(capa["eventos"].notna().sum())
    print(f"  Unidades cartográficas: {len(capa)} | con indicadores: {con_datos}")

    metadatos = construir_metadatos(capa, df)

    # --- exportar GeoJSON ------------------------------------------------
    ruta_geojson = APP_DATOS / "paises.geojson"
    capa.to_file(ruta_geojson, driver="GeoJSON")
    print(f"  GeoJSON: {ruta_geojson}")

    # --- exportar metadatos ---------------------------------------------
    ruta_metadatos = APP_DATOS / "metadatos.json"
    with open(ruta_metadatos, "w", encoding="utf-8") as archivo:
        json.dump(metadatos, archivo, ensure_ascii=False, indent=2)
    print(f"  Metadatos: {ruta_metadatos}")

    # --- evidencia tabular ------------------------------------------------
    ruta_tabla = RESULTADOS_TABLAS / "resumen_capa_tematica.csv"
    tabla.to_csv(ruta_tabla, index=False, encoding="utf-8-sig")
    print(f"  Evidencia: {ruta_tabla}")

    # --- resumen en consola ------------------------------------------------
    print("\nResumen por variable (territorios con datos):")
    for clave, definicion in VARIABLES.items():
        stats = metadatos["variables"][clave]["estadisticos"]
        if stats.get("n"):
            print(
                f"  {definicion['etiqueta']:<32} "
                f"n={stats['n']:>3}  máx={stats['max']:,.2f}  "
                f"mediana={stats['p50']:,.2f}"
            )

    print("\nListo. La capa de visualización temática está preparada.")


if __name__ == "__main__":
    main()
