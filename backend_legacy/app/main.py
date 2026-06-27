"""NANDI intake-layer API entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.responses import ok
from app.api.v1 import intake, media
from app.bots import telegram, whatsapp
from app.config import settings
from app.db import init_db
from app.services import store

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("nandi")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    seeded = await store.seed_from_csv()
    if seeded:
        log.info("Seeded %d synthetic reports from dataset", seeded)
    log.info("Sarvam=%s  Claude=%s  Telegram=%s  Twilio=%s",
             settings.sarvam_enabled, settings.claude_enabled,
             bool(settings.telegram_bot_token), bool(settings.twilio_account_sid))
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(intake.router)
app.include_router(media.router)
app.include_router(telegram.router)
app.include_router(whatsapp.router)


@app.get("/health")
async def health():
    return ok({
        "status": "ok",
        "service": settings.app_name,
        "features": {
            "sarvam": settings.sarvam_enabled,
            "claude": settings.claude_enabled,
            "telegram": bool(settings.telegram_bot_token),
            "whatsapp": bool(settings.twilio_account_sid),
        },
    })
