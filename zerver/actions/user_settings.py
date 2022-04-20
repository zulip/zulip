import datetime
from typing import Optional, Union

import orjson
from django.db import transaction
from django.db.models import F
from django.utils.timezone import now as timezone_now

from confirmation.models import Confirmation, create_confirmation_link
from zerver.lib.avatar import avatar_url
from zerver.lib.cache import (
    cache_delete,
    delete_user_profile_caches,
    user_profile_by_api_key_cache_key,
)
from zerver.lib.i18n import get_language_name
from zerver.lib.queue import queue_json_publish
from zerver.lib.send_email import FromAddress, clear_scheduled_emails, send_email
from zerver.lib.timezone import canonicalize_timezone
from zerver.lib.upload import delete_avatar_image
from zerver.lib.users import check_bot_name_available, check_full_name
from zerver.lib.utils import generate_api_key
from zerver.models import (
    Draft,
    EmailChangeStatus,
    RealmAuditLog,
    ScheduledEmail,
    ScheduledMessageNotificationEmail,
    UserProfile,
    active_user_ids,
    bot_owner_user_ids,
)
from zerver.tornado.django_api import send_event


def send_user_email_update_event(user_profile: UserProfile) -> None:
    payload = dict(user_id=user_profile.id, new_email=user_profile.email)
    event = dict(type="realm_user", op="update", person=payload)
    transaction.on_commit(
        lambda: send_event(
            user_profile.realm,
            event,
            active_user_ids(user_profile.realm_id),
        )
    )


@transaction.atomic(savepoint=False)
def do_change_user_delivery_email(user_profile: UserProfile, new_email: str) -> None:
    delete_user_profile_caches([user_profile])

    user_profile.delivery_email = new_email
    if user_profile.email_address_is_realm_public():
        user_profile.email = new_email
        user_profile.save(update_fields=["email", "delivery_email"])
    else:
        user_profile.save(update_fields=["delivery_email"])

    # We notify just the target user (and eventually org admins, only
    # when email_address_visibility=EMAIL_ADDRESS_VISIBILITY_ADMINS)
    # about their new delivery email, since that field is private.
    payload = dict(user_id=user_profile.id, delivery_email=new_email)
    event = dict(type="realm_user", op="update", person=payload)
    transaction.on_commit(lambda: send_event(user_profile.realm, event, [user_profile.id]))

    if user_profile.avatar_source == UserProfile.AVATAR_FROM_GRAVATAR:
        # If the user is using Gravatar to manage their email address,
        # their Gravatar just changed, and we need to notify other
        # clients.
        notify_avatar_url_change(user_profile)

    if user_profile.email_address_is_realm_public():
        # Additionally, if we're also changing the publicly visible
        # email, we send a new_email event as well.
        send_user_email_update_event(user_profile)

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=user_profile,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_EMAIL_CHANGED,
        event_time=event_time,
    )


def do_start_email_change_process(user_profile: UserProfile, new_email: str) -> None:
    old_email = user_profile.delivery_email
    obj = EmailChangeStatus.objects.create(
        new_email=new_email,
        old_email=old_email,
        user_profile=user_profile,
        realm=user_profile.realm,
    )

    activation_url = create_confirmation_link(obj, Confirmation.EMAIL_CHANGE)
    from zerver.context_processors import common_context

    context = common_context(user_profile)
    context.update(
        old_email=old_email,
        new_email=new_email,
        activate_url=activation_url,
    )
    language = user_profile.default_language
    send_email(
        "zerver/emails/confirm_new_email",
        to_emails=[new_email],
        from_name=FromAddress.security_email_from_name(language=language),
        from_address=FromAddress.tokenized_no_reply_address(),
        language=language,
        context=context,
        realm=user_profile.realm,
    )


def do_change_password(user_profile: UserProfile, password: str, commit: bool = True) -> None:
    user_profile.set_password(password)
    if commit:
        user_profile.save(update_fields=["password"])

    # Imported here to prevent import cycles
    from zproject.backends import RateLimitedAuthenticationByUsername

    RateLimitedAuthenticationByUsername(user_profile.delivery_email).clear_history()
    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=user_profile,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_PASSWORD_CHANGED,
        event_time=event_time,
    )


