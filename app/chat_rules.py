import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.knowledge_store import iter_catalog_paths


@dataclass
class ChatRule:
    id: str
    descricao: str
    triggers: list[str]
    resposta_obrigatoria: str


_rules: list[ChatRule] | None = None


def _normalize(text: str) -> str:
    lowered = text.lower()
    nfkd = unicodedata.normalize("NFKD", lowered)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _load_rule_file(rule_id: str, path: Path) -> ChatRule | None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data or "id" not in data:
        return None
    return ChatRule(
        id=str(data["id"]),
        descricao=str(data.get("descricao", "")),
        triggers=[str(t) for t in data.get("triggers", [])],
        resposta_obrigatoria=str(data.get("resposta_obrigatoria", "")).strip(),
    )


def load_rules() -> list[ChatRule]:
    global _rules
    loaded: list[ChatRule] = []
    for rule_id, path in iter_catalog_paths("rule"):
        rule = _load_rule_file(rule_id, path)
        if rule:
            loaded.append(rule)
    _rules = loaded
    return loaded


def get_rules() -> list[ChatRule]:
    if _rules is None:
        return load_rules()
    return _rules


def match_rules(mensagem: str) -> list[ChatRule]:
    norm_msg = _normalize(mensagem)
    matched: list[ChatRule] = []
    for rule in get_rules():
        for trigger in rule.triggers:
            if _normalize(trigger) in norm_msg:
                matched.append(rule)
                break
    return matched


def consultar_rules(mensagem: str) -> dict:
    matched = match_rules(mensagem)
    if not matched:
        return {"rule_id": None, "instrucao": None, "rules": []}

    primary = matched[0]
    return {
        "rule_id": primary.id,
        "instrucao": primary.resposta_obrigatoria,
        "rules": [{"id": r.id, "descricao": r.descricao} for r in matched],
    }
