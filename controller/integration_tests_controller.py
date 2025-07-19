import logging

import requests
from PyQt5.QtCore import QThread, pyqtSignal, QObject

from services.exporters import python_requests, node_axios, java_restassured
from services.integration_tests_service import IntegrationTestsService
from utils.requests import join_url


class RequestWorker(QThread):
    on_success = pyqtSignal(dict)
    on_error = pyqtSignal(str)

    def __init__(self, method, url, headers=None, params=None, data=None, parent=None):
        super().__init__(parent)
        self.method = method
        self.url = url
        self.headers = headers or {}
        self.params = params or {}
        self.data = data or ""
        self.response = None

    def run(self):
        logger = logging.getLogger(__name__)

        try:
            logger.info(
                f"Enviando requisição: {self.method} {self.url} headers={self.headers} params={self.params} data={self.data}")
            self.response = requests.request(self.method, self.url, headers=self.headers, params=self.params, data=self.data)
            self.on_success.emit({
                "status": self.response.status_code,
                "body": self.response.text,
                "headers": dict(self.response.headers),
            })
            if self.response:
                logger.info(f"Resposta recebida: status={self.response.status_code}")
            else:
                logger.error("Erro ao executar requisição: resposta vazia")
                self.on_error.emit("Erro ao executar requisição")
        except Exception as e:
            logger.error(f"Erro ao executar requisição: {e}")
            self.on_error.emit(str(e))


