"""Carga (script 1) y pipeline (script 3) sobre una base simulada."""
import unittest
from datetime import datetime, timedelta, timezone

from tests.apoyo import ArtefactosFalsos, base_simulada, cargar_script
from streamedu.db import COL_ACCIONES, COL_ACTIVOS, COL_EVALUACIONES, ESTADO_DESCARTADA, ESTADO_PENDIENTE
from streamedu.pipeline import ejecutar_pipeline, formatear_reporte, validar_cliente

seed = cargar_script("1_seed_mongodb.py", "seed_propio")

PROBS = {"ACT-001": 0.85, "ACT-002": 0.84, "ACT-003": 0.03, "ACT-004": 0.45, "ACT-005": 0.05, "ACT-006": 0.95}


class TestCarga(unittest.TestCase):
    def setUp(self):
        self.db = base_simulada()

    def test_carga_e_idempotencia(self):
        r1 = seed.cargar(self.db)
        r2 = seed.cargar(self.db)
        for r in (r1, r2):
            self.assertEqual((r["historicos"], r["historicos_churn"], r["activos"]), (1000, 425, 5))

    def test_demo_super_vip_y_reinicio(self):
        self.assertEqual(seed.cargar(self.db, demo_super_vip=True)["ids_activos"][-1], "ACT-006")
        self.db[COL_ACCIONES].insert_one({"customer_id": "ACT-001", "estado_campana": ESTADO_PENDIENTE})
        r = seed.cargar(self.db, reiniciar=True)
        self.assertEqual((r["activos"], r["acciones"]), (5, 0))

    def test_indices(self):
        seed.cargar(self.db)
        self.assertIn("uq_customer_id", self.db["historical_customers"].index_information())
        self.assertIn("uq_una_accion_pendiente", self.db[COL_ACCIONES].index_information())


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.db = base_simulada()
        seed.cargar(self.db, demo_super_vip=True)
        self.art = ArtefactosFalsos(PROBS)
        self.t0 = datetime(2026, 11, 21, 15, 0, tzinfo=timezone.utc)

    def acciones(self, estado=ESTADO_PENDIENTE):
        return {d["customer_id"]: d for d in self.db[COL_ACCIONES].find({"estado_campana": estado})}

    def test_decisiones_y_acciones(self):
        r = ejecutar_pipeline(self.db, self.art, self.t0)
        clasif = {f["cliente"]["customer_id"]: f["decision"]["clasificacion"] for f in r.filas}
        self.assertEqual(clasif, {
            "ACT-001": "CRÍTICO VIP", "ACT-002": "CRÍTICO ESTÁNDAR", "ACT-003": "BAJO (SEGURO)",
            "ACT-004": "RIESGO MODERADO", "ACT-005": "BAJO (SEGURO)", "ACT-006": "CRÍTICO SUPER VIP",
        })
        acc = self.acciones()
        self.assertEqual(set(acc), {"ACT-001", "ACT-002", "ACT-004", "ACT-006"})
        sv = acc["ACT-006"]
        self.assertEqual(sv["decision_negocio"]["accion_comercial"], "1 Mes Gratis + Mentoría 1 a 1")
        self.assertEqual(sv["decision_negocio"]["presupuesto_asignado_usd"], 49.0)
        self.assertEqual(sv["modelo_version"], "falso000001")
        self.assertEqual(r.costo_total, round(26.10 + 4.35 + 0.50 + 49.00, 2))
        activo = self.db[COL_ACTIVOS].find_one({"customer_id": "ACT-004"})
        self.assertEqual((activo["probabilidad_churn"], activo["riesgo"]), (0.45, "MODERADO"))

    def test_no_duplica_al_repetir(self):
        ejecutar_pipeline(self.db, self.art, self.t0)
        ejecutar_pipeline(self.db, self.art, self.t0 + timedelta(minutes=5))
        self.assertEqual(self.db[COL_ACCIONES].count_documents({}), 4)
        self.assertEqual(self.db[COL_EVALUACIONES].count_documents({}), 2)
        d = self.acciones()["ACT-001"]
        self.assertEqual(d["fecha_creacion"].replace(tzinfo=timezone.utc), self.t0)
        self.assertEqual(d["fecha_actualizacion"].replace(tzinfo=timezone.utc), self.t0 + timedelta(minutes=5))

    def test_si_el_riesgo_baja_la_accion_se_descarta(self):
        ejecutar_pipeline(self.db, self.art, self.t0)
        self.art.probabilidades["ACT-004"] = 0.10
        ejecutar_pipeline(self.db, self.art, self.t0 + timedelta(days=1))
        self.assertNotIn("ACT-004", self.acciones())
        self.assertIn("ACT-004", self.acciones(ESTADO_DESCARTADA))

    def test_si_sube_el_riesgo_se_actualiza_la_misma_accion(self):
        ejecutar_pipeline(self.db, self.art, self.t0)
        self.art.probabilidades["ACT-004"] = 0.80
        ejecutar_pipeline(self.db, self.art, self.t0 + timedelta(days=1))
        self.assertEqual(self.acciones()["ACT-004"]["decision_negocio"]["clasificacion"], "CRÍTICO VIP")
        self.assertEqual(self.db[COL_ACCIONES].count_documents({"customer_id": "ACT-004"}), 1)

    def test_documento_invalido_se_omite_sin_detener(self):
        self.db[COL_ACTIVOS].update_one({"customer_id": "ACT-005"}, {"$unset": {"nombre": ""}, "$set": {"horas_uso_semanal": 500}})
        r = ejecutar_pipeline(self.db, self.art, self.t0)
        self.assertEqual(len(r.filas), 5)
        self.assertEqual(r.omitidos[0]["customer_id"], "ACT-005")
        self.assertIn("[AVISO] Cliente ACT-005 omitido", formatear_reporte(r))

    def test_reporte(self):
        texto = formatear_reporte(ejecutar_pipeline(self.db, self.art, self.t0))
        self.assertIn("$26.10", texto)
        self.assertIn("1 mes (LTV", formatear_reporte(ejecutar_pipeline(self.db, self.art, self.t0)))
        self.assertIn("Presupuesto total de retencion: $79.95", texto)

    def test_validar_cliente(self):
        ok = {"customer_id": "ACT-1", "nombre": "X", "meses_antiguedad": 3, "horas_uso_semanal": 2, "tickets_soporte": 0, "fallos_pago": 0, "dias_sin_conectar": 0}
        self.assertEqual(validar_cliente(ok), [])
        self.assertTrue(validar_cliente(dict(ok, meses_antiguedad=2.5)))
        self.assertTrue(validar_cliente(dict(ok, tickets_soporte=True)))
        self.assertTrue(validar_cliente(dict(ok, cuota_mensual=-5)))


if __name__ == "__main__":
    unittest.main()
