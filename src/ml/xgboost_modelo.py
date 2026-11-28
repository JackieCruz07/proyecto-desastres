"""Entrenamiento, evaluación y exportación de XGBoost.

La exportación convierte los árboles a una estructura plana que la
aplicación puede recorrer en JavaScript, sin servidor ni dependencias.
"""

from __future__ import annotations

import json
import math
import os
import random
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score

from . import config

N_HILOS = max(1, min(8, os.cpu_count() or 1))


def _matriz(X: pd.DataFrame, y: np.ndarray | None = None) -> xgb.DMatrix:
    return xgb.DMatrix(
        X,
        label=y,
        feature_names=list(X.columns),
        nthread=N_HILOS,
        enable_categorical=False,
    )


def parametros_base_clasificacion(y: np.ndarray) -> dict:
    positivos = float(np.sum(y))
    negativos = float(len(y) - positivos)
    return {
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "tree_method": "hist",
        "eta": 0.05,
        "max_depth": 5,
        "subsample": 0.9,
        "colsample_bytree": 0.8,
        "min_child_weight": 2,
        "gamma": 0.0,
        "lambda": 1.0,
        "alpha": 0.0,
        "scale_pos_weight": max(1.0, negativos / max(1.0, positivos)),
        "seed": config.SEMILLA,
        "nthread": N_HILOS,
    }


def parametros_base_regresion() -> dict:
    return {
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        "tree_method": "hist",
        "eta": 0.05,
        "max_depth": 5,
        "subsample": 0.9,
        "colsample_bytree": 0.8,
        "min_child_weight": 2,
        "gamma": 0.0,
        "lambda": 1.0,
        "alpha": 0.0,
        "seed": config.SEMILLA,
        "nthread": N_HILOS,
    }


def _entrenar(
    params: dict,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_val: pd.DataFrame,
    y_val: np.ndarray,
    num_boost_round: int = 600,
    early_stopping_rounds: int = 50,
) -> xgb.Booster:
    dtr = _matriz(X_train, y_train)
    dval = _matriz(X_val, y_val)
    booster = xgb.train(
        params,
        dtr,
        num_boost_round=num_boost_round,
        evals=[(dval, "validacion")],
        early_stopping_rounds=early_stopping_rounds,
        verbose_eval=False,
    )
    return booster


def predecir(booster: xgb.Booster, X: pd.DataFrame) -> np.ndarray:
    d = _matriz(X)
    rango = (0, int(getattr(booster, "best_iteration", 0)) + 1)
    return booster.predict(d, iteration_range=rango)


def predecir_margen(booster: xgb.Booster, X: pd.DataFrame) -> np.ndarray:
    """Logit (margen) antes de la sigmoide, para calibrar temperatura."""
    d = _matriz(X)
    rango = (0, int(getattr(booster, "best_iteration", 0)) + 1)
    return booster.predict(d, output_margin=True, iteration_range=rango)


