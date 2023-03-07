from smtplib import SMTP, SMTPDataError, SMTPException, SMTPRecipientsRefused
from unittest import mock

from django.core.mail.backends.locmem import EmailBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend
from django.core.mail.message import sanitize_address

from zerver.lib.send_email import (
    EmailNotDeliveredError,
    FromAddress,
    build_email,
    initialize_connection,
    logger,
    send_email,
)
from zerver.lib.test_classes import ZulipTestCase


class TestBuildEmail(ZulipTestCase):
    def test_limited_from_length(self) -> None:
        hamlet = self.example_user("hamlet")
        # This is exactly the max length
        limit_length_name = "a" * (320 - len(sanitize_address(FromAddress.NOREPLY, "utf-8")) - 3)
        mail = build_email(
            "zerver/emails/password_reset",
            to_emails=[hamlet.email],
            from_name=limit_length_name,
            from_address=FromAddress.NOREPLY,
            language="en",
        )
        self.assertEqual(mail.extra_headers["From"], f"{limit_length_name} <{FromAddress.NOREPLY}>")

        # One more character makes it flip to just the address, with no name
        mail = build_email(
            "zerver/emails/password_reset",
            to_emails=[hamlet.email],
            from_name=limit_length_name + "a",
            from_address=FromAddress.NOREPLY,
            language="en",
        )
        self.assertEqual(mail.extra_headers["From"], FromAddress.NOREPLY)

    def test_limited_to_length(self) -> None:
        hamlet = self.example_user("hamlet")
        # This is exactly the max length
        limit_length_name = "澳" * 61
        hamlet.full_name = limit_length_name
        hamlet.save()

        mail = build_email(
            "zerver/emails/password_reset",
            to_user_ids=[hamlet.id],
            from_name="Noreply",
            from_address=FromAddress.NOREPLY,
            language="en",
        )
        self.assertEqual(mail.to[0], f"{hamlet.full_name} <{hamlet.delivery_email}>")

        # One more character makes it flip to just the address, with no name
        hamlet.full_name += "澳"
        hamlet.save()
        mail = build_email(
            "zerver/emails/password_reset",
            to_user_ids=[hamlet.id],
            from_name="Noreply",
            from_address=FromAddress.NOREPLY,
            language="en",
        )
        self.assertEqual(mail.to[0], hamlet.delivery_email)


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
        address = FromAddress.NOREPLY
        # Used to check the output
        mail = build_email(
            "zerver/emails/password_reset",
            to_emails=[hamlet.email],
            from_name=from_name,
            from_address=address,
            language="en",
        )
        self.assertEqual(mail.extra_headers["From"], f"{from_name} <{FromAddress.NOREPLY}>")

        # We test the cases that should raise an EmailNotDeliveredError
        errors = {
            f"Unknown error sending password_reset email to {mail.to}": [0],
            f"Error sending password_reset email to {mail.to}": [SMTPException()],
            f"Error sending password_reset email to {mail.to}: {{'{address}': (550, b'User unknown')}}": [
                SMTPRecipientsRefused(recipients={address: (550, b"User unknown")})
            ],
            f"Error sending password_reset email to {mail.to} with error code 242: From field too long": [
                SMTPDataError(242, "From field too long.")
            ],
        }

        for message, side_effect in errors.items():
            with mock.patch.object(EmailBackend, "send_messages", side_effect=side_effect):
                with self.assertLogs(logger=logger) as info_log:
                    with self.assertRaises(EmailNotDeliveredError):
                        send_email(
                            "zerver/emails/password_reset",
                            to_emails=[hamlet.email],
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

    def test_send_email_config_error_logging(self) -> None:
        hamlet = self.example_user("hamlet")

        with self.settings(EMAIL_HOST_USER="test", EMAIL_HOST_PASSWORD=None):
            with self.assertLogs(logger=logger, level="ERROR") as error_log:
                send_email(
                    "zerver/emails/password_reset",
                    to_emails=[hamlet.email],
                    from_name="From Name",
                    from_address=FromAddress.NOREPLY,
                    language="en",
                )

        self.assertEqual(
            error_log.output,
            [
                "ERROR:zulip.send_email:"
                "An SMTP username was set (EMAIL_HOST_USER), but password is unset (EMAIL_HOST_PASSWORD).  "
                "To disable SMTP authentication, set EMAIL_HOST_USER to an empty string."
            ],
        )

        # Empty string is OK
        with self.settings(EMAIL_HOST_USER="test", EMAIL_HOST_PASSWORD=""):
            send_email(
                "zerver/emails/password_reset",
                to_emails=[hamlet.email],
                from_name="From Name",
                from_address=FromAddress.NOREPLY,
                language="en",
            )
