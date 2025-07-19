# data/services/ia/local_pattern_learner.py
import gzip
import json
import os
from collections import Counter, defaultdict, deque
from difflib import SequenceMatcher
from typing import List


class LocalRequestPatternLearner:
    STORAGE_FILE = "requests_patterns.json"
    MAX_RAW_ENTRIES = 50

    def __init__(self):
        self.patterns = defaultdict(lambda: {
            "raw": deque(maxlen=self.MAX_RAW_ENTRIES),
            "hdr_counts": defaultdict(lambda: defaultdict(Counter)),
            "prm_counts": defaultdict(lambda: defaultdict(Counter)),
            "body_key_counts": defaultdict(Counter),
            "body_value_counts": defaultdict(lambda: defaultdict(Counter)),
        })

        gz_path = self.STORAGE_FILE + ".gz"
        self.load(gz_path)

    def load(self, file_path: str):
        """Carrega os padrões de requisições de um arquivo JSON."""
        if os.path.exists(file_path):
            with gzip.open(file_path, "rt", encoding="utf-8") as f:
                data = json.load(f)
            for base, entry in data.items():
                patt = self.patterns[base]
                patt["raw"].extend(entry.get("raw", []))
                for method, hdrs in entry.get("hdr_counts", {}).items():
                    for key, counts in hdrs.items():
                        patt["hdr_counts"][method][key].update(counts)
                for method, prms in entry.get("prm_counts", {}).items():
                    for key, counts in prms.items():
                        patt["prm_counts"][method][key].update(counts)
                for method, counts in entry.get("body_key_counts", {}).items():
                    self.patterns[base]["body_key_counts"][method].update(counts)
                for method, values in entry.get("body_value_counts", {}).items():
                    for key, cnts in values.items():
                        patt["body_value_counts"][method][key].update(cnts)
    def save(self):
        serial = {}
        for base, entry in self.patterns.items():
            serial[base] = {
                "raw": list(entry["raw"]),
                "hdr_counts": {
                    method: {key: dict(cnt) for key, cnt in keys.items()}
                    for method, keys in entry["hdr_counts"].items()
                },
                "prm_counts": {
                    method: {key: dict(cnt) for key, cnt in keys.items()}
                    for method, keys in entry["prm_counts"].items()
                },
                "body_key_counts": {
                    method: dict(cnt)
                    for method, cnt in entry["body_key_counts"].items()
                },
                "body_value_counts": {
                    method: {key: dict(cnt) for key, cnt in keys.items()}
                    for method, keys in entry["body_value_counts"].items()
                }
            }

        with gzip.open(self.STORAGE_FILE + ".gz", "wt", encoding="utf-8") as f:
            json.dump(serial, f, indent=2)


    def register_request(self, method: str, url: str, headers: dict, params: dict, body: str):
        base = self.extract_base_url(url)
        patt = self.patterns[base]

        patt["raw"].append({ "method": method, "headers": headers, "params": params })

        for key, val in headers.items():
            patt["hdr_counts"][method][key][val] += 1
        for key, val in params.items():
            patt["prm_counts"][method][key][val] += 1

        try:
            obj = json.loads(body) if body and isinstance(body, str) else None
            if isinstance(obj, dict):
                for key in obj.keys():
                    patt["body_key_counts"][method][key] += 1
        except json.JSONDecodeError:
            pass

        try:
            obj = json.loads(body) if body and isinstance(body, str) else None
            if isinstance(obj, dict):
                for key, val in obj.items():
                    patt["body_key_counts"][method][key] += 1
                    # registrar valor (string, num ou bool)
                    if isinstance(val, (str, bool, int, float)) or val is None:
                        patt["body_value_counts"][method][key][str(val)] += 1
        except json.JSONDecodeError:
            pass

        self.save()

    def suggest_headers(self, url: str, method: str) -> dict[str, str]:
        """
        Retorna para cada header_key o valor mais frequente já registrado
        para o método e base de URL fornecidos.
        """
        base = self.get_most_similar_base(url)
        method_counters = self.patterns[base]["hdr_counts"].get(method, {})
        suggestions: dict[str, str] = {}
        for header_key, counter in method_counters.items():
            if counter:
                # pega o valor mais comum
                top_value, _ = counter.most_common(1)[0]
                suggestions[header_key] = top_value
        return suggestions

    def suggest_params(self, url: str, method: str) -> dict[str, str]:
        """
        Retorna para cada param_key o valor mais frequente já registrado
        para o método e base de URL fornecidos.
        """
        base = self.get_most_similar_base(url)
        # recupera o dict param_key → Counter(valor → contagem)
        method_counters = self.patterns[base]["prm_counts"].get(method, {})
        suggestions: dict[str, str] = {}
        for param_key, counter in method_counters.items():
            if counter:
                top_value, _ = counter.most_common(1)[0]
                suggestions[param_key] = top_value
        return suggestions

    def extract_base_url(self, url):
        return url.split("?", 1)[0].rsplit("/", 1)[0]

    def get_most_similar_base(self, url: str) -> str:
        target = self.extract_base_url(url)
        best, score = target, 0.0
        for known in self.patterns:
            r = SequenceMatcher(None, known, target).ratio()
            if r > score:
                best, score = known, r
        return best

    def get_header_keys(self, method, url):
        base = self.get_most_similar_base(url)
        method_keys = self.patterns[base]["hdr_counts"].get(method, {})

        if method_keys:
            return list(method_keys.keys())

        fallback_counter = Counter()
        for other_base, entry in self.patterns.items():
            for other_method, keys in entry["hdr_counts"].items():
                for key in keys.keys():
                    fallback_counter[key] += sum(keys[key].values())

        return [k for k, _ in fallback_counter.most_common()]

    def get_param_keys(self, method, url):
        base = self.get_most_similar_base(url)
        method_keys = self.patterns[base]["prm_counts"].get(method, {})

        if method_keys:
            return list(method_keys.keys())

        fallback_counter = Counter()
        for other_base, entry in self.patterns.items():
            for other_method, keys in entry["prm_counts"].items():
                for key in keys.keys():
                    fallback_counter[key] += sum(keys[key].values())

        return [k for k, _ in fallback_counter.most_common()]

    def get_header_values(self, method: str, url: str, key: str) -> list[str]:
        base = self.get_most_similar_base(url)
        ctr = self.patterns[base]["hdr_counts"].get(method, {}).get(key, Counter())

        if ctr and sum(ctr.values()) > 0:
            return [val for val, _ in ctr.most_common()]

        fallback_counter = Counter()
        for other_base, entry in self.patterns.items():
            for other_method, keys in entry["hdr_counts"].items():
                if key in keys:
                    fallback_counter.update(keys[key])

        return [val for val, _ in fallback_counter.most_common()] if fallback_counter else []

    def get_param_values(self, method: str, url: str, key: str) -> list[str]:
        base = self.get_most_similar_base(url)
        ctr = self.patterns[base]["prm_counts"].get(method, {}).get(key, Counter())

        if ctr and sum(ctr.values()) > 0:
            return [val for val, _ in ctr.most_common()]

        fallback_counter = Counter()
        for other_base, entry in self.patterns.items():
            for other_method, keys in entry["prm_counts"].items():
                if key in keys:
                    fallback_counter.update(keys[key])

        return [val for val, _ in fallback_counter.most_common()] if fallback_counter else []

    def get_body_keys(self, method: str, url: str) -> List[str]:
        base = self.get_most_similar_base(url)
        ctr = self.patterns[base]["body_key_counts"].get(method, Counter())
        if ctr and sum(ctr.values()) > 0:
            return [k for k, _ in sorted(ctr.items(), key=lambda kv: -kv[1])]

        fallback_counter = Counter()
        for other_base, entry in self.patterns.items():
            for other_method, keys in entry["body_key_counts"].items():
                fallback_counter.update(keys)

        return [k for k, _ in fallback_counter.most_common()]

    def get_body_values(self, method: str, url: str, key: str) -> list[str]:
        base = self.get_most_similar_base(url)
        ctr = self.patterns[base]["body_value_counts"].get(method, {}).get(key, Counter())

        if ctr and sum(ctr.values()) > 0:
            return [v for v, _ in ctr.most_common()]

        fallback_counter = Counter()
        for other_base, entry in self.patterns.items():
            for other_method, keys in entry["body_value_counts"].items():
                if key in keys:
                    fallback_counter.update(keys[key])

        if fallback_counter:
            return [v for v, _ in fallback_counter.most_common()]

        return []

    def suggest_body_keys(self, method: str, url: str, prefix: str, count: int = 1) -> list[str]:
        base = self.get_most_similar_base(url)
        method_keys = self.patterns[base]["body_key_counts"].get(method, Counter())

        suggestions = [k for k in method_keys if k.startswith(prefix)]
        if suggestions:
            return sorted(suggestions, key=lambda k: -method_keys[k])[:count]

        fallback_counter = Counter()
        for other_base, entry in self.patterns.items():
            for other_method, keys in entry["body_key_counts"].items():
                for key in keys:
                    if key.startswith(prefix):
                        fallback_counter[key] += keys[key]
                        if len(fallback_counter) >= count:
                            break
            if len(fallback_counter) >= count:
                break

        return [k for k, _ in fallback_counter.most_common(count)]

    def suggest_header_keys(self, method: str, url: str, prefix: str, count: int = 1) -> list[str]:
        base = self.get_most_similar_base(url)
        method_keys = self.patterns[base]["hdr_counts"].get(method, {})

        suggestions = [key for key in method_keys if key.startswith(prefix)]
        if suggestions:
            return suggestions[:count]

        fallback_counter = Counter()
        for other_base, entry in self.patterns.items():
            for other_method, keys in entry["hdr_counts"].items():
                for key in keys:
                    if key.startswith(prefix):
                        fallback_counter[key] += sum(keys[key].values())
                        if len(fallback_counter) >= count:
                            break
            if len(fallback_counter) >= count:
                break

        return [k for k, _ in fallback_counter.most_common(count)]

    def suggest_param_keys(self, method: str, url: str, prefix: str, count: int = 1) -> list[str]:
        base = self.get_most_similar_base(url)
        method_keys = self.patterns[base]["prm_counts"].get(method, {})

        suggestions = [key for key in method_keys if key.startswith(prefix)]
        if suggestions:
            return suggestions[:count]

        fallback_counter = Counter()
        for other_base, entry in self.patterns.items():
            for other_method, keys in entry["prm_counts"].items():
                for key in keys:
                    if key.startswith(prefix):
                        fallback_counter[key] += sum(keys[key].values())
                        if len(fallback_counter) >= count:
                            break
            if len(fallback_counter) >= count:
                break

        return [k for k, _ in fallback_counter.most_common(count)]