def buscar_hiperparametros_clasificacion(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_val: pd.DataFrame,
    y_val: np.ndarray,
    n_pruebas: int = 30,
    semilla: int = config.SEMILLA,
) -> tuple[dict, xgb.Booster, pd.DataFrame]:
    """Búsqueda aleatoria con validación temporal.

    La validación es 2023; la prueba 2024–2025 permanece intacta. Se elige la
    configuración con mejor ROC-AUC de validación.
    """
    rng = random.Random(semilla)
    base = parametros_base_clasificacion(y_train)
    mejor_score = -np.inf
    mejor_params = dict(base)
    mejor_booster = None
    filas = []

    for prueba in range(n_pruebas):
        params = dict(base)
        params.update(
            {
                "max_depth": rng.choice([3, 4, 5, 6, 7]),
                "eta": rng.choice([0.03, 0.04, 0.05, 0.07, 0.1]),
                "subsample": rng.choice([0.7, 0.8, 0.9, 1.0]),
                "colsample_bytree": rng.choice([0.6, 0.7, 0.8, 0.9, 1.0]),
                "min_child_weight": rng.choice([1, 2, 3, 5, 8]),
                "gamma": rng.choice([0.0, 0.1, 0.3, 0.5]),
                "lambda": rng.choice([0.5, 1.0, 2.0, 5.0]),
                "alpha": rng.choice([0.0, 0.1, 0.5]),
                "scale_pos_weight": rng.choice(
                    [1.0, base["scale_pos_weight"], 1.5 * base["scale_pos_weight"]]
                ),
            }
        )
        booster = _entrenar(
            params,
            X_train,
            y_train,
            X_val,
            y_val,
            num_boost_round=500,
            early_stopping_rounds=40,
        )
        pred = predecir(booster, X_val)
        score = float(roc_auc_score(y_val, pred))
        filas.append(
            {
                "prueba": prueba + 1,
                "auc_validacion": score,
                "mejor_iteracion": int(getattr(booster, "best_iteration", 0)),
                **{
                    k: params[k]
                    for k in [
                        "max_depth",
                        "eta",
                        "subsample",
                        "colsample_bytree",
                        "min_child_weight",
                        "gamma",
                        "lambda",
                        "alpha",
                        "scale_pos_weight",
                    ]
                },
            }
        )
        if score > mejor_score:
            mejor_score = score
            mejor_params = dict(params)
            mejor_booster = booster

    assert mejor_booster is not None
    return mejor_params, mejor_booster, pd.DataFrame(filas)


def buscar_hiperparametros_regresion(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_val: pd.DataFrame,
    y_val: np.ndarray,
    n_pruebas: int = 20,
    semilla: int = config.SEMILLA,
) -> tuple[dict, xgb.Booster, pd.DataFrame]:
    rng = random.Random(semilla)
    base = parametros_base_regresion()
    mejor_rmse = np.inf
    mejor_params = dict(base)
    mejor_booster = None
    filas = []

    for prueba in range(n_pruebas):
        params = dict(base)
        params.update(
            {
                "max_depth": rng.choice([3, 4, 5, 6, 7]),
                "eta": rng.choice([0.03, 0.05, 0.07, 0.1]),
                "subsample": rng.choice([0.7, 0.8, 0.9, 1.0]),
                "colsample_bytree": rng.choice([0.6, 0.7, 0.8, 0.9, 1.0]),
                "min_child_weight": rng.choice([1, 2, 3, 5, 8]),
                "gamma": rng.choice([0.0, 0.1, 0.3]),
                "lambda": rng.choice([0.5, 1.0, 2.0, 5.0]),
                "alpha": rng.choice([0.0, 0.1, 0.5]),
            }
        )
        booster = _entrenar(
            params,
            X_train,
            y_train,
            X_val,
            y_val,
            num_boost_round=500,
            early_stopping_rounds=40,
        )
        pred = predecir(booster, X_val)
        rmse = float(np.sqrt(np.mean((pred - y_val) ** 2)))
        filas.append(
            {
                "prueba": prueba + 1,
                "rmse_validacion": rmse,
                "mejor_iteracion": int(getattr(booster, "best_iteration", 0)),
                **{
                    k: params[k]
                    for k in [
                        "max_depth",
                        "eta",
                        "subsample",
                        "colsample_bytree",
                        "min_child_weight",
                        "gamma",
                        "lambda",
                        "alpha",
                    ]
                },
            }
        )
        if rmse < mejor_rmse:
            mejor_rmse = rmse
            mejor_params = dict(params)
            mejor_booster = booster

    assert mejor_booster is not None
    return mejor_params, mejor_booster, pd.DataFrame(filas)


def contribuciones_shap(booster: xgb.Booster, X: pd.DataFrame) -> tuple[np.ndarray, float]:
    """SHAP exacto de XGBoost (TreeSHAP) sin depender del paquete shap."""
    d = _matriz(X)
    contribuciones = booster.predict(d, pred_contribs=True)
    return contribuciones[:, :-1], float(contribuciones[0, -1])


