import importlib
import os
from unittest import mock

from zerver.lib.test_classes import ZulipTestCase
from zproject import computed_settings, config, configured_settings


class ConfigTest(ZulipTestCase):
    def test_get_mandatory_secret_succeed(self) -> None:
        secret = config.get_mandatory_secret("shared_secret")
        self.assertGreater(len(secret), 0)

    def test_get_mandatory_secret_failed(self) -> None:
        with self.assertRaisesRegex(config.ZulipSettingsError, "nonexistent"):
            config.get_mandatory_secret("nonexistent")

    def test_disable_mandatory_secret_check(self) -> None:
        with mock.patch.dict(os.environ, {"DISABLE_MANDATORY_SECRET_CHECK": "True"}):
            secret = config.get_mandatory_secret("nonexistent")
        self.assertEqual(secret, "")


class ComputedSettingsTest(ZulipTestCase):
    def test_legacy_avatar_uri_fallback(self) -> None:
        self.addCleanup(importlib.reload, computed_settings)

        # Fall back to legacy DEFAULT_AVATAR_URI when DEFAULT_AVATAR_URL is not set
        with (
            mock.patch.object(configured_settings, "DEFAULT_AVATAR_URL", None),
            mock.patch.object(
                configured_settings, "DEFAULT_AVATAR_URI", "http://example.com/legacy-avatar.svg"
            ),
        ):
            importlib.reload(computed_settings)
            self.assertEqual(
                computed_settings.DEFAULT_AVATAR_URL,
                "http://example.com/legacy-avatar.svg",
            )

        # Canonical DEFAULT_AVATAR_URL takes precedence when both are set
        with (
            mock.patch.object(
                configured_settings,
                "DEFAULT_AVATAR_URL",
                "http://example.com/canonical-avatar.svg",
            ),
            mock.patch.object(
                configured_settings, "DEFAULT_AVATAR_URI", "http://example.com/legacy-avatar.svg"
            ),
        ):
            importlib.reload(computed_settings)
            self.assertEqual(
                computed_settings.DEFAULT_AVATAR_URL,
                "http://example.com/canonical-avatar.svg",
            )
