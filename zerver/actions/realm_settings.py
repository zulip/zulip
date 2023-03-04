import logging
from email.headerregistry import Address
from typing import Any, Dict, Literal, Optional

import orjson
from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.utils.timezone import now as timezone_now

from confirmation.models import Confirmation, create_confirmation_link, generate_key
from zerver.actions.custom_profile_fields import do_remove_realm_custom_profile_fields
from zerver.actions.message_delete import do_delete_messages_by_sender
from zerver.actions.user_groups import update_users_in_full_members_system_group
from zerver.actions.user_settings import do_delete_avatar_image, send_user_email_update_event
from zerver.lib.cache import flush_user_profile
from zerver.lib.create_user import get_display_email_address
from zerver.lib.message import update_first_visible_message_id
from zerver.lib.send_email import FromAddress, send_email_to_admins
from zerver.lib.sessions import delete_user_sessions
from zerver.lib.user_counts import realm_user_count_by_role
from zerver.models import (
    Attachment,
    Realm,
    RealmAuditLog,
    RealmReactivationStatus,
    RealmUserDefault,
    ScheduledEmail,
    Stream,
    UserProfile,
    active_user_ids,
)
from zerver.tornado.django_api import send_event

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import downgrade_now_without_creating_additional_invoices


def active_humans_in_realm(realm: Realm) -> QuerySet[UserProfile]:
    return UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False)


@transaction.atomic(savepoint=False)
def do_set_realm_property(
    realm: Realm, name: str, value: Any, *, acting_user: Optional[UserProfile]
) -> None:
    """Takes in a realm object, the name of an attribute to update, the
    value to update and and the user who initiated the update.
    """
    property_type = Realm.property_types[name]
    assert isinstance(
        value, property_type
    ), f"Cannot update {name}: {value} is not an instance of {property_type}"

    old_value = getattr(realm, name)
    setattr(realm, name, value)
    realm.save(update_fields=[name])

    event = dict(
        type="realm",
        op="update",
        property=name,
        value=value,
    )

    # These settings have a different event format due to their history.
    message_edit_settings = [
        "allow_message_editing",
        "edit_topic_policy",
        "message_content_edit_limit_seconds",
    ]
    if name in message_edit_settings:
        event = dict(
            type="realm",
            op="update_dict",
            property="default",
            data={name: value},
        )

    transaction.on_commit(lambda: send_event(realm, event, active_user_ids(realm.id)))

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm,
        event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
        event_time=event_time,
        acting_user=acting_user,
        extra_data=orjson.dumps(
            {
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: value,
                "property": name,
            }
        ).decode(),
    )

    if name == "email_address_visibility":
        if Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE not in [old_value, value]:
            # We use real email addresses on UserProfile.email only if
            # EMAIL_ADDRESS_VISIBILITY_EVERYONE is configured, so
            # changes between values that will not require changing
            # that field, so we can save work and return here.
            return

        user_profiles = UserProfile.objects.filter(realm=realm, is_bot=False)
        for user_profile in user_profiles:
            user_profile.email = get_display_email_address(user_profile)
        UserProfile.objects.bulk_update(user_profiles, ["email"])

        for user_profile in user_profiles:
            transaction.on_commit(
                lambda: flush_user_profile(sender=UserProfile, instance=user_profile)
            )
            # TODO: Design a bulk event for this or force-reload all clients
            send_user_email_update_event(user_profile)

    if name == "waiting_period_threshold":
        update_users_in_full_members_system_group(realm)


def do_set_realm_authentication_methods(
    realm: Realm, authentication_methods: Dict[str, bool], *, acting_user: Optional[UserProfile]
) -> None:
    old_value = realm.authentication_methods_dict()
    with transaction.atomic():
        for key, value in list(authentication_methods.items()):
            index = getattr(realm.authentication_methods, key).number
            realm.authentication_methods.set_bit(index, int(value))
        realm.save(update_fields=["authentication_methods"])
        updated_value = realm.authentication_methods_dict()
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
            event_time=timezone_now(),
            acting_user=acting_user,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: updated_value,
                    "property": "authentication_methods",
                }
            ).decode(),
        )

    event = dict(
        type="realm",
        op="update_dict",
        property="default",
        data=dict(authentication_methods=updated_value),
    )
    send_event(realm, event, active_user_ids(realm.id))


