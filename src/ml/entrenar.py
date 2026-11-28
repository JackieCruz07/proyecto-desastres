"""Pipeline de entrenamiento de las Actividades 9–12.

Cada función guarda sus modelos y métricas para que los notebooks y la
aplicación reutilicen exactamente los mismos artefactos.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .datos import cargar_y_preparar, resumen_particiones
from .evaluacion import (
    bootstrap_ic,
    comparar_bootstrap,
    cobertura_intervalos,
    evaluar_clasificacion,
    evaluar_regresion,
    tabla_calibracion,
    umbral_optimo,
)
from .preprocesamiento import Preprocesador
from .red_neuronal import (
    calibrar_temperatura,
    entrenar_ensamble_clasificador,
    entrenar_ensamble_regresor,
    exportar_pesos,
    guardar_ensamble,
    predecir_logits,
    predecir_probabilidad,
    predecir_regresor,
)
from .xgboost_modelo import (
    buscar_hiperparametros_clasificacion,
    buscar_hiperparametros_regresion,
    contribuciones_shap,
    exportar_arboles,
    guardar_booster,
    predecir,
    predecir_margen,
)


def _sigmoide(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def _guardar_json(datos: dict | list, ruta: Path | str) -> Path:
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(datos, ensure_ascii=False, indent=1, default=float),
        encoding="utf-8",
    )
    return destino


def _predicciones(
    parte: pd.DataFrame,
    probabilidad: np.ndarray,
    nombre: str,
    etiqueta: str,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "DisNo.": parte["DisNo."].to_numpy(),
            "anio": parte["anio"].astype(int).to_numpy(),
            "y": parte[nombre].astype(int).to_numpy(),
            etiqueta: probabilidad,
        }
    )


def preparar(datos: dict | None = None) -> tuple[dict, Preprocesador]:
    datos = datos or cargar_y_preparar()
    config.RESULTADOS_ML.mkdir(parents=True, exist_ok=True)
    config.MODELOS.mkdir(parents=True, exist_ok=True)
    entrenamiento = datos["train"][datos["train"]["elegible_clasificacion"] == 1]
    preprocesador = Preprocesador().fit(entrenamiento)
    preprocesador.guardar(config.MODELOS / "preprocesador.json")
    resumen_particiones(datos["train"], datos["val"], datos["test"]).to_csv(
        config.RESULTADOS_ML / "resumen_particiones.csv", index=False
    )
    return datos, preprocesador


# ----------------------------------------------------------------------
# Actividad 9. Red neuronal de clasificación
# ----------------------------------------------------------------------
def entrenar_nn_clasificacion(
    datos: dict,
    preprocesador: Preprocesador,
    n_modelos: int = 5,
    guardar: bool = True,
) -> dict:
    train = datos["train"][datos["train"]["elegible_clasificacion"] == 1].copy()
    val = datos["val"][datos["val"]["elegible_clasificacion"] == 1].copy()
    test = datos["test"][datos["test"]["elegible_clasificacion"] == 1].copy()

    Xc_tr, Xn_tr = preprocesador.transform_nn(train)
    Xc_va, Xn_va = preprocesador.transform_nn(val)
    Xc_te, Xn_te = preprocesador.transform_nn(test)
    y_tr = train["alto_impacto"].to_numpy(dtype=int)
    y_va = val["alto_impacto"].to_numpy(dtype=int)
    y_te = test["alto_impacto"].to_numpy(dtype=int)

    modelos, historiales = entrenar_ensamble_clasificador(
        Xc_tr,
        Xn_tr,
        y_tr,
        Xc_va,
        Xn_va,
        y_va,
        preprocesador.cardinalidades,
        n_modelos=n_modelos,
    )
    logits_val = predecir_logits(modelos, Xc_va, Xn_va)
    temperatura = calibrar_temperatura(logits_val, y_va)
    prob_val = predecir_probabilidad(modelos, Xc_va, Xn_va, temperatura)
    prob_test = predecir_probabilidad(modelos, Xc_te, Xn_te, temperatura)
    umbral = umbral_optimo(y_va, prob_val)

    metricas_val = evaluar_clasificacion(y_va, prob_val, umbral)
    metricas_test = evaluar_clasificacion(y_te, prob_test, umbral)
    metricas_test["roc_auc_ic95"] = bootstrap_ic(y_te, prob_test, "roc_auc")
    metricas_test["pr_auc_ic95"] = bootstrap_ic(y_te, prob_test, "pr_auc")
    metricas_test["f1_ic95"] = bootstrap_ic(y_te, prob_test, "f1")

    if guardar:
        config.MODELOS.mkdir(parents=True, exist_ok=True)
        guardar_ensamble(
            modelos,
            config.MODELOS / "clasificador_red_neuronal.pt",
            metadatos={
                "temperatura": temperatura,
                "umbral": umbral,
                "cardinalidades": preprocesador.cardinalidades,
                "columnas_categoricas": preprocesador.cat_cols,
                "columnas_numericas": preprocesador.num_cols_modelo,
                "n_modelos": n_modelos,
                "metricas_validacion": metricas_val,
                "metricas_prueba": metricas_test,
            },
        )
        _guardar_json(
            {
                "modelo": "red_neuronal_clasificacion",
                "temperatura": temperatura,
                "umbral": umbral,
                "validacion": metricas_val,
                "prueba": metricas_test,
            },
            config.MODELOS / "metricas_nn_clasificacion.json",
        )
        historial = pd.DataFrame(
            [
                {"semilla": i + 1, **fila}
                for i, h in enumerate(historiales)
                for fila in h
            ]
        )
        historial.to_csv(config.RESULTADOS_ML / "historial_nn_clasificacion.csv", index=False)
        _predicciones(val, prob_val, "alto_impacto", "nn").to_csv(
            config.RESULTADOS_ML / "pred_nn_val.csv", index=False
        )
        _predicciones(test, prob_test, "alto_impacto", "nn").to_csv(
            config.RESULTADOS_ML / "pred_nn_test.csv", index=False
        )
        tabla_calibracion(y_te, prob_test).to_csv(
            config.RESULTADOS_ML / "calibracion_nn.csv", index=False
        )

    return {
        "modelos": modelos,
        "temperatura": temperatura,
        "umbral": umbral,
        "prob_val": prob_val,
        "prob_test": prob_test,
        "y_val": y_va,
        "y_test": y_te,
        "validacion": metricas_val,
        "prueba": metricas_test,
        "historiales": historiales,
        "test": test,
        "val": val,
    }


# ----------------------------------------------------------------------
# Actividad 10. XGBoost de clasificación
# ----------------------------------------------------------------------
def entrenar_xgb_clasificacion(
    datos: dict,
    preprocesador: Preprocesador,
    n_pruebas: int = 30,
    guardar: bool = True,
) -> dict:
    train = datos["train"][datos["train"]["elegible_clasificacion"] == 1].copy()
    val = datos["val"][datos["val"]["elegible_clasificacion"] == 1].copy()
    test = datos["test"][datos["test"]["elegible_clasificacion"] == 1].copy()

    X_tr = preprocesador.transform_xgb(train)
    X_va = preprocesador.transform_xgb(val)
    X_te = preprocesador.transform_xgb(test)
    y_tr = train["alto_impacto"].to_numpy(dtype=int)
    y_va = val["alto_impacto"].to_numpy(dtype=int)
    y_te = test["alto_impacto"].to_numpy(dtype=int)

    params, booster, pruebas = buscar_hiperparametros_clasificacion(
        X_tr, y_tr, X_va, y_va, n_pruebas=n_pruebas
    )
    margen_val = predecir_margen(booster, X_va)
    margen_test = predecir_margen(booster, X_te)
    temperatura = calibrar_temperatura(margen_val, y_va)
    prob_val = _sigmoide(margen_val / temperatura)
    prob_test = _sigmoide(margen_test / temperatura)
    umbral = umbral_optimo(y_va, prob_val)

    metricas_val = evaluar_clasificacion(y_va, prob_val, umbral)
    metricas_test = evaluar_clasificacion(y_te, prob_test, umbral)
    metricas_test["roc_auc_ic95"] = bootstrap_ic(y_te, prob_test, "roc_auc")
    metricas_test["pr_auc_ic95"] = bootstrap_ic(y_te, prob_test, "pr_auc")
    metricas_test["f1_ic95"] = bootstrap_ic(y_te, prob_test, "f1")

    contribuciones, sesgo = contribuciones_shap(booster, X_te)
    importancia = pd.DataFrame(
        {
            "variable": X_te.columns,
            "shap_medio_absoluto": np.abs(contribuciones).mean(axis=0),
        }
    ).sort_values("shap_medio_absoluto", ascending=False)

    if guardar:
        config.MODELOS.mkdir(parents=True, exist_ok=True)
        guardar_booster(booster, config.MODELOS / "clasificador_xgboost.json")
        exportado = exportar_arboles(booster, list(X_tr.columns))
        _guardar_json(exportado, config.MODELOS / "clasificador_xgboost_arboles.json")
        _guardar_json(
            {
                "modelo": "xgboost_clasificacion",
                "temperatura": temperatura,
                "umbral": umbral,
                "parametros": params,
                "mejor_iteracion": int(getattr(booster, "best_iteration", 0)),
                "sesgo_shap": sesgo,
                "validacion": metricas_val,
                "prueba": metricas_test,
            },
            config.MODELOS / "metricas_xgb_clasificacion.json",
        )
        pruebas.to_csv(config.RESULTADOS_ML / "busqueda_xgb_clasificacion.csv", index=False)
        importancia.to_csv(config.RESULTADOS_ML / "shap_xgb_clasificacion.csv", index=False)
        _predicciones(val, prob_val, "alto_impacto", "xgb").to_csv(
            config.RESULTADOS_ML / "pred_xgb_val.csv", index=False
        )
        _predicciones(test, prob_test, "alto_impacto", "xgb").to_csv(
            config.RESULTADOS_ML / "pred_xgb_test.csv", index=False
        )
        tabla_calibracion(y_te, prob_test).to_csv(
            config.RESULTADOS_ML / "calibracion_xgb.csv", index=False
        )

    # La comparación real con la red se calcula al final, cuando ambas existen.
    return {
        "booster": booster,
        "parametros": params,
        "temperatura": temperatura,
        "umbral": umbral,
        "prob_val": prob_val,
        "prob_test": prob_test,
        "y_val": y_va,
        "y_test": y_te,
        "validacion": metricas_val,
        "prueba": metricas_test,
        "pruebas": pruebas,
        "importancia": importancia,
        "exportado": exportar_arboles(booster, list(X_tr.columns)),
        "test": test,
        "val": val,
    }


# ----------------------------------------------------------------------
# Actividad 11. Regresión de impacto
# ----------------------------------------------------------------------
def entrenar_regresion(
    datos: dict,
    preprocesador: Preprocesador,
    objetivo: str,
    nombre: str,
    n_modelos: int = 5,
    n_pruebas: int = 20,
    guardar: bool = True,
) -> dict:
    train = datos["train"][datos["train"][objetivo].notna()].copy()
    val = datos["val"][datos["val"][objetivo].notna()].copy()
    test = datos["test"][datos["test"][objetivo].notna()].copy()

    Xc_tr, Xn_tr = preprocesador.transform_nn(train)
    Xc_va, Xn_va = preprocesador.transform_nn(val)
    Xc_te, Xn_te = preprocesador.transform_nn(test)
    y_tr = train[objetivo].to_numpy(dtype=float)
    y_va = val[objetivo].to_numpy(dtype=float)
    y_te = test[objetivo].to_numpy(dtype=float)

    modelos, historiales, estadisticas = entrenar_ensamble_regresor(
        Xc_tr,
        Xn_tr,
        y_tr,
        Xc_va,
        Xn_va,
        y_va,
        preprocesador.cardinalidades,
        n_modelos=n_modelos,
    )
    pred_nn_val = predecir_regresor(modelos, Xc_va, Xn_va, estadisticas)
    pred_nn_test = predecir_regresor(modelos, Xc_te, Xn_te, estadisticas)

    X_tr = preprocesador.transform_xgb(train)
    X_va = preprocesador.transform_xgb(val)
    X_te = preprocesador.transform_xgb(test)
    params, booster, pruebas = buscar_hiperparametros_regresion(
        X_tr, y_tr, X_va, y_va, n_pruebas=n_pruebas
    )
    pred_xgb_val = predecir(booster, X_va)
    pred_xgb_test = predecir(booster, X_te)
    exportado = exportar_arboles(booster, list(X_tr.columns))

    # Intervalos empíricos al 80 % a partir de los residuales de validación.
    residual_val = y_va - pred_xgb_val
    q10, q90 = np.quantile(residual_val, [0.1, 0.9])
    inferior = pred_xgb_test + q10
    superior = pred_xgb_test + q90

    metricas = {
        "red_neuronal": {
            "validacion": evaluar_regresion(y_va, pred_nn_val),
            "prueba": evaluar_regresion(y_te, pred_nn_test),
        },
        "xgboost": {
            "validacion": evaluar_regresion(y_va, pred_xgb_val),
            "prueba": evaluar_regresion(y_te, pred_xgb_test),
            "intervalos": {
                "q10_residual": float(q10),
                "q90_residual": float(q90),
                "prueba": cobertura_intervalos(y_te, inferior, superior),
            },
        },
        "n_validacion": int(len(y_va)),
        "n_prueba": int(len(y_te)),
        "target": objetivo,
    }

    if guardar:
        config.MODELOS.mkdir(parents=True, exist_ok=True)
        guardar_ensamble(
            modelos,
            config.MODELOS / f"regresor_{nombre}_red_neuronal.pt",
            metadatos={
                "estadisticas": estadisticas,
                "n_modelos": n_modelos,
                "target": objetivo,
                "metricas": metricas,
            },
        )
        guardar_booster(booster, config.MODELOS / f"regresor_{nombre}_xgboost.json")
        exportado = exportar_arboles(booster, list(X_tr.columns))
        _guardar_json(exportado, config.MODELOS / f"regresor_{nombre}_xgboost_arboles.json")
        _guardar_json(
            {
                "modelo": f"xgboost_regresion_{nombre}",
                "parametros": params,
                "mejor_iteracion": int(getattr(booster, "best_iteration", 0)),
                "target": objetivo,
                "metricas": metricas,
            },
            config.MODELOS / f"metricas_xgb_{nombre}.json",
        )
        pruebas.to_csv(
            config.RESULTADOS_ML / f"busqueda_xgb_{nombre}.csv", index=False
        )
        historial = pd.DataFrame(
            [
                {"semilla": i + 1, **fila}
                for i, h in enumerate(historiales)
                for fila in h
            ]
        )
        historial.to_csv(
            config.RESULTADOS_ML / f"historial_nn_{nombre}.csv", index=False
        )
        pd.DataFrame(
            {
                "DisNo.": test["DisNo."].to_numpy(),
                "anio": test["anio"].astype(int).to_numpy(),
                "y_log": y_te,
                "nn_log": pred_nn_test,
                "xgb_log": pred_xgb_test,
                "xgb_inferior_log": inferior,
                "xgb_superior_log": superior,
            }
        ).to_csv(config.RESULTADOS_ML / f"predicciones_{nombre}_test.csv", index=False)

    return {
        "modelos": modelos,
        "estadisticas": estadisticas,
        "booster": booster,
        "parametros": params,
        "pred_nn_val": pred_nn_val,
        "pred_nn_test": pred_nn_test,
        "pred_xgb_val": pred_xgb_val,
        "pred_xgb_test": pred_xgb_test,
        "y_val": y_va,
        "y_test": y_te,
        "metricas": metricas,
        "pruebas": pruebas,
        "test": test,
        "val": val,
        "exportado": exportado,
    }


# ----------------------------------------------------------------------
# Orquestación
# ----------------------------------------------------------------------
def entrenar_todo(rapido: bool = False) -> dict:
    datos, preprocesador = preparar()
    n_modelos = 2 if rapido else 5
    n_pruebas_clf = 5 if rapido else 30
    n_pruebas_reg = 4 if rapido else 20

    print("Entrenando red neuronal de clasificación…")
    nn = entrenar_nn_clasificacion(datos, preprocesador, n_modelos=n_modelos)
    print("Entrenando XGBoost de clasificación…")
    xgb = entrenar_xgb_clasificacion(datos, preprocesador, n_pruebas=n_pruebas_clf)
    print("Entrenando regresión de personas afectadas…")
    afectados = entrenar_regresion(
        datos, preprocesador, "log_afectados", "afectados",
        n_modelos=n_modelos, n_pruebas=n_pruebas_reg,
    )
    print("Entrenando regresión de daño económico…")
    dano = entrenar_regresion(
        datos, preprocesador, "log_dano", "dano",
        n_modelos=n_modelos, n_pruebas=n_pruebas_reg,
    )

    comparacion_auc = comparar_bootstrap(nn["y_test"], nn["prob_test"], xgb["prob_test"], "roc_auc")
    comparacion_pr = comparar_bootstrap(nn["y_test"], nn["prob_test"], xgb["prob_test"], "pr_auc")

    metricas = {
        "clasificacion": {
            "red_neuronal": {"validacion": nn["validacion"], "prueba": nn["prueba"]},
            "xgboost": {"validacion": xgb["validacion"], "prueba": xgb["prueba"]},
            "comparacion_nn_vs_xgb": {
                "roc_auc": comparacion_auc,
                "pr_auc": comparacion_pr,
            },
            "umbrales": {
                "red_neuronal": nn["umbral"],
                "xgboost": xgb["umbral"],
            },
            "temperaturas": {
                "red_neuronal": nn["temperatura"],
                "xgboost": xgb["temperatura"],
            },
        },
        "regresion_afectados": afectados["metricas"],
        "regresion_dano": dano["metricas"],
        "particiones": resumen_particiones(datos["train"], datos["val"], datos["test"]).to_dict(orient="records"),
        "umbrales_alto_impacto": datos["umbrales"],
    }
    _guardar_json(metricas, config.MODELOS / "metricas.json")

    from .exportar import exportar_modelos_app

    exportar_modelos_app(datos, preprocesador, nn, xgb, afectados, dano, metricas)
    print("Listo. Modelos y métricas guardados en modelos/ y app/modelos/.")
    return {
        "datos": datos,
        "preprocesador": preprocesador,
        "nn": nn,
        "xgb": xgb,
        "afectados": afectados,
        "dano": dano,
        "metricas": metricas,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrena los modelos de desastres.")
    parser.add_argument(
        "--rapido",
        action="store_true",
        help="Menos semillas y pruebas de búsqueda para validar el pipeline.",
    )
    argumentos = parser.parse_args()
    entrenar_todo(rapido=argumentos.rapido)


if __name__ == "__main__":
    main()
