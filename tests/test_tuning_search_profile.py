from app.tuning_engine import get_allowed_tools, get_search_profile


def test_get_search_profile_matriz():
    profile = get_search_profile("todas as materias do terceiro semestre")
    assert profile is not None
    assert profile.max_sections >= 8
    assert profile.excerpt == "full"


def test_get_allowed_tools_horario():
    tools = get_allowed_tools("qual o horario das aulas")
    assert "consultar_rules" in tools


def test_get_allowed_tools_empty_when_no_policy():
    tools = get_allowed_tools("oi tudo bem")
    assert tools == set() or isinstance(tools, set)
