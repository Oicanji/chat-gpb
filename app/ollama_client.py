import json
from typing import Any

import httpx

from app.config import settings
from app.content_prematch import (
    build_content_prematch,
    build_structured_context_for_query,
)
from app.tools import (
    execute_tool,
    reset_tool_log,
    set_active_curso,
    set_active_query,
    set_active_tags,
    tools_for_ollama,
)
from app.tuning_engine import get_allowed_tools

MAX_TOOL_ROUNDS = 5
CHAT_URL = "/v1/chat/completions"

STRUCTURED_SYSTEM_APPEND = (
    "Responda com um unico objeto JSON que obedece exatamente ao schema. "
    "Use somente as chaves definidas no schema, na mesma estrutura (sem envolver em items, "
    "materias ou outro wrapper a menos que o schema exija). "
    "Sem markdown, sem texto fora do JSON."
)


class StructuredParseError(Exception):
    def __init__(self, detail: str, raw_content: str = "", schema_errors: list[str] | None = None):
        self.detail = detail
        self.raw_content = raw_content
        self.schema_errors = schema_errors or []
        super().__init__(detail)


async def check_ollama() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            r.raise_for_status()
            data = r.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            model_ok = any(
                settings.ollama_model in name or name.startswith(settings.ollama_model)
                for name in models
            )
            return {"reachable": True, "models": models, "model_available": model_ok}
    except Exception as exc:
        return {"reachable": False, "error": str(exc), "models": [], "model_available": False}


def _parse_tool_args(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def _extract_tool_calls(message: dict) -> list[dict]:
    calls: list[dict] = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {})
        calls.append(
            {
                "id": tc.get("id", ""),
                "name": fn.get("name", ""),
                "arguments": _parse_tool_args(fn.get("arguments", {})),
            }
        )
    return calls


def _prematch_rules_injection(user_text: str) -> str | None:
    from app.chat_rules import consultar_rules

    result = consultar_rules(user_text)
    if result.get("instrucao"):
        return (
            "[Regra aplicada automaticamente — horario de aula]\n"
            + result["instrucao"]
        )
    return None


def _recent_user_text(messages: list[dict], limit: int = 4) -> str:
    texts = [
        str(m.get("content", ""))
        for m in messages
        if m.get("role") == "user" and str(m.get("content", "")).strip()
    ]
    if not texts:
        return ""
    return "\n".join(texts[-limit:])


def _horario_direct_reply(user_text: str) -> dict | None:
    from app.chat_rules import consultar_rules

    result = consultar_rules(user_text)
    if result.get("rule_id") == "horario" and result.get("instrucao"):
        link = "https://www.ifsc.edu.br/web/campus-garopaba/horario-de-aula"
        return {
            "message": {
                "role": "assistant",
                "content": (
                    "O horario oficial das aulas esta no site do IFSC Garopaba:\n"
                    f"{link}"
                ),
            },
            "tool_calls": [{"name": "consultar_rules", "args": {"mensagem": user_text}}],
        }
    return None


def _build_ollama_messages(
    messages: list[dict],
    system_prompt: str,
    user_text_for_prematch: str,
    course_tag: str | None,
    extra_system: str | None = None,
    *,
    structured: bool = False,
    inject_catalog_context: bool = False,
) -> list[dict]:
    ollama_messages: list[dict] = [{"role": "system", "content": system_prompt}]
    prematch = _prematch_rules_injection(user_text_for_prematch)
    if prematch:
        ollama_messages.append({"role": "system", "content": prematch})

    if structured and inject_catalog_context:
        doc_context, _expected_rows = build_structured_context_for_query(
            user_text_for_prematch, course_tag
        )
        ollama_messages.append({"role": "system", "content": doc_context})
    else:
        doc_context = build_content_prematch(user_text_for_prematch, course_tag)
        if doc_context:
            ollama_messages.append({"role": "system", "content": doc_context})

    if extra_system:
        ollama_messages.append({"role": "system", "content": extra_system})

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant", "system"):
            ollama_messages.append({"role": role, "content": content})
    return ollama_messages


