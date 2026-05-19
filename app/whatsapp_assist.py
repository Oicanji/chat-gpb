from app.content_prematch import build_structured_context_for_query
from app.tuning_engine import catalog_search_intent
from app.course_detect import resolve_curso_from_messages
from app.ollama_client import StructuredParseError, chat_structured_completion
from app.schemas.whatsapp_assist import (
    WHATSAPP_ASSIST_RESPONSE_SCHEMA,
    WhatsAppAssistRequest,
    WhatsAppMessage,
    build_whatsapp_system_prompt,
    build_whatsapp_user_content,
    format_whatsapp_reply,
)


def _build_search_query(messages: list[WhatsAppMessage]) -> str:
    contact = [m for m in messages if not m.outgoing]
    recent = contact[-3:] if contact else messages[-3:]
    parts = [m.text.strip() for m in recent if m.text.strip()]
    if parts:
        return " ".join(parts)
    return messages[-1].text.strip()


def gather_catalog_context(
    messages: list[WhatsAppMessage],
) -> tuple[str, int | None]:
    query = _build_search_query(messages)
    if not query:
        return "", None

    if not catalog_search_intent(query):
        return "", None

    pseudo = [{"role": "user", "content": query}]
    course_tag = resolve_curso_from_messages(pseudo)
    ctx, expected_rows = build_structured_context_for_query(query, course_tag)
    if not ctx.strip() or "Nenhum trecho relevante" in ctx:
        return "", None
    return ctx, expected_rows


def _normalize_fontes(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        nome = str(item.get("nome", "")).strip()
        referencia = str(item.get("referencia", "")).strip()
        como_usou = str(item.get("como_usou", "")).strip()
        if not nome and not referencia:
            continue
        out.append(
            {
                "nome": nome or "Fonte",
                "referencia": referencia or "-",
                "como_usou": como_usou or "-",
            }
        )
    return out


async def run_whatsapp_assist(body: WhatsAppAssistRequest) -> dict:
    catalog_context, expected_disciplines = gather_catalog_context(body.messages)
    has_catalog = bool(catalog_context.strip())
    user_content = build_whatsapp_user_content(
        body.conversation_title,
        body.messages,
        catalog_context,
        expected_disciplines=expected_disciplines,
    )
    chat_messages = [{"role": "user", "content": user_content}]
    system_prompt = build_whatsapp_system_prompt(
        expected_disciplines,
        has_catalog=has_catalog,
    )

    try:
        result = await chat_structured_completion(
            messages=chat_messages,
            system_prompt=system_prompt,
            response_schema=WHATSAPP_ASSIST_RESPONSE_SCHEMA,
            user_text_for_prematch=_build_search_query(body.messages),
            curso_resolvido=resolve_curso_from_messages(chat_messages),
            inject_context=False,
            format_hint=None,
        )
    except StructuredParseError:
        raise
    except Exception as exc:
        raise StructuredParseError(str(exc)) from exc

    data = result.get("data") or {}
    return {
        "explicacao": str(data.get("explicacao", "")).strip(),
        "resposta_sugerida": format_whatsapp_reply(
            str(data.get("resposta_sugerida", ""))
        ),
        "fontes": _normalize_fontes(data.get("fontes")),
    }
