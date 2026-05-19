from contextlib import asynccontextmanager

from typing import Literal



from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile

from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import FileResponse, JSONResponse

from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel, Field



from app import chat_rules

from app.config import CHAT_GPB_ROOT, settings

from app.knowledge_store import (

    create_from_upload,

    create_item,

    delete_item,

    get_item,

    init_store,

    list_items,

    normalize_type,

    update_item,

)

from app.course_detect import resolve_curso_from_messages

from app.models import ChatRequest

from app.ollama_client import (
    StructuredParseError,
    chat_completion,
    chat_structured_completion,
    check_ollama,
)

from app.rules import build_system_prompt

from app.schemas.structured import StructuredChatRequest
from app.schemas.whatsapp_assist import WhatsAppAssistRequest
from app.tuning_store import build_tuning_yaml, field_to_list
from app.whatsapp_assist import run_whatsapp_assist


TAGS_METADATA = [
    {
        "name": "Sistema",
        "description": "Health, paginas estaticas e metadados da API.",
    },
    {
        "name": "Catalogo",
        "description": "CRUD de knowledge, rules e tuning (kinds).",
    },
    {
        "name": "Chat",
        "description": "Chat com Ollama: texto livre ou JSON estruturado.",
    },
]


STATIC_DIR = CHAT_GPB_ROOT / "static"


@asynccontextmanager

async def lifespan(_app: FastAPI):

    init_store()

    chat_rules.load_rules()

    yield





app = FastAPI(
    title="Chat GPB",
    description=(
        "Assistente local IFSC Garopaba (Ollama + PPCs em data/). "
        "Documentacao humana: ferramentas/chat-gpb/API.md"
    ),
    version="1.0.0",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
)



app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



if STATIC_DIR.is_dir():

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")





class KnowledgeCreate(BaseModel):

    type: Literal["knowledge", "rule", "tuning"] = "knowledge"

    title: str = Field(min_length=1)

    content: str = ""

    triggers: str | list[str] | None = None

    tags: list[str] | None = None

    kind: str | None = None

    priority: int | None = None

    enabled: bool = True

    scope_mode: str = "global"

    scope_tags_any: str | list[str] | None = None

    when_any: str | list[str] | None = None

    add: str | list[str] | None = None

    values: str | list[str] | None = None

    phrase: str | None = None

    target: str | None = None

    weight: int | None = None

    pattern: str | None = None

    max_sections: int | None = None

    excerpt: str | None = None

    tools: str | list[str] | None = None


class KnowledgeUpdate(BaseModel):

    title: str | None = None

    content: str | None = None

    triggers: str | list[str] | None = None

    tags: list[str] | None = None

    kind: str | None = None

    priority: int | None = None

    enabled: bool | None = None

    scope_mode: str | None = None

    scope_tags_any: str | list[str] | None = None

    when_any: str | list[str] | None = None

    add: str | list[str] | None = None

    values: str | list[str] | None = None

    phrase: str | None = None

    target: str | None = None

    weight: int | None = None

    pattern: str | None = None

    max_sections: int | None = None

    excerpt: str | None = None

    tools: str | list[str] | None = None


def _tuning_content_from_body(body: KnowledgeCreate | KnowledgeUpdate, require_kind: bool = False) -> str:
    if getattr(body, "content", None) and str(body.content).strip():
        return str(body.content).strip() + "\n"
    kind = getattr(body, "kind", None)
    if not kind:
        if require_kind:
            raise ValueError("Tuning exige kind ou conteudo YAML")
        return ""
    enabled = getattr(body, "enabled", True)
    if enabled is None:
        enabled = True
    scope_tags = field_to_list(getattr(body, "scope_tags_any", None))
    scope_mode = getattr(body, "scope_mode", None) or "global"
    return build_tuning_yaml(
        kind=str(kind),
        enabled=enabled,
        priority=getattr(body, "priority", None) or 100,
        scope_mode=scope_mode,
        scope_tags_any=scope_tags if scope_mode == "tags" else [],
        when_any=field_to_list(getattr(body, "when_any", None)),
        add=field_to_list(getattr(body, "add", None)),
        values=field_to_list(getattr(body, "values", None)),
        phrase=getattr(body, "phrase", None) or "",
        target=getattr(body, "target", None) or "",
        weight=getattr(body, "weight", None) or 1,
        pattern=getattr(body, "pattern", None) or "",
        max_sections=getattr(body, "max_sections", None),
        excerpt=getattr(body, "excerpt", None) or "",
        tools=field_to_list(getattr(body, "tools", None)),
    )


