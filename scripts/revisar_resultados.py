"""Revisa docs/evidencias/resultados.json (generado por preparar_evidencias.py) antes de armar el Word.

Imprime los valores clave y aplica criterios de aceptación.
Código de salida: 0 = todo OK; 2 = OK con observaciones que Matías debe revisar; 1 = falla (no generar el Word).

Uso:  python -B scripts/revisar_resultados.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA = RAIZ / "docs" / "evidencias" / "resultados.json"

fallas, observaciones = [], []


def revisar(condicion: bool, texto: str, grave: bool = True) -> None:
    marca = "OK   " if condicion else ("FALLA" if grave else "OBS. ")
    print(f"  [{marca}] {texto}")
    if not condicion:
        (fallas if grave else observaciones).append(texto)


def main() -> int:
    for flujo in (sys.stdout,):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if not RUTA.exists():
        print(f"[FALLA] No existe {RUTA.relative_to(RAIZ)}: ejecuta primero scripts/preparar_evidencias.py")
        return 1
    texto = RUTA.read_text(encoding="utf-8")
    r = json.loads(texto)
    m, exp = r["metricas"], r["experimento_escalador"]
    rn = m["red_neuronal"]
    a1 = {f["customer_id"]: f for f in r["actividad1"]}
    print(f"Resultados del {r['generado']} | {r['equipo']['sistema']} | Python {r['equipo']['python']} | modelo {r['modelo']['version_modelo']}")

    print("\n1. Atlas")
    c = r["conteos_colecciones"]
    revisar(c.get("historical_customers") == 1000, f"historical_customers = {c.get('historical_customers')} (esperado 1000)")
    revisar(c.get("active_customers") == 6, f"active_customers = {c.get('active_customers')} (esperado 6: los 5 de la guía + ACT-006)")
    revisar(c.get("evaluaciones") == 2, f"evaluaciones = {c.get('evaluaciones')} (esperado 2 corridas)")
    revisar(c.get("metricas_modelo") == 2, f"metricas_modelo = {c.get('metricas_modelo')} (esperado 2: entrenamiento y experimento)")
    revisar(3 <= c.get("retention_actions", 0) <= 6, f"retention_actions = {c.get('retention_actions')} (esperado 3 a 6)")

    print("\n2. Modelo")
    revisar(m["parametros"] == 241, f"parámetros = {m['parametros']} (esperado 241)")
    revisar(m["n_prueba"] == 200 and m["n_entrenamiento"] == 800, f"división {m['n_entrenamiento']}/{m['n_prueba']} (esperado 800/200)")
    revisar(0.70 <= rn["accuracy"] <= 0.80, f"Test Accuracy de la red = {rn['accuracy'] * 100:.2f}% (rango aceptado 70% a 80%)")
    revisar(rn["auc"] >= 0.75, f"AUC de la red = {rn['auc']:.3f} (mínimo 0,75)")
    revisar(rn["accuracy"] > m["linea_base_accuracy"] + 0.08, f"supera la línea base ({m['linea_base_accuracy'] * 100:.1f}%) por más de 8 puntos")
    print(f"         regresión logística {m['regresion_logistica']['accuracy'] * 100:.2f}% | oráculo {m['oraculo']['accuracy'] * 100:.2f}% | semilla elegida {m['semilla_elegida']}")

    print("\n3. Pregunta 2 (escalador)")
    print(f"         con escalador {exp['media_con'] * 100:.2f}% | sin escalador {exp['media_sin'] * 100:.2f}% | AUC {exp['auc_con']:.3f} vs {exp['auc_sin']:.3f}")
    revisar(exp["media_sin"] < exp["media_con"], "sin escalador el accuracy promedio baja (el texto del Word lo explica así)", grave=False)

    print("\n4. Actividad 1")
    for cid in ("ACT-001", "ACT-002", "ACT-003", "ACT-004", "ACT-005"):
        f = a1.get(cid)
        if f is None:
            revisar(False, f"{cid} no aparece")
            continue
        print(f"         {cid} {f['nombre']:16} {f['probabilidad'] * 100:6.2f}%  {f['decision']['clasificacion']:18} (real {f['probabilidad_real'] * 100:.1f}%)")
    revisar(a1["ACT-001"]["decision"]["clasificacion"] == "CRÍTICO VIP", "Ana es CRÍTICO VIP (lo supone la pregunta 1)")
    revisar(a1["ACT-002"]["decision"]["clasificacion"] == "CRÍTICO ESTÁNDAR", "Carlos es CRÍTICO ESTÁNDAR (lo supone la pregunta 1)")
    revisar(a1["ACT-003"]["decision"]["nivel_riesgo"] == "BAJO (SEGURO)", "Lucía queda en BAJO")
    revisar(a1["ACT-005"]["decision"]["nivel_riesgo"] == "BAJO (SEGURO)", "Elena queda en BAJO")
    print(f"         Pedro (caso límite, puede ser BAJO o MODERADO): {a1['ACT-004']['decision']['clasificacion']}")
    revisar(abs(r["presupuesto_actividad1"] - sum(f["decision"]["presupuesto_asignado_usd"] for f in r["actividad1"])) < 0.01,
            f"presupuesto de la Actividad 1 = USD {r['presupuesto_actividad1']:.2f} (cuadra con la suma)")

    print("\n5. Reto SUPER VIP")
    sv = r.get("registro_super_vip")
    revisar(sv is not None, "existe la acción pendiente de ACT-006 en retention_actions")
    if sv:
        d = sv["decision_negocio"]
        revisar(d.get("segmento") == "SUPER_VIP" and abs(d["presupuesto_asignado_usd"] - 49.0) < 0.001,
                f"ACT-006: {d['clasificacion']}, USD {d['presupuesto_asignado_usd']:.2f} (esperado CRÍTICO SUPER VIP, 49,00)")

    print("\n6. Seguridad del archivo")
    revisar("mongodb" not in texto.lower() and "@" not in texto, "resultados.json no contiene URI ni direcciones")

    print()
    if fallas:
        print(f"RESULTADO: FALLA ({len(fallas)}). No generar el Word; reportar a Matías.")
        return 1
    if observaciones:
        print(f"RESULTADO: OK con {len(observaciones)} observación(es). Mostrar a Matías antes de generar el Word.")
        return 2
    print("RESULTADO: OK. Se puede generar el Word.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
