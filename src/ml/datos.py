"""Preparación del dataset para las Actividades 8–13.

La regla principal es evitar fuga de información: el modelo solo recibe
variables disponibles al inicio del evento. Fallecidos, heridos, afectados,
daños, ayuda y fechas de actualización quedan fuera de las entradas.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config


def cargar_socio(ruta: Path | str = config.SOCIO) -> pd.DataFrame:
    """Indicadores socioeconómicos por país usados por la aplicación."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))["paises"]
    filas = []
    for iso, valores in datos.items():
        filas.append(
            {
                "iso": iso,
                "nombre_socio": valores.get("nombre_wdi") or iso,
                "poblacion": valores.get("poblacion"),
                "densidad": valores.get("densidad"),
                "pib_pc_mxn": valores.get("pib_pc_mxn"),
            }
        )
    return pd.DataFrame(filas)


def cargar_nombres_paises(ruta: Path | str = config.GEOJSON_PAISES) -> pd.DataFrame:
    """Nombres en español de los territorios del mapa."""
    geojson = json.loads(Path(ruta).read_text(encoding="utf-8"))
    filas = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        filas.append(
            {
                "iso": props.get("codigo"),
                "nombre": props.get("nombre"),
                "continente": props.get("continente"),
            }
        )
    return pd.DataFrame(filas).dropna(subset=["iso"])


def _texto_limpio(serie: pd.Series) -> pd.Series:
    """Normaliza texto y convierte vacíos en 'Sin dato'."""
    limpio = serie.astype("string").str.strip()
    return limpio.mask(limpio.isna() | (limpio == ""), "Sin dato")


def _duracion_dias(df: pd.DataFrame) -> pd.Series:
    """Duración aproximada en días, sin depender de fechas perfectas.

    Si falta algún componente se usa 1 y se marca la bandera
    ``duracion_faltante``. Así los eventos de un solo día no se pierden.
    """
    anio_ini = pd.to_numeric(df["Start Year"], errors="coerce")
    mes_ini = pd.to_numeric(df["Start Month"], errors="coerce")
    dia_ini = pd.to_numeric(df["Start Day"], errors="coerce")
    anio_fin = pd.to_numeric(df["End Year"], errors="coerce")
    mes_fin = pd.to_numeric(df["End Month"], errors="coerce")
    dia_fin = pd.to_numeric(df["End Day"], errors="coerce")

    completa = (
        anio_ini.notna()
        & mes_ini.notna()
        & dia_ini.notna()
        & anio_fin.notna()
        & mes_fin.notna()
        & dia_fin.notna()
    )

    dias = (
        (anio_fin.fillna(anio_ini) - anio_ini) * 365
        + (mes_fin.fillna(mes_ini) - mes_ini) * 30
        + (dia_fin.fillna(dia_ini) - dia_ini)
    )
    dias = dias.clip(lower=0, upper=3650).fillna(0)
    return dias.where(completa, 0), (~completa)


def preparar_features(df: pd.DataFrame, socio: pd.DataFrame) -> pd.DataFrame:
    """Agrega las variables de entrada y los objetivos auxiliares."""
    df = df.copy()
    df["iso"] = _texto_limpio(df["ISO"])

    # --- Indicadores socioeconómicos ---------------------------------
    columnas_socio = ["iso", "poblacion", "densidad", "pib_pc_mxn", "nombre_socio"]
    df = df.merge(socio[columnas_socio], on="iso", how="left", suffixes=("", "_socio"))

    poblacion = pd.to_numeric(df["poblacion"], errors="coerce").replace(0, np.nan)
    pib_total = pd.to_numeric(df["PIB_MXN_corrientes"], errors="coerce")
    pib_pc = pib_total / poblacion
    pib_pc = pib_pc.fillna(pd.to_numeric(df["pib_pc_mxn"], errors="coerce"))

    df["pib_faltante"] = pib_total.isna().astype(int)
    df["pib_pc"] = pib_pc.fillna(pib_pc.median())
    df["poblacion"] = poblacion
    df["densidad"] = pd.to_numeric(df["densidad"], errors="coerce")

    df["pib_pc_log"] = np.log1p(df["pib_pc"].clip(lower=0))
    df["poblacion_log"] = np.log1p(df["poblacion"].clip(lower=0))
    df["densidad_log"] = np.log1p(df["densidad"].clip(lower=0))

    # --- Tiempo -------------------------------------------------------
    mes = pd.to_numeric(df["Start Month"], errors="coerce")
    mes_valido = mes.between(1, 12)
    angulo = 2 * np.pi * (mes.fillna(1) - 1) / 12
    df["mes_sin"] = np.where(mes_valido, np.sin(angulo), 0.0)
    df["mes_cos"] = np.where(mes_valido, np.cos(angulo), 0.0)
    df["mes_faltante"] = (~mes_valido).astype(int)

    dias, faltante = _duracion_dias(df)
    df["duracion_dias"] = dias
    df["duracion_log"] = np.log1p(dias)
    df["duracion_faltante"] = faltante.astype(int)

    # --- Magnitud -----------------------------------------------------
    df["magnitud"] = pd.to_numeric(df["Magnitude"], errors="coerce")
    df["magnitud_faltante"] = df["magnitud"].isna().astype(int)
    df["escala"] = _texto_limpio(df["Magnitude Scale"])

    # --- Categóricas --------------------------------------------------
    df["tipo"] = _texto_limpio(df["Disaster Type"])
    df["subtipo"] = _texto_limpio(df["Disaster Subtype"])
    df["subgrupo"] = _texto_limpio(df["Disaster Subgroup"])
    df["region"] = _texto_limpio(df["Region"])
    df["subregion"] = _texto_limpio(df["Subregion"])
    df["iso"] = _texto_limpio(df["ISO"])

    df["anio"] = pd.to_numeric(df["Start Year"], errors="coerce").astype("Int64")

    # --- Objetivos auxiliares ----------------------------------------
    df["log_afectados"] = np.log1p(pd.to_numeric(df["Total Affected"], errors="coerce"))
    columna_dano = "Total Damage, Adjusted ('000 MXN)"
    df["log_dano"] = np.log1p(pd.to_numeric(df[columna_dano], errors="coerce"))

    # Marca de elegibilidad: al menos un indicador de impacto humano.
    df["elegible_clasificacion"] = (
        df["Total Deaths"].notna() | df["Total Affected"].notna()
    ).astype(int)

    return df


