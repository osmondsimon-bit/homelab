"""Keep phone output useful while removing common address and credential material."""

import re

LOCAL_NOTICE = "Sensitive or lengthy details are available locally."
MAX_TEXT = 3500
ADDRESSES = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}|(?:[0-9a-f]{0,4}:){2,7}[0-9a-f:.]{0,45}", re.IGNORECASE)
SECRETS = re.compile(
    r"\b(?:sk-|gh[pousr]_|github_pat_)\S+|\bbearer\s+\S+"
    r"|\b\d{4,20}:[A-Za-z0-9_-]{20,100}\b"
    r"|\b(?:password|passphrase|token|secret|api[_-]?key)\s*[:=]\s*[\"']?\S+",
    re.IGNORECASE,
)
SOLICITATION = re.compile(r"\b(?:enter|send|paste|provide|type|share)\b.{0,48}\b(?:password|passphrase|seed phrase|recovery code|one.time code|api.key)\b", re.IGNORECASE)


def safe_text(text):
    """Final transport check; ordinary paths and public URLs are not credentials."""
    if (not isinstance(text, str) or not 0 < len(text) <= MAX_TEXT or ADDRESSES.search(text)
            or SECRETS.search(text) or 'PRIVATE KEY-----' in text or SOLICITATION.search(text)):
        return LOCAL_NOTICE
    return text


def phone_text(text, *, home=None, truncate=True):
    """Render summaries; approval callers disable truncation so scope stays visible."""
    if not isinstance(text, str) or (not truncate and len(text) > MAX_TEXT):
        return LOCAL_NOTICE
    if 'PRIVATE KEY-----' in text or SOLICITATION.search(text):
        return LOCAL_NOTICE
    if home:
        text = text.replace(str(home), '~')
    text = ADDRESSES.sub('[address]', text)
    text = SECRETS.sub('[credential]', text)
    if len(text) > MAX_TEXT and truncate:
        text = text[:MAX_TEXT - 32] + '\nMore details stay local.'
    return safe_text(text)
