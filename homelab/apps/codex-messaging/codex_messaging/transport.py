"""Use bounded Telegram HTTPS and local broker requests without exposing credentials."""

import asyncio
import contextlib
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

from .operations import PolicyError
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


class BrokerClient:
    """Only the coordinator can reach this local socket; methods are not chat-selected RPC."""

    def __init__(self, socket_path):
        self.socket_path = socket_path

    async def _call(self, method, arguments):
        reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(self.socket_path, limit=128_000), timeout=5)
        try:
            writer.write(json.dumps({"version": 1, "method": method, "arguments": arguments}).encode() + b"\n")
            await writer.drain()
            raw = await asyncio.wait_for(reader.readline(), timeout=45)
            reply = json.loads(raw)
            if not isinstance(reply, dict) or reply.get("ok") is not True:
                code = reply.get("error") if isinstance(reply, dict) else None
                raise PolicyError(code if isinstance(code, str) and re.fullmatch(r"[a-z_]{1,60}", code) else "broker_unavailable")
            return reply.get("result")
        except (ValueError, asyncio.LimitOverrunError):
            raise ConnectionError("broker_protocol") from None
        finally:
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()

    async def prepare(self, user_id, chat_id, target, operation, parameters):
        return await self._call("prepare", {"user_id": user_id, "chat_id": chat_id, "target_alias": target,
                                            "operation": operation, "parameters": parameters})

    async def approve(self, user_id, chat_id, approval_id, digest):
        return await self._call("approve", {"user_id": user_id, "chat_id": chat_id,
                                            "approval_id": approval_id, "plan_digest": digest})

    async def diagnose(self, user_id, chat_id, target, parameters):
        return await self._call("diagnose", {"user_id": user_id, "chat_id": chat_id, "target_alias": target,
                                             "parameters": parameters})

    async def pause(self):
        return await self._call("pause", {})

    async def resume(self):
        return await self._call("resume", {})

    async def stop(self):
        return await self._call("stop", {})

    async def status(self, job_id):
        return await self._call("status", {"job_id": job_id})

    async def reconcile(self, job_id):
        return await self._call("reconcile", {"job_id": job_id})

    async def recoverable_jobs(self):
        return await self._call("recoverable_jobs", {})
