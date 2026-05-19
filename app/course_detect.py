from app.tuning_engine import course_scores, detect_course as _detect_course


def detectar_curso(mensagem: str) -> dict:
    scores = course_scores(mensagem)
    best = _detect_course(mensagem)
    if best:
        out_scores = {k: 0 for k in scores}
        out_scores[best] = scores.get(best, 1)
        return {"sugestao": best, "scores": out_scores}
    return {"sugestao": "auto", "scores": scores}


def resolve_curso_from_messages(messages: list[dict]) -> str | None:
    texts = [
        str(m.get("content", ""))
        for m in messages
        if m.get("role") == "user" and str(m.get("content", "")).strip()
    ]
    if not texts:
        return None
    combined = "\n".join(texts)
    return _detect_course(combined)
