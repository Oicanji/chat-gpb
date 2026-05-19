import pytest

from app.schemas.schema_resolve import (
    parse_informal_format,
    resolve_structured_schema,
    split_question_and_format,
)


CST_MATERIAS_MESSAGE = """Me de todas as materias do terceiro semestre do curso de cst.
{
   [
       "nome":"string, nome da materia por extenso",
       "sigla":"string",
       "horas":"int com o total de horas daquela materia"
   ]...
}"""


def test_split_question_and_format():
    q, fmt = split_question_and_format(CST_MATERIAS_MESSAGE)
    assert "terceiro semestre" in q
    assert '"nome"' in fmt
    assert fmt.startswith("{")


def test_parse_informal_materias_cst():
    _, fmt = split_question_and_format(CST_MATERIAS_MESSAGE)
    schema = parse_informal_format(fmt)
    assert schema["type"] == "object"
    assert "materias" in schema["properties"]
    items = schema["properties"]["materias"]["items"]
    assert items["properties"]["nome"]["type"] == "string"
    assert items["properties"]["sigla"]["type"] == "string"
    assert items["properties"]["horas"]["type"] == "integer"
    assert set(items["required"]) == {"nome", "sigla", "horas"}


def test_resolve_from_message_only():
    schema, msgs, _fmt = resolve_structured_schema(
        [{"role": "user", "content": CST_MATERIAS_MESSAGE}],
        None,
        None,
    )
    assert "materias" in schema["properties"]
    assert "terceiro semestre" in msgs[0]["content"]
    assert "{" not in msgs[0]["content"]


def test_resolve_output_format_field():
    schema, _, _fmt = resolve_structured_schema(
        [{"role": "user", "content": "Liste disciplinas"}],
        None,
        '"sigla": "string", "nome": "string"',
    )
    assert schema["type"] == "object"


def test_resolve_explicit_json_schema():
    schema, _, _fmt = resolve_structured_schema(
        [{"role": "user", "content": "x"}],
        {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        },
        None,
    )
    assert schema["properties"]["ok"]["type"] == "boolean"


STAKEHOLDER_FORMAT = """{
   "opcao1":"string",
"opcao2":"string",
"opcao3":"string",
"opcao4":"string","pergunta_correta":"nome da chave da pergunta"
}"""


def test_parse_informal_flat_object_not_array():
    schema = parse_informal_format(STAKEHOLDER_FORMAT)
    assert schema["type"] == "object"
    assert "items" not in schema.get("properties", {})
    assert "materias" not in schema.get("properties", {})
    assert set(schema["properties"]) == {
        "opcao1",
        "opcao2",
        "opcao3",
        "opcao4",
        "pergunta_correta",
    }
    assert schema.get("additionalProperties") is False


def test_should_not_inject_context_for_stakeholder():
    from app.schemas.schema_resolve import should_inject_catalog_context

    schema = parse_informal_format(STAKEHOLDER_FORMAT)
    assert (
        should_inject_catalog_context(
            schema,
            "O que e um Stakeholders? elabora 4 opcoes",
            None,
        )
        is False
    )


CST_MATERIAS_EXPLICIT_KEY = """Me de todas as materias do primeiro semestre do curso de cst.
{
"materias":[
       "nome":"string, nome da materia por extenso",
       "sigla":"string",
       "horas":"int com o total de horas daquela materia"
   ]
}"""


def test_parse_informal_materias_explicit_key():
    _, fmt = split_question_and_format(CST_MATERIAS_EXPLICIT_KEY)
    schema = parse_informal_format(fmt)
    assert "materias" in schema["properties"]
    assert schema["properties"]["materias"]["type"] == "array"
    assert "nome" in schema["properties"]["materias"]["items"]["properties"]


def test_normalize_flat_object_into_materias_array():
    from app.schemas.schema_resolve import normalize_parsed_data

    _, fmt = split_question_and_format(CST_MATERIAS_EXPLICIT_KEY)
    schema = parse_informal_format(fmt)
    flat = {"nome": "LP", "sigla": "LP", "horas": 60}
    out = normalize_parsed_data(flat, schema)
    assert "materias" in out
    assert len(out["materias"]) == 1
    assert out["materias"][0]["sigla"] == "LP"


def test_resolve_missing_format_raises():
    with pytest.raises(ValueError, match="Informe"):
        resolve_structured_schema(
            [{"role": "user", "content": "so a pergunta"}],
            None,
            None,
        )
