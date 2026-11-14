"""Fail closed when a phone reply resembles raw diagnostics or credential material."""

import re


LOCAL_NOTICE = "Details are available locally."
UNSAFE = re.compile(
    r"(?:\d{1,3}\.){3}\d{1,3}"
    r"|(?:[0-9a-f]*:){2,}[0-9a-f:.]+"
    r"|\b(?:sk-|gh[pousr]_|github_pat_|bearer\s+)\S+"
    r"|\b[A-Za-z0-9_+/=-]{32,}\b"
    r"|/(?:home|root|etc|var|proc|run)/"
    r"|https?://|BEGIN [A-Z ]*PRIVATE KEY"
    r"|\b(?:passwords?|passphrases?|seed[ -]phrases?|recovery[ -]codes?|one[ -]time[ -]codes?|api[ -](?:key|token))\b",
    re.IGNORECASE,
)


def safe_text(text, *, known_private=()):
    """Present bounded plain prose; this is a guardrail, not general-purpose DLP."""
    if not isinstance(text, str) or not 0 < len(text) <= 2000:
        return LOCAL_NOTICE
    if UNSAFE.search(text) or any(value and value.casefold() in text.casefold() for value in known_private):
        return LOCAL_NOTICE
    return text
