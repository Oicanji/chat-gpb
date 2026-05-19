# Chat GPB — organizacao de arquivos

Este documento descreve a estrutura do projeto. **Pastas e codigo interno usam nomes em ingles**; **a interface web (`/`, `/admin`) permanece em portugues**.

## Visao geral

```
ferramentas/chat-gpb/
  app/                 # API FastAPI (Python)
  static/              # Interface web (HTML)
  data/                # Base cadastrada (catalog + arquivos)
  .env.example
  requirements.txt
  INSTALACAO.md
  STRUCTURE.md
  RULES.md          # Regras e decisoes do projeto (leia antes de alterar busca/API)
```

## `app/` — backend

| Arquivo | Funcao |
|---------|--------|
| `main.py` | Rotas HTTP: chat, health, `/admin`, `/api/knowledge/*` |
| `config.py` | Caminhos do repo, Ollama, pastas `data/` |
| `knowledge_store.py` | CRUD (`knowledge`, `rule`, `tuning`) |
| `tuning_store.py` / `tuning_engine.py` | Carrega kinds e aplica na busca |
| `tuning_seed.py` | Seed inicial dos kinds integrados |
| `text_utils.py` | Normalizacao e tokenizacao |
| `document_search.py` | Busca generica por secoes em qualquer documento |
| `knowledge_search.py` | Busca em conhecimentos do professor |
| `ppc_search.py` | Busca em PPC (wrapper sobre `document_search`) |
| `content_prematch.py` | Pre-busca automatica antes do modelo |
| `course_detect.py` | Detecao silenciosa de curso |
| `chat_rules.py` | Match de triggers — rules operacionais |
| `rules.py` | System prompt (contexto de curso) |
| `tools.py` | Tools Ollama |
| `ollama_client.py` | Cliente Qwen |

## `data/`

```
data/
  catalog.json
  knowledge/     # documentos (.md, .txt, .mdc)
  rules/         # regras operacionais (.yaml)
  tuning/        # kinds / acertividades de busca (.yaml)
```

### Tipos no catalogo

| `type` | Pasta | Uso |
|--------|-------|-----|
| `knowledge` | `knowledge/` | Material e PPCs; busca via `document_search` |
| `rule` | `rules/` | `consultar_rules` (ex.: horario) |
| `tuning` | `tuning/` | Kinds: stopwords, aliases, expansao, curso, auto_search, section_header |

### Kinds (`tuning`)

Cada arquivo YAML define um kind com `kind`, `enabled`, `priority`, `scope` (global ou `tags_any`).

| kind | Efeito |
|------|--------|
| `stopword` | Palavras ignoradas na tokenizacao |
| `expand_tokens` / `alias` | Se a pergunta contem X, acrescenta tokens Y |
| `course_signal` | Detecao de curso (tecnico / sistemas) |
| `auto_search` | Injeta trechos do documento antes do modelo |
| `section_header` | Regex para fatiar documento em secoes |
| `search_profile` | Perfil de busca (max_sections, excerpt) para listas/matriz |
| `tool_policy` | Tools permitidas no chat livre |

Escopo **global** vale para todos os documentos; escopo **tags** so para knowledge com essas tags (ex.: `ppc`).

Itens seed (`readonly: true`) sao criados em `init_store()` se ainda nao existir tuning.

### Itens integrados (`readonly`)

| id | tags | Uso |
|----|------|-----|
| `ppc-tecnico` / `ppc-sistemas` | `ppc` + curso | PPC oficial |
| `curso-tecnico` / `curso-sistemas` | `curso` + curso | System prompt |
| `horario` | — | Rule Garopaba |
| `stopwords-*`, `alias-*`, etc. | — | Kinds padrao |

## Admin (`/admin`)

Duas abas principais:

1. **Bases e regras** — conhecimentos e rules
2. **Kinds** — acertividades de busca (CRUD de `tuning`)

## Fluxo do chat

```
POST /api/chat
  -> resolve_curso_from_messages (kinds course_signal)
  -> build_system_prompt
  -> build_content_prematch (kinds auto_search + document_search)
  -> Ollama + tools (buscar_ppc, search_knowledge, consultar_rules)
```

Todas as buscas em texto usam `document_search` + kinds aplicaveis ao escopo do documento.
