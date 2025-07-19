import javalang
from pathlib import Path
from typing import List, Dict, Optional

class JavaControllerParser:
    JAVA_PRIMITIVES = {
        "String": "",
        "CharSequence": "",
        "int": 0,
        "Integer": 0,
        "Long": 0,
        "long": 0,
        "Short": 0,
        "short": 0,
        "float": 0.0,
        "double": 0.0,
        "Float": 0.0,
        "Double": 0.0,
        "boolean": True,
        "Boolean": True
    }

    @staticmethod
    def get_java_type_fields(class_name, project_src_dir, visited=None):
        """
        Busca e gera um dict recursivo com os campos e valores default do DTO.
        project_src_dir: diretório do projeto onde buscar todos os arquivos .java.
        visited: set para evitar recursão infinita.
        """
        visited = visited or set()
        if class_name in visited:
            return {}
        visited.add(class_name)

        # Busca o arquivo do DTO no projeto
        java_file = None
        for p in Path(project_src_dir).rglob(f"{class_name}.java"):
            java_file = p
            break
        if not java_file:
            return {}

        source = java_file.read_text(encoding="utf-8")
        tree = javalang.parse.parse(source)
        dto_cls = next((t for t in tree.types if getattr(t, 'name', None) == class_name), None)
        if not dto_cls:
            return {}

        result = {}
        for field in getattr(dto_cls, 'fields', []):
            for decl in field.declarators:
                name = decl.name
                typ = field.type.name if hasattr(field.type, 'name') else str(field.type)
                # Primitivos
                if typ in JavaControllerParser.JAVA_PRIMITIVES:
                    result[name] = JavaControllerParser.JAVA_PRIMITIVES[typ]
                elif typ == "List":
                    # Tenta descobrir tipo genérico (UserDTO, etc)
                    if field.type.arguments:
                        arg = field.type.arguments[0]
                        gen_typ = arg.type.name if hasattr(arg.type, "name") else str(arg.type)
                        result[name] = [JavaControllerParser.get_java_type_fields(gen_typ, project_src_dir, visited)]
                    else:
                        result[name] = []
                elif typ == "Map":
                    result[name] = {}
                elif typ[0].isupper():
                    # Outro DTO: recursivo
                    result[name] = JavaControllerParser.get_java_type_fields(typ, project_src_dir, visited)
                else:
                    result[name] = None
        return result

    @staticmethod
    def extract_response_type(return_type):
        """
        Extrai o tipo dentro de ResponseEntity<...> ou retorna tipo bruto.
        """
        if return_type.startswith("ResponseEntity<") and return_type.endswith(">"):
            return return_type[len("ResponseEntity<"):-1]
        return return_type

    @staticmethod
    def _extract_required(anno):
        required = True
        if hasattr(anno, 'element') and anno.element:
            elems = anno.element if isinstance(anno.element, list) else [anno.element]
            for pair in elems:
                if getattr(pair, 'name', None) == 'required':
                    val = getattr(pair, 'value', None)
                    if hasattr(val, 'value'):
                        v = str(val.value).lower()
                        if v == "false":
                            required = False
                    elif hasattr(val, 'member'):
                        if str(val.member).lower() == "false":
                            required = False
        return required

    @staticmethod
    def parse(file_path: str) -> Dict[str, object]:
        source = Path(file_path).read_text(encoding='utf-8')
        tree   = javalang.parse.parse(source)

        controllers = [
            t for t in tree.types
            if isinstance(t, javalang.tree.ClassDeclaration)
               and any(a.name in ('RestController','Controller') for a in t.annotations)
        ]
        cls = controllers[0] if controllers else tree.types[0]

        if not controllers:
            raise ValueError(f"No controller found in {file_path}")

        class_prefix = ''
        for anno in cls.annotations:
            if anno.name == 'RequestMapping' and hasattr(anno, 'element') and anno.element:
                element = anno.element
                if isinstance(element, list):
                    for pair in element:
                        if getattr(pair, 'name', None) in ('value', 'path') \
                                and hasattr(pair.value, 'value'):
                            class_prefix = pair.value.value.strip('"')
                            break
                else:
                    if hasattr(element, 'value'):
                        class_prefix = element.value.strip('"')
                    elif hasattr(element, 'member'):
                        class_prefix = element.member

        controller_name = cls.name
        endpoints: List[Dict] = []

        spec_names   = ['GetMapping','PostMapping','PutMapping','PatchMapping','DeleteMapping']
        mapping_names = spec_names + ['RequestMapping']

        for method in cls.methods:
            annots_dict = {a.name: a for a in method.annotations if a.name in mapping_names}
            if not annots_dict:
                continue

            spec_anno = next((annots_dict[n] for n in spec_names if n in annots_dict), None)
            req_anno  = annots_dict.get('RequestMapping')

            if spec_anno:
                http_method = spec_anno.name.replace('Mapping','').upper()
            else:
                override = None
                if req_anno and hasattr(req_anno,'element') and req_anno.element:
                    elems = req_anno.element if isinstance(req_anno.element,list) else [req_anno.element]
                    for pair in elems:
                        if getattr(pair,'name',None) == 'method':
                            val = pair.value
                            override = getattr(val,'member',None) or getattr(val,'value',None)
                            break
                http_method = override.upper() if override else 'GET'

            path = ''

            def _extract_path(anno):
                """
                Retorna o valor de 'value' ou 'path' se for uma NormalAnnotation,
                ou o texto da Literal/MemberReference em SingleMemberAnnotation.
                """
                if not hasattr(anno, 'element') or anno.element is None:
                    return ''
                if isinstance(anno.element, list):
                    for pair in anno.element:
                        name = getattr(pair, 'name', None)
                        val = getattr(pair, 'value', None)
                        if name in ('value', 'path') and hasattr(val, 'value'):
                            return val.value.strip('"')
                else:
                    el = anno.element
                    if hasattr(el, 'value'):
                        return el.value.strip('"')
                    if hasattr(el, 'member'):
                        return el.member
                return ''

            if spec_anno:
                path = _extract_path(spec_anno)

            if not path and req_anno:
                path = _extract_path(req_anno)

            query_params:   List[str] = []
            path_vars:      List[str] = []
            request_body_type: Optional[str] = None
            request_body_required = False

            return_type = None
            if hasattr(method, "return_type") and method.return_type is not None:
                if hasattr(method.return_type, "name"):
                    return_type = method.return_type.name
                    # Se for genérico (ex: ResponseEntity<UserDTO>)
                    if hasattr(method.return_type, "arguments") and method.return_type.arguments:
                        args = method.return_type.arguments
                        # Só trata 1 argumento (ResponseEntity<UserDTO>)
                        if args and hasattr(args[0], "type") and hasattr(args[0].type, "name"):
                            return_type += "<" + args[0].type.name + ">"

            for param in method.parameters:
                for pann in param.annotations:
                    if pann.name == 'RequestParam':
                        name = param.name
                        if hasattr(pann,'element') and pann.element:
                            elems = pann.element if isinstance(pann.element,list) else [pann.element]
                            for pair in elems:
                                if getattr(pair,'name',None) in ('value','name') \
                                   and hasattr(pair.value,'value'):
                                    name = pair.value.value.strip('"')
                                    break
                        required = JavaControllerParser._extract_required(pann)
                        query_params.append({"name": name, "required": required})

                    elif pann.name == 'PathVariable':
                        name = param.name
                        if hasattr(pann,'element') and pann.element:
                            elems = pann.element if isinstance(pann.element,list) else [pann.element]
                            for pair in elems:
                                if getattr(pair,'name',None) in ('value','name') \
                                   and hasattr(pair.value,'value'):
                                    name = pair.value.value.strip('"')
                                    break

                        required = JavaControllerParser._extract_required(pann)
                        path_vars.append({"name": name, "required": required})

                    elif pann.name == 'RequestBody':
                        request_body_type = getattr(param.type, 'name', None)
                        required = JavaControllerParser._extract_required(pann)
                        request_body_required = required

            endpoints.append({
                'name': method.name,
                'path': path,
                'http_method': http_method,
                'query_params': query_params,
                'path_variables': path_vars,
                'request_body_type': request_body_type,
                'body_required': request_body_required,
                'return_type': return_type
            })

        return {
            'controller_name': controller_name,
            'class_prefix':    class_prefix,
            'endpoints':       endpoints
        }
