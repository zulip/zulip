from unittest import mock

from zerver.lib.exceptions import ServerNotReadyError
from zerver.lib.test_classes import ZulipTestCase


class HealthTest(ZulipTestCase):
    def test_healthy(self) -> None:
        # We do not actually use rabbitmq in tests, so this fails
        # unless it's mocked out.
        with mock.patch("zerver.views.health.check_rabbitmq"):
            result = self.client_get("/health")
        self.assert_json_success(result)

    def test_database_failure(self) -> None:
        with mock.patch(
            "zerver.views.health.check_database",
            side_effect=ServerNotReadyError("Cannot query postgresql"),
        ), self.assertLogs(level="ERROR") as logs:
            result = self.client_get("/health")
        self.assert_json_error(result, "Cannot query postgresql", status_code=500)
        self.assertIn(
            "zerver.lib.exceptions.ServerNotReadyError: Cannot query postgresql", logs.output[0]
        )
