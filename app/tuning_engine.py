import re
from dataclasses import dataclass

from app.text_utils import normalize
from app.tuning_store import TuningRule, load_rules, scope_matches


@dataclass
class SearchProfile:
    max_sections: int = 2
    excerpt: str = "auto"
    scope_tags_any: list[str] | None = None
    priority: int = 100


def _query_norm(query_tokens: list[str]) -> str:
    return " ".join(query_tokens)


def _when_any_matches(when_any: list[str], text: str) -> bool:
    if not when_any:
        return False
    norm = normalize(text)
    for trigger in when_any:
        t = normalize(trigger)
        if not t:
            continue
        if trigger.startswith("^") or "|" in trigger or "\\" in trigger:
            try:
                if re.search(trigger, text, re.IGNORECASE):
                    return True
            except re.error:
                pass
        if t in norm:
            return True
    return False


def _rules_for(scope_tags: list[str] | None, kind: str) -> list[TuningRule]:
    return [
        r
        for r in load_rules()
        if r.enabled and r.kind == kind and scope_matches(r, scope_tags)
    ]


def _rules_for_query(kind: str) -> list[TuningRule]:
    return [r for r in load_rules() if r.enabled and r.kind == kind]


def get_stopwords(scope_tags: list[str] | None = None) -> set[str]:
    words: set[str] = set()
    for rule in _rules_for(scope_tags, "stopword"):
        words.update(normalize(w) for w in rule.values)
    return words


def expand_tokens(tokens: list[str], scope_tags: list[str] | None = None) -> list[str]:
    norm = _query_norm(tokens)
    extra: list[str] = []
    for kind in ("expand_tokens", "alias"):
        for rule in _rules_for(scope_tags, kind):
            if _when_any_matches(rule.when_any, norm):
                extra.extend(rule.add)
    merged = list(dict.fromkeys(tokens + extra))
    return merged


def course_scores(text: str) -> dict[str, int]:
    norm = normalize(text)
    scores: dict[str, int] = {}
    for rule in _rules_for(None, "course_signal"):
        phrase = normalize(rule.phrase)
        target = (rule.target or "").strip().lower()
        if not phrase or not target:
            continue
        if phrase in norm:
            scores[target] = scores.get(target, 0) + max(1, rule.weight)
    return scores


def detect_course(text: str) -> str | None:
    scores = course_scores(text)
    if not scores:
        return None
    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    best_tag, best_score = ranked[0]
    if best_score <= 0:
        return None
    if len(ranked) > 1 and ranked[1][1] == best_score:
        return None
    return best_tag


def catalog_search_intent(user_text: str) -> bool:
    if get_search_profile(user_text):
        return True
    return should_auto_search(user_text, None)


def should_auto_search(text: str, scope_tags: list[str] | None = None) -> bool:
    for rule in _rules_for(scope_tags, "auto_search"):
        if _when_any_matches(rule.when_any, text):
            return True
    return False


def get_section_patterns(scope_tags: list[str] | None = None) -> list[re.Pattern]:
    patterns: list[re.Pattern] = []
    for rule in _rules_for(scope_tags, "section_header"):
        if not rule.pattern:
            continue
        try:
            patterns.append(re.compile(rule.pattern, re.IGNORECASE))
        except re.error:
            continue
    return patterns


def get_search_profile(text: str) -> SearchProfile | None:
    best: SearchProfile | None = None
    for rule in _rules_for_query("search_profile"):
        if not _when_any_matches(rule.when_any, text):
            continue
        scope_tags = None
        if rule.scope.mode == "tags" and rule.scope.tags_any:
            scope_tags = list(rule.scope.tags_any)
        candidate = SearchProfile(
            max_sections=rule.max_sections if rule.max_sections is not None else 12,
            excerpt=rule.excerpt or "full",
            scope_tags_any=scope_tags,
            priority=rule.priority,
        )
        if best is None or candidate.priority < best.priority:
            best = candidate
    return best


def get_allowed_tools(text: str) -> set[str]:
    allowed: set[str] = set()
    for rule in _rules_for_query("tool_policy"):
        if _when_any_matches(rule.when_any, text):
            allowed.update(rule.tools)
    return allowed
