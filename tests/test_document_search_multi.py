from app.document_knowledge_search import buscar_documento


def test_buscar_documento_multi_sections():
    result = buscar_documento(
        "terceiro semestre 3a fase materias",
        tags_any=["ppc", "sistemas"],
        max_sections=12,
        excerpt="full",
    )
    trechos = result.get("trechos") or []
    assert len(trechos) >= 2
    joined = " ".join(t.get("texto", "") for t in trechos).lower()
    assert "fase" in joined or "semestre" in joined
