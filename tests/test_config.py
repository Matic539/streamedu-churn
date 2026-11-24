import os
import unittest
from unittest import mock

from tests.apoyo import RAIZ  # noqa: F401  (agrega el proyecto al path)
from streamedu.config import ConfigError, enmascarar_uri, leer_config_mongo

# URI ficticia armada por partes para que los escáneres de secretos (p. ej. GitHub) no la confundan con una real.
CLAVE_FALSA = "Cl4veSecreta99"
URI_OK = "mongodb+srv://" + "streamedu_app:" + CLAVE_FALSA + "@" + "cluster0.abcde" + ".mongodb.net/?retryWrites=true&w=majority"


class TestConfig(unittest.TestCase):
    def leer(self, **env):
        with mock.patch.dict(os.environ, env, clear=True):
            return leer_config_mongo()

    def test_uri_valida(self):
        self.assertEqual(self.leer(MONGO_URI=URI_OK, DB_NAME="streamedu_db"), (URI_OK, "streamedu_db"))

    def test_sin_uri_no_cae_en_localhost(self):
        with self.assertRaisesRegex(ConfigError, "Falta MONGO_URI"):
            self.leer()

    def test_uri_de_ejemplo_rechazada(self):
        for uri in (
            "mongodb+srv://streamedu_app:<db_password>@<cluster>.mongodb.net/",
            "mongodb+srv://" + "alumno_dl:tu_password@cluster0.xxxx" + ".mongodb.net/?retryWrites=true",
            "mongodb+srv://" + "usuario:password@tu-cluster.mongodb.net/",
        ):
            with self.subTest(uri=uri), self.assertRaisesRegex(ConfigError, "texto de ejemplo"):
                self.leer(MONGO_URI=uri)

    def test_exige_atlas(self):
        for uri in ("mongodb://" + "u:p@localhost:27017/", "mongodb+srv://" + "u:p@ejemplo.com/", "http://u:p@cluster0.ab.mongodb.net"):
            with self.subTest(uri=uri), self.assertRaises(ConfigError):
                self.leer(MONGO_URI=uri)

    def test_sin_credenciales(self):
        with self.assertRaisesRegex(ConfigError, "usuario y contraseña"):
            self.leer(MONGO_URI="mongodb+srv://cluster0.abcde.mongodb.net/")

    def test_db_name_invalido(self):
        with self.assertRaises(ConfigError):
            self.leer(MONGO_URI=URI_OK, DB_NAME="base con espacios")

    def test_mensajes_y_mascara_no_muestran_la_clave(self):
        masc = enmascarar_uri(URI_OK)
        self.assertNotIn(CLAVE_FALSA, masc)
        self.assertNotIn("streamedu_app", masc)
        self.assertIn("mongodb.net", masc)
        try:
            self.leer(MONGO_URI=URI_OK.replace("mongodb.net", "ejemplo.org"))
        except ConfigError as e:
            self.assertNotIn(CLAVE_FALSA, str(e))


if __name__ == "__main__":
    unittest.main()
