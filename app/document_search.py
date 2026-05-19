import re
from pathlib import Path

from app.text_utils import clean_visible, normalize, tokenize_raw
from app.tuning_engine import expand_tokens, get_section_patterns, get_stopwords

MAX_SECTION_CHARS = 4500
MAX_FALLBACK_SNIPPETS = 4

ANCHOR_TOKENS = frozenset(
    {
        "experiencia",
        "usuario",
        "interfaces",
        "interface",
        "ieu",
        "ux",
        "usabilidade",
    }
)

GENERIC_TOKENS = frozenset(
    {
        "complementares",
        "complementar",
        "materiais",
        "material",
        "basica",
        "conhecimentos",
        "habilidades",
        "unidade",
        "curricular",
        "estudo",
        "estudar",
    }
)

TYPO_FIX = {
    "estutudo": "estudo",
}


def prepare_tokens(query: str, scope_tags: list[str] | None = None) -> list[str]:
    stopwords = get_stopwords(scope_tags)
    base = tokenize_raw(query, stopwords)
    fixed = [TYPO_FIX.get(t, t) for t in base]
    return expand_tokens(fixed, scope_tags)


def _parse_sections(lines: list[str], scope_tags: list[str] | None) -> list[dict]:
    patterns = get_section_patterns(scope_tags)
    if not patterns:
        return []

    headers: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        visible = clean_visible(line)
        for pat in patterns:
            m = pat.search(visible)
            if m:
                title = m.group(1).strip() if m.lastindex and m.group(1) else visible
                headers.append((i, _clean_title(title)))
                break

    if not headers:
        return []

    sections: list[dict] = []
    for idx, (start, title) in enumerate(headers):
        end = headers[idx + 1][0] if idx + 1 < len(headers) else len(lines)
        sections.append(
            {
                "start": start,
                "end": end,
                "title": title,
                "text": "\n".join(lines[start:end]),
            }
        )
    return sections


def _clean_title(title: str) -> str:
    return re.sub(r"\*\*.*", "", title).strip()


def _score_section(section: dict, tokens: list[str]) -> int:
    title_norm = normalize(section["title"])
    body_norm = normalize(section["text"])

    anchors_in_query = [t for t in tokens if t in ANCHOR_TOKENS]
    anchors_in_title = sum(1 for t in anchors_in_query if t in title_norm)

    score = 0
    for token in tokens:
        if token in GENERIC_TOKENS:
            continue
        if token in title_norm:
            score += 10
        elif token in body_norm:
            score += 1

    for token in tokens:
        if token not in GENERIC_TOKENS:
            continue
        if token in title_norm:
            score += 2
        elif token in body_norm and not anchors_in_query:
            score += 1

    if anchors_in_query:
        score += anchors_in_title * 18
        if anchors_in_title == 0:
            score = max(0, score // 3)

    if any(t in tokens for t in ("complementar", "complementares", "bibliografia")):
        if "bibliografia complementar" in body_norm:
            score += 6 if anchors_in_title else 1

    if "experiencia" in title_norm and "usuario" in title_norm:
        score += 12

    if "total carga horaria da" in body_norm:
        score += 15
        for token in tokens:
            if re.match(r"^[1-6]a?$", token) and (
                f"{token}a fase" in body_norm or f"da {token}" in body_norm
            ):
                score += 20

    return score


def _extract_bibliography(text: str) -> str:
    lines = text.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if "bibliografia" in normalize(ln)),
        None,
    )
    if start is None:
        return text[:MAX_SECTION_CHARS]
    return "\n".join(lines[start:])[:MAX_SECTION_CHARS]


def _trim_section_text(text: str, tokens: list[str], excerpt: str) -> str:
    if excerpt == "bibliography":
        return _extract_bibliography(text)
    if len(text) <= MAX_SECTION_CHARS:
        return text
    lines = text.splitlines()
    bib_idx = next(
        (i for i, ln in enumerate(lines) if "bibliografia" in normalize(ln)),
        None,
    )
    if bib_idx is not None:
        start = max(0, bib_idx - 6)
        excerpt_text = "\n".join(lines[start:])
        if len(excerpt_text) <= MAX_SECTION_CHARS:
            return excerpt_text
    return text[:MAX_SECTION_CHARS] + "\n..."


def _pick_sections(
    ranked: list[dict], tokens: list[str], max_sections: int
) -> list[dict]:
    if not ranked:
        return []
    scores = [_score_section(s, tokens) for s in ranked]
    if scores[0] <= 0:
        return []

    if max_sections >= 3:
        picked: list[dict] = []
        for section, score in zip(ranked, scores):
            if score <= 0:
                continue
            picked.append(section)
            if len(picked) >= max_sections:
                break
        return picked or [ranked[0]]

    picked = [ranked[0]]
    if max_sections <= 1:
        return picked

    if len(ranked) > 1 and scores[1] > 0 and scores[0] < scores[1] * 2:
        picked.append(ranked[1])
    return picked[:max_sections]


