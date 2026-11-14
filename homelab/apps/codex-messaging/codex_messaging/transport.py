"""Use bounded outbound Telegram HTTPS without exposing credentials in errors."""

import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

from .presentation import safe_text


class TransportRejected(Exception):
    """Return only safe error categories, never credential-bearing request URLs."""

    def __init__(self, code, retry_after=5):
        self.code, self.retry_after = code, retry_after
        super().__init__(code)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class Telegram:
    """The product uses Telegram only; loopback dependency injection serves offline tests."""

    def __init__(self, token, *, fixture_endpoint=None):
        if not isinstance(token, str) or not re.fullmatch(r"[0-9]{4,20}:[A-Za-z0-9_-]{20,100}", token):
            raise TransportRejected("telegram_token")
        endpoint = "https://api.telegram.org"
        if fixture_endpoint is not None:
            parsed = urllib.parse.urlsplit(fixture_endpoint)
            if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                raise TransportRejected("fixture_endpoint")
            endpoint = fixture_endpoint
        self._base = endpoint + "/bot" + token + "/"
        self._http = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect(),
                                                urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def _call(self, method, body):
        if method not in {"getUpdates", "sendMessage", "answerCallbackQuery"}:
            raise TransportRejected("telegram_method")
        request = urllib.request.Request(self._base + method, json.dumps(body).encode(),
                                         {"Content-Type": "application/json"}, method="POST")
        try:
            with self._http.open(request, timeout=35) as response:
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise TransportRejected("telegram_response")
            result = json.loads(raw)
            if not isinstance(result, dict) or result.get("ok") is not True:
                raise TransportRejected("telegram_rejected")
            return result.get("result")
        except urllib.error.HTTPError as error:
            raise TransportRejected("telegram_rate_limited" if error.code == 429 else "telegram_unavailable") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise TransportRejected("telegram_unavailable") from None

    def get_updates(self, offset):
        result = self._call("getUpdates", {"offset": offset, "timeout": 20, "limit": 100,
                                          "allowed_updates": ["message", "callback_query"]})
        if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
            raise TransportRejected("telegram_response")
        return result

    def send_message(self, body):
        if not set(body) <= {"chat_id", "text", "reply_markup"} or type(body.get("chat_id")) is not int:
            raise TransportRejected("telegram_message")
        if body.get("text") != safe_text(body.get("text")):
            raise TransportRejected("telegram_private_output")
        return self._call("sendMessage", {**body, "link_preview_options": {"is_disabled": True}})
