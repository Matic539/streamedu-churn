import unittest
from unittest import mock

from tests.apoyo import REFERENCIA, base_simulada, cargar_script, errores_esquema
from streamedu.datos import CLIENTE_DEMO_SUPER_VIP, CLIENTES_ACTIVOS, generar_historicos, probabilidad_real
from streamedu.db import esquema_activos, esquema_historicos


class TestDatos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hist = generar_historicos()

    def test_cantidad_y_churn(self):
        self.assertEqual(len(self.hist), 1000)
        self.assertEqual(sum(d["churn"] for d in self.hist), 425)
        self.assertEqual(len({d["customer_id"] for d in self.hist}), 1000)

    def test_reproducible(self):
        self.assertEqual(generar_historicos(), self.hist)

    def test_cumplen_el_validador_de_mongodb(self):
        for d in self.hist:
            self.assertEqual(errores_esquema(d, esquema_historicos()), [], d["customer_id"])
        for c in CLIENTES_ACTIVOS + [CLIENTE_DEMO_SUPER_VIP]:
            self.assertEqual(errores_esquema(c, esquema_activos()), [], c["customer_id"])

    def test_validador_rechaza_datos_malos(self):
        malo = dict(CLIENTES_ACTIVOS[0], horas_uso_semanal=500.0, meses_antiguedad="14")
        del malo["nombre"]
        errores = errores_esquema(malo, esquema_activos())
        self.assertTrue(any("nombre" in e for e in errores))
        self.assertTrue(any("horas_uso_semanal" in e for e in errores))
        self.assertTrue(any("meses_antiguedad" in e for e in errores))

    def test_oraculo_clientes_de_la_guia(self):
        esperados = {"ACT-001": 88.4, "ACT-002": 86.9, "ACT-003": 2.0, "ACT-004": 44.0, "ACT-005": 7.5, "ACT-006": 95.0}
        for c in CLIENTES_ACTIVOS + [CLIENTE_DEMO_SUPER_VIP]:
            self.assertAlmostEqual(probabilidad_real(c) * 100, esperados[c["customer_id"]], delta=0.05)

    def test_act006_es_el_unico_super_vip_posible(self):
        ltv = {c["customer_id"]: c["meses_antiguedad"] * c["cuota_mensual"] for c in CLIENTES_ACTIVOS}
        criticos_reales = {c["customer_id"] for c in CLIENTES_ACTIVOS if probabilidad_real(c) >= 0.70}
        self.assertFalse([cid for cid in criticos_reales if ltv[cid] >= 500])
        self.assertGreaterEqual(CLIENTE_DEMO_SUPER_VIP["meses_antiguedad"] * 29.0, 500)

    @unittest.skipUnless((REFERENCIA / "1_seed_mongodb.py").exists(), "sin el código del docente al lado")
    def test_identico_al_script_del_docente(self):
        db = base_simulada("ref")
        ref = cargar_script("1_seed_mongodb.py", "seed_docente", REFERENCIA)
        with mock.patch.object(ref, "MongoClient", lambda *a, **k: db.client), mock.patch.object(ref, "DB_NAME", "ref"), mock.patch("builtins.print"):
            ref.seed_database()
        docente = list(db["historical_customers"].find({}, {"_id": 0}).sort("customer_id", 1))
        self.assertEqual(docente, self.hist)
        activos = list(db["active_customers"].find({}, {"_id": 0}).sort("customer_id", 1))
        self.assertEqual(activos, CLIENTES_ACTIVOS)


if __name__ == "__main__":
    unittest.main()
