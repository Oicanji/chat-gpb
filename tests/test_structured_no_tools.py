import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.ollama_client import chat_structured_completion


def test_structured_skips_tool_loop():
    schema = {
        "type": "object",
        "properties": {
            "materias": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"nome": {"type": "string"}},
                    "required": ["nome"],
                },
            }
        },
        "required": ["materias"],
    }

    async def run():
        with patch("app.ollama_client.check_ollama", new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {"reachable": True, "model_available": True}
            with patch(
                "app.ollama_client.build_structured_context_for_query",
                return_value=("contexto teste", None),
            ):
                with patch("app.ollama_client._run_tool_loop", new_callable=AsyncMock) as mock_loop:
                    with patch("app.ollama_client.httpx.AsyncClient") as mock_client_cls:
                        mock_client = MagicMock()
                        mock_client_cls.return_value.__aenter__.return_value = mock_client
                        mock_response = MagicMock()
                        mock_response.raise_for_status = MagicMock()
                        mock_response.json.return_value = {
                            "choices": [{"message": {"content": '{"materias":[]}'}}]
                        }
                        mock_client.post = AsyncMock(return_value=mock_response)

                        await chat_structured_completion(
                            messages=[
                                {
                                    "role": "user",
                                    "content": "todas as materias terceiro semestre",
                                }
                            ],
                            system_prompt="test",
                            response_schema=schema,
                            user_text_for_prematch="todas as materias terceiro semestre",
                        )

                        mock_loop.assert_not_called()

    asyncio.run(run())
