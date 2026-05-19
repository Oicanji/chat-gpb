from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.test_schema_resolve import CST_MATERIAS_MESSAGE

SCHEMA = {
    "type": "object",
    "properties": {
        "disciplina": {"type": "string"},
        "itens": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["disciplina", "itens"],
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    with patch("app.main.check_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = {
            "reachable": True,
            "model_available": True,
            "models": ["qwen2.5:7b-instruct"],
        }
        r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "ok" in data
    assert "knowledge_items" in data


def test_openapi_json(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["info"]["title"] == "Chat GPB"
    paths = spec.get("paths", {})
    assert "/api/chat/structured" in paths
    assert "/api/whatsapp/assist" in paths


def test_list_knowledge(client):
    r = client.get("/api/knowledge")
    assert r.status_code == 200
    assert "items" in r.json()


def test_root_json_fallback(client, monkeypatch):
    from unittest.mock import MagicMock

    fake_index = MagicMock()
    fake_index.is_file.return_value = False
    fake_static = MagicMock()
    fake_static.__truediv__ = lambda _self, name: fake_index if name == "index.html" else MagicMock()
    monkeypatch.setattr("app.main.STATIC_DIR", fake_static)
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data.get("docs") == "/docs"
    assert "chat_structured" in data


def test_chat_mocked(client):
    with patch("app.main.check_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = {"reachable": True, "model_available": True}
        with patch("app.main.chat_completion", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = {
                "message": {"role": "assistant", "content": "ok"},
                "tool_calls": [],
            }
            r = client.post(
                "/api/chat",
                json={"messages": [{"role": "user", "content": "oi"}]},
            )
    assert r.status_code == 200
    assert r.json()["message"]["content"] == "ok"


def test_chat_ignores_extra_curso(client):
    with patch("app.main.check_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = {"reachable": True, "model_available": True}
        with patch("app.main.chat_completion", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = {
                "message": {"role": "assistant", "content": "ok"},
                "tool_calls": [],
            }
            r = client.post(
                "/api/chat",
                json={
                    "messages": [{"role": "user", "content": "oi"}],
                    "curso": "auto",
                },
            )
    assert r.status_code == 200


def test_chat_structured_mocked(client):
    with patch("app.main.check_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = {"reachable": True, "model_available": True}
        with patch(
            "app.main.chat_structured_completion",
            new_callable=AsyncMock,
        ) as mock_structured:
            mock_structured.return_value = {
                "data": {"disciplina": "IEU", "itens": ["Livro A"]},
            }
            r = client.post(
                "/api/chat/structured",
                json={
                    "messages": [{"role": "user", "content": "Bibliografia IEU"}],
                    "response_schema": SCHEMA,
                },
            )
    assert r.status_code == 200
    body = r.json()
    assert body["disciplina"] == "IEU"
    assert "data" not in body
    assert "tool_calls" not in body


def test_chat_structured_informal_message(client):
    with patch("app.main.check_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = {"reachable": True, "model_available": True}
        with patch(
            "app.main.chat_structured_completion",
            new_callable=AsyncMock,
        ) as mock_structured:
            mock_structured.return_value = {
                "data": {
                    "materias": [
                        {"nome": "Interfaces e Experiencia do Usuario", "sigla": "IEU", "horas": 60}
                    ]
                },
            }
            r = client.post(
                "/api/chat/structured",
                json={"messages": [{"role": "user", "content": CST_MATERIAS_MESSAGE}]},
            )
    assert r.status_code == 200
    body = r.json()
    assert "materias" in body
    assert "data" not in body
    assert "tool_calls" not in body


def test_whatsapp_assist_mocked(client):
    with patch("app.main.check_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = {"reachable": True, "model_available": True}
        with patch("app.main.run_whatsapp_assist", new_callable=AsyncMock) as mock_wa:
            mock_wa.return_value = {
                "explicacao": "Contato perguntou sobre horario.",
                "resposta_sugerida": "Ola! O horario e das 19h as 22h.",
                "fontes": [
                    {
                        "nome": "Conversa WhatsApp",
                        "referencia": "ultima mensagem da Maria",
                        "como_usou": "pergunta sobre horario",
                    }
                ],
            }
            r = client.post(
                "/api/whatsapp/assist",
                json={
                    "conversation_title": "Aluno",
                    "messages": [
                        {"author": "Maria", "text": "Qual o horario?", "outgoing": False},
                    ],
                },
            )
    assert r.status_code == 200
    body = r.json()
    assert body["explicacao"] == "Contato perguntou sobre horario."
    assert "resposta_sugerida" in body
    assert len(body["fontes"]) == 1


def test_chat_structured_missing_format(client):
    r = client.post(
        "/api/chat/structured",
        json={"messages": [{"role": "user", "content": "so a pergunta"}]},
    )
    assert r.status_code == 422


def test_chat_structured_parse_error(client):
    from app.ollama_client import StructuredParseError

    with patch("app.main.check_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = {"reachable": True, "model_available": True}
        with patch(
            "app.main.chat_structured_completion",
            new_callable=AsyncMock,
        ) as mock_structured:
            mock_structured.side_effect = StructuredParseError(
                "JSON fora do schema",
                raw_content='{"disciplina":""}',
                schema_errors=["'itens' is a required property"],
            )
            r = client.post(
                "/api/chat/structured",
                json={
                    "messages": [{"role": "user", "content": "x"}],
                    "response_schema": SCHEMA,
                },
            )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["detail"] == "JSON fora do schema"
    assert "raw_content" in detail
