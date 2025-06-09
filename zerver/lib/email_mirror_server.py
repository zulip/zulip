import asyncio
import base64
import email
import grp
import logging
import os
import pwd
import signal
import smtplib
import socket
from collections.abc import Awaitable
from contextlib import suppress
from ssl import SSLContext, SSLError
from typing import Any

from aiosmtpd.controller import UnthreadedController
from aiosmtpd.handlers import Message as MessageHandler
from aiosmtpd.smtp import SMTP, Envelope, Session, TLSSetupException
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.mail import EmailMultiAlternatives as DjangoEmailMultiAlternatives
from typing_extensions import override

from version import ZULIP_VERSION
from zerver.lib.email_mirror import decode_stream_email_address, validate_to_address
from zerver.lib.email_mirror_helpers import (
    ZulipEmailForwardError,
    get_email_gateway_message_string_from_address,
)
from zerver.lib.exceptions import JsonableError, RateLimitedError
from zerver.lib.logging_util import log_to_file
from zerver.lib.queue import queue_json_publish_rollback_unsafe

logger = logging.getLogger("zerver.lib.email_mirror")
log_to_file(logger, settings.EMAIL_MIRROR_LOG_PATH)


def send_to_postmaster(msg: email.message.Message) -> None:
    # RFC5321 says:
    #   Any system that includes an SMTP server supporting mail relaying or
    #   delivery MUST support the reserved mailbox "postmaster" as a case-
    #   insensitive local name.  This postmaster address is not strictly
    #   necessary if the server always returns 554 on connection opening (as
    #   described in Section 3.1).  The requirement to accept mail for
    #   postmaster implies that RCPT commands that specify a mailbox for
    #   postmaster at any of the domains for which the SMTP server provides
    #   mail service, as well as the special case of "RCPT TO:<Postmaster>"
    #   (with no domain specification), MUST be supported.
    #
    # We forward such mail to the ZULIP_ADMINISTRATOR.
    mail = DjangoEmailMultiAlternatives(
        subject=f"Mail to postmaster: {msg['Subject']}",
        from_email=settings.NOREPLY_EMAIL_ADDRESS,
        to=[settings.ZULIP_ADMINISTRATOR],
    )
    mail.attach(None, msg, "message/rfc822")
    try:
        mail.send()
    except smtplib.SMTPResponseException as e:
        logger.exception(
            "Error sending bounce email to %s with error code %s: %s",
            mail.to,
            e.smtp_code,
            e.smtp_error,
            stack_info=True,
        )
    except smtplib.SMTPException as e:
        logger.exception("Error sending bounce email to %s: %s", mail.to, str(e), stack_info=True)


class ZulipMessageHandler(MessageHandler):
    def __init__(self) -> None:
        super().__init__(email.message.Message)

    async def handle_RCPT(
        self,
        server: SMTP,
        session: Session,
        envelope: Envelope,
        address: str,
        rcpt_options: list[str],
    ) -> str:
        # Rewrite all postmaster email addresses to just "postmaster"
        if address.lower() == "postmaster":
            envelope.rcpt_tos.append("postmaster")
            return "250 Continue"

        with suppress(ZulipEmailForwardError):
            if get_email_gateway_message_string_from_address(address).lower() == "postmaster":
                envelope.rcpt_tos.append("postmaster")
                return "250 Continue"

        try:
            # Attempt to do the ACL-check now, just to reject early.
            # The authoritative check is done in the worker, but we
            # wish to reject now if we can do so simply.
            await sync_to_async(validate_to_address)(address)

        except RateLimitedError:
            recipient_realm = await sync_to_async(
                lambda a: decode_stream_email_address(a)[0].realm
            )(address)
            logger.warning(
                "Rejecting a MAIL FROM: %s to realm: %s - rate limited.",
                envelope.mail_from,
                recipient_realm.name,
            )
            return "550 4.7.0 Rate-limited due to too many emails on this realm."

        except ZulipEmailForwardError as e:
            return f"550 5.1.1 Bad destination mailbox address: {e}"

        except JsonableError as e:
            return f"550 5.7.1 Permission denied: {e}"

        envelope.rcpt_tos.append(address)
        return "250 Continue"

    @override
    def handle_message(self, message: email.message.Message) -> None:
        msg_base64 = base64.b64encode(bytes(message))

        for address in message["X-RcptTo"].split(", "):
            if address == "postmaster":
                send_to_postmaster(message)
            else:
                queue_json_publish_rollback_unsafe(
                    "email_mirror",
                    {
                        "rcpt_to": address,
                        "msg_base64": msg_base64.decode(),
                    },
                )

    async def handle_exception(self, error: Exception) -> str:
        if isinstance(error, TLSSetupException):  # nocoverage
            if isinstance(error.__cause__, SSLError):
                reason = error.__cause__.reason
            else:
                reason = str(error.__cause__)
            logger.info("Dropping invalid TLS connection: %s", reason)
            return f"421 4.7.6 TLS error: {reason}"
        else:
            logger.exception("SMTP session exception")
            return "500 Server error"


class PermissionDroppingUnthreadedController(UnthreadedController):  # nocoverage
    @override
    def __init__(
        self,
        user: str | None = None,
        group: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        # These may remain None in development, when elevated
        # privileges are not needed because a non-low port is chosen.
        self.user_id: int | None = None
        self.group_id: int | None = None
        if user is not None:
            self.user_id = pwd.getpwnam(user).pw_uid
        if group is not None:
            self.group_id = grp.getgrnam(group).gr_gid

    @override
    def _create_server(self) -> Awaitable[asyncio.AbstractServer]:
        # Make the listen socket, then drop privileges before starting
        # the server
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.hostname, self.port))
        if os.geteuid() == 0:
            assert self.user_id is not None
            assert self.group_id is not None
            logger.info("Dropping privileges to uid %d / gid %d", self.user_id, self.group_id)
            os.setgid(self.group_id)
            os.setuid(self.user_id)

        server = self.loop.create_server(
            self._factory_invoker,
            sock=server_socket,
            ssl=self.ssl_context,
        )

        return server


def run_smtp_server(
    user: str | None, group: str | None, host: str, port: int, tls_context: SSLContext | None
) -> None:  # nocoverage
    logger.info("Listening on %s:%d", host, port)
    server = PermissionDroppingUnthreadedController(
        user=user,
        group=group,
        hostname=host,
        port=port,
        handler=ZulipMessageHandler(),
        tls_context=tls_context,
        ident=f"Zulip Server {ZULIP_VERSION}",
    )

    server.loop.add_signal_handler(signal.SIGINT, server.loop.stop)

    server.begin()
    with suppress(KeyboardInterrupt):
        # The KeyboardInterrupt will exit the loop, but there's no
        # reason to throw a stacktrace rather than conduct an ordered
        # exit.
        server.loop.run_forever()

    server.end()
