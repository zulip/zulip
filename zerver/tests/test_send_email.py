from datetime import timedelta
from smtplib import SMTP, SMTPDataError, SMTPException, SMTPRecipientsRefused
from unittest import mock

import time_machine
from django.core.mail.backends.locmem import EmailBackend
from django.core.mail.message import sanitize_address
from django.test import override_settings
from django.utils.timezone import now as timezone_now

from zerver.lib.send_email import (
    EmailNotDeliveredError,
    FromAddress,
    build_email,
    initialize_connection,
    logger,
    send_email,
)
from zerver.lib.test_classes import ZulipTestCase
from zproject.email_backends import PersistentSMTPEmailBackend


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
    @override_settings(EMAIL_MAX_CONNECTION_LIFETIME_IN_MINUTES=None)
    @time_machine.travel(timezone_now(), tick=False)
    def test_initialize_connection(self) -> None:
        # Test the new connection case
        with mock.patch.object(EmailBackend, "open", return_value=True):
            backend = initialize_connection(None)
            self.assertTrue(isinstance(backend, EmailBackend))

        backend = mock.MagicMock(spec=PersistentSMTPEmailBackend)
        backend.connection = mock.MagicMock(spec=SMTP)

        self.assertTrue(isinstance(backend, PersistentSMTPEmailBackend))

        # Test the old connection case when it is still open
        backend.open.return_value = False
        backend.connection.noop.return_value = [250]

        with mock.patch.object(backend, "opened_at", timezone_now(), create=True):
            initialize_connection(backend)

        self.assertEqual(backend.open.call_count, 1)
        self.assertEqual(backend.connection.noop.call_count, 1)

        # Test the old connection case when it was closed by the server
        backend.connection.noop.return_value = [404]
        backend.close.return_value = False

        with mock.patch.object(backend, "opened_at", timezone_now(), create=True):
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

    @time_machine.travel(timezone_now(), tick=False)
    def test_max_connection_lifetime(self) -> None:
        backend = PersistentSMTPEmailBackend()
        backend.open()
        self.assertEqual(backend.opened_at, timezone_now())

        with mock.patch.object(backend, "open", wraps=backend.open) as open_call, mock.patch.object(
            backend, "close", wraps=backend.close
        ) as close_call:
            # Old connection is open, but we still reopen a new connection because max connection lifetime is 0.
            backend.connection = mock.MagicMock(spec=SMTP)
            backend.connection.noop.return_value = [250]
            initialize_connection(backend)

            self.assertEqual(close_call.call_count, 1)
            self.assertEqual(open_call.call_count, 2)
            self.assertEqual(backend.opened_at, timezone_now())

            # Old connection is open, we will not open a new connection because max connection lifetime is None.
            with self.settings(EMAIL_MAX_CONNECTION_LIFETIME_IN_MINUTES=None):
                # We have to set this a second time to the same values because
                # backend.connection was overwritten in a previous
                # `initialize_connection` call in this test.
                backend.connection = mock.MagicMock(spec=SMTP)
                backend.connection.noop.return_value = [250]
                initialize_connection(backend)

            self.assertEqual(close_call.call_count, 1)
            # The increase in open.call_count by 1 is caused by us calling connection.open()
            # to check whether an open connection already exists. In case of actually opening
            # a new connection, the call count will increase by 2.
            self.assertEqual(open_call.call_count, 3)

            # Old connection is open, we will not open a new connection because not enough time has elapsed.
            with self.settings(EMAIL_MAX_CONNECTION_LIFETIME_IN_MINUTES=5):
                initialize_connection(backend)

            self.assertEqual(close_call.call_count, 1)
            # The increase in open.call_count by 1 is caused by us calling connection.open()
            # to check whether an open connection already exists. In case of actually opening
            # a new connection, the call count will increase by 2.
            self.assertEqual(open_call.call_count, 4)

            # Old connection is open, we will open a new connection because max time has elapsed.
            with self.settings(EMAIL_MAX_CONNECTION_LIFETIME_IN_MINUTES=5), time_machine.travel(
                timezone_now() + timedelta(minutes=6),
                tick=False,
            ):
                self.assertEqual(backend.opened_at, timezone_now() - timedelta(minutes=6))
                initialize_connection(backend)
                self.assertEqual(backend.opened_at, timezone_now())

            self.assertEqual(close_call.call_count, 2)
            self.assertEqual(open_call.call_count, 6)

            hamlet = self.example_user("hamlet")
            with self.settings(EMAIL_HOST_USER="test", EMAIL_HOST_PASSWORD=""), mock.patch.object(
                backend, "send_messages", return_value=1
            ):
                send_email(
                    "zerver/emails/password_reset",
                    to_emails=[hamlet.email],
                    from_name="From Name",
                    from_address=FromAddress.NOREPLY,
                    language="en",
                    connection=backend,
                )
            # no more calls to open and 1 more call to close after sending the message
            # because max connection lifetime is 0
            self.assertEqual(close_call.call_count, 3)
            self.assertEqual(open_call.call_count, 6)

            with self.settings(
                EMAIL_HOST_USER="test",
                EMAIL_HOST_PASSWORD="",
                EMAIL_MAX_CONNECTION_LIFETIME_IN_MINUTES=None,
            ), mock.patch.object(backend, "send_messages", return_value=1):
                send_email(
                    "zerver/emails/password_reset",
                    to_emails=[hamlet.email],
                    from_name="From Name",
                    from_address=FromAddress.NOREPLY,
                    language="en",
                    connection=backend,
                )
            # no more calls to open and no more calls to close after sending the message
            # because max connection lifetime is None
            self.assertEqual(close_call.call_count, 3)
            self.assertEqual(open_call.call_count, 6)

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
