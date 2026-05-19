from app.knowledge_store import _load_catalog, _item_path, _item_type, item_tags
from app.structured_context import build_structured_context
from app.tuning_engine import catalog_search_intent, get_search_profile, should_auto_search


def _resolve_search_tags(
    course_tag: str | None,
    profile,
) -> tuple[list[str] | None, list[str] | None]:
    if profile and profile.scope_tags_any:
        if course_tag:
            tags_all = list(dict.fromkeys([*profile.scope_tags_any, "ppc", course_tag]))
            return None, tags_all
        return list(profile.scope_tags_any), None
    if course_tag:
        return None, ["ppc", course_tag]
    return None, None


def build_structured_context_for_query(
    user_text: str,
    course_tag: str | None,
    *,
    force_search: bool = False,
) -> tuple[str, int | None]:
    profile = get_search_profile(user_text)
    tags_any, tags_all = _resolve_search_tags(course_tag, profile)
    return build_structured_context(
        user_text,
        course_tag,
        tags_any=tags_any,
        tags_all=tags_all,
        force_search=force_search,
    )


def build_content_prematch(user_text: str, course_tag: str | None) -> str | None:
    if not should_auto_search(user_text, None):
        return None

    profile = get_search_profile(user_text)
    max_sections = 1
    excerpt = "auto"
    if profile:
        max_sections = min(profile.max_sections, 3)
        excerpt = profile.excerpt or "auto"

    best_block: tuple[int, str, str] | None = None

    for item in _load_catalog().get("items", []):
        if _item_type(item) != "knowledge":
            continue
        tags = item_tags(item)
        if course_tag and course_tag not in tags and "ppc" in tags:
            continue
        if not should_auto_search(user_text, tags):
            continue

        path = _item_path(item)
        if not path.is_file():
            continue

        from app.document_search import search_document

        result = search_document(
            path,
            user_text,
            scope_tags=tags,
            doc_id=item["id"],
            max_sections=max_sections,
            excerpt=excerpt,
        )
        trechos = result.get("trechos") or []
        if not trechos:
            continue

        t = trechos[0]
        score = int(t.get("pontuacao", 0))
        titulo = t.get("titulo") or item.get("title", item["id"])
        texto = t.get("texto", "")
        if best_block is None or score > best_block[0]:
            best_block = (score, titulo, texto)

    if not best_block:
        return (
            "[Busca automatica em documentos]\n"
            "Nenhum trecho relevante encontrado. Nao invente bibliografia nem materiais."
        )

    _score, titulo, texto = best_block
    return (
        "[Trechos do catalogo — use APENAS o texto abaixo. "
        f"Referencia: {titulo}. "
        "Nao troque por outra disciplina. Nao invente livros.]\n\n"
        f"### {titulo}\n\n{texto}"
    )
