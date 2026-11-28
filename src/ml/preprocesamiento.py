"""Preprocesador reproducible para la red neuronal y XGBoost.

Guarda el vocabulario de categorías, las medianas y las escalas en un JSON
para que la aplicación pueda replicar exactamente la misma transformación
sin depender de Python.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config


class Preprocesador:
    """Transforma variables crudas en matrices para los dos modelos."""

    def __init__(self, min_frecuencia: dict | None = None):
        self.min_frecuencia = min_frecuencia or dict(config.MIN_FRECUENCIA)
        self.cat_cols = list(config.CAT_COLS)
        self.num_cols = list(config.NUM_COLS)
        self.num_cols_modelo = list(config.NUM_COLS_MODELO)
        self.cat_vocab: dict[str, list[str]] = {}
        self.cat_map: dict[str, dict[str, int]] = {}
        self.num_median: dict[str, float] = {}
        self.num_mean: dict[str, float] = {}
        self.num_std: dict[str, float] = {}
        self.mag_global: dict[str, float] = {"media": 0.0, "std": 1.0}
        self.mag_por_escala: dict[str, dict[str, float]] = {}
        self.columnas_xgb: list[str] = []

    # ------------------------------------------------------------------
    # Ajuste
    # ------------------------------------------------------------------
    def fit(self, df: pd.DataFrame) -> "Preprocesador":
        self.cat_vocab = {}
        self.cat_map = {}

        for col in self.cat_cols:
            minimo = int(self.min_frecuencia.get(col, 20))
            conteo = df[col].value_counts()
            categorias = sorted(conteo[conteo >= minimo].index.tolist())
            vocabulario = ["OTRO", "Sin dato"]
            vocabulario += [c for c in categorias if c not in vocabulario]
            self.cat_vocab[col] = vocabulario
            self.cat_map[col] = {valor: i for i, valor in enumerate(vocabulario)}

        # Mediana de cada variable numérica. Se usa también para imputar.
        medianas = df[self.num_cols].median(numeric_only=True)
        self.num_median = {c: float(medianas.get(c, 0.0) or 0.0) for c in self.num_cols}

        base = df[self.num_cols].fillna(self.num_median)
        self.num_mean = {c: float(base[c].mean()) for c in self.num_cols}
        self.num_std = {
            c: float(base[c].std(ddof=0)) if float(base[c].std(ddof=0)) else 1.0
            for c in self.num_cols
        }

        # Estadísticas de magnitud por escala (Km2, Kph, Richter, °C, etc.).
        observada = df[df["magnitud"].notna()].copy()
        if len(observada):
            self.mag_global = {
                "media": float(observada["magnitud"].mean()),
                "std": float(observada["magnitud"].std(ddof=0)) or 1.0,
            }
        for escala, grupo in observada.groupby("escala"):
            if len(grupo) < 10:
                continue
            std = float(grupo["magnitud"].std(ddof=0))
            self.mag_por_escala[str(escala)] = {
                "media": float(grupo["magnitud"].mean()),
                "std": std if std else 1.0,
            }

        self._construir_columnas_xgb()
        return self

    def _construir_columnas_xgb(self) -> None:
        columnas = [f"num__{c}" for c in self.num_cols_modelo]
        for col in self.cat_cols:
            for categoria in self.cat_vocab[col]:
                columnas.append(f"cat__{col}__{categoria}")
        self.columnas_xgb = columnas

    # ------------------------------------------------------------------
    # Transformaciones
    # ------------------------------------------------------------------
    def _codigos(self, df: pd.DataFrame, col: str) -> np.ndarray:
        mapa = self.cat_map[col]
        valores = df[col].astype("string").fillna("Sin dato")
        return valores.map(lambda v: mapa.get(str(v), 0)).to_numpy(dtype=np.int64)

    def _z_magnitud(self, df: pd.DataFrame) -> np.ndarray:
        salida = np.zeros(len(df), dtype=float)
        escalas = df["escala"].astype("string").fillna("Sin dato").to_numpy()
        magnitudes = pd.to_numeric(df["magnitud"], errors="coerce").to_numpy(dtype=float)
        for i, (escala, valor) in enumerate(zip(escalas, magnitudes)):
            if np.isnan(valor):
                continue
            stats = self.mag_por_escala.get(str(escala), self.mag_global)
            salida[i] = (valor - stats["media"]) / (stats["std"] or 1.0)
        return np.clip(salida, -6, 6)

    def transform_num(self, df: pd.DataFrame) -> pd.DataFrame:
        """Variables numéricas imputadas y estandarizadas."""
        base = df[self.num_cols].copy()
        base = base.apply(pd.to_numeric, errors="coerce")
        base["magnitud_z"] = self._z_magnitud(df)
        base = base[self.num_cols_modelo]
        for col in self.num_cols_modelo:
            base[col] = base[col].fillna(self.num_median.get(col, 0.0))
        for col in self.num_cols_modelo:
            media = self.num_mean.get(col, 0.0)
            std = self.num_std.get(col, 1.0) or 1.0
            base[col] = (base[col] - media) / std
        return base.astype("float32")

    def transform_nn(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Devuelve códigos categóricos y matriz numérica para PyTorch."""
        codigos = np.column_stack([self._codigos(df, c) for c in self.cat_cols])
        numericas = self.transform_num(df).to_numpy(dtype=np.float32)
        return codigos.astype(np.int64), numericas

    def transform_xgb(self, df: pd.DataFrame) -> pd.DataFrame:
        """Matriz numérica con one-hot encoding para XGBoost y para la app."""
        numericas = self.transform_num(df)
        columnas: dict[str, np.ndarray] = {}
        for col in self.num_cols_modelo:
            columnas[f"num__{col}"] = numericas[col].to_numpy()

        codigos = {col: self._codigos(df, col) for col in self.cat_cols}
        for col in self.cat_cols:
            vocab = self.cat_vocab[col]
            codes = codigos[col]
            for i, categoria in enumerate(vocab):
                columnas[f"cat__{col}__{categoria}"] = (codes == i).astype("float32")

        return pd.DataFrame(columnas, index=df.index)[self.columnas_xgb]

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------
    @property
    def cardinalidades(self) -> list[int]:
        return [len(self.cat_vocab[c]) for c in self.cat_cols]

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "cat_cols": self.cat_cols,
            "num_cols": self.num_cols,
            "num_cols_modelo": self.num_cols_modelo,
            "cat_vocab": self.cat_vocab,
            "num_median": self.num_median,
            "num_mean": self.num_mean,
            "num_std": self.num_std,
            "mag_global": self.mag_global,
            "mag_por_escala": self.mag_por_escala,
            "columnas_xgb": self.columnas_xgb,
            "min_frecuencia": self.min_frecuencia,
        }

    @classmethod
    def from_dict(cls, datos: dict) -> "Preprocesador":
        obj = cls(min_frecuencia=datos.get("min_frecuencia"))
        obj.cat_cols = datos["cat_cols"]
        obj.num_cols = datos["num_cols"]
        obj.num_cols_modelo = datos["num_cols_modelo"]
        obj.cat_vocab = {k: list(v) for k, v in datos["cat_vocab"].items()}
        obj.cat_map = {
            col: {valor: i for i, valor in enumerate(vocab)}
            for col, vocab in obj.cat_vocab.items()
        }
        obj.num_median = {k: float(v) for k, v in datos["num_median"].items()}
        obj.num_mean = {k: float(v) for k, v in datos["num_mean"].items()}
        obj.num_std = {k: float(v) for k, v in datos["num_std"].items()}
        obj.mag_global = {k: float(v) for k, v in datos["mag_global"].items()}
        obj.mag_por_escala = {
            k: {m: float(n) for m, n in v.items()}
            for k, v in datos["mag_por_escala"].items()
        }
        obj.columnas_xgb = list(datos["columnas_xgb"])
        return obj

    def guardar(self, ruta: Path | str) -> Path:
        destino = Path(ruta)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        return destino

    @classmethod
    def leer(cls, ruta: Path | str) -> "Preprocesador":
        return cls.from_dict(json.loads(Path(ruta).read_text(encoding="utf-8")))

    def perfil_promedio(self, df: pd.DataFrame) -> dict:
        """Perfil típico para explicar los factores en la aplicación."""
        perfil = {"categoricas": {}, "numericas": {}}
        for col in self.cat_cols:
            moda = df[col].astype("string").mode(dropna=True)
            perfil["categoricas"][col] = (
                str(moda.iloc[0]) if len(moda) else "Sin dato"
            )
        for col in self.num_cols_modelo:
            if col == "magnitud_z":
                perfil["numericas"][col] = 0.0
            else:
                perfil["numericas"][col] = float(
                    df[col].median(numeric_only=True) if col in df else 0.0
                )
        return perfil