async def _run_tool_loop(
    client: httpx.AsyncClient,
    ollama_messages: list[dict],
    ollama_tools: list[dict],
) -> tuple[list[dict], list[dict], dict | None]:
    tool_calls_made: list[dict] = []
    if not ollama_tools:
        return ollama_messages, tool_calls_made, None

    for _ in range(MAX_TOOL_ROUNDS):
        payload = {
            "model": settings.ollama_model,
            "messages": ollama_messages,
            "tools": ollama_tools,
            "stream": False,
        }
        response = await client.post(
            f"{settings.ollama_base_url}{CHAT_URL}",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message", {})
        calls = _extract_tool_calls(message)
        if not calls:
            return ollama_messages, tool_calls_made, message
        ollama_messages.append(message)
        for call in calls:
            tool_calls_made.append({"name": call["name"], "args": call["arguments"]})
            result_str = execute_tool(call["name"], call["arguments"])
            ollama_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result_str,
                }
            )
    return ollama_messages, tool_calls_made, None


def _parse_json_content(raw: str, schema: dict | None = None) -> dict:
    from app.json_repair import loads_json_object
    from app.schemas.schema_resolve import normalize_parsed_data

    data = loads_json_object(raw)
    if schema:
        try:
            return normalize_parsed_data(data, schema)
        except ValueError as exc:
            raise StructuredParseError(str(exc)) from exc
    if isinstance(data, dict):
        return data
    raise StructuredParseError("Resposta JSON deve ser um objeto")


async def chat_completion(
    messages: list[dict],
    system_prompt: str,
    user_text_for_prematch: str = "",
    curso_resolvido: str | None = None,
) -> dict:
    reset_tool_log()
    course_tag = curso_resolvido
    if course_tag:
        set_active_tags([course_tag])
    search_query = _recent_user_text(messages) or user_text_for_prematch
    set_active_query(search_query)

    direct = _horario_direct_reply(user_text_for_prematch)
    ollama_status = await check_ollama()
    if not ollama_status.get("model_available"):
        if direct:
            return direct
        return {
            "message": {
                "role": "assistant",
                "content": (
                    f"Modelo '{settings.ollama_model}' nao esta instalado no Ollama. "
                    f"Execute no terminal: ollama pull {settings.ollama_model}"
                ),
            },
            "tool_calls": [],
        }

    allowed = get_allowed_tools(search_query)
    ollama_tools = tools_for_ollama(allowed)

    ollama_messages = _build_ollama_messages(
        messages,
        system_prompt,
        user_text_for_prematch,
        course_tag,
        structured=False,
    )

    tool_calls_made: list[dict] = []

    async with httpx.AsyncClient(timeout=300.0) as client:
        ollama_messages, tool_calls_made, final_message = await _run_tool_loop(
            client, ollama_messages, ollama_tools
        )
        if final_message is None and ollama_tools:
            fallback = direct or {
                "message": {
                    "role": "assistant",
                    "content": "Limite de chamadas de ferramentas atingido. Reformule a pergunta.",
                },
                "tool_calls": tool_calls_made,
            }
            return fallback

        if final_message is None:
            payload = {
                "model": settings.ollama_model,
                "messages": ollama_messages,
                "stream": False,
            }
            response = await client.post(
                f"{settings.ollama_base_url}{CHAT_URL}",
                json=payload,
            )
            response.raise_for_status()
            final_message = (response.json().get("choices") or [{}])[0].get("message", {})

        content = final_message.get("content") or ""
        if not content and direct:
            return direct
        return {
            "message": {"role": "assistant", "content": content},
            "tool_calls": tool_calls_made,
        }


