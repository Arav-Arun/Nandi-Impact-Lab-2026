"""
core.config - single source of truth for runtime configuration.

Every member imports `settings` from here. The field names map 1:1 to the env
variables in `.env.example` (SoW §12.3). Never read os.environ directly elsewhere
in the codebase - add a field here instead, so there is exactly one place that
documents what the system needs to run.

    from core.config import settings
    settings.DATABASE_URL
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed view over the process environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # tolerate env vars owned by other members / tooling
    )

    # ── PostgreSQL (pgvector) ───────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://nandi:password@localhost:5432/nandi"

    # ── Neo4j ───────────────────────────────────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "changeme"

    # ── Redis ───────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Intake AI + channels ────────────────────────────────────────────────
    # Native-language voice→text (Sarvam) and structured field + photo
    # extraction (Claude). Both optional - absent keys → deterministic
    # heuristics so intake always works. Telegram is the conversational channel.
    SARVAM_API_KEY: str = ""
    # LLM for structured intake extraction + photo description. OpenAI is primary;
    # Anthropic is an optional fallback. Absent keys → deterministic heuristics.
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"       # vision + function-calling capable
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-4-8"
    TELEGRAM_BOT_TOKEN: str = ""

    # ── Email (M2) - first configured provider wins: Resend → SendGrid → SMTP ─
    RESEND_API_KEY: str = ""
    SENDGRID_API_KEY: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "NANDI <onboarding@resend.dev>"

    # ── Location-blast / escalation knobs (M2) ──────────────────────────────
    BLAST_INCLUDE_ADJACENT: bool = True     # also target zones adjacent in the graph
    BLAST_ESCALATE_HOURS_1: int = 24        # T+24h: re-blast the zone
    BLAST_ESCALATE_HOURS_2: int = 72        # T+72h: escalate to police

    # ── Embedding (M1) ──────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large"
    EMBEDDING_DIM: int = 1024
    # 1 → deterministic stub embedder (default, no model download). 0 → real model.
    EMBEDDING_FALLBACK: bool = True
    EMBEDDING_DEVICE: str = "cpu"

    # ── Auth (M4 issues JWTs; INTERNAL_KEY guards /internal/* routes - M1) ───
    JWT_SECRET: str = ""
    JWT_EXPIRY_HOURS: int = 8
    INTERNAL_KEY: str = "dev-internal-key-change-me"

    # ── OTP (M2) ────────────────────────────────────────────────────────────
    OTP_TTL_SECONDS: int = 14400  # 4 hours

    # ── Matching knobs (M1) ─────────────────────────────────────────────────
    MATCH_AGE_WINDOW: int = Field(15, description="± years around found person's age")
    MATCH_CANDIDATE_LIMIT: int = Field(10, description="top-N from pgvector pre re-rank")
    MATCH_RETURN_LIMIT: int = Field(3, description="candidates shown to the operator")
    MATCH_MIN_CONFIDENCE: float = Field(0.60, description="below this → not surfaced")
    PGVECTOR_EF_SEARCH: int = Field(64, description="HNSW ef_search at query time")
    MATVIEW_REFRESH_SECONDS: int = 300

    # ── Derived helpers ─────────────────────────────────────────────────────
    @property
    def openai_enabled(self) -> bool:
        """True when an OpenAI key is configured (the primary LLM provider)."""
        return bool(self.OPENAI_API_KEY)

    @property
    def claude_enabled(self) -> bool:
        """True when an Anthropic key is configured (fallback LLM provider)."""
        return bool(self.ANTHROPIC_API_KEY)

    @property
    def llm_enabled(self) -> bool:
        """True when any LLM provider is available (else deterministic heuristics)."""
        return self.openai_enabled or self.claude_enabled

    @property
    def sarvam_enabled(self) -> bool:
        """True when a Sarvam key is configured (else mock STT/translate)."""
        return bool(self.SARVAM_API_KEY)

    # Channel availability - drives which blast/notify channels actually send.
    @property
    def telegram_enabled(self) -> bool:
        return bool(self.TELEGRAM_BOT_TOKEN)

    @property
    def email_enabled(self) -> bool:
        return bool(self.RESEND_API_KEY or self.SENDGRID_API_KEY or (self.SMTP_HOST and self.SMTP_USER))

    @property
    def enabled_channels(self) -> dict[str, bool]:
        return {"telegram": self.telegram_enabled, "email": self.email_enabled}

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """
        Sync (psycopg2) URL derived from the async DATABASE_URL.

        Alembic migrations run synchronously, so we swap the asyncpg driver for
        psycopg2. Keeping this derivation here means there is one DATABASE_URL to
        configure, not two that can drift apart.
        """
        return self.DATABASE_URL.replace("+asyncpg", "").replace(
            "postgresql://", "postgresql+psycopg2://"
        )


@lru_cache
def get_settings() -> Settings:
    """Cached accessor - Settings is parsed from the environment exactly once."""
    return Settings()


# Module-level singleton for convenient `from core.config import settings`.
settings = get_settings()
