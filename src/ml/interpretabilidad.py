"""Interpretabilidad, equidad y robustez de los modelos (Actividad 12).

Produce tres tablas reproducibles:

* ``ablacion_xgb.csv``: cuánto aporta cada grupo de variables.
* ``equidad_modelos.csv``: desempeño por región, PIB y tipo de desastre.
* ``estabilidad_temporal.csv``: métricas por año en validación y prueba.

No se usa el paquete ``shap``: XGBoost calcula TreeSHAP de forma nativa.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

from . import config
from .datos import cargar_y_preparar
from .evaluacion import evaluar_clasificacion
from .preprocesamiento import Preprocesador
from .xgboost_modelo import (
    _entrenar,
    parametros_base_clasificacion,
    predecir,
)

GRUPOS_ABLACION = {
    "Modelo completo": [],
    "Sin PIB per cápita": ["num__pib_pc_log", "num__pib_faltante"],
    "Sin magnitud ni escala": [
        "num__magnitud_z",
        "num__magnitud_faltante",
    ],
    "Sin país, región ni subregión": [],
    "Sin estacionalidad": ["num__mes_sin", "num__mes_cos", "num__mes_faltante"],
}


def _columnas_por_prefijo(columnas: list[str], prefijo: str) -> list[str]:
    return [columna for columna in columnas if columna.startswith(prefijo)]


def _columnas_ablacion(nombre: str, columnas: list[str]) -> list[str]:
    """Devuelve las columnas que se conservan al quitar un grupo."""
    quitar = set(GRUPOS_ABLACION[nombre])
    if nombre == "Sin magnitud ni escala":
        quitar |= set(_columnas_por_prefijo(columnas, "cat__escala__"))
    if nombre == "Sin país, región ni subregión":
        for columna in ("cat__iso__", "cat__region__", "cat__subregion__"):
            quitar |= set(_columnas_por_prefijo(columnas, columna))
    return [columna for columna in columnas if columna not in quitar]


def parametros_entrenamiento() -> dict:
    """Reutiliza los hiperparámetros elegidos en la Actividad 10."""
    ruta = config.MODELOS / "metricas_xgb_clasificacion.json"
    if ruta.exists():
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return dict(datos.get("parametros", {}))
    return {}


def ablacion(datos: dict, preprocesador: Preprocesador) -> pd.DataFrame:
    """Entrena el modelo completo y tres variantes sin un grupo de variables."""
    train = datos["train"][datos["train"]["elegible_clasificacion"] == 1]
    val = datos["val"][datos["val"]["elegible_clasificacion"] == 1]
    test = datos["test"][datos["test"]["elegible_clasificacion"] == 1]

    Xtr = preprocesador.transform_xgb(train)
    Xva = preprocesador.transform_xgb(val)
    Xte = preprocesador.transform_xgb(test)
    ytr = train["alto_impacto"].to_numpy(dtype=int)
    yva = val["alto_impacto"].to_numpy(dtype=int)
    yte = test["alto_impacto"].to_numpy(dtype=int)

    base = parametros_base_clasificacion(ytr)
    base.update({k: v for k, v in parametros_entrenamiento().items() if k in base})
    base["nthread"] = 8

    filas = []
    for nombre, _ in GRUPOS_ABLACION.items():
        columnas = _columnas_ablacion(nombre, list(Xtr.columns))
        booster = _entrenar(
            base,
            Xtr[columnas],
            ytr,
            Xva[columnas],
            yva,
            num_boost_round=500,
            early_stopping_rounds=40,
        )
        probabilidad = predecir(booster, Xte[columnas])
        metricas = evaluar_clasificacion(yte, probabilidad, 0.5)
        filas.append(
            {
                "variante": nombre,
                "n_variables": len(columnas),
                "roc_auc": metricas["roc_auc"],
                "pr_auc": metricas["pr_auc"],
                "f1": metricas["f1"],
                "mejor_iteracion": int(getattr(booster, "best_iteration", 0)),
            }
        )
        print(f"{nombre}: ROC-AUC {metricas['roc_auc']:.4f} · {len(columnas)} variables")

    tabla = pd.DataFrame(filas)
    referencia = float(tabla.loc[tabla["variante"] == "Modelo completo", "roc_auc"].iloc[0])
    tabla["caida_roc_auc"] = referencia - tabla["roc_auc"]
    return tabla


def _metricas_grupo(y: np.ndarray, p: np.ndarray, umbral: float) -> dict:
    pred = (p >= umbral).astype(int)
    return {
        "n": int(len(y)),
        "positivos": int(y.sum()),
        "prevalencia": float(y.mean()) if len(y) else float("nan"),
        "roc_auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else float("nan"),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
    }


def equidad(
    datos: dict,
    probabilidades: dict[str, np.ndarray],
    umbrales: dict[str, float],
) -> pd.DataFrame:
    """Desempeño por región, cuartil de PIB y tipo de desastre.

    ``probabilidades`` debe contener las predicciones de prueba alineadas con
    el orden de ``datos['test']`` elegible para clasificación.
    """
    test = datos["test"][datos["test"]["elegible_clasificacion"] == 1].reset_index(drop=True)
    y = test["alto_impacto"].to_numpy(dtype=int)

    cuartiles = pd.qcut(
        test["pib_pc_log"].fillna(test["pib_pc_log"].median()),
        4,
        labels=["PIB muy bajo", "PIB bajo", "PIB alto", "PIB muy alto"],
        duplicates="drop",
    )
    dimensiones = {
        "region": test["region"].astype(str).to_numpy(),
        "pib_cuartil": np.asarray(cuartiles.astype(str)),
        "tipo": test["tipo"].astype(str).to_numpy(),
    }

    filas = []
    for dimension, valores in dimensiones.items():
        for valor in pd.Series(valores).value_counts().index:
            mascara = valores == valor
            if mascara.sum() < 15:
                continue
            for modelo, probabilidad in probabilidades.items():
                fila = {
                    "dimension": dimension,
                    "grupo": str(valor),
                    "modelo": modelo,
                    **_metricas_grupo(y[mascara], probabilidad[mascara], umbrales[modelo]),
                }
                filas.append(fila)
    return pd.DataFrame(filas)


def estabilidad(probabilidades: dict[str, np.ndarray], umbrales: dict[str, float]) -> pd.DataFrame:
    """Métricas por año de prueba (2024 y 2025)."""
    test = pd.read_csv(config.RESULTADOS_ML / "pred_nn_test.csv")
    y = test["y"].to_numpy(dtype=int)
    anios = test["anio"].to_numpy(dtype=int)

    filas = []
    for anio in sorted(set(anios)):
        mascara = anios == anio
        for modelo, probabilidad in probabilidades.items():
            filas.append(
                {
                    "anio": int(anio),
                    "modelo": modelo,
                    **_metricas_grupo(y[mascara], probabilidad[mascara], umbrales[modelo]),
                }
            )
    return pd.DataFrame(filas)


def generar_todo() -> dict[str, pd.DataFrame]:
    """Ejecuta la ablación, la equidad y la estabilidad; guarda las tablas."""
    datos = cargar_y_preparar()
    preprocesador = Preprocesador.leer(config.MODELOS / "preprocesador.json")

    metricas = json.loads((config.MODELOS / "metricas.json").read_text(encoding="utf-8"))
    clasificacion = metricas["clasificacion"]
    umbrales = {
        "red_neuronal": float(clasificacion["umbrales"]["red_neuronal"]),
        "xgboost": float(clasificacion["umbrales"]["xgboost"]),
    }

    prueba = pd.read_csv(config.RESULTADOS_ML / "pred_nn_test.csv")
    xgb = pd.read_csv(config.RESULTADOS_ML / "pred_xgb_test.csv")
    probabilidades = {
        "red_neuronal": prueba["nn"].to_numpy(dtype=float),
        "xgboost": xgb["xgb"].to_numpy(dtype=float),
    }

    config.RESULTADOS_ML.mkdir(parents=True, exist_ok=True)
    tablas = {
        "ablacion": ablacion(datos, preprocesador),
        "equidad": equidad(datos, probabilidades, umbrales),
        "estabilidad": estabilidad(probabilidades, umbrales),
    }
    tablas["ablacion"].to_csv(config.RESULTADOS_ML / "ablacion_xgb.csv", index=False)
    tablas["equidad"].to_csv(config.RESULTADOS_ML / "equidad_modelos.csv", index=False)
    tablas["estabilidad"].to_csv(
        config.RESULTADOS_ML / "estabilidad_temporal.csv", index=False
    )
    return tablas


if __name__ == "__main__":
    resultado = generar_todo()
    for nombre, tabla in resultado.items():
        print(f"\n### {nombre}\n{tabla.to_string(index=False)}")
