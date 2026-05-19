from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.knowledge_store import _load_catalog, _item_path, _item_type, item_tags

VALID_KINDS = frozenset(
    {
        "stopword",
        "expand_tokens",
        "alias",
        "course_signal",
        "auto_search",
        "section_header",
        "search_profile",
        "tool_policy",
    }
)

_cache: list[TuningRule] | None = None


@dataclass
class TuningScope:
    mode: str = "global"
    tags_any: list[str] = field(default_factory=list)
    tags_all: list[str] = field(default_factory=list)


@dataclass
class TuningRule:
    id: str
    title: str
    kind: str
    enabled: bool
    priority: int
    scope: TuningScope
    values: list[str] = field(default_factory=list)
    when_any: list[str] = field(default_factory=list)
    add: list[str] = field(default_factory=list)
    phrase: str = ""
    target: str = ""
    weight: int = 1
    pattern: str = ""
    max_sections: int | None = None
    excerpt: str = ""
    tools: list[str] = field(default_factory=list)
    readonly: bool = False


def _parse_scope(raw: dict | None) -> TuningScope:
    if not raw:
        return TuningScope()
    return TuningScope(
        mode=str(raw.get("mode", "global")),
        tags_any=[str(t) for t in raw.get("tags_any", [])],
        tags_all=[str(t) for t in raw.get("tags_all", [])],
    )


def _parse_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        parts = re.split(r"[,;\n]+", raw)
        return [p.strip() for p in parts if p.strip()]
    return []


def _parse_rule(item: dict, data: dict) -> TuningRule:
    kind = str(data.get("kind", "")).strip().lower()
    if kind not in VALID_KINDS:
        raise ValueError(f"kind invalido: {kind}")
    return TuningRule(
        id=item["id"],
        title=item.get("title", item["id"]),
        kind=kind,
        enabled=bool(data.get("enabled", True)),
        priority=int(data.get("priority", 100)),
        scope=_parse_scope(data.get("scope")),
        values=_parse_list(data.get("values")),
        when_any=_parse_list(data.get("when_any")),
        add=_parse_list(data.get("add")),
        phrase=str(data.get("phrase", "")).strip(),
        target=str(data.get("target", "")).strip().lower(),
        weight=int(data.get("weight", 1)),
        pattern=str(data.get("pattern", "")).strip(),
        max_sections=int(data["max_sections"]) if data.get("max_sections") is not None else None,
        excerpt=str(data.get("excerpt", "")).strip().lower(),
        tools=_parse_list(data.get("tools")),
        readonly=bool(item.get("readonly")),
    )


def scope_matches(rule: TuningRule, doc_tags: list[str] | None) -> bool:
    if rule.scope.mode == "global" or not rule.scope.tags_any and not rule.scope.tags_all:
        return True
    tags = set(doc_tags or [])
    if rule.scope.tags_all and not all(t in tags for t in rule.scope.tags_all):
        return False
    if rule.scope.tags_any and not any(t in tags for t in rule.scope.tags_any):
        return False
    return True


def load_rules(force: bool = False) -> list[TuningRule]:
    global _cache
    if _cache is not None and not force:
        return _cache

    rules: list[TuningRule] = []
    for item in _load_catalog().get("items", []):
        if _item_type(item) != "tuning":
            continue
        path = _item_path(item)
        if not path.is_file():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            continue
        try:
            rules.append(_parse_rule(item, data))
        except ValueError:
            continue

    rules.sort(key=lambda r: (r.priority, r.id))
    _cache = rules
    return rules


def invalidate_tuning_cache() -> None:
    global _cache
    _cache = None


def build_tuning_yaml(
    kind: str,
    enabled: bool = True,
    priority: int = 100,
    scope_mode: str = "global",
    scope_tags_any: list[str] | None = None,
    scope_tags_all: list[str] | None = None,
    values: list[str] | None = None,
    when_any: list[str] | None = None,
    add: list[str] | None = None,
    phrase: str = "",
    target: str = "",
    weight: int = 1,
    pattern: str = "",
    max_sections: int | None = None,
    excerpt: str = "",
    tools: list[str] | None = None,
) -> str:
    if kind not in VALID_KINDS:
        raise ValueError(f"kind invalido: {kind}")
    data: dict[str, Any] = {
        "kind": kind,
        "enabled": enabled,
        "priority": priority,
        "scope": {
            "mode": scope_mode,
            "tags_any": scope_tags_any or [],
            "tags_all": scope_tags_all or [],
        },
    }
    if values:
        data["values"] = values
    if when_any:
        data["when_any"] = when_any
    if add:
        data["add"] = add
    if phrase:
        data["phrase"] = phrase
    if target:
        data["target"] = target
    if weight != 1:
        data["weight"] = weight
    if pattern:
        data["pattern"] = pattern
    if max_sections is not None:
        data["max_sections"] = max_sections
    if excerpt:
        data["excerpt"] = excerpt
    if tools:
        data["tools"] = tools
    return yaml.dump(data, allow_unicode=True, sort_keys=False)


def field_to_list(raw: str | list[str] | None) -> list[str]:
    return _parse_list(raw)


def parse_tuning_content(content: str) -> dict:
    data = yaml.safe_load(content) or {}
    if not isinstance(data, dict):
        raise ValueError("YAML de tuning invalido")
    kind = str(data.get("kind", "")).lower()
    if kind not in VALID_KINDS:
        raise ValueError(f"kind deve ser um de: {', '.join(sorted(VALID_KINDS))}")
    return data
