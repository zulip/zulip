from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from typing_extensions import override

from zerver.actions.mcp_tokens import do_create_mcp_api_token
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import RealmAuditLog, UserMCPApiToken
from zerver.models.mcp import hash_mcp_api_token
from zerver.models.realm_audit_logs import AuditLogEventType


class MCPTokenTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("hamlet")

    def test_token_str(self) -> None:
        token_row, _raw = do_create_mcp_api_token(self.user, "laptop", acting_user=self.user)
        self.assertIn(self.user.delivery_email, str(token_row))

    def test_create_list_and_revoke(self) -> None:
        data = self.assert_json_success(
            self.api_post(self.user, "/api/v1/mcp_tokens", {"label": "My Client"})
        )
        token_id = data["id"]
        self.assertTrue(data["token"].startswith("zmcp_"))
        self.assertEqual(
            RealmAuditLog.objects.filter(
                modified_user=self.user, event_type=AuditLogEventType.USER_MCP_API_TOKEN_CREATED
            ).count(),
            1,
        )

        listed = self.assert_json_success(self.api_get(self.user, "/api/v1/mcp_tokens"))
        self.assertEqual([token["id"] for token in listed["tokens"]], [token_id])

        self.assert_json_success(self.api_delete(self.user, f"/api/v1/mcp_tokens/{token_id}"))
        self.assertFalse(UserMCPApiToken.objects.filter(id=token_id).exists())
        self.assertTrue(
            RealmAuditLog.objects.filter(
                modified_user=self.user, event_type=AuditLogEventType.USER_MCP_API_TOKEN_REVOKED
            ).exists()
        )

    def test_token_is_stored_only_as_a_digest(self) -> None:
        data = self.assert_json_success(
            self.api_post(self.user, "/api/v1/mcp_tokens", {"label": "client"})
        )
        token_row = UserMCPApiToken.objects.get(id=data["id"])
        self.assertEqual(token_row.token_digest, hash_mcp_api_token(data["token"]))
        self.assertNotEqual(token_row.token_digest, data["token"])

    def test_cannot_revoke_another_users_token(self) -> None:
        othello = self.example_user("othello")
        other_token, _raw = do_create_mcp_api_token(othello, "theirs", acting_user=othello)
        result = self.api_delete(self.user, f"/api/v1/mcp_tokens/{other_token.id}")
        self.assert_json_error(result, "MCP token not found.", status_code=404)
        self.assertTrue(UserMCPApiToken.objects.filter(id=other_token.id).exists())

    def test_invalid_label_is_rejected(self) -> None:
        self.assert_json_error(
            self.api_post(self.user, "/api/v1/mcp_tokens", {"label": ""}), "Invalid token label."
        )

    def test_bots_cannot_create_tokens(self) -> None:
        bot = self.example_user("default_bot")
        self.assert_json_error(
            self.api_post(bot, "/api/v1/mcp_tokens", {"label": "botclient"}),
            "Bots cannot create MCP tokens.",
        )

    def test_per_user_token_limit(self) -> None:
        for i in range(UserMCPApiToken.MAX_TOKENS_PER_USER):
            do_create_mcp_api_token(self.user, f"token {i}", acting_user=self.user)
        self.assert_json_error(
            self.api_post(self.user, "/api/v1/mcp_tokens", {"label": "one too many"}),
            "You already have the maximum number of MCP tokens.",
        )

    def test_management_command_creates_token(self) -> None:
        output = StringIO()
        call_command(
            "create_mcp_api_token",
            self.user.delivery_email,
            "-r",
            self.user.realm.string_id,
            "--label",
            "cli token",
            stdout=output,
        )
        raw_token = next(
            line for line in output.getvalue().splitlines() if line.startswith("zmcp_")
        )
        token_row = UserMCPApiToken.objects.get(user_profile=self.user, label="cli token")
        self.assertEqual(token_row.token_digest, hash_mcp_api_token(raw_token))

    def test_management_command_rejects_bots(self) -> None:
        bot = self.example_user("default_bot")
        with self.assertRaisesRegex(CommandError, "Bots cannot have MCP tokens"):
            call_command("create_mcp_api_token", bot.delivery_email, "-r", bot.realm.string_id)
