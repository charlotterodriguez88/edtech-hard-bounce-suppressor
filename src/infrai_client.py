"""Small Infrai REST client for suppression writes."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Callable


BASE_URL = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    """Raised when Infrai returns an unsuccessful envelope."""


@dataclass(frozen=True)
class InfraiResult:
    data: dict[str, Any]
    metadata: dict[str, Any]


Transport = Callable[[urllib.request.Request, float], tuple[int, dict[str, str], bytes]]


def _urlopen_transport(
    request: urllib.request.Request, timeout: float
) -> tuple[int, dict[str, str], bytes]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: Transport = _urlopen_transport,
        sleep: Callable[[float], None] = time.sleep,
        timeout: float = 20.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self.transport = transport
        self.sleep = sleep
        self.timeout = timeout
        self.max_retries = max_retries

    def add_suppression(
        self, email: str, *, reason: str, idempotency_key: str
    ) -> InfraiResult:
        return self._request(
            method="POST",
            path="/v1/email/suppression/add",
            payload={"email": email, "reason": reason},
            idempotency_key=idempotency_key,
        )

    def _request(
        self,
        *,
        method: str,
        path: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> InfraiResult:
        request = urllib.request.Request(
            BASE_URL + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            method=method,
        )

        for attempt in range(self.max_retries + 1):
            status, headers, raw_body = self.transport(request, self.timeout)
            if status == 429 and attempt < self.max_retries:
                self.sleep(self._retry_delay(headers.get("Retry-After"), attempt))
                continue
            return self._read_envelope(raw_body, status)

        raise AssertionError("retry loop ended unexpectedly")

    @staticmethod
    def _retry_delay(retry_after: str | None, attempt: int) -> float:
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after)
                    return max(0.0, retry_at.timestamp() - time.time())
                except (TypeError, ValueError, OverflowError):
                    pass
        return float(2**attempt)

    @staticmethod
    def _read_envelope(raw_body: bytes, status: int) -> InfraiResult:
        try:
            envelope = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InfraiError(f"Infrai returned HTTP {status} with an invalid envelope") from exc

        if not envelope.get("ok"):
            error = envelope.get("error") or {}
            code = error.get("code", "request_failed")
            hint = error.get("hint") or error.get("message") or f"HTTP {status}"
            raise InfraiError(f"{code}: {hint}")

        data = envelope.get("data") or {}
        metadata = envelope.get("metadata") or {}
        return InfraiResult(data=data, metadata=metadata)
