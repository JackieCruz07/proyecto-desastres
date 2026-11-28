"""Red neuronal multicapa con embeddings para variables categóricas.

Se entrenan varias semillas y se promedian sus logits. Esa ensamble reduce
la varianza típica de una red pequeña sobre datos tabulares.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path

import numpy as np
import torch
from scipy.optimize import minimize_scalar
from sklearn.metrics import roc_auc_score
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from . import config

torch.set_num_threads(max(1, min(8, os.cpu_count() or 1)))


def _dim_embedding(cardinalidad: int) -> int:
    return int(min(16, max(2, round(cardinalidad ** 0.5))))


class RedNeuronal(nn.Module):
    """MLP con una tabla de embeddings por columna categórica."""

    def __init__(
        self,
        cardinalidades: list[int],
        n_numericas: int,
        ocultas: tuple[int, ...] = (64, 32),
        dropout: float = 0.2,
    ):
        super().__init__()
        self.cardinalidades = list(cardinalidades)
        self.dims_embedding = [_dim_embedding(c) for c in cardinalidades]
        self.embeddings = nn.ModuleList(
            [nn.Embedding(c, d) for c, d in zip(cardinalidades, self.dims_embedding)]
        )

        entrada = sum(self.dims_embedding) + n_numericas
        capas: list[nn.Module] = []
        anterior = entrada
        for ancho in ocultas:
            capas += [nn.Linear(anterior, ancho), nn.ReLU(), nn.Dropout(dropout)]
            anterior = ancho
        capas.append(nn.Linear(anterior, 1))
        self.capas = nn.Sequential(*capas)

    def forward(self, categoricas: torch.Tensor, numericas: torch.Tensor) -> torch.Tensor:
        incrustaciones = [
            embedding(categoricas[:, i])
            for i, embedding in enumerate(self.embeddings)
        ]
        x = torch.cat(incrustaciones + [numericas], dim=1)
        return self.capas(x).squeeze(1)


def _tensores(
    Xc: np.ndarray,
    Xn: np.ndarray,
    y: np.ndarray | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor | None]:
    cat = torch.tensor(Xc, dtype=torch.long)
    num = torch.tensor(Xn, dtype=torch.float32)
    objetivo = None if y is None else torch.tensor(y, dtype=torch.float32)
    return cat, num, objetivo


def _cargador(
    Xc: np.ndarray,
    Xn: np.ndarray,
    y: np.ndarray,
    lote: int,
    semilla: int,
    mezclar: bool,
) -> DataLoader:
    cat, num, objetivo = _tensores(Xc, Xn, y)
    dataset = TensorDataset(cat, num, objetivo)
    generador = torch.Generator().manual_seed(semilla)
    return DataLoader(
        dataset,
        batch_size=lote,
        shuffle=mezclar,
        generator=generador if mezclar else None,
    )


def _crear_modelo(
    cardinalidades: list[int],
    n_numericas: int,
    ocultas: tuple[int, ...],
    dropout: float,
    semilla: int,
) -> RedNeuronal:
    torch.manual_seed(semilla)
    np.random.seed(semilla)
    return RedNeuronal(cardinalidades, n_numericas, ocultas, dropout)


def entrenar_clasificador(
    Xc_train: np.ndarray,
    Xn_train: np.ndarray,
    y_train: np.ndarray,
    Xc_val: np.ndarray,
    Xn_val: np.ndarray,
    y_val: np.ndarray,
    cardinalidades: list[int],
    semilla: int = config.SEMILLA,
    epocas: int = 140,
    paciencia: int = 18,
    lote: int = 256,
    tasa: float = 1e-3,
    dropout: float = 0.2,
    ocultas: tuple[int, ...] = (64, 32),
) -> tuple[RedNeuronal, list[dict], int]:
    """Entrena una red y devuelve el mejor estado según PR-AUC de validación."""
    modelo = _crear_modelo(cardinalidades, Xn_train.shape[1], ocultas, dropout, semilla)

    positivos = float(y_train.sum())
    negativos = float(len(y_train) - positivos)
    peso_positivo = torch.tensor(
        max(1.0, negativos / max(1.0, positivos)), dtype=torch.float32
    )
    criterio = nn.BCEWithLogitsLoss(pos_weight=peso_positivo)
    optimizador = torch.optim.AdamW(modelo.parameters(), lr=tasa, weight_decay=1e-4)
    planificador = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizador, mode="max", factor=0.5, patience=5
    )

    cargador = _cargador(Xc_train, Xn_train, y_train, lote, semilla, True)
    cat_val, num_val, _ = _tensores(Xc_val, Xn_val, y_val)

    mejor_auc = -np.inf
    mejor_estado = copy.deepcopy(modelo.state_dict())
    mejor_epoca = 0
    historial: list[dict] = []
    sin_mejora = 0

    for epoca in range(1, epocas + 1):
        modelo.train()
        perdida_total = 0.0
        for cat, num, objetivo in cargador:
            optimizador.zero_grad()
            logits = modelo(cat, num)
            perdida = criterio(logits, objetivo)
            perdida.backward()
            nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
            optimizador.step()
            perdida_total += float(perdida.item()) * len(objetivo)

        modelo.eval()
        with torch.no_grad():
            logits_val = modelo(cat_val, num_val).numpy()
        auc = (
            float(roc_auc_score(y_val, logits_val))
            if len(np.unique(y_val)) == 2
            else 0.5
        )
        planificador.step(auc)
        historial.append(
            {
                "epoca": epoca,
                "perdida": perdida_total / len(y_train),
                "auc_validacion": auc,
                "tasa": float(optimizador.param_groups[0]["lr"]),
            }
        )

        if auc > mejor_auc + 1e-5:
            mejor_auc = auc
            mejor_estado = copy.deepcopy(modelo.state_dict())
            mejor_epoca = epoca
            sin_mejora = 0
        else:
            sin_mejora += 1
            if sin_mejora >= paciencia:
                break

    modelo.load_state_dict(mejor_estado)
    modelo.eval()
    return modelo, historial, mejor_epoca


def entrenar_ensamble_clasificador(
    Xc_train: np.ndarray,
    Xn_train: np.ndarray,
    y_train: np.ndarray,
    Xc_val: np.ndarray,
    Xn_val: np.ndarray,
    y_val: np.ndarray,
    cardinalidades: list[int],
    n_modelos: int = 5,
    semilla: int = config.SEMILLA,
) -> tuple[list[RedNeuronal], list[list[dict]]]:
    modelos: list[RedNeuronal] = []
    historiales: list[list[dict]] = []
    for i in range(n_modelos):
        modelo, historial, _ = entrenar_clasificador(
            Xc_train,
            Xn_train,
            y_train,
            Xc_val,
            Xn_val,
            y_val,
            cardinalidades,
            semilla=semilla + i * 101,
        )
        modelos.append(modelo)
        historiales.append(historial)
    return modelos, historiales


@torch.no_grad()
def predecir_logits(
    modelos: list[RedNeuronal], Xc: np.ndarray, Xn: np.ndarray
) -> np.ndarray:
    cat, num, _ = _tensores(Xc, Xn)
    logits = []
    for modelo in modelos:
        modelo.eval()
        logits.append(modelo(cat, num).numpy())
    return np.mean(logits, axis=0)


def calibrar_temperatura(logits_val: np.ndarray, y_val: np.ndarray) -> float:
    """Ajusta un único parámetro de temperatura sobre validación."""

    def perdida(temperatura: float) -> float:
        t = max(float(temperatura), 1e-3)
        p = 1.0 / (1.0 + np.exp(-np.clip(logits_val / t, -30, 30)))
        p = np.clip(p, 1e-7, 1 - 1e-7)
        return float(-np.mean(y_val * np.log(p) + (1 - y_val) * np.log(1 - p)))

    resultado = minimize_scalar(perdida, bounds=(0.4, 6.0), method="bounded")
    return float(resultado.x)


def predecir_probabilidad(
    modelos: list[RedNeuronal],
    Xc: np.ndarray,
    Xn: np.ndarray,
    temperatura: float = 1.0,
) -> np.ndarray:
    logits = predecir_logits(modelos, Xc, Xn)
    return 1.0 / (1.0 + np.exp(-np.clip(logits / temperatura, -30, 30)))


def entrenar_regresor(
    Xc_train: np.ndarray,
    Xn_train: np.ndarray,
    y_train: np.ndarray,
    Xc_val: np.ndarray,
    Xn_val: np.ndarray,
    y_val: np.ndarray,
    cardinalidades: list[int],
    semilla: int = config.SEMILLA,
    epocas: int = 160,
    paciencia: int = 20,
    lote: int = 256,
    tasa: float = 1e-3,
    dropout: float = 0.15,
    ocultas: tuple[int, ...] = (64, 32),
) -> tuple[RedNeuronal, list[dict], int, dict]:
    """Entrena una red regresora con objetivo estandarizado y pérdida Huber."""
    y_media = float(np.mean(y_train))
    y_std = float(np.std(y_train)) or 1.0
    y_train_n = (y_train - y_media) / y_std
    y_val_n = (y_val - y_media) / y_std

    modelo = _crear_modelo(cardinalidades, Xn_train.shape[1], ocultas, dropout, semilla)
    criterio = nn.SmoothL1Loss(beta=0.5)
    optimizador = torch.optim.AdamW(modelo.parameters(), lr=tasa, weight_decay=1e-4)
    planificador = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizador, mode="min", factor=0.5, patience=6
    )

    cargador = _cargador(Xc_train, Xn_train, y_train_n, lote, semilla, True)
    cat_val, num_val, objetivo_val = _tensores(Xc_val, Xn_val, y_val_n)

    mejor_rmse = np.inf
    mejor_estado = copy.deepcopy(modelo.state_dict())
    mejor_epoca = 0
    historial: list[dict] = []
    sin_mejora = 0

    for epoca in range(1, epocas + 1):
        modelo.train()
        perdida_total = 0.0
        for cat, num, objetivo in cargador:
            optimizador.zero_grad()
            prediccion = modelo(cat, num)
            perdida = criterio(prediccion, objetivo)
            perdida.backward()
            nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
            optimizador.step()
            perdida_total += float(perdida.item()) * len(objetivo)

        modelo.eval()
        with torch.no_grad():
            pred_val = modelo(cat_val, num_val).numpy()
        rmse = float(np.sqrt(np.mean((pred_val - np.asarray(y_val_n)) ** 2)))
        planificador.step(rmse)
        historial.append(
            {
                "epoca": epoca,
                "perdida": perdida_total / len(y_train),
                "rmse_validacion": rmse,
                "tasa": float(optimizador.param_groups[0]["lr"]),
            }
        )

        if rmse < mejor_rmse - 1e-5:
            mejor_rmse = rmse
            mejor_estado = copy.deepcopy(modelo.state_dict())
            mejor_epoca = epoca
            sin_mejora = 0
        else:
            sin_mejora += 1
            if sin_mejora >= paciencia:
                break

    modelo.load_state_dict(mejor_estado)
    modelo.eval()
    return modelo, historial, mejor_epoca, {"media": y_media, "std": y_std}


def entrenar_ensamble_regresor(
    Xc_train: np.ndarray,
    Xn_train: np.ndarray,
    y_train: np.ndarray,
    Xc_val: np.ndarray,
    Xn_val: np.ndarray,
    y_val: np.ndarray,
    cardinalidades: list[int],
    n_modelos: int = 5,
    semilla: int = config.SEMILLA,
) -> tuple[list[RedNeuronal], list[list[dict]], dict]:
    modelos: list[RedNeuronal] = []
    historiales: list[list[dict]] = []
    estadisticas: dict = {}
    for i in range(n_modelos):
        modelo, historial, _, stats = entrenar_regresor(
            Xc_train,
            Xn_train,
            y_train,
            Xc_val,
            Xn_val,
            y_val,
            cardinalidades,
            semilla=semilla + i * 101,
        )
        modelos.append(modelo)
        historiales.append(historial)
        estadisticas = stats
    return modelos, historiales, estadisticas


@torch.no_grad()
def predecir_regresor(
    modelos: list[RedNeuronal],
    Xc: np.ndarray,
    Xn: np.ndarray,
    estadisticas: dict,
) -> np.ndarray:
    cat, num, _ = _tensores(Xc, Xn)
    salidas = []
    for modelo in modelos:
        modelo.eval()
        salidas.append(modelo(cat, num).numpy())
    promedio = np.mean(salidas, axis=0)
    return promedio * float(estadisticas["std"]) + float(estadisticas["media"])


# ----------------------------------------------------------------------
# Persistencia y exportación
# ----------------------------------------------------------------------
def guardar_ensamble(
    modelos: list[RedNeuronal],
    ruta: Path | str,
    metadatos: dict | None = None,
) -> Path:
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "estados": [m.state_dict() for m in modelos],
            "cardinalidades": modelos[0].cardinalidades,
            "dims_embedding": modelos[0].dims_embedding,
            "n_numericas": modelos[0].capas[0].in_features
            - sum(modelos[0].dims_embedding),
            "ocultas": [
                modelos[0].capas[i].out_features
                for i in (0, 3)
                if i < len(modelos[0].capas)
            ],
            "metadatos": metadatos or {},
        },
        destino,
    )
    return destino


def cargar_ensamble(ruta: Path | str) -> tuple[list[RedNeuronal], dict]:
    datos = torch.load(Path(ruta), map_location="cpu", weights_only=False)
    modelos = []
    for estado in datos["estados"]:
        modelo = RedNeuronal(
            datos["cardinalidades"],
            datos["n_numericas"],
            tuple(datos["ocultas"]),
            dropout=0.0,
        )
        modelo.load_state_dict(estado)
        modelo.eval()
        modelos.append(modelo)
    return modelos, datos.get("metadatos", {})


def exportar_pesos(modelos: list[RedNeuronal]) -> dict:
    """Convierte los pesos a listas JSON para la inferencia en el navegador."""
    exportados = []
    for modelo in modelos:
        embeddings = [
            embedding.weight.detach().cpu().numpy().round(6).tolist()
            for embedding in modelo.embeddings
        ]
        capas = []
        for modulo in modelo.capas:
            if isinstance(modulo, nn.Linear):
                capas.append(
                    {
                        "pesos": modulo.weight.detach().cpu().numpy().round(6).tolist(),
                        "sesgo": modulo.bias.detach().cpu().numpy().round(6).tolist(),
                    }
                )
        exportados.append({"embeddings": embeddings, "capas": capas})
    return {
        "n_modelos": len(modelos),
        "modelos": exportados,
        "dims_embedding": modelos[0].dims_embedding,
    }
