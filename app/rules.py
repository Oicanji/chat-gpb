from app.knowledge_store import find_item_by_tags
from app.prompts import TOOL_INSTRUCTIONS


def _strip_mdc_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3 :].lstrip("\n")
    return text


def _read_course_context(course_tag: str) -> str:
    found = find_item_by_tags("knowledge", ["curso", course_tag])
    if not found:
        return ""
    _item, path = found
    return _strip_mdc_frontmatter(path.read_text(encoding="utf-8")).strip()


def build_system_prompt(
    course_tag: str | None = None,
    *,
    structured: bool = False,
    inject_course_context: bool = False,
) -> str:
    if structured:
        parts = [
            "Assistente Chat GPB IFSC Garopaba.",
            "Siga a tarefa na mensagem do usuario e o JSON Schema fornecido.",
        ]
        if inject_course_context and course_tag:
            ctx = _read_course_context(course_tag)
            if ctx:
                parts.extend(["", f"## Contexto (tag {course_tag})", ctx[:4000]])
        return "\n".join(parts)

    parts = [
        "Voce e o assistente Chat GPB do IFSC Garopaba.",
        "Nunca pergunte ao usuario para escolher ou confirmar curso.",
        "",
    ]

    if course_tag:
        ctx = _read_course_context(course_tag)
        parts.extend(
            [
                f"Contexto preferencial: documentos com tag de curso '{course_tag}'.",
                "",
                "## Contexto do curso",
                ctx or f"(nenhum documento com tags curso + {course_tag} no catalogo)",
            ]
        )
    else:
        parts.extend(
            [
                "Perguntas sobre campus (horario, links): priorize consultar_rules.",
                "Perguntas curriculares: use buscar_documento com a pergunta completa do usuario.",
            ]
        )

    parts.extend(["", TOOL_INSTRUCTIONS.strip()])
    return "\n".join(parts)
