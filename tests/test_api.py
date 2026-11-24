"""API FastAPI (script 4) con TestClient, sin Atlas."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd
from fastapi.testclient import TestClient

from tests.apoyo import base_simulada
from streamedu import api as A
from streamedu import modelo as M
from streamedu.datos import generar_historicos

BASE = {"customer_id": "ACT-999", "nombre": "Sofia Vargas", "meses_antiguedad": 10, "horas_uso_semanal": 1.5,
        "tickets_soporte": 4, "fallos_pago": 1, "dias_sin_conectar": 18}


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        M.guardar_artefactos(M.entrenar(pd.DataFrame(generar_historicos()), epocas=3, comparar=False), cls.dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def cliente(self, directorio=None, db="simulada"):
        A.estado.db = base_simulada("api") if db == "simulada" else None
        A.estado.cliente_mongo = None
        self.db = A.estado.db
        parches = [mock.patch.dict(os.environ, {"STREAMEDU_DIR_MODELOS": str(directorio or self.dir)})]
        if db is None:
            parches.append(mock.patch.object(A, "leer_config_mongo", side_effect=A.ConfigError("sin .env")))
        for p in parches:
            p.start()
            self.addCleanup(p.stop)
        tc = TestClient(A.app)
        tc.__enter__()
        self.addCleanup(tc.__exit__, None, None, None)
        return tc

    def test_evaluar_y_registrar_sin_nombre(self):
        r = self.cliente().post("/evaluar-cliente", json=BASE)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertTrue(j["sincronizado_mongodb_cloud"])
        self.assertIn(j["analisis_negocio"]["nivel_riesgo"], ("CRITICO", "MODERADO", "BAJO (SEGURO)"))
        self.assertEqual(j["fuera_de_rango_entrenamiento"], [])
        doc = self.db["api_predictions_log"].find_one({})
        self.assertEqual(doc["customer_id"], "ACT-999")
        self.assertNotIn("nombre", str(doc))

    def test_modelo_se_carga_una_sola_vez(self):
        with mock.patch.object(A, "cargar_artefactos", wraps=A.cargar_artefactos) as espia:
            c = self.cliente()
            for _ in range(3):
                self.assertEqual(c.post("/evaluar-cliente", json=BASE).status_code, 200)
        self.assertEqual(espia.call_count, 1)

    def test_rechaza_entradas_invalidas(self):
        c = self.cliente()
        malos = {
            "cuota negativa": dict(BASE, cuota_mensual=-1000), "cuota cero": dict(BASE, cuota_mensual=0),
            "500 horas por semana": dict(BASE, horas_uso_semanal=500), "100000 dias": dict(BASE, dias_sin_conectar=100000),
            "600 meses": dict(BASE, meses_antiguedad=600), "nombre gigante": dict(BASE, nombre="A" * 100000),
            "id vacio": dict(BASE, customer_id=""), "id con otro formato": dict(BASE, customer_id="$where"),
            "campo extra": dict(BASE, es_admin=True), "nombre vacio": dict(BASE, nombre="   "),
        }
        for nombre, cuerpo in malos.items():
            with self.subTest(nombre):
                self.assertEqual(c.post("/evaluar-cliente", json=cuerpo).status_code, 422)
        self.assertEqual(self.db["api_predictions_log"].count_documents({}), 0)

    def test_aviso_fuera_del_rango_de_entrenamiento(self):
        j = self.cliente().post("/evaluar-cliente", json=dict(BASE, dias_sin_conectar=200)).json()
        self.assertEqual(j["fuera_de_rango_entrenamiento"], ["dias_sin_conectar"])

    def test_sin_modelo_responde_503(self):
        vacio = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, vacio, True)
        c = self.cliente(directorio=vacio)
        self.assertEqual(c.post("/evaluar-cliente", json=BASE).status_code, 503)
        self.assertFalse(c.get("/salud").json()["modelo_cargado"])

    def test_sin_atlas_igual_responde(self):
        r = self.cliente(db=None).post("/evaluar-cliente", json=BASE)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["sincronizado_mongodb_cloud"])

    def test_salud(self):
        j = self.cliente().get("/salud").json()
        self.assertTrue(j["modelo_cargado"])
        self.assertEqual(len(j["modelo_version"]), 12)


if __name__ == "__main__":
    unittest.main()
