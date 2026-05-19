import re

from app.document_knowledge_search import buscar_documento
from app.text_utils import clean_visible, normalize
from app.tuning_engine import catalog_search_intent, get_search_profile

UC_LINE = re.compile(r"^#{2,6}\s+[A-Z][A-Z0-9]", re.IGNORECASE)


def _is_matriz_fase_trecho(trecho: dict) -> bool:
    text = trecho.get("texto") or ""
    norm = normalize(text)
    if "total carga horaria da" not in norm:
        return False
    rows = sum(
        1
        for ln in text.splitlines()
        if UC_LINE.match(clean_visible(ln)) and "total" not in normalize(ln)
    )
    return rows >= 2


def _count_uc_rows(text: str) -> int:
    return sum(
        1
        for ln in text.splitlines()
        if UC_LINE.match(clean_visible(ln)) and "total" not in normalize(ln)
    )


def _select_trechos_for_list(
    trechos: list[dict], *, prefer_matriz: bool = False
) -> list[dict]:
    matriz = [t for t in trechos if _is_matriz_fase_trecho(t)]
    if prefer_matriz and matriz:
        best = max(matriz, key=lambda t: int(t.get("pontuacao", 0)))
        return [best]
    if trechos:
        return [max(trechos, key=lambda t: int(t.get("pontuacao", 0)))]
    return []


def _format_trechos_block(trechos: list[dict], header: str) -> str:
    if not trechos:
        return (
            f"{header}\n"
            "Nenhum trecho relevante encontrado. Nao invente dados fora dos documentos."
        )
    parts = [
        header,
        "Use SOMENTE o texto abaixo. Copie nome e sigla exatamente como aparecem.",
        "Nao invente disciplinas que nao estejam no trecho.",
    ]
    for t in trechos:
        titulo = t.get("titulo") or t.get("documento_id", "")
        texto = t.get("texto", "")
        parts.append(f"\n### {titulo}\n\n{texto}")
    return "\n".join(parts)


def build_structured_context(
    user_text: str,
    course_tag: str | None,
    *,
    tags_any: list[str] | None = None,
    tags_all: list[str] | None = None,
    force_search: bool = False,
) -> tuple[str, int | None]:
    if not force_search and not catalog_search_intent(user_text):
        return "", None

    profile = get_search_profile(user_text)
    max_sections = profile.max_sections if profile else 6
    excerpt = profile.excerpt if profile else "full"

    result = buscar_documento(
        user_text,
        tags_any=tags_any,
        tags_all=tags_all,
        max_sections=max_sections,
        excerpt=excerpt,
    )
    trechos = _select_trechos_for_list(
        result.get("trechos") or [],
        prefer_matriz=profile is not None,
    )

    expected_rows = None
    if trechos:
        expected_rows = _count_uc_rows(trechos[0].get("texto", ""))

    header = "[Contexto para resposta estruturada — documentos do catalogo]"
    if expected_rows and expected_rows >= 2:
        header += (
            f"\nListe exatamente as {expected_rows} disciplinas que aparecem "
            "no trecho (linhas #### SIGLA Nome CH)."
        )

    text = _format_trechos_block(trechos, header)
    return text, expected_rows if expected_rows and expected_rows >= 2 else None