async def chat_structured_completion(
    messages: list[dict],
    system_prompt: str,
    response_schema: dict,
    user_text_for_prematch: str = "",
    curso_resolvido: str | None = None,
    inject_context: bool | None = None,
    format_hint: str | None = None,
) -> dict:
    from app.schemas.schema_resolve import (
        apply_min_items,
        get_root_array_key,
        schema_has_root_object_array,
        should_inject_catalog_context,
        wants_complete_list,
    )
    from app.schemas.structured import validate_instance

    question = _recent_user_text(messages) or user_text_for_prematch
    reset_tool_log()
    course_tag = curso_resolvido
    if course_tag:
        set_active_tags([course_tag])
    set_active_query(question)

    inject_catalog = should_inject_catalog_context(
        response_schema, question, inject_context
    )

    schema_for_ollama = response_schema
    array_key = get_root_array_key(response_schema)
    expected_rows = None
    if inject_catalog:
        _, expected_rows = build_structured_context_for_query(
            question,
            course_tag,
            force_search=inject_context is True,
        )
    if (
        array_key
        and schema_has_root_object_array(response_schema)
        and wants_complete_list(question)
        and expected_rows
    ):
        schema_for_ollama = apply_min_items(
            response_schema, array_key, expected_rows
        )

    ollama_status = await check_ollama()
    if not ollama_status.get("reachable"):
        raise StructuredParseError("Ollama nao esta acessivel")
    if not ollama_status.get("model_available"):
        raise StructuredParseError(
            f"Modelo '{settings.ollama_model}' nao instalado. Execute: ollama pull {settings.ollama_model}"
        )

    schema_hint = json.dumps(schema_for_ollama, ensure_ascii=False)
    extra = f"{STRUCTURED_SYSTEM_APPEND}\n\nJSON Schema da resposta:\n{schema_hint}"
    if format_hint and format_hint.strip():
        extra += (
            "\n\nEstrutura pedida pelo usuario (respeite chaves e aninhamento, ex.: "
            "objeto com array na chave indicada):\n"
            f"{format_hint.strip()}"
        )

    ollama_messages = _build_ollama_messages(
        messages,
        system_prompt,
        user_text_for_prematch,
        course_tag,
        extra_system=extra,
        structured=True,
        inject_catalog_context=inject_catalog,
    )

    allowed = get_allowed_tools(question)
    ollama_tools = tools_for_ollama(allowed)
    tool_calls_made: list[dict] = []

    async with httpx.AsyncClient(timeout=300.0) as client:
        if ollama_tools:
            ollama_messages, tool_calls_made, _ = await _run_tool_loop(
                client, ollama_messages, ollama_tools
            )

        for attempt in range(2):
            if attempt > 0:
                ollama_messages.append(
                    {
                        "role": "system",
                        "content": (
                            "A resposta anterior nao era JSON valido ou nao obedece ao schema. "
                            "Corrija aspas e virgulas (ex.: use 30 e nao 30\" antes de }). "
                            "Devolva somente o objeto JSON."
                        ),
                    }
                )
            payload = {
                "model": settings.ollama_model,
                "messages": ollama_messages,
                "format": schema_for_ollama,
                "stream": False,
            }
            response = await client.post(
                f"{settings.ollama_base_url}{CHAT_URL}",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            raw = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            try:
                parsed = _parse_json_content(raw, schema_for_ollama)
            except (json.JSONDecodeError, StructuredParseError) as exc:
                if attempt == 0:
                    continue
                raise StructuredParseError(
                    "Resposta nao e JSON valido",
                    raw_content=raw,
                ) from exc
            schema_errors = validate_instance(parsed, schema_for_ollama)
            if schema_errors:
                if attempt == 0:
                    continue
                raise StructuredParseError(
                    "JSON fora do schema",
                    raw_content=raw,
                    schema_errors=schema_errors,
                )
            out: dict = {"data": parsed}
            if tool_calls_made:
                out["tool_calls"] = tool_calls_made
            return out

    raise StructuredParseError("Falha ao obter JSON estruturado apos tentativas")