@app.get("/", tags=["Sistema"], summary="Pagina do chat ou metadados")

async def root():

    index = STATIC_DIR / "index.html"

    if index.is_file():

        return FileResponse(index)

    return {
        "info": "Chat GPB API",
        "health": "/health",
        "admin": "/admin",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "chat": "POST /api/chat",
        "chat_structured": "POST /api/chat/structured",
        "whatsapp_assist": "POST /api/whatsapp/assist",
        "knowledge": "GET /api/knowledge",
    }





@app.get("/admin", tags=["Sistema"], summary="Painel admin HTML")

async def admin_page():

    admin = STATIC_DIR / "admin.html"

    if admin.is_file():

        return FileResponse(admin)

    raise HTTPException(status_code=404, detail="admin.html nao encontrado")





@app.get("/health", tags=["Sistema"], summary="Status do Ollama e do catalogo")

async def health():

    ollama = await check_ollama()

    items = list_items()

    return {

        "ok": ollama.get("reachable", False),

        "ollama": ollama.get("reachable", False),

        "model": settings.ollama_model,

        "model_available": ollama.get("model_available", False),

        "models": ollama.get("models", []),

        "catalog_ok": all(i.get("exists", False) for i in items),

        "knowledge_items": len(items),

    }





@app.get("/api/knowledge", tags=["Catalogo"], summary="Lista itens do catalogo")

async def api_knowledge_list(
    type: str | None = Query(None),
):
    filter_type = type
    if filter_type:
        try:
            filter_type = normalize_type(filter_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"items": list_items(filter_type)}





@app.get("/api/knowledge/{item_id}", tags=["Catalogo"], summary="Obtem um item")

async def api_knowledge_get(item_id: str):

    try:

        return get_item(item_id)

    except KeyError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except FileNotFoundError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc





@app.post("/api/knowledge", tags=["Catalogo"], summary="Cria item do catalogo")

async def api_knowledge_create(body: KnowledgeCreate):

    try:

        item_type = normalize_type(body.type)
        content = body.content
        if item_type == "rule" and not content.strip():
            raise ValueError("Rules exigem resposta obrigatoria no campo content")
        if item_type == "tuning":
            content = _tuning_content_from_body(body, require_kind=True)
        item = create_item(
            item_type=item_type,
            title=body.title,
            content=content,
            triggers=body.triggers,
            tags=body.tags,
        )

        return item

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc





@app.post("/api/knowledge/upload", tags=["Catalogo"], summary="Upload knowledge ou rule")

async def api_knowledge_upload(

    type: Literal["knowledge", "rule"] = Form(...),

    title: str = Form(...),

    arquivo: UploadFile = File(...),

    triggers: str = Form(""),

):

    raw = await arquivo.read()

    try:

        item = create_from_upload(
            item_type=normalize_type(type),
            title=title,
            filename=arquivo.filename or "upload.md",

            raw=raw,

            triggers=triggers or None,

        )

        return item

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc





@app.put("/api/knowledge/{item_id}", tags=["Catalogo"], summary="Atualiza item")

async def api_knowledge_update(item_id: str, body: KnowledgeUpdate):

    try:

        content = body.content
        try:
            existing = get_item(item_id)
            if existing.get("type") == "tuning" and (
                body.kind or (content and str(content).strip())
            ):
                content = _tuning_content_from_body(
                    body, require_kind=bool(body.kind and not (content and str(content).strip()))
                )
        except (KeyError, FileNotFoundError):
            pass
        return update_item(
            item_id,
            title=body.title,
            content=content,
            triggers=body.triggers,
            tags=body.tags,
        )

    except KeyError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc





@app.delete("/api/knowledge/{item_id}", tags=["Catalogo"], summary="Remove item")

async def api_knowledge_delete(item_id: str):

    try:

        delete_item(item_id)

        return {"ok": True, "id": item_id}

    except KeyError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc





@app.post(
    "/api/chat",
    tags=["Chat"],
    summary="Chat em texto livre com tools",
    description="Resposta em message.content (string). Usa prematch PPC e loop de ferramentas Ollama.",
)