def importancia_permutacion(
    predecir_funcion,
    X: pd.DataFrame,
    y: np.ndarray,
    metrica,
    n_repeticiones: int = 8,
    semilla: int = config.SEMILLA,
) -> pd.DataFrame:
    """Importancia por permutación, útil para la red neuronal."""
    rng = np.random.default_rng(semilla)
    base = float(metrica(y, predecir_funcion(X)))
    filas = []
    for columna in X.columns:
        valores = X[columna].to_numpy(copy=True)
        scores = []
        for _ in range(n_repeticiones):
            copia = X.copy()
            rng.shuffle(valores)
            copia[columna] = valores
            scores.append(float(metrica(y, predecir_funcion(copia))))
        filas.append(
            {
                "variable": columna,
                "importancia": base - float(np.mean(scores)),
                "desviacion": float(np.std(scores)),
            }
        )
    return pd.DataFrame(filas).sort_values("importancia", ascending=False)


# ----------------------------------------------------------------------
# Exportación de árboles a JSON plano
# ----------------------------------------------------------------------
def _base_margen(booster: xgb.Booster) -> float:
    """Margen inicial del booster (antes de sumar las hojas)."""
    configuracion = json.loads(booster.save_config())
    objetivo = configuracion["learner"]["objective"]["name"]
    base_score_texto = str(
        configuracion["learner"]["learner_model_param"]["base_score"]
    ).strip("[]")
    base_score = float(base_score_texto.split(",")[0])
    if "logistic" in objetivo or "binary" in objetivo:
        base_score = min(max(base_score, 1e-9), 1 - 1e-9)
        return float(math.log(base_score / (1 - base_score)))
    return base_score


def exportar_arboles(booster: xgb.Booster, columnas: list[str]) -> dict:
    """Convierte el booster en una lista de árboles recorribles en JS."""
    modelo = json.loads(bytes(booster.save_raw(raw_format="json")))
    arboles_json = modelo["learner"]["gradient_booster"]["model"]["trees"]
    limite = int(getattr(booster, "best_iteration", len(arboles_json) - 1)) + 1
    arboles_json = arboles_json[:limite]
    arboles = []

    for arbol in arboles_json:
        izquierda = arbol["left_children"]
        derecha = arbol["right_children"]
        indices = arbol["split_indices"]
        umbrales = arbol["split_conditions"]
        hojas = arbol["base_weights"]
        por_defecto = arbol["default_left"]
        nodos = []
        for i in range(len(izquierda)):
            if izquierda[i] == -1:
                nodos.append(
                    {
                        "f": -1,
                        "v": round(float(hojas[i]), 7),
                    }
                )
            else:
                nodos.append(
                    {
                        "f": int(indices[i]),
                        "u": round(float(umbrales[i]), 7),
                        "i": int(izquierda[i]),
                        "d": int(derecha[i]),
                        "n": bool(por_defecto[i]),
                    }
                )
        arboles.append(nodos)

    return {
        "columnas": list(columnas),
        "base_margen": round(_base_margen(booster), 8),
        "objetivo": json.loads(booster.save_config())["learner"]["objective"]["name"],
        "n_arboles": len(arboles),
        "arboles": arboles,
    }


def predecir_con_arboles(exportado: dict, fila: np.ndarray) -> float:
    """Implementación de referencia en Python del recorrido que hará JS."""
    margen = float(exportado["base_margen"])
    for arbol in exportado["arboles"]:
        nodo = 0
        while True:
            actual = arbol[nodo]
            if actual["f"] == -1:
                margen += actual["v"]
                break
            valor = fila[actual["f"]]
            if valor is None or (isinstance(valor, float) and math.isnan(valor)):
                nodo = actual["i"] if actual["n"] else actual["d"]
            elif valor < actual["u"]:
                nodo = actual["i"]
            else:
                nodo = actual["d"]
    return margen


def guardar_booster(booster: xgb.Booster, ruta: Path | str) -> Path:
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(destino)
    return destino
