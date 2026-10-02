import importlib
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from workspace_relay import private_user_id, workspace_request


def event(user="U" + "a" * 32, source="user", text="保服", data="action=update&id=C001&status=已完成"):
    return SimpleNamespace(source=SimpleNamespace(type=source, user_id=user), message=SimpleNamespace(text=text, id="evt-1"), postback=SimpleNamespace(data=data), reply_token="test-reply")


class WorkspaceRelayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # No credentials, background initialization, Google calls or LINE requests in tests.
        with patch.dict(os.environ, {"LINE_CHANNEL_ACCESS_TOKEN": "test-token", "LINE_CHANNEL_SECRET": "test-secret"}), patch("os.path.exists", return_value=False), patch("threading.Thread.start"):
            cls.app = importlib.import_module("app")

    def test_groups_never_have_a_private_identity(self):
        self.assertIsNone(private_user_id(event(source="group")))
        self.assertIsNone(private_user_id(event(source="room")))

    def test_transport_cannot_accept_database_or_tenant_overrides(self):
        with patch.dict(os.environ, {"LINE_BRIDGE_SECRET": "test"}), patch("workspace_relay.post_json", return_value=(200, {"ok": True})) as post:
            workspace_request("line-a", "context", tenantId="other", database="owner", lineUserId="other")
        payload = post.call_args.args[2]
        self.assertEqual(payload, {"lineUserId": "line-a", "action": "context"})

    def test_non_owner_messages_and_old_cards_never_touch_owner_db(self):
        with patch.object(self.app, "_legacy_data_authorized", return_value=False), patch.object(self.app, "get_db") as db, patch.object(self.app, "_workspace_reply") as relay:
            self.app.handle_message(event())
            self.app.handle_postback(event())
        db.assert_not_called()
        self.assertEqual(relay.call_count, 2)

    def test_owner_unbound_and_group_requests_fail_closed(self):
        with patch.object(self.app, "_legacy_data_authorized", return_value=True), patch.object(self.app, "has_workspace", return_value=False), patch.object(self.app, "get_db") as db, patch.object(self.app, "line_bot"):
            for source in ["user", "group", "room"]:
                self.app.handle_message(event(source=source))
                self.app.handle_postback(event(source=source))
        db.assert_not_called()

    def test_new_user_case_sync_does_not_write_owner_sheet_or_push(self):
        from test_site_bridge import VALID
        with patch.dict(os.environ, {"LINE_BRIDGE_SECRET": "test"}), patch.object(self.app, "workspace_request", return_value=(200, {"ok": True})), patch.object(self.app, "_legacy_data_authorized", return_value=False), patch.object(self.app, "get_db") as db, patch.object(self.app, "line_bot") as line:
            response = self.app.app.test_client().post('/api/site-sync/cases', json=VALID, headers={"Authorization": "Bearer test"})
        self.assertEqual(response.status_code, 200)
        db.assert_not_called()
        line.push_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
