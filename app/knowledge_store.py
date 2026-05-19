import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.config import settings

MAX_FILE_BYTES = 512 * 1024
ALLOWED_KNOWLEDGE_EXT = {".md", ".txt", ".mdc"}
MAX_KNOWLEDGE_BYTES = 2 * 1024 * 1024
ALLOWED_RULE_EXT = {".yaml", ".yml", ".md"}
VALID_TYPES = frozenset({"knowledge", "rule", "tuning"})


def normalize_type(raw: str) -> str:
    value = raw.strip().lower()
    if value in VALID_TYPES:
        return value
    raise ValueError("type must be knowledge, rule or tuning")


def _item_type(item: dict) -> str:
    return str(item.get("type", ""))


def _item_title(item: dict) -> str:
    return str(item.get("title", ""))


def _public_item(item: dict) -> dict:
    return dict(item)


def item_tags(item: dict) -> list[str]:
    return [str(t) for t in item.get("tags", [])]


def has_tags(item: dict, required: list[str]) -> bool:
    tags = set(item_tags(item))
    return all(t in tags for t in required)


def format_size_mb(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 MB"
    mb = size_bytes / (1024 * 1024)
    if mb < 0.01:
        return f"{mb:.3f} MB"
    return f"{mb:.2f} MB"


def find_item_by_tags(item_type: str, required_tags: list[str]) -> tuple[dict, Path] | None:
    for item in _load_catalog().get("items", []):
        if _item_type(item) != item_type:
            continue
        if not has_tags(item, required_tags):
            continue
        path = _item_path(item)
        if path.is_file():
            return item, path
    return None


def iter_catalog_paths(
    item_type: str | None = None,
    require_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
) -> list[tuple[str, Path]]:
    paths: list[tuple[str, Path]] = []
    for item in _load_catalog().get("items", []):
        if item_type and _item_type(item) != item_type:
            continue
        if require_tags and not has_tags(item, require_tags):
            continue
        if exclude_tags and any(t in item_tags(item) for t in exclude_tags):
            continue
        path = _item_path(item)
        if path.is_file():
            paths.append((item["id"], path))
    return paths


def _assert_editable(item: dict) -> None:
    if item.get("readonly"):
        raise ValueError("Item integrado (somente leitura) nao pode ser alterado ou removido")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text.lower())
    ascii_text = "".join(c for c in norm if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return slug or "item"


def _unique_id(base: str, catalog: dict) -> str:
    existing = {item["id"] for item in catalog.get("items", [])}
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


def ensure_data_dirs() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.knowledge_dir.mkdir(parents=True, exist_ok=True)
    settings.rules_data_dir.mkdir(parents=True, exist_ok=True)
    settings.tuning_dir.mkdir(parents=True, exist_ok=True)
    if not settings.catalog_path.is_file():
        settings.catalog_path.write_text(
            json.dumps({"items": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _load_catalog() -> dict:
    ensure_data_dirs()
    return json.loads(settings.catalog_path.read_text(encoding="utf-8"))


def _save_catalog(catalog: dict) -> None:
    settings.catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _find_item(catalog: dict, item_id: str) -> dict | None:
    for item in catalog.get("items", []):
        if item["id"] == item_id:
            return item
    return None


def _item_path(item: dict) -> Path:
    return settings.data_dir / item["filename"]


def _parse_triggers(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    parts = re.split(r"[,;\n]+", str(raw))
    return [p.strip() for p in parts if p.strip()]


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    meta = yaml.safe_load(text[3:end]) or {}
    body = text[end + 3 :].lstrip("\n")
    return meta if isinstance(meta, dict) else {}, body


def reload_cache() -> None:
    from app import chat_rules

    chat_rules.load_rules()
    from app import knowledge_search

    knowledge_search.invalidate_cache()
    from app.tuning_store import invalidate_tuning_cache

    invalidate_tuning_cache()


def list_items(item_type: str | None = None) -> list[dict]:
    catalog = _load_catalog()
    filter_type = normalize_type(item_type) if item_type else None
    items = []
    for item in catalog.get("items", []):
        if filter_type and _item_type(item) != filter_type:
            continue
        path = _item_path(item)
        enriched = _public_item(item)
        enriched["exists"] = path.is_file()
        if path.is_file():
            size = path.stat().st_size
            enriched["size_bytes"] = size
            enriched["size_mb"] = format_size_mb(size)
            text = path.read_text(encoding="utf-8")
            if _item_type(item) == "tuning":
                try:
                    data = yaml.safe_load(text) or {}
                    kind = data.get("kind", "") if isinstance(data, dict) else ""
                    enriched["kind"] = kind
                    enriched["preview"] = f"kind={kind}" if kind else text.replace("\n", " ")[:80]
                except yaml.YAMLError:
                    enriched["preview"] = text.replace("\n", " ")[:80]
            else:
                preview = text.replace("\n", " ")[:120]
                enriched["preview"] = preview + ("..." if len(text) > 120 else "")
        else:
            enriched["size_bytes"] = 0
            enriched["size_mb"] = "0 MB"
            enriched["preview"] = ""
        items.append(enriched)
    return sorted(items, key=lambda x: x.get("updated_at", ""), reverse=True)


def get_item(item_id: str) -> dict:
    catalog = _load_catalog()
    item = _find_item(catalog, item_id)
    if not item:
        raise KeyError(f"Item nao encontrado: {item_id}")
    path = _item_path(item)
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo ausente: {item['filename']}")
    content = path.read_text(encoding="utf-8")
    return {**_public_item(item), "content": content}


def _write_rule_yaml(
    path: Path,
    item_id: str,
    titulo: str,
    triggers: list[str],
    resposta: str,
) -> None:
    data = {
        "id": item_id,
        "descricao": titulo,
        "triggers": triggers,
        "resposta_obrigatoria": resposta.strip(),
    }
    path.write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _validate_size(content: str) -> None:
    if len(content.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError(f"Arquivo excede {MAX_FILE_BYTES // 1024} KB")


def create_item(
    item_type: str,
    title: str,
    content: str,
    triggers: list[str] | str | None = None,
    tags: list[str] | None = None,
    item_id: str | None = None,
    ext: str = ".md",
) -> dict:
    item_type = normalize_type(item_type)
    if item_type == "tuning":
        from app.tuning_store import parse_tuning_content

        parse_tuning_content(content)
        limit = MAX_FILE_BYTES
    elif item_type == "knowledge":
        limit = MAX_KNOWLEDGE_BYTES
    else:
        limit = MAX_FILE_BYTES
    if len(content.encode("utf-8")) > limit:
        raise ValueError(f"Arquivo excede {limit // 1024} KB")

    catalog = _load_catalog()
    base_id = _slugify(item_id or title)
    new_id = _unique_id(base_id, catalog)
    now = _now_iso()
    tag_list = tags or []

    if item_type == "tuning":
        rel = f"tuning/{new_id}.yaml"
        path = settings.data_dir / rel
        path.write_text(content.strip() + "\n", encoding="utf-8")
        trigger_list = []
    elif item_type == "rule":
        trigger_list = _parse_triggers(triggers)
        if not trigger_list:
            raise ValueError("Rules exigem ao menos um trigger")
        if not content.strip():
            raise ValueError("Rules exigem resposta obrigatoria")
        rel = f"rules/{new_id}.yaml"
        path = settings.data_dir / rel
        _write_rule_yaml(path, new_id, title, trigger_list, content)
    else:
        ext_norm = ext if ext in ALLOWED_KNOWLEDGE_EXT else ".md"
        rel = f"knowledge/{new_id}{ext_norm}"
        path = settings.data_dir / rel
        path.write_text(content, encoding="utf-8")
        trigger_list = []

    entry = {
        "id": new_id,
        "type": item_type,
        "title": title,
        "triggers": trigger_list if item_type == "rule" else [],
        "tags": tag_list,
        "filename": rel,
        "created_at": now,
        "updated_at": now,
    }
    catalog.setdefault("items", []).append(entry)
    _save_catalog(catalog)
    reload_cache()
    return _public_item(entry)


def create_from_upload(
    item_type: str,
    title: str,
    filename: str,
    raw: bytes,
    triggers: list[str] | str | None = None,
    tags: list[str] | None = None,
) -> dict:
    item_type = normalize_type(item_type)
    limit = MAX_KNOWLEDGE_BYTES if item_type == "knowledge" else MAX_FILE_BYTES
    if len(raw) > limit:
        raise ValueError(f"Arquivo excede {limit // 1024} KB")

    ext = Path(filename).suffix.lower()
    text = raw.decode("utf-8")

    if item_type == "tuning":
        if ext not in (".yaml", ".yml"):
            raise ValueError("Tuning: use .yaml")
        from app.tuning_store import parse_tuning_content

        parse_tuning_content(text)
        return create_item(
            item_type="tuning",
            title=title,
            content=text,
            tags=tags,
        )

    if item_type == "rule":
        if ext in (".yaml", ".yml"):
            data = yaml.safe_load(text) or {}
            if not isinstance(data, dict):
                raise ValueError("YAML invalido")
            return create_item(
                item_type="rule",
                title=str(data.get("descricao", title)),
                content=str(data.get("resposta_obrigatoria", "")),
                triggers=data.get("triggers", triggers),
                tags=tags,
                item_id=str(data.get("id", title)),
            )
        meta, body = _parse_frontmatter(text)
        return create_item(
            item_type="rule",
            title=str(meta.get("descricao", title)),
            content=body or str(meta.get("resposta_obrigatoria", "")),
            triggers=meta.get("triggers", triggers),
            tags=tags,
            item_id=str(meta.get("id", title)),
        )

    if ext not in ALLOWED_KNOWLEDGE_EXT:
        raise ValueError("Knowledge: use .md, .txt ou .mdc")
    return create_item(
        item_type="knowledge",
        title=title,
        content=text,
        tags=tags,
        ext=ext,
    )


def update_item(
    item_id: str,
    title: str | None = None,
    content: str | None = None,
    triggers: list[str] | str | None = None,
    tags: list[str] | None = None,
) -> dict:
    catalog = _load_catalog()
    item = _find_item(catalog, item_id)
    if not item:
        raise KeyError(f"Item nao encontrado: {item_id}")
    _assert_editable(item)

    if title is not None:
        item["title"] = title
    if tags is not None:
        item["tags"] = tags

    path = _item_path(item)
    item_type = _item_type(item)

    if item_type == "tuning" and content is not None:
        from app.tuning_store import parse_tuning_content

        parse_tuning_content(content)
        path.write_text(content.strip() + "\n", encoding="utf-8")
    elif item_type == "rule":
        trigger_list = (
            _parse_triggers(triggers) if triggers is not None else item.get("triggers", [])
        )
        if triggers is not None:
            item["triggers"] = trigger_list
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        data = yaml.safe_load(current) or {} if current else {}
        resposta = content if content is not None else str(data.get("resposta_obrigatoria", ""))
        _write_rule_yaml(
            path,
            item_id,
            _item_title(item),
            item["triggers"],
            resposta,
        )
    elif content is not None:
        if len(content.encode("utf-8")) > MAX_KNOWLEDGE_BYTES:
            raise ValueError(f"Arquivo excede {MAX_KNOWLEDGE_BYTES // 1024} KB")
        path.write_text(content, encoding="utf-8")

    item["updated_at"] = _now_iso()
    _save_catalog(catalog)
    reload_cache()
    return _public_item(item)


def delete_item(item_id: str) -> None:
    catalog = _load_catalog()
    item = _find_item(catalog, item_id)
    if not item:
        raise KeyError(f"Item nao encontrado: {item_id}")
    _assert_editable(item)
    path = _item_path(item)
    if path.is_file():
        path.unlink()
    catalog["items"] = [i for i in catalog["items"] if i["id"] != item_id]
    _save_catalog(catalog)
    reload_cache()


def init_store() -> None:
    ensure_data_dirs()
    from app.tuning_seed import ensure_tuning_extras, seed_default_tuning

    seed_default_tuning()
    ensure_tuning_extras()
