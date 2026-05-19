from app.json_repair import loads_json_object


def test_repair_trailing_quote_after_number():
    raw = """{
"materias":[
       {"nome":"ATP", "sigla":"ATP", "horas":60},
       {"nome":"MAT", "sigla":"MAT", "horas":30"}
]
}"""
    broken = raw.replace('"horas":30}', '"horas":30"}')
    data = loads_json_object(broken)
    assert len(data["materias"]) == 2
    assert data["materias"][1]["horas"] == 30
