"""Red neuronal: arquitectura, reproducibilidad y artefactos sin pickle (entrenamientos cortos)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from tests.apoyo import RAIZ  # noqa: F401
from streamedu import modelo as M
from streamedu.datos import CLIENTES_ACTIVOS, generar_historicos


class TestModelo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = pd.DataFrame(generar_historicos())
        cls.res = M.entrenar(cls.df, epocas=3)
        cls.dir = Path(tempfile.mkdtemp())
        cls.meta = M.guardar_artefactos(cls.res, cls.dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_arquitectura_de_la_guia(self):
        m = M.construir_modelo()
        self.assertEqual(m.count_params(), 241)
        capas = [(c.name, type(c).__name__, getattr(getattr(c, "activation", None), "__name__", None)) for c in m.layers]
        self.assertEqual(capas, [
            ("oculta_1", "Dense", "relu"), ("dropout", "Dropout", None),
            ("oculta_2", "Dense", "relu"), ("salida", "Dense", "sigmoid"),
        ])
        self.assertEqual(m.layers[1].rate, 0.2)

    def test_division_estratificada_y_metricas(self):
        m = self.res.metricas
        self.assertEqual((m["n_entrenamiento"], m["n_prueba"]), (800, 200))
        self.assertAlmostEqual(m["tasa_churn_prueba"], 0.425, delta=0.005)
        for clave in ("accuracy", "precision", "recall", "f1", "auc", "brier"):
            self.assertIn(clave, m["red_neuronal"])
        mc = m["red_neuronal"]["matriz_confusion"]
        self.assertEqual(sum(mc.values()), 200)
        self.assertGreater(m["oraculo"]["auc"], 0.75)

    def test_reproducible_con_la_misma_semilla(self):
        otro = M.entrenar(self.df, epocas=3, comparar=False)
        X = self.res.escalador.transformar([[c[f] for f in M.FEATURES] for c in CLIENTES_ACTIVOS])
        np.testing.assert_array_equal(self.res.modelo.predict(X, verbose=0), otro.modelo.predict(X, verbose=0))

    def test_artefactos_sin_pickle_y_carga_identica(self):
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["churn_model.keras", "escalador.json", "metadata.json"])
        art = M.cargar_artefactos(self.dir)
        X = self.res.escalador.transformar([[c[f] for f in M.FEATURES] for c in CLIENTES_ACTIVOS])
        np.testing.assert_allclose(art.predecir(CLIENTES_ACTIVOS), self.res.modelo.predict(X, verbose=0).ravel(), rtol=1e-6)
        self.assertEqual(art.version, self.meta["version_modelo"])
        self.assertIn("rangos_entrenamiento", art.metadata)

    def test_detecta_archivos_alterados(self):
        copia = Path(tempfile.mkdtemp())
        try:
            for p in self.dir.iterdir():
                shutil.copy(p, copia / p.name)
            esc = json.loads((copia / "escalador.json").read_text(encoding="utf-8"))
            esc["media"][0] += 1
            (copia / "escalador.json").write_text(json.dumps(esc), encoding="utf-8")
            with self.assertRaises(M.IntegridadError):
                M.cargar_artefactos(copia)
            (copia / "escalador.json").unlink()
            with self.assertRaises(M.ModeloNoEntrenadoError):
                M.cargar_artefactos(copia)
        finally:
            shutil.rmtree(copia, ignore_errors=True)

    def test_escalador_json_valida(self):
        base = self.res.escalador.a_dict()
        for malo in (dict(base, features=["x"] * 5), dict(base, media=[0.0]), dict(base, desviacion=[1, 1, 1, 0, 1]), dict(base, media=["a"] * 5)):
            with self.assertRaises(M.IntegridadError):
                M.Escalador.desde_dict(malo)

    def test_experimento_sin_escalador(self):
        filas = M.experimento_escalador(self.df, semillas=(42,), epocas=2, clientes=CLIENTES_ACTIVOS[:1])
        self.assertEqual([f["usa_escalador"] for f in filas], [True, False])
        self.assertIn("ACT-001", filas[1]["probabilidades"])

    def test_exige_columnas_y_datos(self):
        with self.assertRaises(ValueError):
            M.entrenar(self.df.drop(columns=["churn"]))
        with self.assertRaises(ValueError):
            M.entrenar(self.df.head(10))


if __name__ == "__main__":
    unittest.main()