def do_set_realm_stream(
    realm: Realm,
    field: Literal["notifications_stream", "signup_notifications_stream"],
    stream: Optional[Stream],
    stream_id: int,
    *,
    acting_user: Optional[UserProfile],
) -> None:
    # We could calculate more of these variables from `field`, but
    # it's probably more readable to not do so.
    if field == "notifications_stream":
        old_value = realm.notifications_stream_id
        realm.notifications_stream = stream
        property = "notifications_stream_id"
    elif field == "signup_notifications_stream":
        old_value = realm.signup_notifications_stream_id
        realm.signup_notifications_stream = stream
        property = "signup_notifications_stream_id"
    else:
        raise AssertionError("Invalid realm stream field.")

    with transaction.atomic():
        realm.save(update_fields=[field])

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
            event_time=event_time,
            acting_user=acting_user,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: stream_id,
                    "property": field,
                }
            ).decode(),
        )

    event = dict(
        type="realm",
        op="update",
        property=property,
        value=stream_id,
    )
    send_event(realm, event, active_user_ids(realm.id))


def do_set_realm_notifications_stream(
    realm: Realm, stream: Optional[Stream], stream_id: int, *, acting_user: Optional[UserProfile]
) -> None:
    do_set_realm_stream(realm, "notifications_stream", stream, stream_id, acting_user=acting_user)


def do_set_realm_signup_notifications_stream(
    realm: Realm, stream: Optional[Stream], stream_id: int, *, acting_user: Optional[UserProfile]
) -> None:
    do_set_realm_stream(
        realm, "signup_notifications_stream", stream, stream_id, acting_user=acting_user
    )


def do_set_realm_user_default_setting(
    realm_user_default: RealmUserDefault,
    name: str,
    value: Any,
    *,
    acting_user: Optional[UserProfile],
) -> None:
    old_value = getattr(realm_user_default, name)
    realm = realm_user_default.realm
    event_time = timezone_now()

    with transaction.atomic(savepoint=False):
        setattr(realm_user_default, name, value)
        realm_user_default.save(update_fields=[name])

        RealmAuditLog.objects.create(
            realm=realm,
            event_type=RealmAuditLog.REALM_DEFAULT_USER_SETTINGS_CHANGED,
            event_time=event_time,
            acting_user=acting_user,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: value,
                    "property": name,
                }
            ).decode(),
        )

    event = dict(
        type="realm_user_settings_defaults",
        op="update",
        property=name,
        value=value,
    )
    send_event(realm, event, active_user_ids(realm.id))


def do_deactivate_realm(realm: Realm, *, acting_user: Optional[UserProfile]) -> None:
    """
    Deactivate this realm. Do NOT deactivate the users -- we need to be able to
    tell the difference between users that were intentionally deactivated,
    e.g. by a realm admin, and users who can't currently use Zulip because their
    realm has been deactivated.
    """
    if realm.deactivated:
        return

    realm.deactivated = True
    realm.save(update_fields=["deactivated"])

    if settings.BILLING_ENABLED:
        downgrade_now_without_creating_additional_invoices(realm)

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm,
        event_type=RealmAuditLog.REALM_DEACTIVATED,
        event_time=event_time,
        acting_user=acting_user,
        extra_data=orjson.dumps(
            {
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(realm),
            }
        ).decode(),
    )

    ScheduledEmail.objects.filter(realm=realm).delete()
    for user in active_humans_in_realm(realm):
        # Don't deactivate the users, but do delete their sessions so they get
        # bumped to the login screen, where they'll get a realm deactivation
        # notice when they try to log in.
        delete_user_sessions(user)

    # This event will only ever be received by clients with an active
    # longpoll connection, because by this point clients will be
    # unable to authenticate again to their event queue (triggering an
    # immediate reload into the page explaining the realm was
    # deactivated). So the purpose of sending this is to flush all
    # active longpoll connections for the realm.
    event = dict(type="realm", op="deactivated", realm_id=realm.id)
    send_event(realm, event, active_user_ids(realm.id))


def do_reactivate_realm(realm: Realm) -> None:
    if not realm.deactivated:
        logging.warning("Realm %s cannot be reactivated because it is already active.", realm.id)
        return

    realm.deactivated = False
    with transaction.atomic():
        realm.save(update_fields=["deactivated"])

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            # We hardcode acting_user=None, since realm reactivation
            # uses an email authentication mechanism that will never
            # know which user initiated the change.
            acting_user=None,
            realm=realm,
            event_type=RealmAuditLog.REALM_REACTIVATED,
            event_time=event_time,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(realm),
                }
            ).decode(),
        )


def do_add_deactivated_redirect(realm: Realm, redirect_url: str) -> None:
    realm.deactivated_redirect = redirect_url
    realm.save(update_fields=["deactivated_redirect"])


