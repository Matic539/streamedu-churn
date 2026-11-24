import unittest
from unittest import mock

from tests.apoyo import REFERENCIA, cargar_script
from streamedu import negocio as N
from streamedu.negocio import aplicar_logica_negocio


def cli(meses, cuota=29.0):
    return {"meses_antiguedad": meses, "cuota_mensual": cuota}


class TestTabla(unittest.TestCase):
    def test_costos(self):
        self.assertEqual(N.COSTO_VIP, 26.10)
        self.assertEqual(N.COSTO_ESTANDAR, 4.35)
        self.assertEqual(N.COSTO_MODERADO, 0.50)
        self.assertEqual(N.COSTO_SUPER_VIP, 49.00)

    def test_cuatro_niveles_de_la_guia(self):
        casos = [
            (cli(14), 0.85, "CRITICO", "CRÍTICO VIP", 26.10),
            (cli(2), 0.85, "CRITICO", "CRÍTICO ESTÁNDAR", 4.35),
            (cli(8), 0.55, "MODERADO", "RIESGO MODERADO", 0.50),
            (cli(20), 0.02, "BAJO (SEGURO)", "BAJO (SEGURO)", 0.0),
        ]
        for c, p, nivel, clasif, costo in casos:
            with self.subTest(clasif=clasif):
                d = aplicar_logica_negocio(c, p)
                self.assertEqual((d["nivel_riesgo"], d["clasificacion"], d["presupuesto_asignado_usd"]), (nivel, clasif, costo))

    def test_super_vip(self):
        d = aplicar_logica_negocio(cli(18), 0.90)  # LTV 522
        self.assertEqual(d["segmento"], "SUPER_VIP")
        self.assertEqual(d["accion_comercial"], "1 Mes Gratis + Mentoría 1 a 1")
        self.assertEqual(d["presupuesto_asignado_usd"], 49.00)
        self.assertTrue(d["es_cliente_vip"] and d["es_super_vip"])

    def test_super_vip_tiene_prioridad_sobre_vip(self):
        self.assertEqual(aplicar_logica_negocio(cli(17), 0.90)["segmento"], "VIP")        # 493
        self.assertEqual(aplicar_logica_negocio(cli(20, 25.0), 0.90)["segmento"], "SUPER_VIP")  # 500 exacto

    def test_super_vip_requiere_riesgo_critico(self):
        d = aplicar_logica_negocio(cli(20), 0.02)  # Lucía: LTV 580 pero riesgo bajo
        self.assertTrue(d["es_super_vip"])
        self.assertEqual(d["clasificacion"], "BAJO (SEGURO)")
        self.assertEqual(d["presupuesto_asignado_usd"], 0.0)

    def test_umbral_vip_mes_7(self):
        self.assertFalse(aplicar_logica_negocio(cli(6), 0.9)["es_cliente_vip"])   # 174
        self.assertTrue(aplicar_logica_negocio(cli(7), 0.9)["es_cliente_vip"])    # 203

    def test_bordes_de_probabilidad(self):
        for p, nivel in ((0.3999, "BAJO (SEGURO)"), (0.40, "MODERADO"), (0.6999, "MODERADO"), (0.70, "CRITICO"), (1.0, "CRITICO"), (0.0, "BAJO (SEGURO)")):
            with self.subTest(p=p):
                self.assertEqual(aplicar_logica_negocio(cli(5), p)["nivel_riesgo"], nivel)

    def test_clasifica_con_lo_que_guarda(self):
        d = aplicar_logica_negocio(cli(5), 0.69996)  # se guarda 0.7000: debe ser CRITICO
        self.assertEqual(d["probabilidad_usada"], 0.7)
        self.assertEqual(d["nivel_riesgo"], "CRITICO")

    def test_entradas_invalidas(self):
        for c, p in ((cli(5), 1.2), (cli(5), -0.1), (cli(5), float("nan")), (cli(-1), 0.5), (cli(5, 0.0), 0.5), (cli("5"), 0.5), (cli(True), 0.5)):
            with self.subTest(c=c, p=p), self.assertRaises(ValueError):
                aplicar_logica_negocio(c, p)

    def test_cuota_por_defecto(self):
        self.assertEqual(aplicar_logica_negocio({"meses_antiguedad": 10}, 0.9)["ltv_acumulado_usd"], 290.0)


@unittest.skipUnless((REFERENCIA / "3_business_pipeline.py").exists(), "sin el código del docente al lado")
class TestComparacionConDocente(unittest.TestCase):
    """Fuera de la zona SUPER VIP, la regla propia debe decidir igual que la del docente."""

    @classmethod
    def setUpClass(cls):
        with mock.patch("builtins.print"):
            cls.ref = cargar_script("3_business_pipeline.py", "pipeline_docente", REFERENCIA)

    def test_grilla(self):
        claves = ("nivel_riesgo", "es_cliente_vip", "ltv_acumulado_usd", "accion_comercial", "presupuesto_asignado_usd")
        comparados = super_vip = 0
        for meses in range(0, 41):
            for cuota in (29.0, 25.5, 12.0):
                for i in range(0, 1001):
                    p = i / 1000
                    propia = aplicar_logica_negocio(cli(meses, cuota), p)
                    docente = self.ref.aplicar_logica_negocio(cli(meses, cuota), p)
                    if propia["segmento"] == "SUPER_VIP":
                        super_vip += 1
                        self.assertEqual(docente["accion_comercial"], N.ACCION_VIP)
                        continue
                    comparados += 1
                    self.assertEqual({k: propia[k] for k in claves}, {k: docente[k] for k in claves}, (meses, cuota, p))
        self.assertGreater(comparados, 100000)
        self.assertGreater(super_vip, 1000)


if __name__ == "__main__":
    unittest.main()
