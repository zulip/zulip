from smtplib import SMTP, SMTPDataError, SMTPException, SMTPRecipientsRefused
from unittest import mock

from django.core.mail.backends.locmem import EmailBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend
from django.core.mail.message import sanitize_address

from zerver.lib.send_email import (
    EmailNotDeliveredException,
    FromAddress,
    build_email,
    initialize_connection,
    logger,
    send_email,
)
from zerver.lib.test_classes import ZulipTestCase


class TestBuildEmail(ZulipTestCase):
    def test_build_SES_compatible_From_field_limit(self) -> None:
        hamlet = self.example_user("hamlet")
        limit_length_name = "a" * (320 - len(sanitize_address(FromAddress.NOREPLY, "utf-8")) - 3)
        mail = build_email(
            "zerver/emails/password_reset",
            to_emails=[hamlet],
            from_name=limit_length_name,
            from_address=FromAddress.NOREPLY,
            language="en",
        )
        self.assertEqual(mail.extra_headers["From"], f"{limit_length_name} <{FromAddress.NOREPLY}>")

    def test_build_and_send_SES_incompatible_From_address(self) -> None:
        hamlet = self.example_user("hamlet")
        from_name = "Zulip"
        # Address by itself is > 320 bytes even without the name. Should trigger exception.
        overly_long_address = "a" * 320 + "@zulip.com"
        mail = build_email(
            "zerver/emails/password_reset",
            to_emails=[hamlet],
            from_name=from_name,
            from_address=overly_long_address,
            language="en",
        )
        self.assertEqual(mail.extra_headers["From"], overly_long_address)
        self.assertGreater(len(sanitize_address(mail.extra_headers["From"], "utf-8")), 320)

        with mock.patch.object(
            EmailBackend, "send_messages", side_effect=SMTPDataError(242, "From field too long.")
        ):
            with self.assertLogs(logger=logger) as info_log:
                with self.assertRaises(EmailNotDeliveredException):
                    send_email(
                        "zerver/emails/password_reset",
                        to_emails=[hamlet],
                        from_name=from_name,
                        from_address=overly_long_address,
                        language="en",
                    )
        self.assert_length(info_log.records, 2)
        self.assertEqual(
            info_log.output[0], f"INFO:{logger.name}:Sending password_reset email to {mail.to}"
        )
        self.assertTrue(
            info_log.output[1].startswith(
                f"ERROR:{logger.name}:Error sending password_reset email to {mail.to} with error code 242: From field too long."
            )
        )

    def test_build_and_send_refused(self) -> None:
        hamlet = self.example_user("hamlet")
        address = "zulip@example.com"
        with mock.patch.object(
            EmailBackend,
            "send_messages",
            side_effect=SMTPRecipientsRefused(recipients={address: (550, b"User unknown")}),
        ):
            with self.assertLogs(logger=logger) as info_log:
                with self.assertRaises(EmailNotDeliveredException):
                    send_email(
                        "zerver/emails/password_reset",
                        to_emails=[hamlet],
                        from_name="Zulip",
                        from_address=address,
                        language="en",
                    )
        self.assert_length(info_log.records, 2)
        self.assertEqual(
            info_log.output[0], f"INFO:{logger.name}:Sending password_reset email to {[hamlet]}"
        )
        self.assertFalse(
            info_log.output[1].startswith(
                f"ERROR:{logger.name}:Error sending password_reset email to {[hamlet]}: {{'{address}': (550, 'User unknown')}}"
            )
        )


class TestSendEmail(ZulipTestCase):
    def test_initialize_connection(self) -> None:
        # Test the new connection case
        with mock.patch.object(EmailBackend, "open", return_value=True):
            backend = initialize_connection(None)
            self.assertTrue(isinstance(backend, EmailBackend))

        backend = mock.MagicMock(spec=SMTPBackend)
        backend.connection = mock.MagicMock(spec=SMTP)

        self.assertTrue(isinstance(backend, SMTPBackend))

        # Test the old connection case when it is still open
        backend.open.return_value = False
        backend.connection.noop.return_value = [250]
        initialize_connection(backend)
        self.assertEqual(backend.open.call_count, 1)
        self.assertEqual(backend.connection.noop.call_count, 1)

        # Test the old connection case when it was closed by the server
        backend.connection.noop.return_value = [404]
        backend.close.return_value = False
        initialize_connection(backend)
        # 2 more calls to open, 1 more call to noop and 1 call to close
        self.assertEqual(backend.open.call_count, 3)
        self.assertEqual(backend.connection.noop.call_count, 2)
        self.assertEqual(backend.close.call_count, 1)

        # Test backoff procedure
        backend.open.side_effect = OSError
        with self.assertRaises(OSError):
            initialize_connection(backend)
        # 3 more calls to open as we try 3 times before giving up
        self.assertEqual(backend.open.call_count, 6)

    def test_send_email_exceptions(self) -> None:
        hamlet = self.example_user("hamlet")
        from_name = FromAddress.security_email_from_name(language="en")
        # Used to check the output
        mail = build_email(
            "zerver/emails/password_reset",
            to_emails=[hamlet],
            from_name=from_name,
            from_address=FromAddress.NOREPLY,
            language="en",
        )
        self.assertEqual(mail.extra_headers["From"], f"{from_name} <{FromAddress.NOREPLY}>")

        # We test the two cases that should raise an EmailNotDeliveredException
        errors = {
            f"Unknown error sending password_reset email to {mail.to}": [0],
            f"Error sending password_reset email to {mail.to}": [SMTPException()],
        }

        for message, side_effect in errors.items():
            with mock.patch.object(EmailBackend, "send_messages", side_effect=side_effect):
                with self.assertLogs(logger=logger) as info_log:
                    with self.assertRaises(EmailNotDeliveredException):
                        send_email(
                            "zerver/emails/password_reset",
                            to_emails=[hamlet],
                            from_name=from_name,
                            from_address=FromAddress.NOREPLY,
                            language="en",
                        )
                self.assert_length(info_log.records, 2)
                self.assertEqual(
                    info_log.output[0],
                    f"INFO:{logger.name}:Sending password_reset email to {mail.to}",
                )
                self.assertTrue(info_log.output[1].startswith(f"ERROR:zulip.send_email:{message}"))
