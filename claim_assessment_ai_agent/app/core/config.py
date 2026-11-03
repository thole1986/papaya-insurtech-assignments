from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", validate_assignment=True
    )

    run_mode: Literal["offline", "live"] = "offline"
    google_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    database_url: str = "sqlite+aiosqlite:///./runtime/claims.db"
    assessment_timeout_seconds: float = Field(default=180, gt=0)
    provider_timeout_seconds: float = Field(default=30, gt=0)

    @property
    def provider_ready(self) -> bool:
        return self.run_mode == "offline" or bool(
            self.google_api_key.get_secret_value() and self.llm_model
        )
