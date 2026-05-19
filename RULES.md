# Chat GPB — regras do projeto

Este arquivo consolida as **decisões e restrições** acordadas para o assistente local IFSC Garopaba (`ferramentas/chat-gpb/`). Serve como referência para quem mantém o código, o admin (`/admin`) e a API.

Documentação complementar:

| Arquivo | Conteúdo |
|---------|----------|
| `STRUCTURE.md` | Mapa de pastas e módulos |
| `API.md` | Rotas HTTP, exemplos curl |
| `INSTALACAO.md` | Venv, Ollama, subir servidor |
| `.cursor/skills/chat-gpb/SKILL.md` | Guia para o agente Cursor no repositório `aulas` |

---

## 1. Identidade

- **Chat GPB**: FastAPI + Ollama (padrão `qwen2.5:7b-instruct`), porta **8765**.
- **Autocontido**: em runtime **não** lê `documentos/` do repo `aulas` nem `.cursor/rules/`. PPCs e contexto de curso ficam em `data/knowledge/`; ajustes de busca em `data/tuning/`.
- **UI em português**; **código e pastas em inglês** (`knowledge`, `tuning`, `document_search`, etc.).
- **Dois modos de chat** com comportamentos diferentes (ver secção 5).

---

## 2. Princípio central: configurar no admin, não no Python

### O que vai no admin (`/admin` → Kinds)

Tudo que depende de **vocabulário, curso, gatilhos de busca ou política de tools** deve ser kind YAML em `data/tuning/`, editável no admin ou no seed (`app/tuning_seed.py`).

| Kind | Função |
|------|--------|
| `stopword` | Palavras ignoradas na tokenização |
| `expand_tokens` | Se a pergunta contém X, acrescenta tokens Y |
| `alias` | Siglas e sinônimos (ex.: IEU → interfaces, experiência) |
| `course_signal` | Detecção silenciosa de “curso” via frase → **tag** do catálogo |
| `auto_search` | Dispara pré-busca antes do modelo (chat livre) |
| `section_header` | Regex que fatia documentos em seções (ex.: UC no PPC) |
| `search_profile` | Perfil de busca para listas/matriz/fase (`max_sections`, `excerpt`) |
| `tool_policy` | Quais tools o Ollama pode ver no **chat livre** |

Escopo de cada kind no YAML:

- `scope.mode: global` — regra vale em qualquer contexto de documento.
- `scope.mode: tags` + `tags_any` / `tags_all` — no **documento** (ex.: só PPC com tag `ppc`).

**Importante:** `search_profile` e `tool_policy` casam pela **pergunta** do usuário (`when_any`). O `scope.tags_any` desses kinds indica **em quais documentos buscar**, não filtra se a regra aparece na lista de regras da pergunta.

### O que fica no Python (algoritmo genérico)

- Tokenização, pontuação de seções, concatenação de trechos.
- Chamadas HTTP ao Ollama.
- Validação JSON Schema no structured.

**Não** reintroduzir no código:

- Parser fixo de matriz curricular (linhas `#### SIGLA` por fase).
- Enum `tecnico` / `sistemas` em tools, API ou detecção de curso.
- Listas fixas do tipo “se contém `cst` → sistemas” em `tuning_engine` ou `course_detect`.
- Tool loop no structured (removido: structured usa tools quando `tool_policy` casar).

### Tags de curso

- `course_signal.target` é **tag livre** do catálogo (ex.: `sistemas`, `tecnico`), não validada contra enum no Python.
- PPCs no catálogo usam tags como `ppc` + `sistemas` ou `ppc` + `tecnico`.

---

## 3. Catálogo (`data/catalog.json`)

| `type` | Pasta | Uso |
|--------|-------|-----|
| `knowledge` | `data/knowledge/` | PPCs, contexto de curso (`.mdc`), material do professor |
| `rule` | `data/rules/` | Respostas operacionais (`horario`, links) — `consultar_rules` |
| `tuning` | `data/tuning/` | Kinds (YAML) |

- Itens `readonly: true` (seed integrado): **ver** no admin, **não** excluir; duplicar sem `readonly` se precisar variante.
- `search_knowledge` (material do professor) **exclui** tags `ppc` e `curso` da busca geral.
- Ao atualizar PPC: copiar de `documentos/ppc-*.md` (repo `aulas`) para `data/knowledge/ppc-*.md` e manter tags no `catalog.json`.

---

## 4. Busca em documentos

```
tuning (kinds)
  → tuning_engine (stopwords, expand, course, search_profile, tool_policy, section regex)
    → document_search.search_document (por arquivo)
      → document_knowledge_search.buscar_documento (filtra itens do catálogo por tags)
```

- **`buscar_documento`**: `consulta` + `tags` opcionais (array de strings do catálogo). Sem enum de curso na tool.
- **`ppc_search`**: wrapper fino (tags `ppc` + tag de curso detectada).
- **`max_sections` / `excerpt`**: vêm do `search_profile` quando a pergunta casa; senão valores conservadores (poucas seções no chat).
- **`excerpt`**: `full` | `auto` | `none` — em `auto`, perguntas de bibliografia podem retornar só o bloco de bibliografia da seção vencedora.
- **Nunca** usar `max_sections=1` no structured para perguntas de “todas as matérias” / fase / matriz — isso enviesa o modelo para uma única disciplina.

Exemplo de kind para listas (seed `search-matriz-fase`):

```yaml
kind: search_profile
enabled: true
priority: 45
scope:
  mode: tags
  tags_any: [ppc]
when_any:
  - terceiro semestre
  - todas as materias
  - matriz curricular
max_sections: 12
excerpt: full
```

---

## 5. API — dois pipelines

### `POST /api/chat` (texto livre)

