"""
core.logging_utils — logging helpers, including the phone-masking that SoW §12.8
non-negotiable #2 requires.

    NON-NEGOTIABLE: No plaintext phone numbers in logs.
    Always pass phone numbers through mask_phone() before they touch a logger.

Usage:
    from core.logging_utils import get_logger, mask_phone
    log = get_logger(__name__)
    log.info("notified filer %s", mask_phone(phone))
"""

from __future__ import annotations

import logging
import re

# Module-level flag so we configure the root handler exactly once.
_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    """Install a single stream handler with a consistent format. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger. Safe to call from any module at import time."""
    configure_logging()
    return logging.getLogger(name)


def mask_phone(phone: str | None) -> str:
    """
    Mask a phone number for safe logging: +919876543210 -> +91XXXXXX3210.

    Intake phone fields are free-form Text, so the input may contain spaces,
    hyphens, dots, or parentheses ("+91 98765-43210"). We therefore operate on
    the DIGITS only and rebuild a canonical masked form, keeping the leading
    country/operator code and the last 4 digits and replacing the middle with X.
    Separators are intentionally dropped — the output is for logs, not dialling.

    Returns "<none>" for empty input. Never raises — logging must not blow up
    because a phone field was malformed (SoW §12.8 #2: no plaintext phones).
    """
    if not phone:
        return "<none>"
    try:
        text = str(phone)
        digits = re.sub(r"\D", "", text)
        if len(digits) < 4:
            # Too short to be a real number; mask whatever digits exist entirely.
            return "X" * len(digits) if digits else "<masked>"

        last4 = digits[-4:]
        # Show a 2-digit country/operator code only when the number is long
        # enough that doing so still leaves middle digits masked.
        lead = digits[:2] if len(digits) > 6 else ""
        middle = "X" * (len(digits) - len(lead) - len(last4))
        plus = "+" if text.lstrip().startswith("+") else ""
        return f"{plus}{lead}{middle}{last4}"
    except Exception:  # pragma: no cover - defensive: logging must never fail
        return "<masked>"