class IntegrationTestsController(QObject):
    def __init__(self):
        super().__init__()
        self.service = IntegrationTestsService()

    def get_projects(self):
        return self.service.load()

    def add_project(self, name, path):
        self.service.add_project(name, path)

    def set_project_base_url(self, project, base_url):
        self.service.set_project_base_url(project, base_url)

    def set_controller_path(self, project, controller, path):
        self.service.set_controller_path(project, controller, path)

    def remove_project(self, name):
        self.service.remove_project(name)

    def add_controller(self, project_name, controller_name):
        self.service.add_controller(project_name, controller_name)

    def remove_controller(self, project_name, controller_name):
        self.service.remove_controller(project_name, controller_name)

    def add_endpoint(self, project, controller, endpoint, path="", method="GET"):
        self.service.add_endpoint(project, controller, endpoint, path, method)

    def set_endpoint_path(self, project, controller, endpoint, path):
        self.service.set_endpoint_path(project, controller, endpoint, path)

    def remove_endpoint(self, project, controller, endpoint):
        self.service.remove_endpoint(project, controller, endpoint)

    def duplicate_endpoint(self, project, controller, endpoint):
        self.service.duplicate_endpoint(project, controller, endpoint)

    def rename_endpoint(self, project, controller, old_name, new_name):
        self.service.rename_endpoint(project, controller, old_name, new_name)

    def add_test(self, project, controller, endpoint, test_name):
        self.service.add_test(project, controller, endpoint, test_name)

    def rename_test(self, project, controller, endpoint, old_name, new_name):
        self.service.rename_test(project, controller, endpoint, old_name, new_name)

    def duplicate_test(self, project, controller, endpoint, test_name):
        self.service.duplicate_test(project, controller, endpoint, test_name)

    def remove_test(self, project, controller, endpoint, test_name):
        self.service.remove_test(project, controller, endpoint, test_name)

    def run_test(self, project, controller, endpoint, test_name, on_success=None, on_error=None):
        data = self.service.load()
        proj = data.get(project, {})
        ctrl = proj.get("controllers", {}).get(controller, {})
        ep = ctrl.get("endpoints", {}).get(endpoint, {})
        test = ep.get("tests", {}).get(test_name)
        if not test:
            raise Exception("Teste não encontrado")

        base_url = proj.get('base_url', '')
        ctrl_path = ctrl.get('path', '').strip('/')
        ep_path = ep.get('path', '').strip('/')
        url = join_url(base_url, ctrl_path, ep_path)

        headers = test.get("headers", {})
        params = test.get("query_params", {})
        body = test.get("body", "")

        worker = RequestWorker(
            method=test.get("method", "GET"),
            url=url,
            headers=headers,
            params=params,
            data=body,
            parent=self
        )

        if on_success:
            worker.on_success.connect(on_success)
        if on_error:
            worker.on_error.connect(on_error)
        worker.start()

    def update_test(self, project, controller, endpoint, test_name, new_config):
        self.service.update_test(project, controller, endpoint, test_name, new_config)

    def list_tests(self, project_name: str, controller_name: str, endpoint_name: str):
        """
        Retorna uma lista de dicionários, cada um representando um teste configurado
        para o endpoint especificado.
        """
        data = self.service.load()
        ep = (
            data
            .get(project_name, {})
            .get("controllers", {})
            .get(controller_name, {})
            .get("endpoints", {})
            .get(endpoint_name, {})
        )
        tests = ep.get("tests", {})
        result = []
        default_method = ep.get("method", "GET")
        for name, cfg in tests.items():
            result.append({
                "name": name,
                "controller": controller_name,
                "endpoint": endpoint_name,
                "method": cfg.get("method", default_method),
                "headers": cfg.get("headers", {}),
                "query_params": cfg.get("query_params", {}),
                "body": cfg.get("body", ""),
            })
        return result

    def export_tests(self, project, controller, endpoint, language):
        data = self.service.load()
        proj = data.get(project, {})
        ctrl = proj.get("controllers", {}).get(controller, {})
        ep = ctrl.get("endpoints", {}).get(endpoint, {})
        tests = ep.get("tests", {})

        base_url = proj.get("base_url", "")
        ctrl_path = ctrl.get("path", "")
        ep_path = ep.get("path", "")

        if language == "python":
            return python_requests(tests, base_url, ctrl_path, ep_path)
        if language == "node":
            return node_axios(tests, base_url, ctrl_path, ep_path)
        if language == "java":
            return java_restassured(tests, base_url, ctrl_path, ep_path)
        raise ValueError(f"Linguagem desconhecida: {language}")

    def export_controller_tests(self, project, controller, language):
        """
        Gera um único arquivo com todos os endpoints+testes desse controlador.
        """
        data = self.service.load()
        proj = data.get(project, {})
        ctrl = proj.get("controllers", {}).get(controller, {})

        snippets = []
        for ep_name, ep_data in ctrl.get("endpoints", {}).items():
            code = self.export_tests(project, controller, ep_name, language)
            snippets.append(code)
        return "\n\n".join(snippets)

    def export_project_tests(self, project, language):
        """
        Para cada controlador do projeto gera um arquivo separado.
        Retorna um dict { controller_name: code_string }.
        """
        data = self.service.load()
        proj = data.get(project, {})
        result = {}
        for ctrl_name in proj.get("controllers", {}):
            code = self.export_controller_tests(project, ctrl_name, language)
            result[ctrl_name] = code
        return result

    def export_postman_collection(self, project, controller, endpoint):
        """
        Gera um Postman Collection JSON (v2.1) para este endpoint,
        contendo cada teste configurado como uma request.
        """
        data = self.service.load()
        proj = data.get(project, {})
        ctrl = proj.get("controllers", {}).get(controller, {})
        ep   = ctrl.get("endpoints", {}).get(endpoint, {})
        tests = ep.get("tests", {})

        base_url   = proj.get("base_url", "")
        ctrl_path  = ctrl.get("path", "")
        ep_path    = ep.get("path", "")
        url        = join_url(base_url, ctrl_path, ep_path)

        collection = {
            "info": {
                "name": f"{project} - {controller} - {endpoint}",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "item": []
        }
        for name, cfg in tests.items():
            method = cfg.get("method", ep.get("method", "GET"))
            collection["item"].append({
                "name": name,
                "request": {
                    "method": method,
                    "header": [
                        {"key": k, "value": v}
                        for k, v in cfg.get("headers", {}).items()
                    ],
                    "body": {
                        "mode": "raw",
                        "raw": cfg.get("body", "")
                    },
                    "url": {
                        "raw": url
                    }
                }
            })
        return collection

    def import_java_project(self, project_name, project_path):
        return self.service.import_java_project(project_name, project_path)



    # """
    #     Você é um especialista em testes automatizados de APIs REST, boas práticas de arquitetura de software, debugging e análise de logs. Sua tarefa é analisar um teste de endpoint HTTP a partir dos dados detalhados abaixo.
    #
    #     Receba:
    #     - Método HTTP: {method}
    #     - URL: {url}
    #     - Query Parameters: {query_params}
    #     - Headers: {headers}
    #     - Body enviado: {body}
    #     - Body esperado: {expected_body}
    #     - Verificações (assertions): {assertions}
    #     - Log de execução do teste: {log}
    #
    #     Sua resposta deve ser **objetiva, concisa e técnica**, composta obrigatoriamente dos seguintes itens:
    #
    #     1. **Análise do teste**
    #        - Resuma se o teste cobre bem o cenário, identificando pontos fortes e eventuais fragilidades (ex: falta de validação, dados genéricos, cobertura incompleta).
    #
    #     2. **Diagnóstico do log**
    #        - Se houver erro ou falha no teste, identifique a causa mais provável usando o log e os dados fornecidos.
    #        - Caso o teste tenha passado, comente sobre a robustez do teste e se existem oportunidades de tornar o teste mais confiável.
    #
    #     3. **Sugestões de melhoria**
    #        - Liste sugestões práticas para aprimorar o teste (ex: melhorias nos asserts, exemplos de dados mais realistas, validação de headers, tratamento de status HTTP).
    #        - Se encontrar boas práticas não seguidas no endpoint, inclua recomendações de refatoração ou proteção extra (ex: tratamento de erro, resposta padrão para erro, autenticação).
    #
    #     4. **Correção**
    #        - Se houve erro, forneça um passo a passo direto sobre como corrigir o teste para garantir que ele passe, ou para cobrir corretamente o cenário proposto.
    #
    #     **Importante:** Seja preciso e direto, sem repetições.
    #     Evite respostas genéricas, use termos técnicos e proponha exemplos quando necessário.
    #
    #     [INÍCIO DOS DADOS]
    #     Método: {method}
    #     URL: {url}
    #     Query Params: {query_params}
    #     Headers: {headers}
    #     Body enviado: {body}
    #     Body esperado: {expected_body}
    #     Verificações: {assertions}
    #     Log de execução:
    #     {log}
    #     [FIM DOS DADOS]
    # """