1. Detecção de curso silenciosa (`course_signal`); **nunca** pedir ao usuário para escolher curso no prompt.
2. `build_system_prompt` — contexto mínimo do curso detectado.
3. Pré-busca (`build_content_prematch`) quando `auto_search` ou perfil de busca casar.
4. **Tools** só se algum `tool_policy` casar (`when_any` → lista `tools`). Se nenhum casar → **nenhuma** tool (evita `buscar_documento` acidental).
5. `set_active_query` com a pergunta **completa** do usuário; tools não devem substituir por consulta encurtada do modelo.

Tools possíveis (quando permitidas):

| Tool | Uso |
|------|-----|
| `consultar_rules` | Horário, links operacionais |
| `buscar_documento` | Trechos em PPC/documentos por tags |
| `search_knowledge` | Material extra do professor |

### `POST /api/chat/structured` (JSON obrigatório)

1. **Sem** campo `curso` no body (se enviado por engano, é ignorado).
2. **Tool loop** quando algum `tool_policy` casar (mesmas regras do chat livre); depois uma (ou duas) chamadas Ollama com `format: response_schema` (sem tools na fase JSON).
3. **Formato informal** na mensagem:
   - Objeto plano `{ "opcao1": "string", ... }` → resposta com **as mesmas chaves no topo** (não vira `items` nem array).
   - Lista/matriz só quando o bloco pedir array de verdade: `{ [ "nome": "string", ... ]... }` ou `...` no formato.
4. **`inject_context`** (opcional no body): `null` = só injeta catálogo se `search_profile` casar ou schema for matriz de matérias (`materias`+nome+sigla+horas); `false` = nunca; `true` = sempre.
5. Formato explícito: `response_schema` (JSON Schema) tem prioridade e obedece literalmente (`additionalProperties: false` no schema gerado).
6. **Resposta HTTP 200 = somente o objeto do schema** — sem envelope.
7. Erro de parse/schema: HTTP **422** com `detail`, `raw_content`, `schema_errors`.

Exemplo de resposta desejada (3º semestre CST):

```json
{
  "materias": [
    { "nome": "Interfaces e Experiencia do Usuario", "sigla": "IEU", "horas": 60 }
  ]
}
```

---

## 6. Comportamento do modelo

- Bibliografia e ementa vêm dos **trechos injetados** ou da tool; **não inventar** livros nem disciplinas.
- Se o pré-contexto trouxer título de UC, a resposta deve usar **essa** disciplina (ex.: IEU ≠ Programação para Internet).
- Structured: system curto — responder **somente** JSON do schema; preencher arrays quando a pergunta pedir “todas” e o contexto tiver várias seções.
- `minItems` no schema pode ser elevado quando `search_profile` casar e a pergunta pedir lista completa (`apply_min_items`).

---

## 7. O que **não** fazer (checklist)

| Proibido | Motivo |
|----------|--------|
| `matriz_extract` ou parser de linhas fixas do PPC | Layout do PPC varia entre arquivos/versões |
| Hardcode `tecnico`/`sistemas`/`cst` no Python | Curso e gatilhos vivem nos kinds |
| Tools na fase JSON do structured (`format` + `tools` juntos) | A resposta final deve ser só JSON do schema |
| Prematch de 1 seção para “todas as matérias” | Resposta com uma disciplina só |
| Envelope no corpo 200 do structured | Cliente espera JSON puro do schema |
| Pedir “qual curso?” ao usuário | Detecção silenciosa via `course_signal` |
| Duplicar lógica de busca fora de `document_search` | Um motor genérico + kinds |

---

## 8. Admin (`/admin`)

- **Bases e regras**: CRUD de `knowledge` e `rule`; upload `.md`, `.txt`, `.yaml`.
- **Kinds**: CRUD de `tuning` por formulário (por kind) ou YAML completo.
- Campos extras no formulário: `search_profile` (`max_sections`, `excerpt`, `when_any`), `tool_policy` (`tools`, `when_any`), `course_signal` (`target` como texto livre).

Seed e migração leve:

- `init_store()` → `seed_default_tuning()` se não houver tuning.
- `ensure_tuning_extras()` adiciona kinds novos (`search-matriz-fase`, `tool-horario`, `tool-ppc`) em catálogos já existentes.

---

## 9. Testes e qualidade

```text
cd ferramentas/chat-gpb
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

Cobertura relevante das regras acima:

- `test_tuning_search_profile.py` — kinds `search_profile` / `tool_policy`
- `test_structured_tools.py` — structured usa tool loop quando `tool_policy` casar
- `test_document_search_multi.py` — várias seções com `max_sections` alto
- `test_api_routes.py` — corpo 200 do structured sem envelope

Insomnia: `Chat-GPB.insomnia.json` (base `http://127.0.0.1:8765`).

---

## 10. Relação com o repositório `aulas`

- **Fonte** dos PPCs: `documentos/ppc-informatica-tecnico-integrado.md`, `documentos/ppc-sistemas-para-internet.md` — copiar manualmente para `data/knowledge/`.
- **Regras Cursor** do repo (`tecnico-informatica-conhecimento`, `sistemas-para-internet-conhecimento`) orientam respostas **no IDE**; o Chat GPB usa cópias em `data/knowledge/curso-*.mdc` + kinds, não lê `.cursor/` em runtime.
- Skill do agente no monorepo: `.cursor/skills/chat-gpb/SKILL.md` e regra `.cursor/rules/chat-gpb.mdc` — devem permanecer alinhados a este `RULES.md`.

---

## 11. Subir o servidor

```text
cd ferramentas/chat-gpb
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
```

- Chat: http://127.0.0.1:8765/
- Admin: http://127.0.0.1:8765/admin
- Swagger: http://127.0.0.1:8765/docs

Variáveis: `.env` (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `CHAT_GPB_PORT`).
