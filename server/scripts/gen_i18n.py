"""
scripts.gen_i18n - generate real UI translations for every Sarvam language.

Reads the English source strings from the frontend i18n module (the EN map),
translates each string with Sarvam's translation model, and writes one locale
file per language to frontend/src/lib/locales/<code>.json. The React app loads
those automatically, so the entire interface translates.

  python -m scripts.gen_i18n            # all languages, only missing keys
  python -m scripts.gen_i18n --force    # retranslate everything
  python -m scripts.gen_i18n hi ta      # only these languages

Idempotent: existing translations are kept unless --force. Interpolation tokens
like {n}/{z} are verified in the output; if a translation drops one, that key
falls back to English so the UI never breaks.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import httpx

from core.config import settings
from core.logging_utils import get_logger

log = get_logger("nandi.gen_i18n")

ROOT = Path(__file__).resolve().parents[2]
I18N_SRC = ROOT / "frontend" / "src" / "lib" / "i18n.tsx"
OUT_DIR = ROOT / "frontend" / "src" / "lib" / "locales"

BASE = "https://api.sarvam.ai"

# UI code -> Sarvam translate target code. English is the source, so it is omitted.
TARGETS = {
    "hi": "hi-IN", "mr": "mr-IN", "bn": "bn-IN", "te": "te-IN", "ta": "ta-IN",
    "kn": "kn-IN", "gu": "gu-IN", "ml": "ml-IN", "pa": "pa-IN", "od": "od-IN",
}

CONCURRENCY = 2
RETRIES = 6


def load_en() -> dict[str, str]:
    """Extract the EN string map from i18n.tsx (values never contain a raw quote)."""
    text = I18N_SRC.read_text(encoding="utf-8")
    m = re.search(r"export const EN[^{]*\{(.*?)\n\};", text, re.S)
    if not m:
        raise SystemExit("Could not locate the EN block in i18n.tsx")
    pairs = re.findall(r'"([^"]+)":\s*"((?:[^"\\]|\\.)*)"', m.group(1))
    # EN values contain no backslash escapes, so keep them verbatim (UTF-8 safe).
    return {k: v for k, v in pairs}


def tokens(s: str) -> set[str]:
    return set(re.findall(r"\{[a-zA-Z0-9_]+\}", s))


async def translate_one(client: httpx.AsyncClient, text: str, target: str, sem: asyncio.Semaphore) -> str | None:
    payload = {
        "input": text,
        "source_language_code": "en-IN",
        "target_language_code": target,
        "model": "mayura:v1",
    }
    async with sem:
        for attempt in range(RETRIES):
            try:
                r = await client.post(f"{BASE}/translate", json=payload,
                                      headers={"api-subscription-key": settings.SARVAM_API_KEY})
                if r.status_code == 429:
                    await asyncio.sleep(2.0 * (attempt + 1))  # back off on rate limit
                    continue
                r.raise_for_status()
                out = (r.json().get("translated_text") or "").strip()
                await asyncio.sleep(0.15)  # gentle pacing under the rate limit
                if out and tokens(text) <= tokens(out):
                    return out
                return None  # dropped an interpolation token -> fall back to English
            except Exception as exc:
                if attempt == RETRIES - 1:
                    log.warning("translate failed (%s): %s", target, exc)
                    return None
                await asyncio.sleep(2.0 * (attempt + 1))
    return None


async def gen_lang(client: httpx.AsyncClient, code: str, target: str, en: dict[str, str], force: bool) -> None:
    out_path = OUT_DIR / f"{code}.json"
    existing: dict[str, str] = {}
    if out_path.exists() and not force:
        existing = json.loads(out_path.read_text(encoding="utf-8"))

    todo = [k for k in en if force or k not in existing]
    if not todo:
        log.info("%s: up to date (%d keys)", code, len(en))
        return

    sem = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*(translate_one(client, en[k], target, sem) for k in todo))

    merged = dict(existing)
    ok = 0
    for k, res in zip(todo, results):
        if res:
            merged[k] = res
            ok += 1
    # keep keys ordered like EN for clean diffs
    ordered = {k: merged[k] for k in en if k in merged}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log.info("%s: wrote %d/%d translated (%d total keys)", code, ok, len(todo), len(ordered))


async def main() -> None:
    if not settings.SARVAM_API_KEY:
        raise SystemExit("SARVAM_API_KEY is not set - cannot generate translations.")

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    force = "--force" in sys.argv
    langs = {c: TARGETS[c] for c in args if c in TARGETS} if args else TARGETS

    en = load_en()
    log.info("Loaded %d English keys; generating %d language(s).", len(en), len(langs))
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        for code, target in langs.items():
            await gen_lang(client, code, target, en, force)
    log.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
