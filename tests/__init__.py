import logging
import os
import warnings

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
# Avisos de bibliotecas de terceros que no vienen del proyecto: no ensucian la salida de las pruebas.
warnings.filterwarnings("ignore", message=r".*__array__ implementation doesn't accept a copy keyword.*")
warnings.filterwarnings("ignore", message=r".*Using `httpx` with `starlette.testclient` is deprecated.*")
logging.getLogger("tensorflow").setLevel(logging.ERROR)
logging.getLogger("streamedu.api").setLevel(logging.ERROR)
