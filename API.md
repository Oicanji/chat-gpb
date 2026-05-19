# Chat GPB — API HTTP

Base URL local: `http://127.0.0.1:8765`

| Recurso | URL |
|---------|-----|
| Swagger UI (testar rotas) | http://127.0.0.1:8765/docs |
| ReDoc | http://127.0.0.1:8765/redoc |
| OpenAPI JSON | http://127.0.0.1:8765/openapi.json |
| Insomnia | Importar `Chat-GPB.insomnia.json` (ambiente **Local** → `http://127.0.0.1:8765`) |

## Rotas

### Sistema

| Metodo | Path | Descricao |
|--------|------|-----------|
| GET | `/` | Chat HTML ou JSON com links da API |
| GET | `/admin` | Admin HTML (bases, regras, kinds) |
| GET | `/health` | Status Ollama + catalogo |
| GET | `/static/*` | Arquivos estaticos |

### Catalogo (`knowledge`, `rule`, `tuning`)

| Metodo | Path | Descricao |
|--------|------|-----------|
| GET | `/api/knowledge` | Lista itens (`?type=knowledge\|rule\|tuning`) |
| GET | `/api/knowledge/{id}` | Item + conteudo |
| POST | `/api/knowledge` | Cria item (JSON) |
| POST | `/api/knowledge/upload` | Upload (`knowledge` ou `rule`) |
| PUT | `/api/knowledge/{id}` | Atualiza (respeita `readonly`) |
| DELETE | `/api/knowledge/{id}` | Remove (respeita `readonly`) |

### Chat

| Metodo | Path | Descricao |
|--------|------|-----------|
| POST | `/api/chat` | Resposta em texto livre + tools |
| POST | `/api/chat/structured` | Resposta **obrigatoriamente** JSON (`response_schema`) |
| POST | `/api/whatsapp/assist` | Assistente WhatsApp Web: `explicacao` + `resposta_sugerida` |

---

## POST /api/whatsapp/assist

Usado pelo userscript Tampermonkey em `ferramentas/assistente-whatsapp/`. Analisa o historico de mensagens coletado no DOM do WhatsApp Web (sem tools nem injecao de PPC).

**Request:**

```json
{
  "conversation_title": "GPTralaleiros",
  "messages": [
    { "author": "Rian", "text": "Tem rodizio?", "outgoing": false },
    { "author": "Voce", "text": "Vou verificar.", "outgoing": true }
  ]
}
```

- `outgoing: true` = mensagem enviada pelo atendente (`message-out`); `false` = contato.
- Ordem cronologica (antigas primeiro), ate 20 mensagens.

**Response 200:**

```json
{
  "explicacao": "O contato pergunta sobre rodizio...",
  "resposta_sugerida": "Ola! Ainda nao confirmei o rodizio; retorno em breve.",
  "fontes": [
    {
      "nome": "PPC Sistemas para Internet",
      "referencia": "secao horarios",
      "como_usou": "confirmacao de turno noturno"
    }
  ]
}
```

- `fontes`: origem das informacoes (catalogo, PPC, conversa). Array vazio se nada a citar.
- `resposta_sugerida`: uma linha no WhatsApp (salvo listas); tom informal sem girias.
- O backend busca trechos no catalogo antes do modelo e pede citacao em `fontes`.

**Response 422:** mesmo formato do structured (`detail`, `raw_content`, `schema_errors`).

---

## POST /api/chat/structured

O modelo devolve JSON validado. Tres formas de definir o formato:

1. **`response_schema`** — JSON Schema (`type: object` ou `type: array`; array vira `{ "items": [...] }`).
2. **`output_format`** — texto informal (campos `"campo": "tipo, descricao"`).
3. **Na mensagem** — pergunta + bloco `{ [ "nome": "string, ...", ... ] }` (o bloco e removido da pergunta enviada ao modelo).

Tipos reconhecidos no formato informal: `string`, `int`/`integer`, `number`, `bool`, `array`. Listas usam chave `materias` (se o texto citar materia/disciplina) ou `items`.

**Exemplo (formato na mensagem, CST 3o semestre):**

```json
{
  "messages": [{
    "role": "user",
    "content": "Me de todas as materias do terceiro semestre do curso de cst.\n{\n   [\n       \"nome\":\"string, nome da materia por extenso\",\n       \"sigla\":\"string\",\n       \"horas\":\"int com o total de horas daquela materia\"\n   ]...\n}"
  }],
}
```

**Request (JSON Schema classico):**

```json
{
  "messages": [{"role": "user", "content": "Bibliografia complementar de IEU"}],
  "response_schema": {
    "type": "object",
    "properties": {
      "disciplina": {"type": "string"},
      "bibliografia_complementar": {
        "type": "array",
        "items": {"type": "string"}
      }
    },
    "required": ["disciplina", "bibliografia_complementar"]
  },
}
```

**Response 200:** corpo HTTP = **somente** o objeto JSON do schema (sem envelope `data`, `tool_calls`, `curso`, etc.).

```json
{
  "materias": [
    { "nome": "Interfaces e Experiencia do Usuario", "sigla": "IEU", "horas": 60 }
  ]
}
```

O pipeline structured usa **tool loop** quando algum `tool_policy` casar (mesmo criterio do chat livre); em seguida gera o JSON com `format: response_schema`. O prematch de catalogo continua via `search_profile` / `section_header` nos kinds.

**Response 422:** JSON invalido ou fora do schema (`detail`, `raw_content`).

---

## Testes rapidos (curl)

```bash
# Health
curl -s http://127.0.0.1:8765/health | jq

# Listar kinds
curl -s "http://127.0.0.1:8765/api/knowledge?type=tuning" | jq

# Chat texto
curl -s http://127.0.0.1:8765/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Horario de aula"}]}'

# Chat estruturado
curl -s http://127.0.0.1:8765/api/chat/structured \
  -H "Content-Type: application/json" \
  -d '{
    "messages":[{"role":"user","content":"Bibliografia complementar Interfaces e Experiencia do Usuario CST"}],
    "response_schema":{
      "type":"object",
      "properties":{
        "disciplina":{"type":"string"},
        "itens":{"type":"array","items":{"type":"string"}}
      },
      "required":["disciplina","itens"]
    }
  }'

# WhatsApp assist
curl -s http://127.0.0.1:8765/api/whatsapp/assist \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_title": "GPTralaleiros",
    "messages": [
      {"author": "Rian", "text": "Tem rodizio?", "outgoing": false},
      {"author": "Voce", "text": "Vou verificar.", "outgoing": true}
    ]
  }'
```

## Testes automatizados

```bash
cd ferramentas/chat-gpb
pip install -r requirements-dev.txt
pytest tests/ -q
```