def _wants_bibliography(tokens: list[str]) -> bool:
    joined = " ".join(tokens)
    return any(
        k in joined
        for k in ("bibliografia", "complementar", "complementares", "livro", "referencia")
    )


def _trecho_matriz_carga_horaria(lines: list[str], tokens: list[str]) -> dict | None:
    phase_hints = {t for t in tokens if re.match(r"^[1-6]a?$", t)}
    for i, line in enumerate(lines):
        norm = normalize(clean_visible(line))
        if "total carga horaria da" not in norm:
            continue
        if phase_hints and not any(p in norm for p in phase_hints):
            continue
        end = i + 1
        start = max(0, i - 30)
        for j in range(i, max(0, i - 50), -1):
            nj = normalize(clean_visible(lines[j]))
            if re.match(r"^#+\s*[1-6]\s*[aoª]?\s*$", nj):
                start = j
                break
        text = "\n".join(lines[start:end])
        rows = sum(
            1
            for ln in lines[start:end]
            if re.match(r"^#{2,6}\s+[A-Z]{2,}", clean_visible(ln))
            and "total" not in normalize(ln)
        )
        if rows < 2:
            continue
        return {
            "linha_inicio": start + 1,
            "linha_fim": end,
            "titulo": clean_visible(line).strip("# ").strip() or "Matriz curricular",
            "texto": text[:MAX_SECTION_CHARS],
            "pontuacao": 500,
        }
    return None


def _line_fallback(lines: list[str], tokens: list[str]) -> list[dict]:
    scored: list[tuple[int, int]] = []
    for i, line in enumerate(lines):
        norm_line = normalize(clean_visible(line))
        score = sum(1 for t in tokens if t in norm_line and t not in GENERIC_TOKENS)
        if score > 0:
            scored.append((score, i))
    scored.sort(key=lambda x: (-x[0], x[1]))

    snippets: list[dict] = []
    used: set[int] = set()
    for _score, line_no in scored[: MAX_FALLBACK_SNIPPETS * 2]:
        if len(snippets) >= MAX_FALLBACK_SNIPPETS:
            break
        if any(abs(line_no - u) <= 2 for u in used):
            continue
        start = max(0, line_no - 5)
        end = min(len(lines), line_no + 25)
        text = "\n".join(lines[start:end])
        snippets.append(
            {
                "linha_inicio": start + 1,
                "linha_fim": end,
                "titulo": "",
                "texto": text[:MAX_SECTION_CHARS],
            }
        )
        for j in range(start, end):
            used.add(j)
    return snippets


def search_document(
    path: Path,
    consulta: str,
    scope_tags: list[str] | None = None,
    doc_id: str = "",
    max_sections: int = 2,
    excerpt: str = "auto",
) -> dict:
    tokens = prepare_tokens(consulta, scope_tags)
    if not tokens:
        return {"erro": "consulta vazia ou muito curta", "trechos": [], "tokens": []}

    excerpt_mode = excerpt
    if excerpt_mode == "none":
        excerpt_mode = "full"
    elif excerpt_mode == "auto":
        excerpt_mode = "bibliography" if _wants_bibliography(tokens) else "full"

    lines = path.read_text(encoding="utf-8").splitlines()
    sections = _parse_sections(lines, scope_tags)
    trechos: list[dict] = []

    if sections:
        ranked = sorted(sections, key=lambda s: _score_section(s, tokens), reverse=True)
        for section in _pick_sections(ranked, tokens, max_sections):
            trechos.append(
                {
                    "linha_inicio": section["start"] + 1,
                    "linha_fim": section["end"],
                    "titulo": section["title"],
                    "texto": _trim_section_text(section["text"], tokens, excerpt_mode),
                    "pontuacao": _score_section(section, tokens),
                }
            )

    if not trechos:
        trechos = _line_fallback(lines, tokens)

    list_query = max_sections >= 3 or any(
        t in tokens for t in ("fase", "semestre", "materias", "matriz")
    )
    if list_query:
        matriz = _trecho_matriz_carga_horaria(lines, tokens)
        if matriz:
            trechos = [matriz] + [t for t in trechos if t is not matriz][: max_sections - 1]

    return {
        "id": doc_id,
        "arquivo": path.name,
        "consulta": consulta,
        "tokens": tokens,
        "trechos": trechos,
    }
