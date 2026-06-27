"""Central configuration. All secrets come from the environment / .env file.

Nothing here is required to boot — missing keys simply disable the feature that
needs them (e.g. no SARVAM_API_KEY → Sarvam calls fall back to a mock), so the
app always starts and the dashboard always renders. Keys are added per phase.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NANDI Intake"
    env: str = "dev"

    # Storage — SQLite by default (zero infra, swappable for the team's Postgres later)
    database_url: str = f"sqlite+aiosqlite:///{BACKEND_DIR / 'nandi.db'}"
    seed_csv_path: str = str(REPO_DIR / "dataset" / "Synthetic_Missing_Persons_2500.csv")

    # CORS — Vite dev server
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- External services (optional; feature-flagged on presence) ---
    sarvam_api_key: str | None = None
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-8"

    telegram_bot_token: str | None = None

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str | None = None  # e.g. "whatsapp:+14155238886" (sandbox)

    @property
    def sarvam_enabled(self) -> bool:
        return bool(self.sarvam_api_key)

    @property
    def claude_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
