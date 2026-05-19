import json
import re
from typing import Any

from jsonschema import Draft202012Validator

FIELD_RE = re.compile(
    r'"([^"]+)"\s*:\s*"([^"]*)"',
    re.MULTILINE,
)
ARRAY_WRAPPER_RE = re.compile(r'"([^"]+)"\s*:\s*\[', re.IGNORECASE)


def _infer_json_type(hint: str) -> dict[str, Any]:
    h = hint.lower().strip()
    if re.search(r"\bint\b|\binteger\b", h):
        return {"type": "integer"}
    if re.search(r"\bnumber\b|\bfloat\b|\bdouble\b", h):
        return {"type": "number"}
    if re.search(r"\bbool", h):
        return {"type": "boolean"}
    if re.search(r"\barray\b", h):
        return {"type": "array", "items": {"type": "string"}}
    return {"type": "string"}


def _explicit_array_key(text: str) -> str | None:
    m = ARRAY_WRAPPER_RE.search(text)
    return m.group(1) if m else None


def _format_requests_array(text: str) -> bool:
    if _explicit_array_key(text):
        return True
    t = text.strip()
    if "..." in t or "…" in t:
        return True
    if re.search(r"\{\s*\[", t, re.DOTALL):
        return True
    return False


def _guess_array_key(text: str) -> str:
    explicit = _explicit_array_key(text)
    if explicit:
        return explicit
    t = text.lower()
    if any(w in t for w in ("materia", "disciplina", "unidade curricular", "uc ")):
        return "materias"
    return "items"


def _object_schema(
    properties: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
    Draft202012Validator.check_schema(schema)
    return schema


def ensure_object_schema(schema: dict[str, Any]) -> dict[str, Any]:
    if schema.get("type") == "object":
        Draft202012Validator.check_schema(schema)
        return schema
    if schema.get("type") == "array":
        wrapped = {
            "type": "object",
            "properties": {"items": schema},
            "required": ["items"],
            "additionalProperties": False,
        }
        Draft202012Validator.check_schema(wrapped)
        return wrapped
    raise ValueError("response_schema deve ser type object ou array (lista de itens)")


def parse_informal_format(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("output_format vazio")

    if text.startswith("{"):
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                if obj.get("type") in ("object", "array") or "properties" in obj:
                    return ensure_object_schema(obj)
        except json.JSONDecodeError:
            pass

    fields = FIELD_RE.findall(text)
    if not fields:
        raise ValueError(
            "Formato informal nao reconhecido. Use chaves como "
            '"campo": "string, descricao" dentro de { ... }'
        )

    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, hint in fields:
        properties[name] = _infer_json_type(hint)
        required.append(name)

    item_schema = _object_schema(properties, required)

    if _format_requests_array(text):
        array_key = _guess_array_key(text)
        return _object_schema(
            {array_key: {"type": "array", "items": item_schema}},
            [array_key],
        )

    return item_schema


def split_question_and_format(content: str) -> tuple[str, str | None]:
    for i, ch in enumerate(content):
        if ch != "{" or i == 0:
            continue
        before = content[:i].strip()
        fmt = content[i:].strip()
        if before and '"' in fmt:
            return before, fmt
    return content.strip(), None


def resolve_structured_schema(
    messages: list[dict],
    response_schema: dict[str, Any] | None,
    output_format: str | None,
) -> tuple[dict[str, Any], list[dict], str | None]:
    fmt_text = (output_format or "").strip() or None
    msgs = [dict(m) for m in messages]

    if not response_schema and not fmt_text:
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i].get("role") != "user":
                continue
            question, embedded = split_question_and_format(
                str(msgs[i].get("content", ""))
            )
            if embedded:
                fmt_text = embedded
                msgs[i] = {**msgs[i], "content": question}
            break

    if response_schema is not None:
        return ensure_object_schema(response_schema), msgs, fmt_text

    if fmt_text:
        return parse_informal_format(fmt_text), msgs, fmt_text

    raise ValueError(
        "Informe response_schema (JSON Schema), output_format (texto informal) "
        "ou inclua o bloco { ... } com campos na mensagem do usuario"
    )


def get_root_array_key(schema: dict[str, Any]) -> str | None:
    props = schema.get("properties") or {}
    for key, prop in props.items():
        if isinstance(prop, dict) and prop.get("type") == "array":
            return key
    return None


def schema_item_properties(schema: dict[str, Any]) -> set[str]:
    key = get_root_array_key(schema)
    if not key:
        return set()
    items = (schema.get("properties") or {}).get(key, {}).get("items", {})
    if not isinstance(items, dict):
        return set()
    return set((items.get("properties") or {}).keys())


def schema_expects_materias(schema: dict[str, Any]) -> bool:
    key = get_root_array_key(schema)
    if key != "materias":
        return False
    props = schema_item_properties(schema)
    return "nome" in props and "sigla" in props and "horas" in props


def schema_has_root_object_array(schema: dict[str, Any]) -> bool:
    key = get_root_array_key(schema)
    if not key:
        return False
    items = (schema.get("properties") or {}).get(key, {}).get("items", {})
    return isinstance(items, dict) and items.get("type") == "object"


def should_inject_catalog_context(
    schema: dict[str, Any],
    question: str,
    inject_context: bool | None,
) -> bool:
    if inject_context is False:
        return False
    if inject_context is True:
        return True
    from app.tuning_engine import get_search_profile

    if get_search_profile(question):
        return True
    if schema_has_root_object_array(schema) and wants_complete_list(question):
        return True
    return schema_expects_materias(schema)


def apply_min_items(schema: dict[str, Any], array_key: str, count: int) -> dict[str, Any]:
    import copy

    out = copy.deepcopy(schema)
    prop = out.get("properties", {}).get(array_key)
    if isinstance(prop, dict) and count > 0:
        prop["minItems"] = count
    return out


def wants_complete_list(question: str) -> bool:
    t = question.lower()
    return any(
        w in t
        for w in (
            "todas",
            "todos",
            "lista",
            "listar",
            "quais materias",
            "quais matérias",
            "me de todas",
            "me dê todas",
        )
    )


def normalize_parsed_data(parsed: Any, schema: dict[str, Any]) -> dict[str, Any]:
    array_key = get_root_array_key(schema)
    item_fields = schema_item_properties(schema)

    if isinstance(parsed, dict):
        if array_key and array_key not in parsed and item_fields:
            keys = set(parsed.keys())
            if keys and keys <= item_fields:
                return {array_key: [parsed]}
        return parsed

    if isinstance(parsed, list):
        if array_key:
            return {array_key: parsed}
        array_keys = [
            k
            for k, v in (schema.get("properties") or {}).items()
            if isinstance(v, dict) and v.get("type") == "array"
        ]
        if len(array_keys) == 1:
            return {array_keys[0]: parsed}
        raise ValueError(
            "Resposta deve ser um objeto com as chaves do schema, nao uma lista solta"
        )

    raise ValueError("Resposta JSON deve ser objeto ou lista")


def get_materias_array_key(schema: dict[str, Any]) -> str | None:
    return get_root_array_key(schema)
