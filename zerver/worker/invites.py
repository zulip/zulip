# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
from datetime import timedelta
from typing import Any, Mapping

from typing_extensions import override

from zerver.actions.invites import do_send_confirmation_email
from zerver.context_processors import common_context
from zerver.lib.send_email import FromAddress, send_future_email
from zerver.models import PreregistrationUser
from zerver.models.prereg_users import filter_to_valid_prereg_users
from zerver.models.users import get_user_profile_by_id
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("invites")
class ConfirmationEmailWorker(QueueProcessingWorker):
    @override
    def consume(self, data: Mapping[str, Any]) -> None:
        if "invite_expires_in_days" in data:
            invite_expires_in_minutes = data["invite_expires_in_days"] * 24 * 60
        elif "invite_expires_in_minutes" in data:
            invite_expires_in_minutes = data["invite_expires_in_minutes"]
        invitee = filter_to_valid_prereg_users(
            PreregistrationUser.objects.filter(id=data["prereg_id"]), invite_expires_in_minutes
        ).first()
        if invitee is None:
            # The invitation could have been revoked
            return

        referrer = get_user_profile_by_id(data["referrer_id"])
        logger.info(
            "Sending invitation for realm %s to %s", referrer.realm.string_id, invitee.email
        )
        if "email_language" in data:
            email_language = data["email_language"]
        else:
            email_language = referrer.realm.default_language

        activate_url = do_send_confirmation_email(
            invitee, referrer, email_language, invite_expires_in_minutes
        )
        if invite_expires_in_minutes is None:
            # We do not queue reminder email for never expiring
            # invitations. This is probably a low importance bug; it
            # would likely be more natural to send a reminder after 7
            # days.
            return

        # queue invitation reminder
        if invite_expires_in_minutes >= 4 * 24 * 60:
            context = common_context(referrer)
            context.update(
                activate_url=activate_url,
                referrer_name=referrer.full_name,
                referrer_email=referrer.delivery_email,
                referrer_realm_name=referrer.realm.name,
            )
            send_future_email(
                "zerver/emails/invitation_reminder",
                referrer.realm,
                to_emails=[invitee.email],
                from_address=FromAddress.tokenized_no_reply_placeholder,
                language=email_language,
                context=context,
                delay=timedelta(minutes=invite_expires_in_minutes - (2 * 24 * 60)),
            )
