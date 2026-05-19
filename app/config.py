from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

CHAT_GPB_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=CHAT_GPB_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    chat_gpb_port: int = 8765
    chat_gpb_cors_origins: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        defaults = [
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "https://web.whatsapp.com",
            "null",
        ]
        extra = [
            o.strip()
            for o in self.chat_gpb_cors_origins.split(",")
            if o.strip()
        ]
        seen: set[str] = set()
        out: list[str] = []
        for origin in defaults + extra:
            if origin not in seen:
                seen.add(origin)
                out.append(origin)
        return out

    @property
    def chat_gpb_root(self) -> Path:
        return CHAT_GPB_ROOT

    @property
    def data_dir(self) -> Path:
        return CHAT_GPB_ROOT / "data"

    @property
    def catalog_path(self) -> Path:
        return self.data_dir / "catalog.json"

    @property
    def knowledge_dir(self) -> Path:
        return self.data_dir / "knowledge"

    @property
    def rules_data_dir(self) -> Path:
        return self.data_dir / "rules"

    @property
    def tuning_dir(self) -> Path:
        return self.data_dir / "tuning"


settings = Settings()
