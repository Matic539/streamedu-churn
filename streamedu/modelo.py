"""Red neuronal densa (MLP) para predecir el abandono, con medición completa.

Arquitectura de la guía sin cambios (241 parámetros):
    Entrada (5) -> Dense 16 ReLU -> Dropout 0,2 -> Dense 8 ReLU -> Dense 1 Sigmoid
Optimizador Adam, pérdida entropía cruzada binaria, 35 épocas, lote 16.

Diferencias con el script del docente:
- Semillas fijas y operaciones deterministas: la misma corrida da los mismos números.
- División estratificada (misma proporción de churn en entrenamiento y prueba).
- Escalador guardado como JSON (media y desviación), no como pickle.
- Métricas además de accuracy: línea base, precisión, recall, F1, AUC, Brier y matriz de confusión,
  comparadas con una regresión logística y con el oráculo (la fórmula que generó los datos).
- Artefactos con huella SHA-256 que se verifica antes de cargarlos.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np  # noqa: E402

from .config import FEATURES, SEMILLA  # noqa: E402
from .datos import probabilidad_real_matriz  # noqa: E402

ARCHIVO_MODELO = "churn_model.keras"
ARCHIVO_ESCALADOR = "escalador.json"
ARCHIVO_METADATA = "metadata.json"

EPOCAS = 35
LOTE = 16
TEST_SIZE = 0.2
VALIDACION = 0.1


class ModeloNoEntrenadoError(RuntimeError):
    pass


class IntegridadError(RuntimeError):
    pass


@dataclass
class Escalador:
    """StandardScaler serializable sin pickle."""

    media: list[float]
    desviacion: list[float]
    features: list[str] = field(default_factory=lambda: list(FEATURES))

    @classmethod
    def ajustar(cls, X) -> "Escalador":
        from sklearn.preprocessing import StandardScaler

        s = StandardScaler().fit(X)
        return cls(media=[float(v) for v in s.mean_], desviacion=[float(v) for v in s.scale_])

    def transformar(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=np.float32)
        return ((X - np.asarray(self.media, dtype=np.float32)) / np.asarray(self.desviacion, dtype=np.float32)).astype(np.float32)

    def a_dict(self) -> dict:
        return {"features": self.features, "media": self.media, "desviacion": self.desviacion}

    @classmethod
    def desde_dict(cls, d: dict) -> "Escalador":
        media, desv, feats = d.get("media"), d.get("desviacion"), d.get("features")
        if list(feats or []) != list(FEATURES):
            raise IntegridadError("El escalador fue creado con otras variables.")
        for nombre, valores in (("media", media), ("desviacion", desv)):
            if not isinstance(valores, list) or len(valores) != len(FEATURES):
                raise IntegridadError(f"Escalador inválido: {nombre} debe tener {len(FEATURES)} valores.")
            if not all(isinstance(v, (int, float)) and np.isfinite(v) for v in valores):
                raise IntegridadError(f"Escalador inválido: {nombre} tiene valores no numéricos.")
        if any(v <= 0 for v in desv):
            raise IntegridadError("Escalador inválido: desviación no positiva.")
        return cls(media=[float(v) for v in media], desviacion=[float(v) for v in desv], features=list(feats))


def fijar_semillas(semilla: int) -> None:
    import tensorflow as tf
    from tensorflow import keras

    keras.utils.set_random_seed(semilla)
    if not getattr(fijar_semillas, "_determinismo", False):
        tf.config.experimental.enable_op_determinism()  # mismas operaciones, mismos resultados
        fijar_semillas._determinismo = True


def construir_modelo(n_entradas: int = len(FEATURES)):
    from tensorflow import keras
    from tensorflow.keras import layers

    modelo = keras.Sequential(
        [
            keras.Input(shape=(n_entradas,), name="entrada"),
            layers.Dense(16, activation="relu", name="oculta_1"),
            layers.Dropout(0.2, name="dropout"),
            layers.Dense(8, activation="relu", name="oculta_2"),
            layers.Dense(1, activation="sigmoid", name="salida"),
        ],
        name="streamedu_churn_mlp",
    )
    modelo.compile(
        optimizer="adam",
        loss="binary_crossentropy",
        metrics=["accuracy", keras.metrics.AUC(name="auc")],
    )
    return modelo


def evaluar_probabilidades(y_real, prob, umbral: float = 0.5) -> dict:
    from sklearn.metrics import (
        accuracy_score,
        brier_score_loss,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    y_real = np.asarray(y_real).astype(int)
    prob = np.asarray(prob, dtype=float)
    pred = (prob >= umbral).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_real, pred, labels=[0, 1]).ravel()
    return {
        "accuracy": float(accuracy_score(y_real, pred)),
        "precision": float(precision_score(y_real, pred, zero_division=0)),
        "recall": float(recall_score(y_real, pred, zero_division=0)),
        "f1": float(f1_score(y_real, pred, zero_division=0)),
        "auc": float(roc_auc_score(y_real, prob)),
        "brier": float(brier_score_loss(y_real, prob)),
        "matriz_confusion": {"vn": int(tn), "fp": int(fp), "fn": int(fn), "vp": int(tp)},
    }


@dataclass
class ResultadoEntrenamiento:
    modelo: object
    escalador: Escalador | None
    metricas: dict
    historial: dict
    rangos_entrenamiento: dict
    semilla: int
    epocas: int


def entrenar(df, usar_escalador: bool = True, semilla: int = SEMILLA, epocas: int = EPOCAS,
             lote: int = LOTE, comparar: bool = True) -> ResultadoEntrenamiento:
    """Entrena con un DataFrame que tenga FEATURES y churn. No toca la base de datos."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split

    faltan = [c for c in (*FEATURES, "churn") if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas: {faltan}")
    if len(df) < 50:
        raise ValueError("Se necesitan al menos 50 registros históricos para entrenar.")
    X = df[list(FEATURES)].to_numpy(dtype=np.float32)
    y = df["churn"].to_numpy(dtype=np.int64)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=TEST_SIZE, random_state=SEMILLA, stratify=y)

    escalador = Escalador.ajustar(X_tr) if usar_escalador else None
    A_tr = escalador.transformar(X_tr) if escalador else X_tr
    A_te = escalador.transformar(X_te) if escalador else X_te

    fijar_semillas(semilla)
    modelo = construir_modelo()
    hist = modelo.fit(A_tr, y_tr, epochs=epocas, batch_size=lote, validation_split=VALIDACION, shuffle=True, verbose=0)
    prob_te = modelo.predict(A_te, verbose=0).ravel()

    metricas = {
        "red_neuronal": evaluar_probabilidades(y_te, prob_te),
        "n_entrenamiento": int(len(y_tr)),
        "n_prueba": int(len(y_te)),
        "tasa_churn_total": float(y.mean()),
        "tasa_churn_prueba": float(y_te.mean()),
        "linea_base_accuracy": float(1 - y_te.mean()),
        "parametros": int(modelo.count_params()),
        "usa_escalador": bool(usar_escalador),
    }
    if comparar:
        esc_lr = escalador or Escalador.ajustar(X_tr)
        lr = LogisticRegression(max_iter=1000).fit(esc_lr.transformar(X_tr), y_tr)
        metricas["regresion_logistica"] = evaluar_probabilidades(y_te, lr.predict_proba(esc_lr.transformar(X_te))[:, 1])
        metricas["oraculo"] = evaluar_probabilidades(y_te, probabilidad_real_matriz(X_te))

    rangos = {f: [float(X_tr[:, i].min()), float(X_tr[:, i].max())] for i, f in enumerate(FEATURES)}
    historial = {k: [float(v) for v in vals] for k, vals in hist.history.items()}
    return ResultadoEntrenamiento(modelo, escalador, metricas, historial, rangos, semilla, epocas)


