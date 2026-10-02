"""Shared bot transport. Identity is taken only from verified LINE events."""
import os
from site_bridge import post_json


def private_user_id(event):
    source = getattr(event, "source", None)
    if getattr(source, "type", None) != "user":
        return None
    return getattr(source, "user_id", None)


def workspace_request(line_user_id, action, **values):
    if not line_user_id:
        return 403, {}
    secret = os.environ.get("LINE_BRIDGE_SECRET", "")
    if not secret:
        return 503, {}
    base = os.environ.get("SITE_BASE_URL", "https://claims-assistant.waynechiuchiu.chatgpt.site").rstrip("/")
    # Never accept tenant IDs or database locations from a LINE message.
    allowed = {key: value for key, value in values.items() if key in {"text", "data", "eventId", "caseId"}}
    return post_json(f"{base}/api/line/relay", secret,
                     {"lineUserId": line_user_id, "action": action, **allowed}, timeout=20)


def has_workspace(line_user_id):
    status, data = workspace_request(line_user_id, "context")
    return status == 200 and data.get("ok") is True
