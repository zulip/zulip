from typing import Any
from unittest.mock import patch

from zerver.lib.test_classes import ZulipTestCase
from zerver.webhooks.slack.view import get_slack_sender_name


class SlackSenderNameCoverageTest(ZulipTestCase):
    def test_get_slack_sender_name_whitespace_candidates_fallback(self) -> None:
        def fake_get(url: str, get_param: str, token: str, **kwargs: Any) -> dict[str, Any]:
            if url.endswith("/users.info"):
                return {
                    "user": {
                        "name": "",  # empty username
                        "profile": {
                            "display_name_normalized": "   \t  ",  # will .strip() to empty
                            "display_name": "",
                            "real_name_normalized": "",
                            "real_name": "",
                        },
                    }
                }
            return {}  # nocoverage

        with patch("zerver.webhooks.slack.view.get_slack_api_data", side_effect=fake_get):
            assert get_slack_sender_name("U123", "xoxp-XXXX") == "Slack user"
