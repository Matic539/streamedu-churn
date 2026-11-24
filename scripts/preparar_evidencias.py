"""Fase 5: deja Atlas en un estado conocido y guarda los resultados para el Word.

Ejecuta el flujo de la guía de principio a fin:
  1. Script 1 con --reiniciar: 1.000 históricos y los 5 clientes de la guía.
  2. Script 2: 5 reinicios, se elige por validación y se guarda el modelo.
  3. Pregunta 2: experimento con y sin StandardScaler (5 semillas).
  4. Script 3 con los 5 clientes: valores de la Actividad 1.
  5. Reto SUPER VIP: agrega ACT-006 y vuelve a ejecutar el script 3.
Al final imprime un resumen pensado para la captura 2 y escribe docs/evidencias/resultados.json
(sin URI ni credenciales), que usa entrega/generar_word.py.

Uso:  python -B scripts/preparar_evidencias.py      (tarda de 2 a 4 minutos)
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import importlib.util  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from streamedu.config import ConfigError, configurar_consola, dir_modelos, leer_config_mongo  # noqa: E402
from streamedu.db import (  # noqa: E402
    COL_ACCIONES,
    COL_ACTIVOS,
    COL_HISTORICOS,
    COL_METRICAS,
    ConexionError,
    ESTADO_PENDIENTE,
    conectar,
)
from streamedu.datos import probabilidad_real  # noqa: E402
from streamedu.modelo import (  # noqa: E402
    SEMILLAS_REINICIO,
    cargar_artefactos,
    entrenar_con_reinicios,
    experimento_escalador,
    guardar_artefactos,
)
from streamedu.pipeline import ejecutar_pipeline  # noqa: E402

SALIDA = RAIZ / "docs" / "evidencias" / "resultados.json"


def _script(nombre: str, alias: str):
    spec = importlib.util.spec_from_file_location(alias, RAIZ / nombre)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fila(f: dict) -> dict:
    c, d = f["cliente"], f["decision"]
    return {
        "customer_id": c["customer_id"],
        "nombre": c["nombre"],
        "meses_antiguedad": c["meses_antiguedad"],
        "probabilidad": f["probabilidad"],
        "probabilidad_real": round(probabilidad_real(c), 4),
        "decision": d,
    }


def paso(n: int, texto: str) -> None:
    print(f"\n[{n}/5] {texto}", flush=True)


def main() -> int:
    configurar_consola()
    t0 = time.perf_counter()
    try:
        uri, db_name = leer_config_mongo()
        cliente, db = conectar(uri, db_name)
    except (ConfigError, ConexionError) as e:
        print(f"[ERROR] {e}")
        return 1
    seed = _script("1_seed_mongodb.py", "seed")
    try:
        paso(1, "Carga de datos en Atlas (script 1 --reiniciar)")
        carga = seed.cargar(db, reiniciar=True)
        for aviso in carga["avisos"]:
            print(f"  [AVISO] {aviso}")
        print(f"  historical_customers {carga['historicos']} | active_customers {carga['activos']}")

        paso(2, f"Entrenamiento (script 2: {len(SEMILLAS_REINICIO)} reinicios de 35 épocas)")
        df = pd.DataFrame(list(db[COL_HISTORICOS].find({}, {"_id": 0})))
        res, _ = entrenar_con_reinicios(df)
        meta = guardar_artefactos(res, dir_modelos())
        db[COL_METRICAS].insert_one({
            "tipo": "entrenamiento", "fecha": datetime.now(timezone.utc), "modelo_version": meta["version_modelo"],
            "semilla": res.semilla, "epocas": res.epocas, "metricas": res.metricas,
            "perdida_por_epoca": res.historial["loss"], "perdida_validacion_por_epoca": res.historial["val_loss"],
        })
        print(f"  modelo {meta['version_modelo']} (semilla {res.semilla})")

        paso(3, "Pregunta 2: con y sin StandardScaler (5 semillas)")
        clientes5 = list(db[COL_ACTIVOS].find({}, {"_id": 0}).sort("customer_id", 1))
        experimento = experimento_escalador(df, clientes=clientes5)
        db[COL_METRICAS].insert_one({
            "tipo": "experimento_sin_escalador", "fecha": datetime.now(timezone.utc), "epocas": 35,
            "resultados": [{k: v for k, v in f.items() if k != "probabilidades"} for f in experimento],
        })

        paso(4, "Pipeline con los 5 clientes de la guía (script 3): Actividad 1")
        artefactos = cargar_artefactos(dir_modelos())
        corrida1 = ejecutar_pipeline(db, artefactos)

        paso(5, "Reto SUPER VIP: agrega ACT-006 y vuelve a ejecutar el script 3")
        seed.cargar(db, demo_super_vip=True)
        corrida2 = ejecutar_pipeline(db, artefactos)
        sv = db[COL_ACCIONES].find_one({"customer_id": "ACT-006", "estado_campana": ESTADO_PENDIENTE}, {"_id": 0})
        conteos = {c: db[c].count_documents({}) for c in sorted(db.list_collection_names())}
    finally:
        cliente.close()

    m = res.metricas
    exp = {
        "filas": experimento,
        "media_con": float(np.mean([f["accuracy"] for f in experimento if f["usa_escalador"]])),
        "media_sin": float(np.mean([f["accuracy"] for f in experimento if not f["usa_escalador"]])),
        "auc_con": float(np.mean([f["auc"] for f in experimento if f["usa_escalador"]])),
        "auc_sin": float(np.mean([f["auc"] for f in experimento if not f["usa_escalador"]])),
        "perdida_con": float(np.mean([f["perdida_final"] for f in experimento if f["usa_escalador"]])),
        "perdida_sin": float(np.mean([f["perdida_final"] for f in experimento if not f["usa_escalador"]])),
    }
    resultados = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "equipo": {"sistema": platform.platform(), "python": platform.python_version()},
        "base": db_name,
        "conteos_colecciones": conteos,
        "modelo": {k: meta[k] for k in ("version_modelo", "fecha_entrenamiento", "semilla", "epocas", "versiones")},
        "metricas": m,
        "experimento_escalador": exp,
        "actividad1": [_fila(f) for f in corrida1.filas],
        "presupuesto_actividad1": corrida1.costo_total,
        "corrida_super_vip": {"corrida_id": corrida2.corrida_id, "filas": [_fila(f) for f in corrida2.filas]},
        "registro_super_vip": json.loads(json.dumps(sv, default=str)) if sv else None,
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")

    rn = m["red_neuronal"]
    print("\n" + "=" * 86)
    print(f"STREAMEDU | Deep Learning + MongoDB Atlas | base {db_name} | modelo {meta['version_modelo']}")
    print("=" * 86)
    print("Atlas: " + " | ".join(f"{k} {v}" for k, v in conteos.items()))
    print(f"Red: Entrada(5) > Dense 16 ReLU > Dropout 0,2 > Dense 8 ReLU > Dense 1 Sigmoid | {m['parametros']} parámetros | Adam + entropía cruzada binaria")
    print(f"Prueba ({m['n_prueba']} clientes no vistos): Test Accuracy {rn['accuracy'] * 100:.2f}% | AUC {rn['auc']:.3f} | recall {rn['recall'] * 100:.1f}%"
          f" | línea base {m['linea_base_accuracy'] * 100:.1f}% | reg. logística {m['regresion_logistica']['accuracy'] * 100:.1f}% | oráculo {m['oraculo']['accuracy'] * 100:.1f}%")
    print(f"Pregunta 2 (5 semillas): con escalador {exp['media_con'] * 100:.2f}% | sin escalador {exp['media_sin'] * 100:.2f}%")
    print("-" * 86)
    print(f"{'ID':8} {'Nombre':16} {'Prob.':>7}  {'Clasificación':18} {'Costo':>7}  Acción")
    for f in corrida2.filas:
        c, d = f["cliente"], f["decision"]
        print(f"{c['customer_id']:8} {c['nombre'][:16]:16} {f['probabilidad'] * 100:6.2f}%  {d['clasificacion']:18} {d['presupuesto_asignado_usd']:7.2f}  {d['accion_comercial'][:44]}")
    print("-" * 86)
    print(f"[OK] Resultados en {SALIDA.relative_to(RAIZ)} | {time.perf_counter() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
