import os
from datetime import timedelta
from functools import lru_cache

import orjson
from django.conf import settings
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.actions.scheduled_messages import check_schedule_message
from zerver.lib.exceptions import JsonableError
from zerver.lib.timestamp import ceiling_to_day, datetime_to_global_time
from zerver.models.clients import get_client
from zerver.models.realms import Realm
from zerver.models.users import UserProfile, get_system_bot


@lru_cache(None)
def get_demo_organization_wordlists() -> dict[str, list[str]]:
    path = os.path.join(settings.DEPLOY_ROOT, "zerver/lib", "demo_organization_words.json")
    with open(path, "rb") as reader:
        return orjson.loads(reader.read())


def demo_organization_owner_email_exists(realm: Realm) -> bool:
    human_owner_emails = set(realm.get_human_owner_users().values_list("delivery_email", flat=True))
    return human_owner_emails != {""}


def check_demo_organization_has_set_email(realm: Realm) -> None:
    # This should be called after checking that the realm has
    # a demo_organization_scheduled_deletion_date set.
    assert realm.demo_organization_scheduled_deletion_date is not None
    if not demo_organization_owner_email_exists(realm):
        raise JsonableError(_("Configure owner account email address."))


def get_demo_organization_deadline_days_remaining(realm: Realm) -> int:
    assert realm.demo_organization_scheduled_deletion_date is not None
    days_remaining = (realm.demo_organization_scheduled_deletion_date - timezone_now()).days
    return days_remaining


def get_scheduled_deletion_global_time(realm: Realm) -> str:
    assert realm.demo_organization_scheduled_deletion_date is not None
    scheduled_deletion_cronjob_timestamp = ceiling_to_day(
        realm.demo_organization_scheduled_deletion_date
    ) + timedelta(hours=6)
    return datetime_to_global_time(scheduled_deletion_cronjob_timestamp)


def schedule_demo_organization_deletion_reminder(user: UserProfile) -> None:
    assert user.is_realm_owner
    realm = user.realm
    assert realm.demo_organization_scheduled_deletion_date is not None
    deliver_at = realm.demo_organization_scheduled_deletion_date - timedelta(days=7)
    sender = get_system_bot(settings.NOTIFICATION_BOT, realm.id)
    client = get_client("Internal")

    message_content = _("""
As a reminder, this [demo organization]({demo_help}) will be automatically deleted on {deletion_time}, unless it's [converted into a permanent organization]({convert_demo}).
""").format(
        demo_help="/help/demo-organizations",
        deletion_time=get_scheduled_deletion_global_time(realm),
        convert_demo="/help/demo-organizations#convert-a-demo-organization-to-a-permanent-organization",
    )

    check_schedule_message(
        sender,
        client,
        "private",
        [user.id],
        None,
        message_content,
        deliver_at,
        realm,
        skip_events=True,
    )
