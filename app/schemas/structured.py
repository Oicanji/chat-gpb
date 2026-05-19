from typing import Any

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import ChatMessage
from app.schemas.schema_resolve import resolve_structured_schema


class StructuredChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    messages: list[ChatMessage] = Field(min_length=1)
    response_schema: dict[str, Any] | None = None
    output_format: str | None = None
    inject_context: bool | None = Field(
        default=None,
        description=(
            "Injetar trechos do catalogo antes do modelo. "
            "null=automatico (so matriz/PPC ou search_profile); false=nunca; true=sempre."
        ),
    )

    @model_validator(mode="after")
    def require_schema_source(self) -> "StructuredChatRequest":
        has_explicit = self.response_schema is not None or (
            self.output_format and self.output_format.strip()
        )
        if has_explicit:
            return self
        for msg in reversed(self.messages):
            if msg.role == "user" and "{" in msg.content and '"' in msg.content:
                return self
        raise ValueError(
            "Informe response_schema, output_format ou inclua o formato na mensagem"
        )

    def resolved_schema_and_messages(
        self,
    ) -> tuple[dict[str, Any], list[dict], str | None]:
        return resolve_structured_schema(
            [m.model_dump() for m in self.messages],
            self.response_schema,
            self.output_format,
        )


def validate_instance(data: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    return [e.message for e in errors]