SEMILLAS_REINICIO = (42, 43, 44, 45, 46)


def entrenar_con_reinicios(df, semillas=SEMILLAS_REINICIO, epocas: int = EPOCAS) -> tuple[ResultadoEntrenamiento, list[dict]]:
    """Entrena la misma red con varias semillas y elige la de menor pérdida de VALIDACIÓN.

    Motivo: con algunas inicializaciones las neuronas ReLU quedan inactivas para una zona de
    los datos y la red entrega la misma probabilidad a clientes distintos (con la semilla 42,
    Lucía y Elena salían ambas con 30,2%). Elegir por validación no mira el conjunto de prueba.
    """
    mejor, tabla = None, []
    for s in semillas:
        r = entrenar(df, semilla=s, epocas=epocas, comparar=False)
        val = r.historial["val_loss"][-1]
        tabla.append({
            "semilla": s,
            "val_loss": val,
            "test_accuracy": r.metricas["red_neuronal"]["accuracy"],
            "test_auc": r.metricas["red_neuronal"]["auc"],
        })
        if mejor is None or val < mejor.historial["val_loss"][-1]:
            mejor = r
    final = entrenar(df, semilla=mejor.semilla, epocas=epocas, comparar=True)  # misma semilla: mismo modelo
    final.metricas["reinicios"] = tabla
    final.metricas["semilla_elegida"] = final.semilla
    return final, tabla