def do_scrub_realm(realm: Realm, *, acting_user: Optional[UserProfile]) -> None:
    if settings.BILLING_ENABLED:
        downgrade_now_without_creating_additional_invoices(realm)

    users = UserProfile.objects.filter(realm=realm)
    for user in users:
        do_delete_messages_by_sender(user)
        do_delete_avatar_image(user, acting_user=acting_user)
        user.full_name = f"Scrubbed {generate_key()[:15]}"
        scrubbed_email = Address(
            username=f"scrubbed-{generate_key()[:15]}", domain=realm.host
        ).addr_spec
        user.email = scrubbed_email
        user.delivery_email = scrubbed_email
        user.save(update_fields=["full_name", "email", "delivery_email"])

    do_remove_realm_custom_profile_fields(realm)
    Attachment.objects.filter(realm=realm).delete()

    RealmAuditLog.objects.create(
        realm=realm,
        event_time=timezone_now(),
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_SCRUBBED,
    )


@transaction.atomic(durable=True)
def do_change_realm_org_type(
    realm: Realm,
    org_type: int,
    acting_user: Optional[UserProfile],
) -> None:
    old_value = realm.org_type
    realm.org_type = org_type
    realm.save(update_fields=["org_type"])

    RealmAuditLog.objects.create(
        event_type=RealmAuditLog.REALM_ORG_TYPE_CHANGED,
        realm=realm,
        event_time=timezone_now(),
        acting_user=acting_user,
        extra_data=str({"old_value": old_value, "new_value": org_type}),
    )

    event = dict(type="realm", op="update", property="org_type", value=org_type)
    transaction.on_commit(lambda: send_event(realm, event, active_user_ids(realm.id)))


@transaction.atomic(savepoint=False)
def do_change_realm_plan_type(
    realm: Realm, plan_type: int, *, acting_user: Optional[UserProfile]
) -> None:
    old_value = realm.plan_type

    if plan_type == Realm.PLAN_TYPE_LIMITED:
        # We do not allow public access on limited plans.
        do_set_realm_property(realm, "enable_spectator_access", False, acting_user=acting_user)

    realm.plan_type = plan_type
    realm.save(update_fields=["plan_type"])
    RealmAuditLog.objects.create(
        event_type=RealmAuditLog.REALM_PLAN_TYPE_CHANGED,
        realm=realm,
        event_time=timezone_now(),
        acting_user=acting_user,
        extra_data=str({"old_value": old_value, "new_value": plan_type}),
    )

    if plan_type == Realm.PLAN_TYPE_PLUS:
        realm.max_invites = Realm.INVITES_STANDARD_REALM_DAILY_MAX
        realm.message_visibility_limit = None
        realm.upload_quota_gb = Realm.UPLOAD_QUOTA_STANDARD
    elif plan_type == Realm.PLAN_TYPE_STANDARD:
        realm.max_invites = Realm.INVITES_STANDARD_REALM_DAILY_MAX
        realm.message_visibility_limit = None
        realm.upload_quota_gb = Realm.UPLOAD_QUOTA_STANDARD
    elif plan_type == Realm.PLAN_TYPE_SELF_HOSTED:
        realm.max_invites = None  # type: ignore[assignment] # https://github.com/python/mypy/issues/3004
        realm.message_visibility_limit = None
        realm.upload_quota_gb = None
    elif plan_type == Realm.PLAN_TYPE_STANDARD_FREE:
        realm.max_invites = Realm.INVITES_STANDARD_REALM_DAILY_MAX
        realm.message_visibility_limit = None
        realm.upload_quota_gb = Realm.UPLOAD_QUOTA_STANDARD
    elif plan_type == Realm.PLAN_TYPE_LIMITED:
        realm.max_invites = settings.INVITES_DEFAULT_REALM_DAILY_MAX
        realm.message_visibility_limit = Realm.MESSAGE_VISIBILITY_LIMITED
        realm.upload_quota_gb = Realm.UPLOAD_QUOTA_LIMITED
    else:
        raise AssertionError("Invalid plan type")

    update_first_visible_message_id(realm)

    realm.save(
        update_fields=[
            "_max_invites",
            "enable_spectator_access",
            "message_visibility_limit",
            "upload_quota_gb",
        ]
    )

    event = {
        "type": "realm",
        "op": "update",
        "property": "plan_type",
        "value": plan_type,
        "extra_data": {"upload_quota": realm.upload_quota_bytes()},
    }
    transaction.on_commit(lambda: send_event(realm, event, active_user_ids(realm.id)))


def do_send_realm_reactivation_email(realm: Realm, *, acting_user: Optional[UserProfile]) -> None:
    obj = RealmReactivationStatus.objects.create(realm=realm)

    url = create_confirmation_link(obj, Confirmation.REALM_REACTIVATION)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_REACTIVATION_EMAIL_SENT,
        event_time=timezone_now(),
    )
    context = {"confirmation_url": url, "realm_uri": realm.uri, "realm_name": realm.name}
    language = realm.default_language
    send_email_to_admins(
        "zerver/emails/realm_reactivation",
        realm,
        from_address=FromAddress.tokenized_no_reply_address(),
        from_name=FromAddress.security_email_from_name(language=language),
        language=language,
        context=context,
    )
