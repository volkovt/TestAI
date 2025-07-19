import json

def python_requests(tests: dict, base_url: str, ctrl_path: str, ep_path: str) -> str:
    lines = [
        "import requests",
        "",
        f"BASE_URL = '{base_url}'",
        f"ENDPOINT = '{ctrl_path}{ep_path}'",
        "",
    ]
    for name, cfg in tests.items():
        fn = name.replace(' ', '_').lower()
        lines.append(f"def test_{fn}():")
        # headers
        hdrs = cfg.get("headers", {})
        if hdrs:
            lines.append(f"    headers = {json.dumps(hdrs)}")
        # params
        params = cfg.get("query_params", {})
        if params:
            lines.append(f"    params = {json.dumps(params)}")
        # body
        body = cfg.get("body", "").strip()
        if body:
            lines.append(f"    data = {json.dumps(json.loads(body), indent=4)}")
        # request
        call = "    resp = requests.{method}(\n        BASE_URL + ENDPOINT".format(
            method=cfg.get("method","get").lower()
        )
        if hdrs:   call += ", headers=headers"
        if params: call += ", params=params"
        if body:   call += ", json=data"
        call += "\n    )"
        lines.append(call)
        # assertions
        exp_status = cfg.get("expected_status", 200)
        lines.append(f"    assert resp.status_code == {exp_status}")
        exp_body = cfg.get("expected_body","").strip()
        if exp_body:
            lines.append(f"    assert resp.text == {exp_body!r}")
        # custom assertions
        for a in cfg.get("assertions", []):
            t, target, exp = a["type"], a["target"], a["expected"]
            if t == "Body Contains":
                lines.append(f"    assert {exp!r} in resp.text")
            elif t == "Header Equals":
                lines.append(f"    assert resp.headers.get({target!r}) == {exp!r}")
            # (adicione outros casos conforme necessário)
        lines.append("")  # linha em branco
    return "\n".join(lines)

def node_axios(tests: dict, base_url: str, ctrl_path: str, ep_path: str) -> str:
    lines = [
        "const axios = require('axios');",
        "",
        f"const BASE_URL = '{base_url}';",
        f"const ENDPOINT = '{ctrl_path}{ep_path}';",
        "",
    ]
    for name, cfg in tests.items():
        fn = name.replace(' ', '_')
        lines.append(f"async function test_{fn}() {{")
        hdrs = cfg.get("headers", {})
        if hdrs:
            lines.append(f"  const headers = {json.dumps(hdrs)};")
        params = cfg.get("query_params", {})
        if params:
            lines.append(f"  const params = {json.dumps(params)};")
        body = cfg.get("body","").strip()
        if body:
            lines.append(f"  const data = {body};")
        call = "  const resp = await axios.{method}(\n    BASE_URL + ENDPOINT".format(
            method=cfg.get("method","get").lower()
        )
        if hdrs or params or body:
            call += ", {"
            if hdrs:   call += "\n      headers,"
            if params: call += "\n      params,"
            if body:   call += "\n      data,"
            call += "\n    }"
        call += "\n  );"
        lines.append(call)
        exp_status = cfg.get("expected_status",200)
        lines.append(f"  if (resp.status !== {exp_status}) throw new Error('Status esperado {exp_status}, obtido ' + resp.status);")
        exp_body = cfg.get("expected_body","").strip()
        if exp_body:
            lines.append(f"  if (resp.data !== {json.dumps(exp_body)}) throw new Error('Body diferente');")
        for a in cfg.get("assertions", []):
            t,target,exp = a["type"],a["target"],a["expected"]
            if t=="Body Contains":
                lines.append(f"  if (!resp.data.includes({json.dumps(exp)})) throw new Error('Body não contém {exp}');")
            elif t=="Header Equals":
                lines.append(f"  if (resp.headers['{target}'] !== {json.dumps(exp)}) throw new Error('Header {target} != {exp}');")
        lines.append("}")
        lines.append("")
    return "\n".join(lines)

def java_restassured(tests: dict, base_url: str, ctrl_path: str, ep_path: str) -> str:
    lines = [
        "import io.restassured.RestAssured;",
        "import io.restassured.response.Response;",
        "import static org.hamcrest.MatcherAssert.assertThat;",
        "import static org.hamcrest.Matchers.*;",
        "",
        f"RestAssured.baseURI = \"{base_url}\";",
        "",
    ]
    for name, cfg in tests.items():
        fn = name.replace(' ', '_')
        lines.append(f"public void test{fn}() {{")
        method = cfg.get("method","GET").upper()
        url = f"\"{ctrl_path}{ep_path}\""
        call = f"    Response resp = RestAssured.{method.lower()}({url})"
        # headers
        for k,v in cfg.get("headers",{}).items():
            call += f".header(\"{k}\", \"{v}\")"
        # params
        for k,v in cfg.get("query_params",{}).items():
            call += f".queryParam(\"{k}\", \"{v}\")"
        # body
        body = cfg.get("body","").strip()
        if body:
            call += f".body({json.dumps(body)})"
        call += ".when().request();"
        lines.append(call)
        exp_status = cfg.get("expected_status",200)
        lines.append(f"    assertThat(resp.getStatusCode(), equalTo({exp_status}));")
        exp_body = cfg.get("expected_body","").strip()
        if exp_body:
            lines.append(f"    assertThat(resp.getBody().asString(), equalTo({json.dumps(exp_body)}));")
        for a in cfg.get("assertions",[]):
            t,target,exp = a["type"],a["target"],a["expected"]
            if t=="Body Contains":
                lines.append(f"    assertThat(resp.getBody().asString(), containsString({json.dumps(exp)}));")
            elif t=="Header Equals":
                lines.append(f"    assertThat(resp.getHeader(\"{target}\"), equalTo({json.dumps(exp)}));")
        lines.append("}")
        lines.append("")
    return "\n".join(lines)
