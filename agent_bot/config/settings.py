"""Configuration and settings manager supporting Gemini, Groq, OpenRouter, and OpenAI."""
from pathlib import Path
from typing import List, Optional, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

class Settings(BaseSettings):
    # Asosiy papkalar
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)
    data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "data")
    
    # Telegram
    telegram_bot_token: str = Field(default="YOUR_BOT_TOKEN", alias="TELEGRAM_BOT_TOKEN")
    allowed_telegram_ids: Any = Field(default_factory=list, alias="ALLOWED_TELEGRAM_IDS")

    # AI API Keys (Ko'p modellik gibrid tizim)
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")

    # Model ID va endpointlar (yagona OpenAI-compat mijoz orqali)
    gemini_model: str = Field(default="gemini-4-argon", alias="GEMINI_MODEL")
    groq_model: str = Field(default="openai/gpt-oss-20b", alias="GROQ_MODEL")
    openrouter_model: str = Field(
        default="liquid/lfm-2.5-2.6b:free", alias="OPENROUTER_MODEL"
    )
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    anthropic_model: str = Field(default="claude-3-7-sonnet-20250219", alias="ANTHROPIC_MODEL")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1", alias="OPENAI_BASE_URL"
    )
    local_model: str = Field(default="qwen3:4b", alias="LOCAL_MODEL")
    llm_temperature: float = Field(default=0.4, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2048, alias="LLM_MAX_TOKENS")
    llm_timeout_s: int = Field(default=60, alias="LLM_TIMEOUT_S")

    # Standart til va rejim
    default_language: str = Field(default="uz", alias="DEFAULT_LANGUAGE")
    debug_mode: bool = Field(default=True, alias="DEBUG_MODE")

    # Cheklovlar yo'q — barcha foydalanuvchilar uchun cheksiz ochiq
    rate_limit_per_minute: int = 999999
    max_history_length: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("allowed_telegram_ids", mode="before")
    @classmethod
    def parse_allowed_ids(cls, v: Any) -> List[int]:
        if not v:
            return []
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
        if isinstance(v, (list, tuple)):
            return [int(x) for x in v if str(x).isdigit()]
        return []

    def is_user_allowed(self, user_id: int) -> bool:
        """Foydalanuvchiga ruxsat bor yoki yo'qligini tekshirish.
        Agar ro'yxat bo'sh bo'lsa (standart holat), barcha foydalanuvchilar uchun ochiq.
        """
        if not self.allowed_telegram_ids:
            return True
        return user_id in self.allowed_telegram_ids

settings = Settings()
