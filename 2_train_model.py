"""Script 2: entrena la red neuronal (Keras) con los históricos de MongoDB Atlas.

Arquitectura de la guía: Entrada(5) -> Dense 16 ReLU -> Dropout 0,2 -> Dense 8 ReLU -> Dense 1 Sigmoid.
Guarda modelos/churn_model.keras, modelos/escalador.json y modelos/metadata.json (sin pickle)
y registra las métricas en la colección "metricas_modelo".

Uso:
  python -B 2_train_model.py                  entrena (5 reinicios, elige por validación) y guarda
  python -B 2_train_model.py --sin-escalador  pregunta 2: compara con y sin StandardScaler (no guarda modelo)
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from streamedu.config import configurar_consola, FEATURES, ConfigError, dir_modelos, enmascarar_uri, leer_config_mongo  # noqa: E402
from streamedu.db import COL_ACTIVOS, COL_HISTORICOS, COL_METRICAS, ConexionError, conectar  # noqa: E402
from streamedu.modelo import (  # noqa: E402
    EPOCAS,
    SEMILLAS_REINICIO,
    entrenar_con_reinicios,
    experimento_escalador,
    guardar_artefactos,
)


def leer_historicos(db) -> pd.DataFrame:
    df = pd.DataFrame(list(db[COL_HISTORICOS].find({}, {"_id": 0})))
    if df.empty:
        raise ValueError("No hay datos históricos: ejecuta primero 1_seed_mongodb.py")
    return df


def fila_metricas(nombre: str, m: dict) -> str:
    return f"  {nombre:22} {m['accuracy'] * 100:7.2f}% {m['precision'] * 100:8.2f}% {m['recall'] * 100:7.2f}% {m['auc']:6.3f} {m['brier']:6.3f}"


def imprimir_resultado(res, meta) -> None:
    m = res.metricas
    print("\nArquitectura (Keras Sequential):")
    res.modelo.summary(print_fn=lambda s, **_: print("  " + s))
    print(f"\n[INFO] Reinicios (se elige la menor pérdida de validación; el conjunto de prueba no participa):")
    for r in m["reinicios"]:
        marca = "  <- elegida" if r["semilla"] == m["semilla_elegida"] else ""
        print(f"  semilla {r['semilla']}: val_loss {r['val_loss']:.4f}{marca}")
    print(f"\n[INFO] Conjunto de prueba: {m['n_prueba']} clientes no vistos ({m['tasa_churn_prueba'] * 100:.1f}% con churn)")
    print(f"  {'Modelo':22} {'Accuracy':>8} {'Precisión':>9} {'Recall':>8} {'AUC':>6} {'Brier':>6}")
    print(f"  {'Línea base (nadie se va)':22} {m['linea_base_accuracy'] * 100:7.2f}%")
    print(fila_metricas("Red neuronal (Keras)", m["red_neuronal"]))
    print(fila_metricas("Regresión logística", m["regresion_logistica"]))
    print(fila_metricas("Oráculo (fórmula real)", m["oraculo"]))
    mc = m["red_neuronal"]["matriz_confusion"]
    print(f"  Matriz de confusión de la red (umbral 0,5): VN {mc['vn']} | FP {mc['fp']} | FN {mc['fn']} | VP {mc['vp']}")
    print(f"\n[OK] Test Accuracy de la red: {m['red_neuronal']['accuracy'] * 100:.2f}%")
    print(f"[OK] Modelo guardado en {dir_modelos()} (versión {meta['version_modelo']}, {m['parametros']} parámetros)")


def correr_experimento(db, df, semillas, epocas) -> None:
    clientes = list(db[COL_ACTIVOS].find({}, {"_id": 0}).sort("customer_id", 1))
    filas = experimento_escalador(df, semillas=semillas, epocas=epocas, clientes=clientes)
    print("\nPregunta 2: misma red con y sin StandardScaler (mismas semillas)")
    print(f"  {'Semilla':>7} {'Con escalador':>14} {'Sin escalador':>14}   (Test Accuracy)")
    con = {f["semilla"]: f for f in filas if f["usa_escalador"]}
    sin = {f["semilla"]: f for f in filas if not f["usa_escalador"]}
    for s in semillas:
        print(f"  {s:>7} {con[s]['accuracy'] * 100:13.2f}% {sin[s]['accuracy'] * 100:13.2f}%")
    for nombre, grupo in (("Con escalador", list(con.values())), ("Sin escalador", list(sin.values()))):
        acc = np.array([f["accuracy"] for f in grupo]) * 100
        auc = np.array([f["auc"] for f in grupo])
        loss = np.array([f["perdida_final"] for f in grupo])
        print(f"  {nombre}: accuracy media {acc.mean():.2f}% (mín {acc.min():.2f}, máx {acc.max():.2f}) | AUC media {auc.mean():.3f} | pérdida final media {loss.mean():.3f}")
    if clientes:
        print("\n  Probabilidad por cliente (con / sin escalador), por semilla:")
        for c in clientes:
            cid = c["customer_id"]
            pares = "  ".join(f"{con[s]['probabilidades'][cid] * 100:5.1f}/{sin[s]['probabilidades'][cid] * 100:5.1f}" for s in semillas)
            print(f"  {cid}: {pares}")
    db[COL_METRICAS].insert_one({
        "tipo": "experimento_sin_escalador",
        "fecha": datetime.now(timezone.utc),
        "epocas": epocas,
        "resultados": [{k: v for k, v in f.items() if k != "probabilidades"} for f in filas],
    })
    print("\n[OK] Experimento registrado en metricas_modelo (no se modificó el modelo guardado).")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sin-escalador", action="store_true", help="experimento de la pregunta 2")
    p.add_argument("--epocas", type=int, default=EPOCAS)
    args = p.parse_args(argv)
    configurar_consola()
    try:
        uri, db_name = leer_config_mongo()
        cliente, db = conectar(uri, db_name)
    except (ConfigError, ConexionError) as e:
        print(f"[ERROR] {e}")
        return 1
    try:
        print(f"[INFO] Conectado a {enmascarar_uri(uri)} | base {db_name}")
        df = leer_historicos(db)
        print(f"[INFO] Datos descargados de MongoDB Atlas: {len(df)} filas, variables {', '.join(FEATURES)}")
        if args.sin_escalador:
            correr_experimento(db, df, SEMILLAS_REINICIO, args.epocas)
            return 0
        print(f"[INFO] Entrenando la red neuronal ({len(SEMILLAS_REINICIO)} reinicios de {args.epocas} épocas)...")
        res, _ = entrenar_con_reinicios(df, epocas=args.epocas)
        meta = guardar_artefactos(res, dir_modelos())
        db[COL_METRICAS].insert_one({
            "tipo": "entrenamiento",
            "fecha": datetime.now(timezone.utc),
            "modelo_version": meta["version_modelo"],
            "semilla": res.semilla,
            "epocas": res.epocas,
            "metricas": res.metricas,
            "perdida_por_epoca": res.historial["loss"],
            "perdida_validacion_por_epoca": res.historial["val_loss"],
        })
        imprimir_resultado(res, meta)
        print("[OK] Métricas registradas en la colección metricas_modelo.")
        return 0
    except ValueError as e:
        print(f"[ERROR] {e}")
        return 1
    finally:
        cliente.close()


if __name__ == "__main__":
    sys.exit(main())
