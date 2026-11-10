"""Protocol 1 admission for complete legacy operations. No credentials are persisted.

An admitted operation is never retried here. Unknown write results leave an
unresolved broker lease; only an operator can reconcile that lease.
"""
import functools
import json
import os
import re
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PROTOCOL = 1
DEFAULT_SITE_BASE_URL = "https://claims-assistant.waynechiuchiu.chatgpt.site"
SITE_BROKER_URL = DEFAULT_SITE_BASE_URL + "/api/migration/legacy-writer"
_local = threading.local()
# Only these fixed strings may leave an admission failure boundary. Never pass
# through HTTP bodies, exception text, URLs, credentials, JWTs or OIDC claims.
_LOCAL_DIAGNOSTICS = frozenset({
    "INVALID_ADMISSION_ORIGIN", "INVALID_LEGACY_CLIENT", "ADMISSION_NETWORK_UNAVAILABLE",
    "INVALID_ADMISSION_RESPONSE", "BRIDGE_AUTH_NOT_CONFIGURED", "ACTIONS_OIDC_NOT_CONFIGURED",
    "ACTIONS_OIDC_UNAVAILABLE", "ADMISSION_NOT_CONFIRMED", "ADMISSION_STATUS_NOT_CONFIRMED",
    "LEGACY_OPERATION_UNCERTAIN", "PROBE_RELEASE_NOT_CONFIRMED",
    "SITES_SERVICE_ACCESS_NOT_CONFIGURED", "SITES_SERVICE_ACCESS_INVALID",
})
_BROKER_DIAGNOSTICS = frozenset({
    "INVALID_INPUT", "FORBIDDEN", "LEGACY_OWNER_UNAVAILABLE", "LEGACY_FROZEN",
    "TOO_MANY_UNRESOLVED_WRITERS", "WRITER_ID_CONFLICT", "OPERATION_ALREADY_FINISHED",
    "WRITER_NOT_FOUND", "WRITER_OUTCOME_CONFLICT", "INVALID_RESPONSE", "UNRECOGNIZED_ERROR",
})


class LegacyWriterError(RuntimeError):
    """Admission was refused or could not be positively confirmed."""


class LegacyFrozen(LegacyWriterError):
    pass


class LegacyUnavailable(LegacyWriterError):
    pass


def _http_diagnostic(status, body):
    if type(status) is not int or not 100 <= status <= 599:
        return "ADMISSION_NOT_CONFIRMED"
    code = body.get("error") if isinstance(body, dict) else None
    if type(code) is not str or code not in _BROKER_DIAGNOSTICS:
        code = "UNRECOGNIZED_ERROR" if code is not None else "INVALID_RESPONSE"
    return "ADMISSION_HTTP_" + str(status) + "_" + code


def _safe_diagnostic(error):
    # Inspect only an exact built-in string argument, never str(error), which
    # can execute custom formatting or expose a transport's request/body.
    if isinstance(error, LegacyUnavailable) and len(error.args) == 1 and type(error.args[0]) is str:
        code = error.args[0]
        if code in _LOCAL_DIAGNOSTICS:
            return code
        match = re.fullmatch(r"ADMISSION_HTTP_([1-5][0-9]{2})_([A-Z_]+)", code)
        if match and match.group(2) in _BROKER_DIAGNOSTICS:
            return code
    return "ADMISSION_NOT_CONFIRMED"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a bridge secret or Actions token to a redirect target.
        return None


def endpoint():
    base = os.environ.get("SITE_BASE_URL", DEFAULT_SITE_BASE_URL).rstrip("/")
    try:
        parsed = urlsplit(base)
        valid = (parsed.scheme == "https" and
                 parsed.hostname == "claims-assistant.waynechiuchiu.chatgpt.site" and
                 parsed.port in (None, 443) and not parsed.username and not parsed.password and
                 not parsed.query and not parsed.fragment and parsed.path in ("", "/"))
    except Exception:
        valid = False
    if not valid:
        raise LegacyUnavailable("INVALID_ADMISSION_ORIGIN")
    return SITE_BROKER_URL


def _service_access_token():
    token = os.environ.get("SITES_SERVICE_ACCESS_TOKEN", "").strip()
    if not token:
        raise LegacyUnavailable("SITES_SERVICE_ACCESS_NOT_CONFIGURED")
    if len(token) > 16384 or not re.fullmatch(r"[!-~]+", token):
        raise LegacyUnavailable("SITES_SERVICE_ACCESS_INVALID")
    return token