def do_change_full_name(
    user_profile: UserProfile, full_name: str, acting_user: Optional[UserProfile]
) -> None:
    old_name = user_profile.full_name
    user_profile.full_name = full_name
    user_profile.save(update_fields=["full_name"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=acting_user,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_FULL_NAME_CHANGED,
        event_time=event_time,
        extra_data=old_name,
    )
    payload = dict(user_id=user_profile.id, full_name=user_profile.full_name)
    send_event(
        user_profile.realm,
        dict(type="realm_user", op="update", person=payload),
        active_user_ids(user_profile.realm_id),
    )
    if user_profile.is_bot:
        send_event(
            user_profile.realm,
            dict(type="realm_bot", op="update", bot=payload),
            bot_owner_user_ids(user_profile),
        )


def check_change_full_name(
    user_profile: UserProfile, full_name_raw: str, acting_user: Optional[UserProfile]
) -> str:
    """Verifies that the user's proposed full name is valid.  The caller
    is responsible for checking check permissions.  Returns the new
    full name, which may differ from what was passed in (because this
    function strips whitespace)."""
    new_full_name = check_full_name(full_name_raw)
    do_change_full_name(user_profile, new_full_name, acting_user)
    return new_full_name


def check_change_bot_full_name(
    user_profile: UserProfile, full_name_raw: str, acting_user: UserProfile
) -> None:
    new_full_name = check_full_name(full_name_raw)

    if new_full_name == user_profile.full_name:
        # Our web app will try to patch full_name even if the user didn't
        # modify the name in the form.  We just silently ignore those
        # situations.
        return

    check_bot_name_available(
        realm_id=user_profile.realm_id,
        full_name=new_full_name,
    )
    do_change_full_name(user_profile, new_full_name, acting_user)


@transaction.atomic(durable=True)
def do_change_tos_version(user_profile: UserProfile, tos_version: str) -> None:
    user_profile.tos_version = tos_version
    user_profile.save(update_fields=["tos_version"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=user_profile,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_TERMS_OF_SERVICE_VERSION_CHANGED,
        event_time=event_time,
    )


def do_regenerate_api_key(user_profile: UserProfile, acting_user: UserProfile) -> str:
    old_api_key = user_profile.api_key
    new_api_key = generate_api_key()
    user_profile.api_key = new_api_key
    user_profile.save(update_fields=["api_key"])

    # We need to explicitly delete the old API key from our caches,
    # because the on-save handler for flushing the UserProfile object
    # in zerver/lib/cache.py only has access to the new API key.
    cache_delete(user_profile_by_api_key_cache_key(old_api_key))

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=acting_user,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_API_KEY_CHANGED,
        event_time=event_time,
    )

    if user_profile.is_bot:
        send_event(
            user_profile.realm,
            dict(
                type="realm_bot",
                op="update",
                bot=dict(
                    user_id=user_profile.id,
                    api_key=new_api_key,
                ),
            ),
            bot_owner_user_ids(user_profile),
        )

    event = {"type": "clear_push_device_tokens", "user_profile_id": user_profile.id}
    queue_json_publish("deferred_work", event)

    return new_api_key


def notify_avatar_url_change(user_profile: UserProfile) -> None:
    if user_profile.is_bot:
        bot_event = dict(
            type="realm_bot",
            op="update",
            bot=dict(
                user_id=user_profile.id,
                avatar_url=avatar_url(user_profile),
            ),
        )
        transaction.on_commit(
            lambda: send_event(
                user_profile.realm,
                bot_event,
                bot_owner_user_ids(user_profile),
            )
        )

    payload = dict(
        avatar_source=user_profile.avatar_source,
        avatar_url=avatar_url(user_profile),
        avatar_url_medium=avatar_url(user_profile, medium=True),
        avatar_version=user_profile.avatar_version,
        # Even clients using client_gravatar don't need the email,
        # since we're sending the URL anyway.
        user_id=user_profile.id,
    )

    event = dict(type="realm_user", op="update", person=payload)
    transaction.on_commit(
        lambda: send_event(
            user_profile.realm,
            event,
            active_user_ids(user_profile.realm_id),
        )
    )


@transaction.atomic(savepoint=False)
def do_change_avatar_fields(
    user_profile: UserProfile,
    avatar_source: str,
    skip_notify: bool = False,
    *,
    acting_user: Optional[UserProfile],
) -> None:
    user_profile.avatar_source = avatar_source
    user_profile.avatar_version += 1
    user_profile.save(update_fields=["avatar_source", "avatar_version"])
    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        modified_user=user_profile,
        event_type=RealmAuditLog.USER_AVATAR_SOURCE_CHANGED,
        extra_data={"avatar_source": avatar_source},
        event_time=event_time,
        acting_user=acting_user,
    )

    if not skip_notify:
        notify_avatar_url_change(user_profile)


