import logging
import os
import json
import threading
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal

from controller.java_controller_parser import JavaControllerParser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JavaImportWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, controller, project, project_path, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.project = project
        self.project_path = project_path

    def run(self):
        try:
            controllers = self.controller.import_java_project(self.project, self.project_path)
            logger.info(f"[JavaImportWorker] Importação concluída com sucesso: {len(controllers)} controladores encontrados.")
            self.finished.emit(controllers)
        except Exception as e:
            logger.error(f"[JavaImportWorker] Erro ao importar projeto Java: {str(e)}")
            self.error.emit(str(e))


class IntegrationTestsService:
    _lock = threading.Lock()

    def __init__(self, base_path=None):
        self.base_path = base_path or os.path.expanduser("")
        self.file_path = os.path.join(self.base_path, "integration_test_session")
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w") as f:
                json.dump({}, f, indent=2)

    def load(self):
        with self._lock:
            with open(self.file_path, "r") as f:
                return json.load(f)

    def save(self, data: dict):
        with self._lock:
            tmp_path = self.file_path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.file_path)

    def add_project(self, project_name, path):
        data = self.load()
        if project_name in data:
            raise Exception(f"Projeto '{project_name}' já existe!")
        data[project_name] = {
            "project_path": path,  # pode ser ""
            "controllers": {}
        }
        self.save(data)

    def set_project_base_url(self, project_name, base_url):
        data = self.load()
        if project_name in data:
            data[project_name]["base_url"] = base_url
            self.save(data)

    def set_controller_path(self, project_name, controller_name, path):
        data = self.load()
        ctrl = data.get(project_name, {}).get("controllers", {}).get(controller_name)
        if ctrl is not None:
            ctrl["path"] = path
            self.save(data)

    def remove_project(self, project_name):
        data = self.load()
        if project_name in data:
            data.pop(project_name)
            self.save(data)

    def add_controller(self, project_name, controller_name):
        data = self.load()
        project = data.get(project_name)
        if not project:
            raise Exception("Projeto não encontrado")
        if controller_name in project["controllers"]:
            raise Exception(f"Controlador '{controller_name}' já existe!")
        project["controllers"][controller_name] = {
            "description": "",
            "tests": []
        }
        self.save(data)

    def remove_controller(self, project_name, controller_name):
        data = self.load()
        project = data.get(project_name)
        if not project:
            raise Exception("Projeto não encontrado")
        if controller_name in project["controllers"]:
            project["controllers"].pop(controller_name)
            self.save(data)

    def add_endpoint(self, project_name, controller_name, endpoint_name, path="", method="GET", query_params=None):
        data = self.load()
        ctrl = data.get(project_name, {}).get("controllers", {}).get(controller_name)
        if ctrl is not None:
            if "endpoints" not in ctrl:
                ctrl["endpoints"] = {}
            if endpoint_name in ctrl["endpoints"]:
                raise Exception(f"Endpoint '{endpoint_name}' já existe!")
            ctrl["endpoints"][endpoint_name] = {
                "description": "",
                "method": method,
                "query_params": query_params or [],
                "path_variables": [],
                "request_body_type": None,
                "path": path,
                "test_cases": []
            }
            self.save(data)

    def set_endpoint_path(self, project_name, controller_name, endpoint_name, path):
        data = self.load()
        ep = data.get(project_name, {}).get("controllers", {}).get(controller_name, {}).get("endpoints", {}).get(
            endpoint_name)
        if ep is not None:
            ep["path"] = path
            self.save(data)

    def remove_endpoint(self, project_name, controller_name, endpoint_name):
        data = self.load()
        ctrl = data.get(project_name, {}).get("controllers", {}).get(controller_name)
        if ctrl and "endpoints" in ctrl and endpoint_name in ctrl["endpoints"]:
            ctrl["endpoints"].pop(endpoint_name)
            self.save(data)

    def duplicate_endpoint(self, project_name, controller_name, endpoint_name):
        data = self.load()
        ctrl = data.get(project_name, {}).get("controllers", {}).get(controller_name)
        if ctrl and "endpoints" in ctrl and endpoint_name in ctrl["endpoints"]:
            original = ctrl["endpoints"][endpoint_name].copy()
            base_new_name = f"{endpoint_name} (copy)"
            new_name = base_new_name
            idx = 2
            while new_name in ctrl["endpoints"]:
                new_name = f"{base_new_name} {idx}"
                idx += 1
            ctrl["endpoints"][new_name] = original
            self.save(data)

    def rename_endpoint(self, project_name, controller_name, old_name, new_name):
        data = self.load()
        ctrl = data.get(project_name, {}).get("controllers", {}).get(controller_name)
        if not ctrl or "endpoints" not in ctrl or old_name not in ctrl["endpoints"]:
            raise Exception("Endpoint não encontrado.")
        if new_name in ctrl["endpoints"]:
            raise Exception(f"Já existe um endpoint chamado '{new_name}'.")
        ctrl["endpoints"][new_name] = ctrl["endpoints"].pop(old_name)
        self.save(data)


    def add_test(self, project_name, controller_name, endpoint_name, test_name):
        data = self.load()
        ep = data.get(project_name, {}) \
                 .get("controllers", {}) \
                 .get(controller_name, {}) \
                 .get("endpoints", {}) \
                 .get(endpoint_name)
        if ep is None:
            raise Exception("Endpoint não encontrado.")
        if "tests" not in ep:
            ep["tests"] = {}
        if test_name in ep["tests"]:
            raise Exception(f"Teste '{test_name}' já existe!")
        ep["tests"][test_name] = {
            "description": "",
            "headers": {},
            "query_params": {},
            "body": "",
            "expected_status": 200,
            "expected_body": "",
            "assertions": []
        }
        self.save(data)

    def update_test(self, project_name, controller_name, endpoint_name, test_name, new_config):
        data = self.load()
        data[project_name]["controllers"][controller_name]["endpoints"][endpoint_name]["tests"][test_name] = new_config
        self.save(data)

    def rename_test(self, project_name, controller_name, endpoint_name, old_name, new_name):
        data = self.load()
        tests = data.get(project_name, {}) \
                    .get("controllers", {}) \
                    .get(controller_name, {}) \
                    .get("endpoints", {}) \
                    .get(endpoint_name, {}) \
                    .get("tests", {})
        if old_name not in tests:
            raise Exception("Teste não encontrado.")
        if new_name in tests:
            raise Exception(f"Já existe um teste chamado '{new_name}'.")
        tests[new_name] = tests.pop(old_name)
        self.save(data)

    def duplicate_test(self, project_name, controller_name, endpoint_name, test_name):
        data = self.load()
        ep = data.get(project_name, {}) \
                 .get("controllers", {}) \
                 .get(controller_name, {}) \
                 .get("endpoints", {}) \
                 .get(endpoint_name)
        if ep is None or "tests" not in ep or test_name not in ep["tests"]:
            raise Exception("Teste não encontrado.")
        original = ep["tests"][test_name].copy()
        base = f"{test_name} (copy)"
        new_name = base
        i = 2
        while new_name in ep["tests"]:
            new_name = f"{base} {i}"
            i += 1
        ep["tests"][new_name] = original
        self.save(data)

    def remove_test(self, project_name, controller_name, endpoint_name, test_name):
        data = self.load()
        ep = data.get(project_name, {}) \
                 .get("controllers", {}) \
                 .get(controller_name, {}) \
                 .get("endpoints", {}) \
                 .get(endpoint_name)
        if ep and "tests" in ep and test_name in ep["tests"]:
            ep["tests"].pop(test_name)
            self.save(data)

    def import_java_controller(self, project_name: str, file_path: str):
        data = self.load()
        if project_name not in data:
            raise Exception(f"Projeto '{project_name}' não encontrado.")

        try:
            result = JavaControllerParser.parse(file_path)

            project_src_dir = data[project_name].get("project_path") or ""
            if not project_src_dir:
                project_src_dir = str(Path(file_path).parent)

            name = result['controller_name']
            prefix = result.get('class_prefix', '')

            proj = data[project_name]
            controllers = proj.setdefault('controllers', {})
            ctrl = controllers.setdefault(name, {})
            if prefix:
                ctrl['path'] = prefix

            endpoints = ctrl.setdefault('endpoints', {})
            for ep in result['endpoints']:
                key = ep['name']
                cfg = endpoints.setdefault(key, {})
                cfg['method'] = ep['http_method']
                cfg['path'] = ep['path']

                cfg['query_params'] = ep['query_params']
                cfg['path_variables'] = ep['path_variables']
                cfg['body_required'] = ep.get('body_required', False)
                if ep['request_body_type']:
                    example_body = JavaControllerParser.get_java_type_fields(ep['request_body_type'], project_src_dir)
                    cfg['body'] = json.dumps(example_body, indent=2) if example_body else '{}'
                    cfg['body_example'] = cfg['body']
                    cfg['request_body_type'] = ep['request_body_type']
                else:
                    cfg.setdefault('body', '')

                response_type = ep.get('return_type')
                if response_type:
                    main_type = JavaControllerParser.extract_response_type(response_type)
                    response_example = JavaControllerParser.get_java_type_fields(main_type, project_src_dir)
                    cfg['response_example'] = json.dumps(response_example, indent=2) if response_example else ''
                else:
                    cfg['response_example'] = ''

                tests = cfg.setdefault('tests', {})
                tests['success'] = {
                    'description': '',
                    'headers': {},
                    'query_params': {qp['name']: '' for qp in cfg['query_params']},
                    'path_variables': {pv['name']: '' for pv in cfg['path_variables']},
                    'body': cfg.get('body', ''),
                    'expected_status': 200,
                    'expected_body': cfg.get('response_example', ''),
                    'assertions': [
                        {'type': 'status_code', 'target': '', 'expected': 200}
                    ],
                    'json_schema': ''
                }
        except Exception as e:
            logger.error(f"[IntegrationTestsService] Erro ao importar controlador Java: {str(e)}")
            pass

        self.save(data)

    def import_java_project(self, project_name: str, project_path: str):
        """
        Importa recursivamente todos os arquivos Controller Java de um projeto.
        """
        data = self.load()
        if project_name not in data:
            raise Exception(f"Projeto '{project_name}' não encontrado.")

        controllers_found = []
        for java_file in Path(project_path).rglob("*.java"):
            try:
                result = JavaControllerParser.parse(str(java_file))
                if not result:
                    continue
                if 'controller_name' in result:
                    self.import_java_controller(project_name, str(java_file))
                    controllers_found.append(result['controller_name'])
            except Exception as e:
                logger.warning(f"[IntegrationTestsService] Ignorado {java_file}: {str(e)}")
                continue

        return controllers_found
