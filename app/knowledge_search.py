from pathlib import Path

from app.document_search import search_document
from app.knowledge_store import (
    _find_item,
    _item_path,
    _load_catalog,
    iter_catalog_paths,
    item_tags,
)

_file_cache: list[tuple[str, str, Path, list[str]]] | None = None


def invalidate_cache() -> None:
    global _file_cache
    _file_cache = None


def _collect_files() -> list[tuple[str, str, Path, list[str]]]:
    global _file_cache
    if _file_cache is not None:
        return _file_cache

    catalog = _load_catalog()
    files: list[tuple[str, str, Path, list[str]]] = []
    for item_id, path in iter_catalog_paths(
        "knowledge",
        exclude_tags=["ppc", "curso"],
    ):
        item = _find_item(catalog, item_id)
        tags = item_tags(item) if item else []
        files.append((item_id, path.name, path, tags))

    _file_cache = files
    return files


def search_knowledge(query: str) -> dict:
    files = _collect_files()
    if not files:
        return {"query": query, "total_arquivos": 0, "trechos": []}

    all_snippets: list[dict] = []
    for item_id, filename, path, tags in files:
        result = search_document(path, query, scope_tags=tags, doc_id=item_id)
        for t in result.get("trechos", []):
            all_snippets.append(
                {
                    "id": item_id,
                    "arquivo": filename,
                    "titulo": t.get("titulo", ""),
                    "linha_inicio": t["linha_inicio"],
                    "linha_fim": t["linha_fim"],
                    "texto": t["texto"],
                }
            )

    all_snippets.sort(key=lambda x: (-len(x.get("texto", "")), x["id"]))
    return {
        "query": query,
        "total_arquivos": len(files),
        "trechos": all_snippets[:8],
    }