def revision(client):
    if client not in ("bot", "watcher"):
        raise LegacyUnavailable("INVALID_LEGACY_CLIENT")
    value = os.environ.get("RAILWAY_GIT_COMMIT_SHA" if client == "bot" else "GITHUB_SHA", "")
    return value.lower() if re.fullmatch(r"[0-9a-fA-F]{40}", value) else "unreported"


def _request_json(url, token, payload=None):
    # Only the exact canonical broker URL may receive the Sites service token.
    # Admission POSTs to another host/path fail before any credentials are sent.
    if payload is not None and url != SITE_BROKER_URL:
        raise LegacyUnavailable("INVALID_ADMISSION_ORIGIN")
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    # Sites reserves Authorization for its edge login flow. Carry only the
    # watcher's broker OIDC token separately; GitHub token retrieval and the
    # Bot bridge continue to use the standard Authorization header.
    authorization_header = "X-Legacy-Writer-Authorization" if isinstance(payload, dict) and payload.get("client") == "watcher" else "Authorization"
    headers = {
        authorization_header: "Bearer " + token, "Accept": "application/json",
        "Content-Type": "application/json", "Cache-Control": "no-store",
    }
    if url == SITE_BROKER_URL:
        headers["OAI-Sites-Authorization"] = "Bearer " + _service_access_token()
    req = Request(url, data=data, method="GET" if payload is None else "POST", headers=headers)
    try:
        response = build_opener(_NoRedirect()).open(req, timeout=20)
    except HTTPError as error:
        response = error
    except Exception:
        raise LegacyUnavailable("ADMISSION_NETWORK_UNAVAILABLE") from None
    with response:
        try:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError()
            result = json.loads(raw.decode("utf-8"))
            if not isinstance(result, dict):
                raise ValueError()
        except Exception:
            raise LegacyUnavailable("INVALID_ADMISSION_RESPONSE") from None
        return response.code, result


def _authorization(client, audience):
    if client not in ("bot", "watcher"):
        raise LegacyUnavailable("INVALID_LEGACY_CLIENT")
    if audience != SITE_BROKER_URL:
        raise LegacyUnavailable("INVALID_ADMISSION_ORIGIN")
    # Fail before retrieving an OIDC token or starting any customer operation.
    _service_access_token()
    if client == "bot":
        token = os.environ.get("LINE_BRIDGE_SECRET", "").strip()
        if not token:
            raise LegacyUnavailable("BRIDGE_AUTH_NOT_CONFIGURED")
        return token
    # Official GitHub Actions OIDC request variables. The exact broker URL is aud.
    # https://docs.github.com/en/actions/reference/security/oidc
    url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    request_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or
            not parsed.hostname.endswith(".actions.githubusercontent.com") or
            parsed.username or parsed.password or parsed.fragment or not request_token):
        raise LegacyUnavailable("ACTIONS_OIDC_NOT_CONFIGURED")
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != "audience"]
    query.append(("audience", audience))
    url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))
    status, body = _request_json(url, request_token)
    token = body.get("value")
    if status != 200 or not isinstance(token, str) or not token.strip():
        raise LegacyUnavailable("ACTIONS_OIDC_UNAVAILABLE")
    return token


def _exchange(client, request_id, action, outcome=None):
    url = endpoint()
    payload = {"client": client, "action": action, "requestId": request_id, "revision": revision(client)}
    if outcome:
        payload["outcome"] = outcome
    token = _authorization(client, url)
    status, body = _request_json(url, token, payload)
    if action == "acquire" and status == 409 and body.get("error") == "LEGACY_FROZEN":
        raise LegacyFrozen("LEGACY_FROZEN")
    if (status != 200 or body.get("ok") is not True or
            type(body.get("protocol")) is not int or body["protocol"] != PROTOCOL or
            body.get("leaseId") != request_id):
        raise LegacyUnavailable(_http_diagnostic(status, body))


def _release(client, request_id, outcome):
    try:
        _exchange(client, request_id, "release", outcome)
        return True
    except Exception as error:
        # Deliberately never log a token, HTTP body, customer record, or credentials.
        print("[Migration] Legacy lease release unconfirmed; reconciliation required: " + _safe_diagnostic(error), flush=True)
        return False