async def api_chat(body: ChatRequest):

    if body.stream:

        raise HTTPException(

            status_code=501,

            detail="Streaming ainda nao implementado; use stream: false",

        )



    curso_resolvido = resolve_curso_from_messages(
        [m.model_dump() for m in body.messages]
    )

    system_prompt = build_system_prompt(curso_resolvido)



    user_messages = [m for m in body.messages if m.role == "user"]

    last_user = user_messages[-1].content if user_messages else ""



    ollama_status = await check_ollama()

    if not ollama_status.get("reachable"):

        raise HTTPException(

            status_code=503,

            detail="Ollama nao esta acessivel. Verifique se o servico esta rodando.",

        )

    try:

        result = await chat_completion(
            messages=[m.model_dump() for m in body.messages],
            system_prompt=system_prompt,
            user_text_for_prematch=last_user,
            curso_resolvido=curso_resolvido,
        )

    except Exception as exc:

        raise HTTPException(status_code=502, detail=str(exc)) from exc



    return result


@app.post(
    "/api/chat/structured",
    tags=["Chat"],
    summary="Chat com resposta JSON obrigatoria",
    description=(
        "Corpo da resposta 200 = somente o JSON no formato pedido (ex. `{ \"materias\": [...] }`), "
        "sem envelope. Formato via `response_schema`, `output_format` ou bloco na mensagem. "
        "Em falha retorna 422 com `raw_content`."
    ),
    responses={
        422: {
            "description": "JSON invalido ou fora do schema",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "JSON fora do schema",
                        "raw_content": "{...}",
                        "schema_errors": ["'disciplina' is a required property"],
                    }
                }
            },
        },
    },
)
async def api_chat_structured(body: StructuredChatRequest):
    try:
        response_schema, chat_messages, format_hint = body.resolved_schema_and_messages()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    course_tag = resolve_curso_from_messages(chat_messages)

    from app.schemas.schema_resolve import should_inject_catalog_context

    inject_catalog = should_inject_catalog_context(
        response_schema,
        next(
            (
                str(m.get("content", ""))
                for m in reversed(chat_messages)
                if m.get("role") == "user"
            ),
            "",
        ),
        body.inject_context,
    )

    system_prompt = build_system_prompt(
        course_tag,
        structured=True,
        inject_course_context=inject_catalog,
    )
    user_messages = [m for m in chat_messages if m.get("role") == "user"]
    last_user = user_messages[-1].get("content", "") if user_messages else ""

    ollama_status = await check_ollama()
    if not ollama_status.get("reachable"):
        raise HTTPException(
            status_code=503,
            detail="Ollama nao esta acessivel. Verifique se o servico esta rodando.",
        )

    try:
        result = await chat_structured_completion(
            messages=chat_messages,
            system_prompt=system_prompt,
            response_schema=response_schema,
            user_text_for_prematch=last_user,
            curso_resolvido=course_tag,
            inject_context=body.inject_context,
            format_hint=format_hint,
        )
    except StructuredParseError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": exc.detail,
                "raw_content": exc.raw_content,
                "schema_errors": exc.schema_errors,
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return JSONResponse(content=result["data"])


@app.post(
    "/api/whatsapp/assist",
    tags=["Chat"],
    summary="Assistente WhatsApp Web (structured)",
    description=(
        "Analisa historico de mensagens do WhatsApp Web e devolve explicacao do contexto "
        "e resposta sugerida em um unico JSON (sem injecao de PPC/catalogo)."
    ),
    responses={
        422: {
            "description": "JSON invalido ou fora do schema",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "JSON fora do schema",
                        "raw_content": "{}",
                        "schema_errors": [],
                    }
                }
            },
        },
    },
)
async def api_whatsapp_assist(body: WhatsAppAssistRequest):
    ollama_status = await check_ollama()
    if not ollama_status.get("reachable"):
        raise HTTPException(
            status_code=503,
            detail="Ollama nao esta acessivel. Verifique se o servico esta rodando.",
        )

    try:
        result = await run_whatsapp_assist(body)
    except StructuredParseError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": exc.detail,
                "raw_content": exc.raw_content,
                "schema_errors": exc.schema_errors,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return JSONResponse(content=result)


