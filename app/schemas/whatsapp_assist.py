import re
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, field_validator

LIST_LINE_RE = re.compile(r"^\s*(\d+\.|-|\*)\s+")
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F600-\U0001F64F"
    "\u2600-\u26FF"
    "\u2700-\u27BF"
    "]+",
    flags=re.UNICODE,
)

WHATSAPP_ASSIST_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "explicacao": {
            "type": "string",
            "description": (
                "Resumo do que foi conversado ou da ultima pergunta do contato; "
                "priorizar mensagens recebidas recentes."
            ),
        },
        "resposta_sugerida": {
            "type": "string",
            "description": (
                "Mensagem para WhatsApp: tom informal sem girias, levemente bem-humorada "
                "sem piadas; em uma linha salvo listas e não utilize markdown para responder, e sem emojis."
            ),
        },
        "fontes": {
            "type": "array",
            "description": (
                "Origem das informacoes usadas. Vazio se so inferencia obvia do historico "
                "sem citar trecho especifico."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "nome": {
                        "type": "string",
                        "description": "Titulo do documento, PPC, regra ou 'Conversa WhatsApp'.",
                    },
                    "referencia": {
                        "type": "string",
                        "description": "Secao, mensagem ou id consultado.",
                    },
                    "como_usou": {
                        "type": "string",
                        "description": "Breve nota do que foi extraido dessa fonte.",
                    },
                },
                "required": ["nome", "referencia", "como_usou"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["explicacao", "resposta_sugerida", "fontes"],
    "additionalProperties": False,
}

Draft202012Validator.check_schema(WHATSAPP_ASSIST_RESPONSE_SCHEMA)


class WhatsAppMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    author: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=8000)
    outgoing: bool = Field(
        description="True se enviada pelo atendente (message-out no WhatsApp Web)."
    )


class WhatsAppAssistRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    conversation_title: str = Field(default="", max_length=300)
    messages: list[WhatsAppMessage] = Field(min_length=1, max_length=20)

    @field_validator("messages")
    @classmethod
    def strip_messages(cls, value: list[WhatsAppMessage]) -> list[WhatsAppMessage]:
        cleaned: list[WhatsAppMessage] = []
        for msg in value:
            author = msg.author.strip()
            text = msg.text.strip()
            if not author or not text:
                continue
            cleaned.append(
                WhatsAppMessage(author=author, text=text, outgoing=msg.outgoing)
            )
        if not cleaned:
            raise ValueError("Informe ao menos uma mensagem com autor e texto.")
        return cleaned


def format_whatsapp_reply(text: str) -> str:
    text = EMOJI_RE.sub("", text).strip()
    text = re.sub(r"\s{2,}", " ", text)
    if not text:
        return text
    lines = text.splitlines()
    stripped = [ln for ln in lines if ln.strip()]
    if any(LIST_LINE_RE.match(ln) for ln in stripped):
        return text.strip()
    if len(stripped) <= 1:
        return re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    if sum(1 for ln in lines if not ln.strip()) >= 1:
        return text.strip()
    return re.sub(r"\s+", " ", text.replace("\n", " ")).strip()


def build_whatsapp_system_prompt(
    expected_disciplines: int | None = None,
    *,
    has_catalog: bool = False,
) -> str:
    lines = [
        "Voce auxilia um atendente do IFSC Garopaba no WhatsApp Web. "
        "Analise o historico e, se houver, os trechos do catalogo institucional. "
        "Produza JSON conforme o schema.\n",
        "Priorize as ultimas mensagens do CONTATO (outgoing=false).\n",
        "explicacao: contexto claro; Markdown simples permitido (**negrito**, listas com -).\n",
        "resposta_sugerida: texto para colar no WhatsApp — tom de conversa, informal mas "
        "sem girias; levemente bem-humorado e acolhedor, sem piadas; profissional do IFSC. "
        "PROIBIDO usar emojis. Sem markdown na resposta_sugerida.\n",
        "Se o catalogo nao tiver a informacao, diga que vai confirmar — nao invente disciplinas, "
        "fases nem cargas horarias.\n",
        "Fora de listas: uma unica linha (sem quebras de linha).\n",
        "fontes: para cada informacao que nao veio so do tom da conversa, indique origem. "
        "Use trechos do catalogo quando aplicavel. Array vazio apenas se nada especifico foi usado.",
    ]

    if expected_disciplines and expected_disciplines >= 2:
        lines.append(
            f"\nOBRIGATORIO: o trecho do catalogo lista {expected_disciplines} disciplinas — "
            f"inclua as {expected_disciplines} na resposta_sugerida (lista com '-')."
        )
    return "\n".join(lines)


def build_whatsapp_user_content(
    conversation_title: str,
    messages: list[WhatsAppMessage],
    catalog_context: str = "",
    expected_disciplines: int | None = None,
) -> str:
    lines = ["Historico da conversa (ordem cronologica, antigas primeiro):"]
    if conversation_title.strip():
        lines.append(f"Titulo: {conversation_title.strip()}")
    lines.append("")
    for i, msg in enumerate(messages, start=1):
        papel = "Atendente" if msg.outgoing else "Contato"
        lines.append(f"{i}. [{papel}] {msg.author}: {msg.text}")
    lines.append("")
    if catalog_context.strip():
        lines.append(catalog_context.strip())
        lines.append("")
    lines.append(
        "Explique o contexto, cite fontes quando usar dados de documentos ou mensagens "
        "especificas, e sugira a resposta para enviar agora."
    )
    if expected_disciplines and expected_disciplines >= 2:
        lines.append(
            f"Liste na resposta_sugerida as {expected_disciplines} disciplinas do trecho "
            "(sigla, nome e CH como no PPC)."
        )
    return "\n".join(lines)