def broker_status(client="bot"):
    url = endpoint()
    payload = {"client": client, "action": "status", "requestId": str(uuid.uuid4()), "revision": revision(client)}
    status, body = _request_json(url, _authorization(client, url), payload)
    if status != 200:
        raise LegacyUnavailable(_http_diagnostic(status, body))
    phase, freeze_id = body.get("phase"), body.get("freezeId")
    if (body.get("ok") is not True or type(body.get("protocol")) is not int or
            body["protocol"] != PROTOCOL or phase not in ("open", "closing", "frozen") or
            (freeze_id is not None and not isinstance(freeze_id, str)) or
            (phase == "frozen" and not freeze_id)):
        raise LegacyUnavailable("ADMISSION_STATUS_NOT_CONFIRMED")
    result = {"protocol": PROTOCOL, "phase": phase, "freezeId": freeze_id}
    for key in ("activeWriters", "uncertainWriters"):
        count = body.get(key)
        if type(count) is not int or count < 0:
            raise LegacyUnavailable("ADMISSION_STATUS_NOT_CONFIRMED")
        result[key] = count
    if phase == "frozen" and (result["activeWriters"] or result["uncertainWriters"]):
        raise LegacyUnavailable("ADMISSION_STATUS_NOT_CONFIRMED")
    return result


@dataclass
class _Lease:
    client: str
    request_id: str
    writes_attempted: bool = False
    uncertain: bool = False
    release_confirmed: bool = False


def mark_uncertain():
    lease = getattr(_local, "lease", None)
    if lease is not None:
        lease.uncertain = True


@contextmanager
def operation(client):
    """Acquire once for a logical operation; nested transport writes inherit it."""
    current = getattr(_local, "lease", None)
    if current is not None:
        if current.client != client or current.uncertain:
            raise LegacyUnavailable("LEGACY_OPERATION_UNCERTAIN")
        yield current
        return
    request_id = str(uuid.uuid4())
    try:
        _exchange(client, request_id, "acquire")
    except LegacyFrozen:
        raise
    except Exception as error:
        # The acquire may have reached the broker. No legacy work has been sent.
        _release(client, request_id, "aborted")
        raise LegacyUnavailable(_safe_diagnostic(error)) from None
    lease = _Lease(client, request_id)
    _local.lease = lease
    failed = False
    try:
        yield lease
    except BaseException:
        failed = True
        raise
    finally:
        _local.lease = None
        outcome = "uncertain" if lease.uncertain else ("aborted" if failed and not lease.writes_attempted else "completed")
        lease.release_confirmed = _release(client, request_id, outcome)


def legacy_operation(client):
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            with operation(client):
                return fn(*args, **kwargs)
        return wrapped
    return decorate


def sheet_operation(fn):
    """Logical Bot DB mutator, including initialization and hidden read repairs."""
    @functools.wraps(fn)
    def wrapped(self, *args, **kwargs):
        if getattr(self, "readonly", False):
            raise LegacyFrozen("READ_ONLY_LEGACY_CONNECTION")
        with operation("bot"):
            return fn(self, *args, **kwargs)
    return wrapped


def guard_gspread_client(client, legacy_client, readonly=False):
    """Guard every transport mutation, including batch/header/delete/init writes."""
    transport = getattr(client, "http_client", client)
    original = getattr(transport, "request", None)
    if not callable(original):
        raise LegacyUnavailable("UNSUPPORTED_GSPREAD_TRANSPORT")
    existing = getattr(transport, "_legacy_writer_guard", None)
    if existing:
        if existing != (legacy_client, readonly):
            raise LegacyUnavailable("GSPREAD_GUARD_CONFLICT")
        return client

    @functools.wraps(original)
    def guarded(method, *args, **kwargs):
        if str(method).upper() in ("GET", "HEAD"):
            return original(method, *args, **kwargs)
        if readonly:
            raise LegacyFrozen("READ_ONLY_LEGACY_CONNECTION")
        with operation(legacy_client) as lease:
            lease.writes_attempted = True
            try:
                return original(method, *args, **kwargs)
            except BaseException:
                lease.uncertain = True
                raise
    transport.request = guarded
    transport._legacy_writer_guard = (legacy_client, readonly)
    return client


def migration_notice():
    return "既有資料已進入網站移轉保護，請到工作台查看及操作：" + os.environ.get("SITE_BASE_URL", DEFAULT_SITE_BASE_URL).rstrip("/")


def probe(client="watcher"):
    """No customer reads, login, crawler import, or legacy mutation."""
    with operation(client) as lease:
        pass
    if not lease.release_confirmed:
        raise LegacyUnavailable("PROBE_RELEASE_NOT_CONFIRMED")
