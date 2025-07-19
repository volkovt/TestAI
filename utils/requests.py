import shlex
import re
import base64

def parse_curl(curl_command: str) -> dict:
    """
    Converte um comando curl em dict contendo:
      - method: GET, POST, etc.
      - url: URL a ser chamada
      - headers: dict de cabeçalhos
      - data: corpo da requisição (string)
    Suporta:
      • line continuations com \\
      • aspas simples e duplas
      • -X / --request
      • -H / --header
      • -d / --data, --data-raw, --data-binary
      • --url
      • parâmetros posicionais de URL
    """
    # 1) Normalize line-continuations
    cmd = re.sub(r'\\\s*\n', ' ', curl_command).strip()
    # 2) Tokeniza respeitando aspas
    tokens = shlex.split(cmd)
    # 3) Remove “curl” inicial, se presente
    if tokens and tokens[0] == 'curl':
        tokens = tokens[1:]

    method  = 'GET'
    url     = ''
    headers = {}
    data    = ''

    it = iter(tokens)
    for token in it:
        # METHOD
        if token in ('-X', '--request'):
            try:
                method = next(it).upper()
            except StopIteration:
                pass
        elif token.startswith('-X'):
            method = token[2:].upper()
        elif token.startswith('--request='):
            method = token.split('=', 1)[1].upper()

        # HEADER
        elif token in ('-H', '--header'):
            try:
                h = next(it)
            except StopIteration:
                continue
            if ':' in h:
                k, v = h.split(':', 1)
                headers[k.strip()] = v.strip()
        elif token.startswith('-H'):
            h = token[2:].lstrip('=')
            if ':' in h:
                k, v = h.split(':', 1)
                headers[k.strip()] = v.strip()
        elif token.startswith('--header='):
            h = token.split('=', 1)[1]
            if ':' in h:
                k, v = h.split(':', 1)
                headers[k.strip()] = v.strip()

        # DATA / BODY
        elif token in ('-d', '--data', '--data-raw', '--data-binary', '--data-ascii'):
            try:
                data = next(it)
            except StopIteration:
                pass
        elif token.startswith('-d'):
            data = token[2:].lstrip('=')
        elif token.startswith('--data='):
            data = token.split('=', 1)[1]
        elif token.startswith('--data-raw='):
            data = token.split('=', 1)[1]
        elif token.startswith('--data-binary='):
            data = token.split('=', 1)[1]
        elif token.startswith('--data-ascii='):
            data = token.split('=', 1)[1]

        # URL explicita
        elif token in ('--url',):
            try:
                url = next(it)
            except StopIteration:
                pass
        elif token.startswith('--url='):
            url = token.split('=', 1)[1]

        # CREDENCIAIS (ex. -u user:pass)
        elif token in ('-u', '--user'):
            try:
                creds = next(it)
                basic = base64.b64encode(creds.encode()).decode()
                headers['Authorization'] = f'Basic {basic}'
            except StopIteration:
                pass

        # QUALQUER OUTRO NÃO-FLAG → URL
        elif not token.startswith('-') and not url:
            url = token

    return {
        'method':  method,
        'url':     url,
        'headers': headers,
        'data':    data,
    }

def join_url(*parts):
    """
    Concatena pedaços de URL garantindo apenas uma barra entre eles.
    Preserva o http(s):// corretamente.
    """
    new_parts = []
    for i, p in enumerate(parts):
        if not p:
            continue
        p = str(p)
        if i != 0:
            p = p.lstrip("/")
        if i != len(parts) - 1:
            p = p.rstrip("/")
        new_parts.append(p)
    if not new_parts:
        return ""
    url = "/".join(new_parts)
    return url

