import logging

# Assuming ZulipTestCase is imported from test_classes, as per the Zulip codebase.
from zerver.lib.test_classes import ZulipTestCase


class TestAssertNoLogs(ZulipTestCase):
    def test_no_logs_success(self) -> None:
        """
        Test case where no logs are emitted inside the context manager, 
        which should pass without raising an AssertionError.
        """
        logger = logging.getLogger("zulip.testlogger.success")

        # The test should pass as no messages at the default level (DEBUG) or higher are logged.
        with self.assertNoLogs("zulip.testlogger.success"):
            logger.debug("A debug message")
            logger.info("An info message")

    def test_logs_fail(self) -> None:
        """
        Test case where a log is emitted, which should correctly raise an AssertionError.
        """
        logger_name = "zulip.testlogger.fail"
        logger = logging.getLogger(logger_name)

        try:
            with self.assertNoLogs(logger_name, level=logging.WARNING):
                # This log is WARNING level, so it should be caught and cause a failure.
                logger.warning("Something happened that should be caught")
                # This log is below the WARNING level, so it should be ignored by the handler.
                logger.info("This info message should not be in the error output")
        except AssertionError as e:
            # Assert that the captured log message is in the error output
            self.assertIn("Something happened that should be caught", str(e))
            # Assert that the format of the message is also correct
            self.assertIn("WARNING: Something happened that should be caught", str(e))
            # Assert that the message below the 'level' threshold was correctly ignored
            self.assertNotIn("info message", str(e))
            return

        # If no AssertionError was raised, explicitly fail the test
        self.fail("assertNoLogs did not detect logged messages and did not raise AssertionError")