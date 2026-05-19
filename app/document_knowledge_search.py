from app.document_search import search_document
from app.knowledge_store import _load_catalog, _item_path, _item_type, has_tags, item_tags


def _item_matches_tags_any(item: dict, tags_any: list[str] | None) -> bool:
    if not tags_any:
        return True
    tags = set(item_tags(item))
    return any(t in tags for t in tags_any)


def buscar_documento(
    consulta: str,
    tags_any: list[str] | None = None,
    tags_all: list[str] | None = None,
    max_sections: int = 2,
    excerpt: str = "auto",
) -> dict:
    if not consulta.strip():
        return {"erro": "consulta vazia", "trechos": []}

    merged: list[dict] = []
    docs_consultados: list[str] = []

    for item in _load_catalog().get("items", []):
        if _item_type(item) != "knowledge":
            continue
        if tags_all and not has_tags(item, tags_all):
            continue
        if not _item_matches_tags_any(item, tags_any):
            continue

        path = _item_path(item)
        if not path.is_file():
            continue

        tags = item_tags(item)
        result = search_document(
            path,
            consulta,
            scope_tags=tags,
            doc_id=item["id"],
            max_sections=max_sections,
            excerpt=excerpt,
        )
        docs_consultados.append(item["id"])
        for t in result.get("trechos") or []:
            row = dict(t)
            row["documento_id"] = item["id"]
            row["documento_tags"] = tags
            merged.append(row)

    merged.sort(key=lambda x: int(x.get("pontuacao", 0)), reverse=True)
    cap = max(max_sections * 3, 4)
    return {
        "documentos": docs_consultados,
        "trechos": merged[:cap],
    }