def crear_objetivo_clasificacion(df: pd.DataFrame, train: pd.DataFrame) -> dict:
    """Crea ``alto_impacto`` con umbrales calculados solo en entrenamiento.

    El umbral es el percentil 75 de cada indicador observado. Un evento es
    de alto impacto si supera cualquiera de los dos umbrales.
    """
    umbral_muertes = float(train["Total Deaths"].quantile(0.75))
    umbral_afectados = float(train["Total Affected"].quantile(0.75))

    muertes = pd.to_numeric(df["Total Deaths"], errors="coerce").fillna(0)
    afectados = pd.to_numeric(df["Total Affected"], errors="coerce").fillna(0)
    df["alto_impacto"] = (
        (muertes >= umbral_muertes) | (afectados >= umbral_afectados)
    ).astype(int)

    return {
        "muertes_p75": umbral_muertes,
        "afectados_p75": umbral_afectados,
        "definicion": (
            "Evento de alto impacto si los fallecimientos son mayores o "
            "iguales al percentil 75 de entrenamiento o si los afectados "
            "son mayores o iguales a su percentil 75."
        ),
    }


def dividir_temporal(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Partición temporal: entrenamiento, validación y prueba."""
    train = df[df["anio"] <= config.ANIO_ENTRENAMIENTO_FIN].copy()
    val = df[df["anio"] == config.ANIO_VALIDACION].copy()
    test = df[
        df["anio"].between(config.ANIO_PRUEBA_INICIO, config.ANIO_PRUEBA_FIN)
    ].copy()
    return train, val, test


def cargar_y_preparar(
    ruta_dataset: Path | str = config.DATASET,
    ruta_socio: Path | str = config.SOCIO,
) -> dict:
    """Carga, limpia y divide el dataset. Devuelve todo lo necesario."""
    df = pd.read_csv(ruta_dataset, low_memory=False)
    df = df[df["Start Year"].between(2000, config.ANIO_PRUEBA_FIN)].copy()

    socio = cargar_socio(ruta_socio)
    df = preparar_features(df, socio)

    train, val, test = dividir_temporal(df)
    umbrales = crear_objetivo_clasificacion(df, train)
    # Volvemos a dividir para que las tres particiones incluyan el objetivo.
    train, val, test = dividir_temporal(df)

    return {
        "df": df,
        "train": train,
        "val": val,
        "test": test,
        "umbrales": umbrales,
        "socio": socio,
    }


def resumen_particiones(train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Tabla de control con conteos y prevalencia de alto impacto."""
    filas = []
    for nombre, parte in [("Entrenamiento", train), ("Validación", val), ("Prueba", test)]:
        elegibles = parte[parte["elegible_clasificacion"] == 1]
        filas.append(
            {
                "particion": nombre,
                "anios": f"{int(parte['anio'].min())}–{int(parte['anio'].max())}",
                "eventos": len(parte),
                "elegibles_clasificacion": len(elegibles),
                "alto_impacto": int(elegibles["alto_impacto"].sum()),
                "prevalencia_alto_impacto": round(
                    float(elegibles["alto_impacto"].mean()) * 100, 2
                ),
                "con_afectados": int(elegibles["Total Affected"].notna().sum()),
                "con_dano": int(elegibles["log_dano"].notna().sum()),
                "con_magnitud": int(elegibles["magnitud"].notna().sum()),
            }
        )
    return pd.DataFrame(filas)


def guardar_dataset_modelado(df: pd.DataFrame, ruta: Path | str | None = None) -> Path:
    """Guarda una copia auditable del dataset con las variables del modelo."""
    destino = Path(ruta) if ruta else config.RESULTADOS_ML / "dataset_modelado.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    columnas = (
        ["DisNo.", "anio", "iso", "tipo", "subtipo", "subgrupo", "region", "subregion"]
        + config.NUM_COLS
        + [
            "magnitud",
            "escala",
            "Total Deaths",
            "Total Affected",
            "alto_impacto",
            "log_afectados",
            "log_dano",
            "elegible_clasificacion",
        ]
    )
    df[columnas].to_csv(destino, index=False, encoding="utf-8")
    return destino
