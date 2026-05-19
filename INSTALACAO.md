# Chat GPB — instalacao

API local de chat com Qwen (Ollama), busca nos PPCs e rules declarativas.

## 1. Ollama

1. Instale em https://ollama.com
2. Baixe o modelo:

```bash
ollama pull qwen2.5:7b-instruct
```

Modelo menor se faltar RAM/GPU:

```bash
ollama pull qwen2.5:3b-instruct
```

Defina no `.env`: `OLLAMA_MODEL=qwen2.5:3b-instruct`

3. Teste:

```bash
ollama run qwen2.5:7b-instruct
```

Saia com `/bye`.

## 2. Python

Na pasta do projeto:

```bash
cd ferramentas/chat-gpb
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` para `.env` se quiser alterar modelo ou porta.

## 3. Subir a API

Com o venv ativo, a partir de `ferramentas/chat-gpb`:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
```

Abra http://127.0.0.1:8765/ no navegador.

## 4. Testes rapidos

Health:

```bash
curl http://127.0.0.1:8765/health
```

Chat (horario):

```bash
curl -X POST http://127.0.0.1:8765/api/chat -H "Content-Type: application/json" -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Qual o horario das aulas?\"}],\"stream\":false}"
```

A resposta deve incluir o link https://www.ifsc.edu.br/web/campus-garopaba/horario-de-aula

## 5. Variaveis de ambiente

| Variavel | Padrao |
|----------|--------|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` |
| `CHAT_GPB_PORT` | `8765` |

## 6. Base de conhecimento (admin)

Abra http://127.0.0.1:8765/admin:

- Aba **Bases e regras**: conhecimentos (`.md`/`.txt`) e rules (triggers + resposta)
- Aba **Kinds**: acertividades de busca (stopwords, aliases, expansao de tokens, detecao de curso, pre-busca, regex de secao)
- Itens `readonly` (PPCs, kinds padrao) aparecem na lista mas nao podem ser excluidos

Arquivos em `ferramentas/chat-gpb/data/` (`catalog.json`, `knowledge/`, `rules/`, `tuning/`).

Organizacao completa: [STRUCTURE.md](STRUCTURE.md).

### API

Documentacao completa: [API.md](API.md). Coleção Insomnia: importar `Chat-GPB.insomnia.json` (ambiente **Local**, base `http://127.0.0.1:8765`).

| Recurso | URL |
|---------|-----|
| Swagger (testar rotas) | http://127.0.0.1:8765/docs |
| ReDoc | http://127.0.0.1:8765/redoc |
| OpenAPI JSON | http://127.0.0.1:8765/openapi.json |

Rotas principais:

| Metodo | Rota |
|--------|------|
| GET | `/health` |
| POST | `/api/chat` |
| POST | `/api/chat/structured` |
| GET | `/api/knowledge` |
| POST | `/api/knowledge` (JSON) |
| POST | `/api/knowledge/upload` (multipart) |
| PUT | `/api/knowledge/{id}` |
| DELETE | `/api/knowledge/{id}` |

**Chat estruturado** (`POST /api/chat/structured`): envie `response_schema` (JSON Schema com `type: object`). A resposta vem em `data` (objeto JSON validado), nunca texto livre no campo principal.

```bash
curl -s http://127.0.0.1:8765/api/chat/structured \
  -H "Content-Type: application/json" \
  -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Bibliografia IEU CST\"}],\"response_schema\":{\"type\":\"object\",\"properties\":{\"disciplina\":{\"type\":\"string\"},\"itens\":{\"type\":\"array\",\"items\":{\"type\":\"string\"}}},\"required\":[\"disciplina\",\"itens\"]}}"
```

Testes automatizados:

```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```
