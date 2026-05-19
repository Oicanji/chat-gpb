from app.document_knowledge_search import buscar_documento


def buscar_ppc(
    curso_tag: str,
    consulta: str,
    max_sections: int = 2,
    excerpt: str = "auto",
) -> dict:
    tags_all = ["ppc"]
    if curso_tag:
        tags_all.append(curso_tag)
    result = buscar_documento(
        consulta,
        tags_any=None,
        tags_all=tags_all,
        max_sections=max_sections,
        excerpt=excerpt,
    )
    if curso_tag:
        result["tag_curso"] = curso_tag
    return result
