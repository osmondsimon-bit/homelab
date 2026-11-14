"""Reject non-subscription execution without echoing account or credential information."""

from pathlib import Path
from decimal import Decimal, InvalidOperation


def worker_environment(context: Path, inherited: dict) -> dict:
    """Build, rather than merge, a credential-free launching environment."""
    forbidden = {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "OPENAI_BASE_URL", "CHATGPT_BASE_URL",
                 "CODEX_MODEL_PROVIDER", "CODEX_ACCESS_TOKEN", "OPENAI_ACCESS_TOKEN"}
    for name, value in inherited.items():
        if value and (name.upper() in forbidden or name.upper().endswith(("_API_KEY", "_ACCESS_TOKEN", "_BASE_URL"))):
            raise AuthenticationRejected("environment_override")
    return {"PATH": "/usr/bin:/bin", "HOME": str(context), "CODEX_HOME": str(context / ".codex"), "LANG": "C.UTF-8"}


class AuthenticationRejected(Exception):
    """Carry only a safe operational error code."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require_subscription(account_reply: dict, usage_reply: dict) -> None:
    """Require the built-in subscription backend before a model turn."""
    account = account_reply.get("account")
    included_plans = {"free", "go", "plus", "pro", "prolite", "team", "business", "enterprise", "edu", "ent26"}
    if (account_reply.get("requiresOpenaiAuth") is not True or not isinstance(account, dict)
            or account.get("type") != "chatgpt" or account.get("planType") not in included_plans):
        raise AuthenticationRejected("subscription_required")
    buckets = usage_reply.get("rateLimitsByLimitId")
    limits = buckets.get("codex", {}) if isinstance(buckets, dict) and "codex" in buckets else usage_reply.get("rateLimits") or {}
    if not isinstance(limits, dict):
        raise AuthenticationRejected("usage_unknown")
    if limits.get("rateLimitReachedType") or limits.get("spendControlReached"):
        raise AuthenticationRejected("usage_exhausted")
    seen = False
    for name in ("primary", "secondary"):
        window = limits.get(name)
        if window is None:
            continue
        if not isinstance(window, dict) or type(window.get("usedPercent")) is not int or not 0 <= window["usedPercent"] <= 100:
            raise AuthenticationRejected("usage_unknown")
        seen = True
        if window["usedPercent"] >= 100:
            raise AuthenticationRejected("usage_exhausted")
    if not seen:
        raise AuthenticationRejected("usage_unknown")
    credits = limits.get("credits")
    if (not isinstance(credits, dict) or credits.get("hasCredits") is not False
            or credits.get("unlimited") is not False):
        raise AuthenticationRejected("credit_state_requires_review")
    balance = credits.get("balance")
    if balance is not None:
        try:
            if not isinstance(balance, str) or Decimal(balance) != 0:
                raise InvalidOperation
        except InvalidOperation:
            raise AuthenticationRejected("credit_state_requires_review") from None
