import logging

from PyQt5.QtCore import QRunnable, QObject, pyqtSignal
import requests

from utils.requests import join_url

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestWorkerSignals(QObject):
    """
    Sinais para comunicação entre o QRunnable e a UI thread.
    """
    result = pyqtSignal(dict, object)  # args: test_descriptor, requests.Response
    error  = pyqtSignal(dict, str)     # args: test_descriptor, traceback_str
    finished = pyqtSignal(dict, dict)

class TestRunnable(QRunnable):
    """
    QRunnable que executa um único teste HTTP e emite sinais com o Response.
    """
    def __init__(self, project, controller, test_descriptor, on_success=None, on_error=None):
        super().__init__()
        self.project = project
        self.controller = controller
        self.test = test_descriptor
        self.signals = TestWorkerSignals()

        if on_success:
            self.signals.finished.connect(on_success)
        if on_error:
            self.signals.error.connect(on_error)

    def run(self):
        try:
            logger.info(f"[TestRunnable] Iniciando teste '{self.test.get('name', '')}'")
        except Exception as e:
            logger.error(f"[TestRunnable] Erro no log inicial: {e}", exc_info=True)

        try:
            data = self.controller.service.load()
            logger.info(f"[TestRunnable] Configuração carregada para projeto '{self.project}'")
        except Exception as e:
            logger.error(f"[TestRunnable] Erro ao carregar dados da service: {e}", exc_info=True)
            self.signals.error.emit(self.test, str(e))
            return

        try:
            proj = data.get(self.project, {})
            ctrl = proj.get("controllers", {}).get(self.test["controller"], {})
            ep = ctrl.get("endpoints", {}).get(self.test["endpoint"], {})
            base_url = proj.get("base_url", "")
            ctrl_path = ctrl.get("path", "")
            ep_path = ep.get("path", "")
            url = join_url(base_url, ctrl_path, ep_path)
            method = self.test.get("method", ep.get("method", "GET"))
            headers = self.test.get("headers", {})
            params = self.test.get("query_params", {})
            body = self.test.get("body", "")

            logger.info(f"[TestRunnable] Preparado: {method} {url} | params={params} | headers={headers}")
        except Exception as e:
            logger.error(f"[TestRunnable] Erro ao montar request: {e}", exc_info=True)
            self.signals.error.emit(self.test, str(e))
            return

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=body,
                timeout=30
            )
            logger.info(f"[TestRunnable] Response recebido: {response.status_code}")
        except Exception as e:
            logger.error(f"[TestRunnable] Erro ao executar request: {e}", exc_info=True)
            self.signals.error.emit(self.test, str(e))
            return

        try:
            self.signals.result.emit(self.test, response)
        except Exception as e:
            logger.error(f"[TestRunnable] Erro no emit result: {e}", exc_info=True)

        try:
            data_out = {
                "status": response.status_code,
                "body": response.text,
                "headers": dict(response.headers),
            }
            self.signals.finished.emit(self.test, data_out)
        except Exception as e:
            logger.error(f"[TestRunnable] Erro no emit finished: {e}", exc_info=True)