def do_delete_avatar_image(user: UserProfile, *, acting_user: Optional[UserProfile]) -> None:
    do_change_avatar_fields(user, UserProfile.AVATAR_FROM_GRAVATAR, acting_user=acting_user)
    delete_avatar_image(user)


def update_scheduled_email_notifications_time(
    user_profile: UserProfile, old_batching_period: int, new_batching_period: int
) -> None:
    existing_scheduled_emails = ScheduledMessageNotificationEmail.objects.filter(
        user_profile=user_profile
    )

    scheduled_timestamp_change = datetime.timedelta(
        seconds=new_batching_period
    ) - datetime.timedelta(seconds=old_batching_period)

    existing_scheduled_emails.update(
        scheduled_timestamp=F("scheduled_timestamp") + scheduled_timestamp_change
    )


@transaction.atomic(durable=True)
def do_change_user_setting(
    user_profile: UserProfile,
    setting_name: str,
    setting_value: Union[bool, str, int],
    *,
    acting_user: Optional[UserProfile],
) -> None:
    old_value = getattr(user_profile, setting_name)
    event_time = timezone_now()

    if setting_name == "timezone":
        assert isinstance(setting_value, str)
        setting_value = canonicalize_timezone(setting_value)
    else:
        property_type = UserProfile.property_types[setting_name]
        assert isinstance(setting_value, property_type)
    setattr(user_profile, setting_name, setting_value)

    # TODO: Move these database actions into a transaction.atomic block.
    user_profile.save(update_fields=[setting_name])

    if setting_name in UserProfile.notification_setting_types:
        # Prior to all personal settings being managed by property_types,
        # these were only created for notification settings.
        #
        # TODO: Start creating these for all settings, and do a
        # backfilled=True migration.
        RealmAuditLog.objects.create(
            realm=user_profile.realm,
            event_type=RealmAuditLog.USER_SETTING_CHANGED,
            event_time=event_time,
            acting_user=acting_user,
            modified_user=user_profile,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: setting_value,
                    "property": setting_name,
                }
            ).decode(),
        )
    # Disabling digest emails should clear a user's email queue
    if setting_name == "enable_digest_emails" and not setting_value:
        clear_scheduled_emails(user_profile.id, ScheduledEmail.DIGEST)

    if setting_name == "email_notifications_batching_period_seconds":
        assert isinstance(old_value, int)
        assert isinstance(setting_value, int)
        update_scheduled_email_notifications_time(user_profile, old_value, setting_value)

    event = {
        "type": "user_settings",
        "op": "update",
        "property": setting_name,
        "value": setting_value,
    }
    if setting_name == "default_language":
        assert isinstance(setting_value, str)
        event["language_name"] = get_language_name(setting_value)

    transaction.on_commit(lambda: send_event(user_profile.realm, event, [user_profile.id]))

    if setting_name in UserProfile.notification_settings_legacy:
        # This legacy event format is for backwards-compatibility with
        # clients that don't support the new user_settings event type.
        # We only send this for settings added before Feature level 89.
        legacy_event = {
            "type": "update_global_notifications",
            "user": user_profile.email,
            "notification_name": setting_name,
            "setting": setting_value,
        }
        transaction.on_commit(
            lambda: send_event(user_profile.realm, legacy_event, [user_profile.id])
        )

    if setting_name in UserProfile.display_settings_legacy or setting_name == "timezone":
        # This legacy event format is for backwards-compatibility with
        # clients that don't support the new user_settings event type.
        # We only send this for settings added before Feature level 89.
        legacy_event = {
            "type": "update_display_settings",
            "user": user_profile.email,
            "setting_name": setting_name,
            "setting": setting_value,
        }
        if setting_name == "default_language":
            assert isinstance(setting_value, str)
            legacy_event["language_name"] = get_language_name(setting_value)

        transaction.on_commit(
            lambda: send_event(user_profile.realm, legacy_event, [user_profile.id])
        )

    # Updates to the time zone display setting are sent to all users
    if setting_name == "timezone":
        payload = dict(
            email=user_profile.email,
            user_id=user_profile.id,
            timezone=canonicalize_timezone(user_profile.timezone),
        )
        timezone_event = dict(type="realm_user", op="update", person=payload)
        transaction.on_commit(
            lambda: send_event(
                user_profile.realm,
                timezone_event,
                active_user_ids(user_profile.realm_id),
            )
        )

    if setting_name == "enable_drafts_synchronization" and setting_value is False:
        # Delete all of the drafts from the backend but don't send delete events
        # for them since all that's happened is that we stopped syncing changes,
        # not deleted every previously synced draft - to do that use the DELETE
        # endpoint.
        Draft.objects.filter(user_profile=user_profile).delete()
