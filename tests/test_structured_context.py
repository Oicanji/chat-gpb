from app.config import settings
from app.content_prematch import build_structured_context_for_query
from app.structured_context import (
    _is_matriz_fase_trecho,
    _select_trechos_for_list,
    build_structured_context,
)
from app.tuning_store import invalidate_tuning_cache


def test_select_matriz_trecho():
    good = {
        "texto": "#### ATP Algo 60 60\n#### FSI Fund 30 30\n#### Total Carga Horária da 1ª Fase 300",
        "pontuacao": 10,
    }
    bad = {
        "texto": "#### IEU Interfaces e Experiencia do Usuario\nBibliografia complementar...",
        "pontuacao": 20,
    }
    picked = _select_trechos_for_list([bad, good], prefer_matriz=True)
    assert len(picked) == 1
    assert _is_matriz_fase_trecho(picked[0])
    assert "ATP" in picked[0]["texto"]


def test_trabalhos_sem_intent_nao_injetam_matriz():
    invalidate_tuning_cache()
    ctx, expected = build_structured_context(
        "Alunos nao apresentaram trabalhos; afeta nota na semana proxima?",
        None,
    )
    assert ctx == ""
    assert expected is None


def test_primeiro_semestre_context_has_atp():
    invalidate_tuning_cache()
    path = settings.data_dir / "knowledge" / "ppc-sistemas.md"
    if not path.is_file():
        return
    ctx, expected = build_structured_context_for_query(
        "Me de todas as materias do primeiro semestre do curso de cst.",
        "sistemas",
    )
    assert "ATP" in ctx
    assert "FSI" in ctx
    assert "MAT" in ctx
    assert expected == 4
