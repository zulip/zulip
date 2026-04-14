import logging
from datetime import datetime, time, timezone
from typing import Any

from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.actions.message_send import check_message, do_send_messages
from zerver.lib.addressee import Addressee
from zerver.lib.exceptions import (
    JsonableError,
    RealmDeactivatedError,
    ResourceNotFoundError,
    UserDeactivatedError,
)
from zerver.lib.recurring_scheduled_messages import compute_next_delivery
from zerver.models import RecurringScheduledMessage, UserProfile
from zerver.models.clients import get_client
from zerver.tornado.django_api import send_event_on_commit

logger = logging.getLogger(__name__)

UTC = timezone.utc


@transaction.atomic(durable=True)
def do_create_recurring_scheduled_message(
    sender: UserProfile,
    content: str,
    destinations: list[dict[str, Any]],
    recurrence_type: str,
    recurrence_days: list[int],
    scheduled_time: time,
    deliver_at: datetime | None = None,
) -> RecurringScheduledMessage:
    """Create a new recurring scheduled message job.

    For one_time jobs, `deliver_at` must be provided and is used as next_delivery.
    For all other recurrence types, next_delivery is computed from scheduled_time.
    """
    if recurrence_type == RecurringScheduledMessage.ONE_TIME:
        if deliver_at is None:
            raise JsonableError(_("deliver_at is required for one-time scheduled messages."))
        next_delivery = deliver_at
    else:
        next_delivery = compute_next_delivery(
            recurrence_type,
            recurrence_days,
            scheduled_time,
            timezone_now(),
        )

    job = RecurringScheduledMessage.objects.create(
        sender=sender,
        realm=sender.realm,
        content=content,
        destinations=destinations,
        recurrence_type=recurrence_type,
        recurrence_days=recurrence_days,
        scheduled_time=scheduled_time,
        next_delivery=next_delivery,
        is_active=True,
    )

    event = {
        "type": "recurring_scheduled_messages",
        "op": "add",
        "recurring_scheduled_message": job.to_api_dict(),
    }
    send_event_on_commit(sender.realm, event, [sender.id])

    return job


def do_get_recurring_scheduled_messages(user_profile: UserProfile) -> list[dict[str, Any]]:
    """Return all active recurring scheduled message jobs for this user."""
    jobs = RecurringScheduledMessage.objects.filter(
        sender=user_profile,
        is_active=True,
    ).order_by("next_delivery")
    return [job.to_api_dict() for job in jobs]


@transaction.atomic(durable=True)
def do_cancel_recurring_scheduled_message(
    job_id: int,
    user_profile: UserProfile,
) -> None:
    """Cancel an active recurring scheduled message job."""
    try:
        job = RecurringScheduledMessage.objects.get(
            id=job_id,
            sender=user_profile,
            is_active=True,
        )
    except RecurringScheduledMessage.DoesNotExist:
        raise ResourceNotFoundError(_("Recurring scheduled message does not exist."))

    job.is_active = False
    job.save(update_fields=["is_active"])

    event = {
        "type": "recurring_scheduled_messages",
        "op": "remove",
        "recurring_scheduled_message_id": job_id,
    }
    send_event_on_commit(user_profile.realm, event, [user_profile.id])


def do_deliver_recurring_scheduled_message(job: RecurringScheduledMessage) -> None:
    """Send a recurring scheduled message to all its destinations.

    Must be called from within a durable transaction
    (see try_deliver_one_recurring_scheduled_message). Each destination is
    attempted in its own savepoint so a failure on one does not prevent the
    others from being sent. After all sends, the job is either deactivated
    (one_time) or rescheduled to its next occurrence (recurring types).
    """
    if job.realm.deactivated:
        job.is_active = False
        job.save(update_fields=["is_active"])
        raise RealmDeactivatedError

    if not job.sender.is_active:
        job.is_active = False
        job.save(update_fields=["is_active"])
        raise UserDeactivatedError

    client = get_client("ZulipServer")

    for destination in job.destinations:
        try:
            with transaction.atomic():  # savepoint: isolates each destination
                dest_type = destination["type"]
                if dest_type == "stream":
                    addressee = Addressee.for_stream_id(
                        destination["stream_id"],
                        destination["topic"],
                    )
                else:
                    addressee = Addressee.for_user_ids(destination["user_ids"], job.realm)

                send_request = check_message(
                    job.sender,
                    client,
                    addressee,
                    job.content,
                    job.realm,
                )
                do_send_messages([send_request])

        except Exception:
            destination_label = destination.get("type", "unknown")
            if destination_label == "stream":
                destination_label = f"stream:{destination.get('stream_id', 'unknown')}"
            elif destination_label == "direct":
                destination_label = (
                    f"direct:{len(destination.get('user_ids', []))}_recipients"
                )
            logger.exception(
                "Failed to deliver recurring scheduled message %s to destination %s",
                job.id,
                destination_label,
                stack_info=True,
            )
            raise

    # Update job state — runs within the caller's durable transaction.
    if job.recurrence_type == RecurringScheduledMessage.ONE_TIME:
        job.is_active = False
        job.save(update_fields=["is_active"])
        event: dict[str, Any] = {
            "type": "recurring_scheduled_messages",
            "op": "remove",
            "recurring_scheduled_message_id": job.id,
        }
    else:
        job.next_delivery = compute_next_delivery(
            job.recurrence_type,
            job.recurrence_days,
            job.scheduled_time,
            timezone_now(),
        )
        job.save(update_fields=["next_delivery"])
        event = {
            "type": "recurring_scheduled_messages",
            "op": "update",
            "recurring_scheduled_message": job.to_api_dict(),
        }

    send_event_on_commit(job.realm, event, [job.sender_id])


@transaction.atomic(durable=True)
def try_deliver_one_recurring_scheduled_message() -> bool:
    """Find the earliest due job and deliver it. Returns True if a job was found.

    Called in a tight loop by the worker until no more jobs are due.
    """
    job = (
        RecurringScheduledMessage.objects.filter(
            next_delivery__lte=timezone_now(),
            is_active=True,
        )
        .order_by("next_delivery", "id")
        .select_for_update()
        .first()
    )

    if job is None:
        return False

    logger.info(
        "Delivering recurring scheduled message %s (sender: %s, recurrence: %s, destinations: %s)",
        job.id,
        job.sender_id,
        job.recurrence_type,
        len(job.destinations),
    )

    try:
        do_deliver_recurring_scheduled_message(job)
    except (RealmDeactivatedError, UserDeactivatedError):
        # Job already deactivated inside do_deliver; let the transaction commit.
        pass
    except Exception:
        logger.exception(
            "Unexpected error delivering recurring scheduled message %s",
            job.id,
            stack_info=True,
        )
        # Advance next_delivery so the worker does not get stuck in a tight
        # retry loop on this job. For one_time jobs, deactivate instead.
        if job.recurrence_type != RecurringScheduledMessage.ONE_TIME:
            job.next_delivery = compute_next_delivery(
                job.recurrence_type,
                job.recurrence_days,
                job.scheduled_time,
                timezone_now(),
            )
            job.save(update_fields=["next_delivery"])
            event: dict[str, Any] = {
                "type": "recurring_scheduled_messages",
                "op": "update",
                "recurring_scheduled_message": job.to_api_dict(),
            }
        else:
            job.is_active = False
            job.save(update_fields=["is_active"])
            event = {
                "type": "recurring_scheduled_messages",
                "op": "remove",
                "recurring_scheduled_message_id": job.id,
            }
        send_event_on_commit(job.realm, event, [job.sender_id])
    return True
