"""Secure bridge helpers shared by the LINE Bot and insurance operations site."""
from __future__ import annotations

import hmac
import json
import re
from typing import Any
from urllib import error, request

CASE_FIELDS = {
    "lineUserId", "caseId", "idempotencyKey", "documentType",
    "customerDisplayName", "insurers", "createdAt", "status",
}
SENSITIVE_FIELD_FRAGMENTS = (
    "card", "credit", "expiry", "cvv", "idnumber", "identity",
    "bankaccount", "medical", "diagnosis", "accident", "pdf", "file",
)


def bearer_authorized(header: str, expected: str) -> bool:
    if not expected or not header.startswith("Bearer "):
        return False
    return hmac.compare_digest(header[7:].strip(), expected)


def validate_case_payload(payload: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(payload, dict):
        return None, "INVALID_JSON"
    unknown = set(payload) - CASE_FIELDS
    if unknown:
        lowered = {str(key).lower().replace("_", "") for key in unknown}
        if any(fragment in key for key in lowered for fragment in SENSITIVE_FIELD_FRAGMENTS):
            return None, "SENSITIVE_FIELD_REJECTED"
        return None, "UNKNOWN_FIELD"

    required = ("lineUserId", "caseId", "idempotencyKey", "documentType", "createdAt", "status")
    if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in required):
        return None, "MISSING_REQUIRED_FIELD"
    if not re.fullmatch(r"U[0-9A-Za-z]{20,64}", payload["lineUserId"].strip()):
        return None, "INVALID_LINE_USER_ID"
    if payload["documentType"] not in {"claim", "cardAuth"}:
        return None, "INVALID_DOCUMENT_TYPE"

    display_name = payload.get("customerDisplayName", "")
    insurers = payload.get("insurers", [])
    if not isinstance(display_name, str) or len(display_name) > 80:
        return None, "INVALID_DISPLAY_NAME"
    if not isinstance(insurers, list) or len(insurers) > 20 or any(not isinstance(v, str) or len(v) > 80 for v in insurers):
        return None, "INVALID_INSURERS"
    for key in ("caseId", "idempotencyKey", "createdAt", "status"):
        if len(payload[key]) > 160:
            return None, "FIELD_TOO_LONG"

    cleaned = {key: payload.get(key) for key in CASE_FIELDS}
    cleaned["lineUserId"] = cleaned["lineUserId"].strip()
    cleaned["caseId"] = cleaned["caseId"].strip()
    cleaned["idempotencyKey"] = cleaned["idempotencyKey"].strip()
    cleaned["customerDisplayName"] = display_name.strip()
    cleaned["insurers"] = [v.strip() for v in insurers if v.strip()]
    cleaned["createdAt"] = cleaned["createdAt"].strip()
    cleaned["status"] = cleaned["status"].strip()
    return cleaned, None


def post_json(url: str, bearer_secret: str, payload: dict[str, Any], timeout: int = 12) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {bearer_secret}",
            "Content-Type": "application/json",
            "User-Agent": "insurance-service-bot/secure-bridge",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read(32768)
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            return response.status, parsed if isinstance(parsed, dict) else {}
    except error.HTTPError as exc:
        raw = exc.read(32768)
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            parsed = {}
        return exc.code, parsed if isinstance(parsed, dict) else {}
    except (error.URLError, TimeoutError, OSError):
        return 0, {}


def mask_policy_number(value: Any) -> str:
    text = re.sub(r"\s+", "", str(value or ""))
    if len(text) <= 4:
        return "*" * len(text)
    return f"{text[:2]}{'*' * max(4, len(text) - 5)}{text[-3:]}"


def mask_vehicle_number(value: Any) -> str:
    text = re.sub(r"\s+", "", str(value or ""))
    if not text:
        return ""
    tail = text[-4:]
    return f"***-{tail}"
