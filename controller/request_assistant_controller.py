from typing import List

from services.pattern_learner import LocalRequestPatternLearner

class RequestsAssistantController:
    def __init__(self):
        self.local_learner = LocalRequestPatternLearner()

    def register_request(self, method, url, headers, params, body):
        self.local_learner.register_request(method, url, headers, params, body)

    def suggest_locally(self, method, url):
        headers = self.local_learner.suggest_headers(url, method)
        params = self.local_learner.suggest_params(url, method)
        return headers, params

    def get_header_keys(self, method, url):
        return self.local_learner.get_header_keys(method, url)

    def get_param_keys(self, method, url):
        return self.local_learner.get_param_keys(method, url)

    def get_header_values(self, method: str, url: str, key: str) -> list[str]:
        return self.local_learner.get_header_values(method, url, key)

    def get_param_values(self, method: str, url: str, key: str) -> list[str]:
        return self.local_learner.get_param_values(method, url, key)

    def get_body_keys(self, method: str, url: str) -> List[str]:
        return self.local_learner.get_body_keys(method, url)

    def get_body_values(self, method: str, url: str, key: str) -> list[str]:
        return self.local_learner.get_body_values(method, url, key)

    def suggest_body_keys(self, method: str, url: str, prefix: str, count: int = 1) -> list[str]:
        return self.local_learner.suggest_body_keys(method, url, prefix, count)

    def suggest_header_keys(self, method: str, url: str, prefix: str, count: int = 1) -> list[str]:
        return self.local_learner.suggest_header_keys(method, url, prefix, count)

    def suggest_param_keys(self, method: str, url: str, prefix: str, count: int = 1) -> list[str]:
        return self.local_learner.suggest_param_keys(method, url, prefix, count)