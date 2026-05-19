import json

from app import chat_rules, knowledge_search
from app.document_knowledge_search import buscar_documento

TOOL_BUSCAR_DOCUMENTO = {
    "type": "function",
    "function": {
        "name": "buscar_documento",
        "description": (
            "Busca trechos em documentos do catalogo (PPC, material). "
            "Opcional: filtrar por tags do item no catalogo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "consulta": {
                    "type": "string",
                    "description": "Termos de busca (pergunta completa do usuario)",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags do catalogo para filtrar documentos (ex.: ppc, sistemas)",
                },
            },
            "required": ["consulta"],
        },
    },
}

TOOL_SEARCH_KNOWLEDGE = {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": "Busca trechos em conhecimentos cadastrados pelo professor (nao e PPC oficial).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Termos para buscar na base de conhecimentos",
                },
            },
            "required": ["query"],
        },
    },
}

TOOL_CONSULTAR_RULES = {
    "type": "function",
    "function": {
        "name": "consultar_rules",
        "description": "Consulta regras operacionais (ex.: horario de aula com link oficial).",
        "parameters": {
            "type": "object",
            "properties": {
                "mensagem": {"type": "string"},
            },
            "required": ["mensagem"],
        },
    },
}

TOOL_REGISTRY: dict[str, dict] = {
    "buscar_documento": TOOL_BUSCAR_DOCUMENTO,
    "buscar_ppc": TOOL_BUSCAR_DOCUMENTO,
    "search_knowledge": TOOL_SEARCH_KNOWLEDGE,
    "consultar_rules": TOOL_CONSULTAR_RULES,
}

OLLAMA_TOOLS = [
    TOOL_BUSCAR_DOCUMENTO,
    TOOL_SEARCH_KNOWLEDGE,
    TOOL_CONSULTAR_RULES,
]


def tools_for_ollama(allowed: set[str] | None) -> list[dict]:
    if not allowed:
        return []
    seen: set[str] = set()
    out: list[dict] = []
    for name in allowed:
        key = name.strip().lower()
        if key == "buscar_ppc":
            key = "buscar_documento"
        if key in seen or key not in TOOL_REGISTRY:
            continue
        seen.add(key)
        out.append(TOOL_REGISTRY[key])
    return out


_TOOL_LOG: list[dict] = []
_ACTIVE_TAGS: list[str] = []
_ACTIVE_QUERY: str | None = None


def reset_tool_log() -> None:
    _TOOL_LOG.clear()


def get_tool_log() -> list[dict]:
    return list(_TOOL_LOG)


def set_active_tags(tags: list[str] | None) -> None:
    global _ACTIVE_TAGS
    _ACTIVE_TAGS = [t.strip().lower() for t in (tags or []) if t.strip()]


def set_active_curso(curso: str | None) -> None:
    if curso:
        set_active_tags([curso])


def set_active_query(query: str | None) -> None:
    global _ACTIVE_QUERY
    _ACTIVE_QUERY = query.strip() if query and query.strip() else None


def execute_tool(name: str, arguments: dict) -> str:
    tool_name = name.strip().lower()
    if tool_name == "buscar_ppc":
        tool_name = "buscar_documento"

    if tool_name == "buscar_documento":
        consulta = _ACTIVE_QUERY or arguments.get("consulta", "")
        if _ACTIVE_QUERY:
            arguments = {**arguments, "consulta": _ACTIVE_QUERY}
        arg_tags = arguments.get("tags") or []
        if isinstance(arg_tags, str):
            arg_tags = [arg_tags]
        tags = list(dict.fromkeys([*_ACTIVE_TAGS, *[str(t).lower() for t in arg_tags]]))
        tags_any = tags if tags else None
        tags_all = None
        if tags and "ppc" in tags:
            tags_all = tags
            tags_any = None
        from app.tuning_engine import get_search_profile

        profile = get_search_profile(consulta)
        max_sections = profile.max_sections if profile else 2
        excerpt = profile.excerpt if profile else "auto"
        result = buscar_documento(
            consulta,
            tags_any=tags_any,
            tags_all=tags_all,
            max_sections=max_sections,
            excerpt=excerpt,
        )
    elif tool_name == "search_knowledge":
        query = _ACTIVE_QUERY or arguments.get("query", "")
        result = knowledge_search.search_knowledge(query)
    elif tool_name == "consultar_rules":
        result = chat_rules.consultar_rules(arguments.get("mensagem", ""))
    else:
        result = {"erro": f"tool desconhecida: {name}"}

    _TOOL_LOG.append({"name": name, "args": arguments, "result": result})
    return json.dumps(result, ensure_ascii=False)