def experimento_escalador(df, semillas=(42, 43, 44, 45, 46), epocas: int = EPOCAS, clientes=None) -> list[dict]:
    """Pregunta 2: misma red con y sin StandardScaler, varias semillas. No guarda modelos."""
    filas = []
    for usar in (True, False):
        for s in semillas:
            r = entrenar(df, usar_escalador=usar, semilla=s, epocas=epocas, comparar=False)
            fila = {
                "usa_escalador": usar,
                "semilla": s,
                "accuracy": r.metricas["red_neuronal"]["accuracy"],
                "auc": r.metricas["red_neuronal"]["auc"],
                "perdida_final": r.historial["loss"][-1],
            }
            if clientes:
                X = np.asarray([[c[f] for f in FEATURES] for c in clientes], dtype=np.float32)
                A = r.escalador.transformar(X) if r.escalador else X
                fila["probabilidades"] = {c["customer_id"]: float(p) for c, p in zip(clientes, r.modelo.predict(A, verbose=0).ravel())}
            filas.append(fila)
    return filas


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 16), b""):
            h.update(bloque)
    return h.hexdigest()


def guardar_artefactos(res: ResultadoEntrenamiento, directorio: Path) -> dict:
    import sklearn
    import tensorflow as tf
    from tensorflow import keras

    if res.escalador is None:
        raise ValueError("El modelo de producción se guarda solo con escalador.")
    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)
    ruta_modelo = directorio / ARCHIVO_MODELO
    ruta_esc = directorio / ARCHIVO_ESCALADOR
    res.modelo.save(ruta_modelo)
    ruta_esc.write_text(json.dumps(res.escalador.a_dict(), indent=2), encoding="utf-8")
    meta = {
        "version_modelo": _sha256(ruta_modelo)[:12],
        "fecha_entrenamiento": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "features": list(FEATURES),
        "semilla": res.semilla,
        "epocas": res.epocas,
        "rangos_entrenamiento": res.rangos_entrenamiento,
        "metricas": res.metricas,
        "versiones": {"tensorflow": tf.__version__, "keras": keras.__version__, "scikit-learn": sklearn.__version__},
        "sha256": {ARCHIVO_MODELO: _sha256(ruta_modelo), ARCHIVO_ESCALADOR: _sha256(ruta_esc)},
    }
    (directorio / ARCHIVO_METADATA).write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


@dataclass
class Artefactos:
    modelo: object
    escalador: Escalador
    metadata: dict

    @property
    def version(self) -> str:
        return self.metadata["version_modelo"]

    def predecir(self, clientes: list[dict]) -> np.ndarray:
        X = np.asarray([[float(c[f]) for f in FEATURES] for c in clientes], dtype=np.float32)
        if X.size == 0:
            return np.zeros(0)
        # Llamada directa (sin predict): más rápida para lotes chicos y sin retrazado de tf.function.
        return np.asarray(self.modelo(self.escalador.transformar(X), training=False)).ravel().astype(float)


def cargar_artefactos(directorio: Path) -> Artefactos:
    """Carga solo si las huellas SHA-256 coinciden con metadata.json. Sin pickle."""
    from tensorflow import keras

    directorio = Path(directorio)
    rutas = {n: directorio / n for n in (ARCHIVO_MODELO, ARCHIVO_ESCALADOR, ARCHIVO_METADATA)}
    if not all(r.exists() for r in rutas.values()):
        raise ModeloNoEntrenadoError("No hay modelo entrenado: ejecuta primero 2_train_model.py")
    meta = json.loads(rutas[ARCHIVO_METADATA].read_text(encoding="utf-8"))
    for nombre in (ARCHIVO_MODELO, ARCHIVO_ESCALADOR):
        if meta.get("sha256", {}).get(nombre) != _sha256(rutas[nombre]):
            raise IntegridadError(f"{nombre} no coincide con su huella en metadata.json: vuelve a entrenar.")
    if meta.get("features") != list(FEATURES):
        raise IntegridadError("El modelo fue entrenado con otras variables.")
    escalador = Escalador.desde_dict(json.loads(rutas[ARCHIVO_ESCALADOR].read_text(encoding="utf-8")))
    modelo = keras.models.load_model(rutas[ARCHIVO_MODELO], compile=False, safe_mode=True)
    return Artefactos(modelo, escalador, meta)
