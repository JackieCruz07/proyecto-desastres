"""Métricas, intervalos de confianza y comparación de modelos."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    median_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)


def umbral_optimo(y: np.ndarray, probabilidad: np.ndarray) -> float:
    """Umbral que maximiza F1 sobre validación."""
    candidatos = np.arange(0.05, 0.96, 0.01)
    puntajes = [f1_score(y, (probabilidad >= u).astype(int), zero_division=0) for u in candidatos]
    return float(candidatos[int(np.argmax(puntajes))])


def evaluar_clasificacion(
    y: np.ndarray, probabilidad: np.ndarray, umbral: float = 0.5
) -> dict:
    y = np.asarray(y).astype(int)
    p = np.clip(np.asarray(probabilidad, dtype=float), 1e-7, 1 - 1e-7)
    pred = (p >= umbral).astype(int)
    matriz = confusion_matrix(y, pred, labels=[0, 1])
    tn, fp, fn, tp = matriz.ravel()
    return {
        "n": int(len(y)),
        "positivos": int(y.sum()),
        "prevalencia": float(y.mean()),
        "umbral": float(umbral),
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p)),
        "verdaderos_negativos": int(tn),
        "falsos_positivos": int(fp),
        "falsos_negativos": int(fn),
        "verdaderos_positivos": int(tp),
        "exactitud": float((tp + tn) / len(y)),
    }


def bootstrap_ic(
    y: np.ndarray,
    probabilidad: np.ndarray,
    metrica: str = "roc_auc",
    n_repeticiones: int = 1000,
    semilla: int = 42,
) -> tuple[float, float]:
    rng = np.random.default_rng(semilla)
    y = np.asarray(y).astype(int)
    probabilidad = np.asarray(probabilidad, dtype=float)
    valores = []
    for _ in range(n_repeticiones):
        indices = rng.integers(0, len(y), len(y))
        if len(np.unique(y[indices])) < 2:
            continue
        if metrica == "roc_auc":
            valores.append(roc_auc_score(y[indices], probabilidad[indices]))
        elif metrica == "pr_auc":
            valores.append(average_precision_score(y[indices], probabilidad[indices]))
        elif metrica == "f1":
            valores.append(
                f1_score(
                    y[indices],
                    (probabilidad[indices] >= 0.5).astype(int),
                    zero_division=0,
                )
            )
    if not valores:
        return (float("nan"), float("nan"))
    return (float(np.percentile(valores, 2.5)), float(np.percentile(valores, 97.5)))


def comparar_bootstrap(
    y: np.ndarray,
    prob_a: np.ndarray,
    prob_b: np.ndarray,
    metrica: str = "roc_auc",
    n_repeticiones: int = 1000,
    semilla: int = 42,
) -> dict:
    """Diferencia pareada (A − B) con intervalo de confianza bootstrap."""
    rng = np.random.default_rng(semilla)
    y = np.asarray(y).astype(int)
    a = np.asarray(prob_a, dtype=float)
    b = np.asarray(prob_b, dtype=float)

    def puntuar(yy, pp):
        if metrica == "roc_auc":
            return roc_auc_score(yy, pp)
        if metrica == "pr_auc":
            return average_precision_score(yy, pp)
        return f1_score(yy, (pp >= 0.5).astype(int), zero_division=0)

    diferencias = []
    for _ in range(n_repeticiones):
        indices = rng.integers(0, len(y), len(y))
        if len(np.unique(y[indices])) < 2:
            continue
        diferencias.append(puntuar(y[indices], a[indices]) - puntuar(y[indices], b[indices]))

    diferencia = puntuar(y, a) - puntuar(y, b)
    return {
        "metrica": metrica,
        "diferencia": float(diferencia),
        "ic95_inferior": float(np.percentile(diferencias, 2.5)),
        "ic95_superior": float(np.percentile(diferencias, 97.5)),
        "p_valor_aproximado": float(
            2 * min(np.mean(np.array(diferencias) <= 0), np.mean(np.array(diferencias) >= 0))
        ),
        "n_repeticiones": len(diferencias),
    }


def tabla_calibracion(
    y: np.ndarray, probabilidad: np.ndarray, bins: int = 10
) -> pd.DataFrame:
    y = np.asarray(y).astype(int)
    p = np.asarray(probabilidad, dtype=float)
    cortes = np.linspace(0, 1, bins + 1)
    grupo = np.clip(np.digitize(p, cortes) - 1, 0, bins - 1)
    filas = []
    for i in range(bins):
        mascara = grupo == i
        if not mascara.any():
            continue
        filas.append(
            {
                "bin": i + 1,
                "inicio": float(cortes[i]),
                "fin": float(cortes[i + 1]),
                "n": int(mascara.sum()),
                "probabilidad_media": float(p[mascara].mean()),
                "frecuencia_observada": float(y[mascara].mean()),
            }
        )
    return pd.DataFrame(filas)


def evaluar_regresion(y_log: np.ndarray, pred_log: np.ndarray) -> dict:
    y_log = np.asarray(y_log, dtype=float)
    pred_log = np.asarray(pred_log, dtype=float)
    y = np.expm1(y_log)
    pred = np.expm1(pred_log)
    return {
        "n": int(len(y)),
        "mae_log": float(mean_absolute_error(y_log, pred_log)),
        "rmse_log": float(np.sqrt(mean_squared_error(y_log, pred_log))),
        "r2_log": float(r2_score(y_log, pred_log)),
        "medae_log": float(median_absolute_error(y_log, pred_log)),
        "mae_original": float(mean_absolute_error(y, pred)),
        "rmse_original": float(np.sqrt(mean_squared_error(y, pred))),
        "r2_original": float(r2_score(y, pred)),
        "medae_original": float(median_absolute_error(y, pred)),
    }


def cobertura_intervalos(
    y_log: np.ndarray, inferior_log: np.ndarray, superior_log: np.ndarray
) -> dict:
    y = np.expm1(np.asarray(y_log, dtype=float))
    inferior = np.expm1(np.asarray(inferior_log, dtype=float))
    superior = np.expm1(np.asarray(superior_log, dtype=float))
    dentro = (y >= inferior) & (y <= superior)
    ancho = superior - inferior
    return {
        "cobertura": float(dentro.mean()),
        "ancho_medio": float(ancho.mean()),
        "ancho_mediano": float(np.median(ancho)),
        "n": int(len(y)),
    }
