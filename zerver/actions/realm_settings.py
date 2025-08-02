import datetime
import logging
import zoneinfo
from email.headerregistry import Address
from enum import Enum
from typing import Any, Literal

from django.conf import settings
from django.db import transaction
from django.utils.timezone import get_current_timezone_name as timezone_get_current_timezone_name
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from confirmation.models import Confirmation, create_confirmation_link, generate_key
from zerver.actions.custom_profile_fields import do_remove_realm_custom_profile_fields
from zerver.actions.message_delete import do_delete_messages_by_sender
from zerver.actions.user_groups import update_users_in_full_members_system_group
from zerver.actions.user_settings import do_delete_avatar_image
from zerver.lib.demo_organizations import demo_organization_owner_email_exists
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import parse_message_time_limit_setting, update_first_visible_message_id
from zerver.lib.queue import queue_json_publish_rollback_unsafe
from zerver.lib.retention import move_messages_to_archive
from zerver.lib.send_email import FromAddress, send_email, send_email_to_admins
from zerver.lib.sessions import delete_realm_user_sessions
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.timezone import canonicalize_timezone
from zerver.lib.types import UserGroupMembersData
from zerver.lib.upload import delete_message_attachments
from zerver.lib.user_counts import realm_user_count_by_role
from zerver.lib.user_groups import (
    convert_to_user_group_members_dict,
    get_group_setting_value_for_api,
    get_group_setting_value_for_audit_log_data,
)
from zerver.lib.utils import optional_bytes_to_mib
from zerver.models import (
    ArchivedAttachment,
    Attachment,
    Message,
    NamedUserGroup,
    Realm,
    RealmAuditLog,
    RealmAuthenticationMethod,
    RealmReactivationStatus,
    RealmUserDefault,
    Recipient,
    ScheduledEmail,
    Stream,
    Subscription,
    UserGroup,
    UserProfile,
)
from zerver.models.groups import SystemGroups
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import (
    MessageEditHistoryVisibilityPolicyEnum,
    RealmTopicsPolicyEnum,
    get_default_max_invites_for_realm_plan_type,
    get_realm,
)
from zerver.models.users import active_user_ids
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(savepoint=False)
def do_set_realm_property(
    realm: Realm, name: str, raw_value: Any, *, acting_user: UserProfile | None
) -> None:
    """Takes in a realm object, the name of an attribute to update, the
    value to update and the user who initiated the update.
    """
    property_type = Realm.property_types[name]
    assert isinstance(raw_value, property_type), (
        f"Cannot update {name}: {raw_value} is not an instance of {property_type}"
    )

    old_value = getattr(realm, name)
    if isinstance(raw_value, Enum):
        value = raw_value.value
    else:
        value = raw_value

    if old_value == value:
        return

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
        "message_content_edit_limit_seconds",
    ]
    if name in message_edit_settings:
        event = dict(
            type="realm",
            op="update_dict",
            property="default",
            data={name: value},
        )
    if name == "message_edit_history_visibility_policy":
        event = dict(
            type="realm",
            op="update",
            property=name,
            value=MessageEditHistoryVisibilityPolicyEnum(value).name,
        )
    if name == "topics_policy":
        event = dict(
            type="realm",
            op="update_dict",
            property="default",
            data={
                name: RealmTopicsPolicyEnum(value).name,
                "mandatory_topics": value == RealmTopicsPolicyEnum.disable_empty_topic.value,
            },
        )

    send_event_on_commit(realm, event, active_user_ids(realm.id))

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm,
        event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
        event_time=event_time,
        acting_user=acting_user,
        extra_data={
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: value,
            "property": name,
        },
    )

    if name == "waiting_period_threshold":
        update_users_in_full_members_system_group(realm, acting_user=acting_user)


@transaction.atomic(durable=True)
def do_set_push_notifications_enabled_end_timestamp(
    realm: Realm, value: int | None, *, acting_user: UserProfile | None
) -> None:
    # Variant of do_set_realm_property with a bit of extra complexity
    # for the fact that we store a datetime object in the database but
    # use an integer format timestamp in the API.
    name = "push_notifications_enabled_end_timestamp"
    old_timestamp = None
    old_datetime = getattr(realm, name)
    if old_datetime is not None:
        old_timestamp = datetime_to_timestamp(old_datetime)

    if old_timestamp == value:
        return

    new_datetime = None
    if value is not None:
        new_datetime = timestamp_to_datetime(value)
    setattr(realm, name, new_datetime)
    realm.save(update_fields=[name])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm,
        event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
        event_time=event_time,
        acting_user=acting_user,
        extra_data={
            RealmAuditLog.OLD_VALUE: old_timestamp,
            RealmAuditLog.NEW_VALUE: value,
            "property": name,
        },
    )

    event = dict(
        type="realm",
        op="update",
        property=name,
        value=value,
    )
    send_event_on_commit(realm, event, active_user_ids(realm.id))


@transaction.atomic(savepoint=False)
def do_change_realm_permission_group_setting(
    realm: Realm,
    setting_name: str,
    user_group: UserGroup,
    old_setting_api_value: int | UserGroupMembersData | None = None,
    *,
    acting_user: UserProfile | None,
) -> None:
    """Takes in a realm object, the name of an attribute to update, the
    user_group to update and the user who initiated the update.
    """
    assert setting_name in Realm.REALM_PERMISSION_GROUP_SETTINGS
    old_value = getattr(realm, setting_name)

    setattr(realm, setting_name, user_group)
    realm.save(update_fields=[setting_name])

    if old_setting_api_value is None:
        # Most production callers will have computed this as part of
        # verifying whether there's an actual change to make, but it
        # feels quite clumsy to have to pass it from unit tests, so we
        # compute it here if not provided by the caller.
        old_setting_api_value = get_group_setting_value_for_api(old_value)
    new_setting_api_value = get_group_setting_value_for_api(user_group)

    if not hasattr(old_value, "named_user_group") and hasattr(user_group, "named_user_group"):
        # We delete the UserGroup which the setting was set to
        # previously if it does not have any linked NamedUserGroup
        # object, as it is not used anywhere else. A new UserGroup
        # object would be created if the setting is later set to
        # a combination of users and groups.
        old_value.delete()

    event = dict(
        type="realm",
        op="update_dict",
        property="default",
        data={setting_name: convert_to_user_group_members_dict(new_setting_api_value)},
    )

    send_event_on_commit(realm, event, active_user_ids(realm.id))

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm,
        event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
        event_time=event_time,
        acting_user=acting_user,
        extra_data={
            RealmAuditLog.OLD_VALUE: get_group_setting_value_for_audit_log_data(
                old_setting_api_value
            ),
            RealmAuditLog.NEW_VALUE: get_group_setting_value_for_audit_log_data(
                new_setting_api_value
            ),
            "property": setting_name,
        },
    )


def parse_and_set_setting_value_if_required(
    realm: Realm, setting_name: str, value: int | str, *, acting_user: UserProfile | None
) -> tuple[int | None, bool]:
    parsed_value = parse_message_time_limit_setting(
        value,
        Realm.MESSAGE_TIME_LIMIT_SETTING_SPECIAL_VALUES_MAP,
        setting_name=setting_name,
    )

    setting_value_changed = False
    if parsed_value is None and getattr(realm, setting_name) is not None:
        # We handle "None" here separately, since in the update_realm view
        # function, do_set_realm_property is called only if setting value is
        # not "None". For values other than "None", the view function itself
        # sets the value by calling "do_set_realm_property".
        do_set_realm_property(
            realm,
            setting_name,
            parsed_value,
            acting_user=acting_user,
        )
        setting_value_changed = True

    return parsed_value, setting_value_changed


def get_realm_authentication_methods_for_page_params_api(
    realm: Realm, authentication_methods: dict[str, bool]
) -> dict[str, Any]:
    # To avoid additional queries, this expects passing in the authentication_methods
    # dictionary directly, which is useful when the caller already has to fetch it
    # for other purposes - and that's the circumstance in which this function is
    # currently used. We can trivially make this argument optional if needed.

    from zproject.backends import AUTH_BACKEND_NAME_MAP

    result_dict: dict[str, dict[str, str | bool]] = {
        backend_name: {"enabled": enabled, "available": True}
        for backend_name, enabled in authentication_methods.items()
    }

    if not settings.BILLING_ENABLED:
        return result_dict

    # The rest of the function is only for the mechanism of restricting
    # certain backends based on the realm's plan type on Zulip Cloud.

    from corporate.models.plans import CustomerPlan

    for backend_name, backend_result in result_dict.items():
        available_for = AUTH_BACKEND_NAME_MAP[backend_name].available_for_cloud_plans

        if available_for is not None and realm.plan_type not in available_for:
            backend_result["available"] = False

            required_upgrade_plan_number = min(
                set(available_for).intersection({Realm.PLAN_TYPE_STANDARD, Realm.PLAN_TYPE_PLUS})
            )
            if required_upgrade_plan_number == Realm.PLAN_TYPE_STANDARD:
                required_upgrade_plan_name = CustomerPlan.name_from_tier(
                    CustomerPlan.TIER_CLOUD_STANDARD
                )
            else:
                assert required_upgrade_plan_number == Realm.PLAN_TYPE_PLUS
                required_upgrade_plan_name = CustomerPlan.name_from_tier(
                    CustomerPlan.TIER_CLOUD_PLUS
                )

            backend_result["unavailable_reason"] = _(
                "You need to upgrade to the {required_upgrade_plan_name} plan to use this authentication method."
            ).format(required_upgrade_plan_name=required_upgrade_plan_name)
        else:
            backend_result["available"] = True

    return result_dict


def validate_authentication_methods_dict_from_api(
    realm: Realm, authentication_methods: dict[str, bool]
) -> None:
    current_authentication_methods = realm.authentication_methods_dict()
    for name in authentication_methods:
        if name not in current_authentication_methods:
            raise JsonableError(
                _("Invalid authentication method: {name}. Valid methods are: {methods}").format(
                    name=name, methods=sorted(current_authentication_methods.keys())
                )
            )

    if settings.BILLING_ENABLED:
        validate_plan_for_authentication_methods(realm, authentication_methods)


def validate_plan_for_authentication_methods(
    realm: Realm, authentication_methods: dict[str, bool]
) -> None:
    from zproject.backends import AUTH_BACKEND_NAME_MAP

    old_authentication_methods = realm.authentication_methods_dict()
    newly_enabled_authentication_methods = {
        name
        for name, enabled in authentication_methods.items()
        if enabled and not old_authentication_methods.get(name, False)
    }
    for name in newly_enabled_authentication_methods:
        available_for = AUTH_BACKEND_NAME_MAP[name].available_for_cloud_plans
        if available_for is not None and realm.plan_type not in available_for:
            # This should only be feasible via the API, since app UI should prevent
            # trying to enable an unavailable authentication method.
            raise JsonableError(
                _("Authentication method {name} is not available on your current plan.").format(
                    name=name
                )
            )


@transaction.atomic(savepoint=False)
def do_set_realm_authentication_methods(
    realm: Realm, authentication_methods: dict[str, bool], *, acting_user: UserProfile | None
) -> None:
    old_value = realm.authentication_methods_dict()
    for key, value in authentication_methods.items():
        # This does queries in a loop, but this isn't a performance sensitive
        # path and is only run rarely.
        if value:
            RealmAuthenticationMethod.objects.get_or_create(realm=realm, name=key)
        else:
            RealmAuthenticationMethod.objects.filter(realm=realm, name=key).delete()

    updated_value = realm.authentication_methods_dict()
    RealmAuditLog.objects.create(
        realm=realm,
        event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
        event_time=timezone_now(),
        acting_user=acting_user,
        extra_data={
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: updated_value,
            "property": "authentication_methods",
        },
    )

    event_data = dict(
        authentication_methods=get_realm_authentication_methods_for_page_params_api(
            realm, updated_value
        )
    )
    event = dict(
        type="realm",
        op="update_dict",
        property="default",
        data=event_data,
    )
    send_event_on_commit(realm, event, active_user_ids(realm.id))


def do_set_realm_stream(
    realm: Realm,
    field: Literal[
        "moderation_request_channel",
        "new_stream_announcements_stream",
        "signup_announcements_stream",
        "zulip_update_announcements_stream",
    ],
    stream: Stream | None,
    stream_id: int,
    *,
    acting_user: UserProfile | None,
) -> None:
    # We could calculate more of these variables from `field`, but
    # it's probably more readable to not do so.
    if field == "moderation_request_channel":
        old_value = realm.moderation_request_channel_id
        realm.moderation_request_channel = stream
        property = "moderation_request_channel_id"
    elif field == "new_stream_announcements_stream":
        old_value = realm.new_stream_announcements_stream_id
        realm.new_stream_announcements_stream = stream
        property = "new_stream_announcements_stream_id"
    elif field == "signup_announcements_stream":
        old_value = realm.signup_announcements_stream_id
        realm.signup_announcements_stream = stream
        property = "signup_announcements_stream_id"
    elif field == "zulip_update_announcements_stream":
        old_value = realm.zulip_update_announcements_stream_id
        realm.zulip_update_announcements_stream = stream
        property = "zulip_update_announcements_stream_id"
    else:
        raise AssertionError("Invalid realm stream field.")

    with transaction.atomic(durable=True):
        realm.save(update_fields=[field])

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
            event_time=event_time,
            acting_user=acting_user,
            extra_data={
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: stream_id,
                "property": field,
            },
        )

        event = dict(
            type="realm",
            op="update",
            property=property,
            value=stream_id,
        )
        send_event_on_commit(realm, event, active_user_ids(realm.id))


def do_set_realm_moderation_request_channel(
    realm: Realm, stream: Stream | None, stream_id: int, *, acting_user: UserProfile | None
) -> None:
    if stream is not None and stream.is_public():
        raise JsonableError(_("Moderation request channel must be private."))
    do_set_realm_stream(
        realm, "moderation_request_channel", stream, stream_id, acting_user=acting_user
    )


def do_set_realm_new_stream_announcements_stream(
    realm: Realm, stream: Stream | None, stream_id: int, *, acting_user: UserProfile | None
) -> None:
    do_set_realm_stream(
        realm, "new_stream_announcements_stream", stream, stream_id, acting_user=acting_user
    )


def do_set_realm_signup_announcements_stream(
    realm: Realm, stream: Stream | None, stream_id: int, *, acting_user: UserProfile | None
) -> None:
    do_set_realm_stream(
        realm, "signup_announcements_stream", stream, stream_id, acting_user=acting_user
    )


def do_set_realm_zulip_update_announcements_stream(
    realm: Realm, stream: Stream | None, stream_id: int, *, acting_user: UserProfile | None
) -> None:
    do_set_realm_stream(
        realm, "zulip_update_announcements_stream", stream, stream_id, acting_user=acting_user
    )


@transaction.atomic(durable=True)
def do_set_realm_user_default_setting(
    realm_user_default: RealmUserDefault,
    name: str,
    raw_value: Any,
    *,
    acting_user: UserProfile | None,
) -> None:
    old_value = getattr(realm_user_default, name)
    realm = realm_user_default.realm
    event_time = timezone_now()

    if isinstance(raw_value, Enum):
        value = raw_value.value
        event_value = raw_value.name
    else:
        value = raw_value
        event_value = raw_value

    setattr(realm_user_default, name, value)
    realm_user_default.save(update_fields=[name])

    RealmAuditLog.objects.create(
        realm=realm,
        event_type=AuditLogEventType.REALM_DEFAULT_USER_SETTINGS_CHANGED,
        event_time=event_time,
        acting_user=acting_user,
        extra_data={
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: value,
            "property": name,
        },
    )

    event = dict(
        type="realm_user_settings_defaults",
        op="update",
        property=name,
        value=event_value,
    )
    send_event_on_commit(realm, event, active_user_ids(realm.id))


RealmDeactivationReasonType = Literal[
    "owner_request",
    "tos_violation",
    "inactivity",
    "self_hosting_migration",
    "demo_expired",
    # When we change the subdomain of a realm, we leave
    # behind a deactivated gravestone realm.
    "subdomain_change",
]


def do_deactivate_realm(
    realm: Realm,
    *,
    acting_user: UserProfile | None,
    deactivation_reason: RealmDeactivationReasonType,
    deletion_delay_days: int | None = None,
    email_owners: bool,
) -> None:
    """
    Deactivate this realm. Do NOT deactivate the users -- we need to be able to
    tell the difference between users that were intentionally deactivated,
    e.g. by a realm admin, and users who can't currently use Zulip because their
    realm has been deactivated.
    """
    if realm.deactivated:
        return

    if settings.BILLING_ENABLED:
        from corporate.lib.stripe import RealmBillingSession

    with transaction.atomic(durable=True):
        realm.deactivated = True
        if deletion_delay_days is None:
            realm.save(update_fields=["deactivated"])
        else:
            realm.scheduled_deletion_date = timezone_now() + datetime.timedelta(
                days=deletion_delay_days
            )
            realm.save(update_fields=["scheduled_deletion_date", "deactivated"])

        if settings.BILLING_ENABLED:
            billing_session = RealmBillingSession(user=acting_user, realm=realm)
            billing_session.downgrade_now_without_creating_additional_invoices()

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=AuditLogEventType.REALM_DEACTIVATED,
            event_time=event_time,
            acting_user=acting_user,
            extra_data={
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(realm),
                "deactivation_reason": deactivation_reason,
            },
        )

        from zerver.lib.remote_server import maybe_enqueue_audit_log_upload

        maybe_enqueue_audit_log_upload(realm)

        ScheduledEmail.objects.filter(realm=realm).delete()

        # This event will only ever be received by clients with an active
        # longpoll connection, because by this point clients will be
        # unable to authenticate again to their event queue (triggering an
        # immediate reload into the page explaining the realm was
        # deactivated). So the purpose of sending this is to flush all
        # active longpoll connections for the realm.
        event = dict(type="realm", op="deactivated", realm_id=realm.id)
        send_event_on_commit(realm, event, active_user_ids(realm.id))

        if deletion_delay_days == 0:
            event = {
                "type": "scrub_deactivated_realm",
                "realm_id": realm.id,
            }
            queue_json_publish_rollback_unsafe("deferred_work", event)

    # Don't deactivate the users, as that would lose a lot of state if
    # the realm needs to be reactivated, but do delete their sessions
    # so they get bumped to the login screen, where they'll get a
    # realm deactivation notice when they try to log in.
    #
    # Note: This is intentionally outside the transaction because it
    # is unsafe to modify sessions inside transactions with the
    # cached_db session plugin we're using, and our session engine
    # declared in zerver/lib/safe_session_cached_db.py enforces this.
    delete_realm_user_sessions(realm)

    # Flag to send deactivated realm email to organization owners; is false
    # for realm exports and realm subdomain changes so that those actions
    # do not email active organization owners.
    if email_owners:
        do_send_realm_deactivation_email(realm, acting_user, deletion_delay_days)


def delete_expired_demo_organizations() -> None:
    demo_organizations_to_delete = Realm.objects.filter(
        deactivated=False, demo_organization_scheduled_deletion_date__lte=timezone_now()
    )
    for demo_organization in demo_organizations_to_delete:
        email_owners = False
        if demo_organization_owner_email_exists(demo_organization):
            email_owners = True
        # By setting deletion_delay_days to zero, we send an event to
        # the deferred work queue to scrub the realm data when
        # deactivating the realm.
        do_deactivate_realm(
            realm=demo_organization,
            acting_user=None,
            deactivation_reason="demo_expired",
            deletion_delay_days=0,
            email_owners=email_owners,
        )


def do_reactivate_realm(realm: Realm) -> None:
    if not realm.deactivated:
        logging.warning("Realm %s cannot be reactivated because it is already active.", realm.id)
        return

    realm.deactivated = False
    realm.scheduled_deletion_date = None
    with transaction.atomic(durable=True):
        realm.save(update_fields=["deactivated", "scheduled_deletion_date"])

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            # We hardcode acting_user=None, since realm reactivation
            # uses an email authentication mechanism that will never
            # know which user initiated the change.
            acting_user=None,
            realm=realm,
            event_type=AuditLogEventType.REALM_REACTIVATED,
            event_time=event_time,
            extra_data={
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(realm),
            },
        )

        from zerver.lib.remote_server import maybe_enqueue_audit_log_upload

        maybe_enqueue_audit_log_upload(realm)


def do_add_deactivated_redirect(realm: Realm, redirect_url: str) -> None:
    realm.deactivated_redirect = redirect_url
    realm.save(update_fields=["deactivated_redirect"])


def do_delete_all_realm_attachments(realm: Realm, *, batch_size: int = 1000) -> None:
    # Delete attachment files from the storage backend, so that we
    # don't leave them dangling.
    for obj_class in Attachment, ArchivedAttachment:
        last_id = 0
        while True:
            to_delete = (
                obj_class._default_manager.filter(realm_id=realm.id, pk__gt=last_id)
                .order_by("pk")
                .values_list("pk", "path_id")[:batch_size]
            )
            if len(to_delete) > 0:
                delete_message_attachments([row[1] for row in to_delete])
                last_id = to_delete[len(to_delete) - 1][0]
            if len(to_delete) < batch_size:
                break
        obj_class._default_manager.filter(realm=realm).delete()


@transaction.atomic(durable=True)
def do_scrub_realm(realm: Realm, *, acting_user: UserProfile | None) -> None:
    if settings.BILLING_ENABLED:
        from corporate.lib.stripe import RealmBillingSession

        billing_session = RealmBillingSession(user=acting_user, realm=realm)
        billing_session.downgrade_now_without_creating_additional_invoices()

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

    internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
    # We could more simply obtain the Message list by just doing
    # Message.objects.filter(sender__realm=internal_realm, realm=realm), but it's
    # more secure against bugs that may cause Message.realm to be incorrect for some
    # cross-realm messages to also determine the actual Recipients - to prevent
    # deletion of excessive messages.
    all_recipient_ids_in_realm = [
        *Stream.objects.filter(realm=realm).values_list("recipient_id", flat=True),
        *UserProfile.objects.filter(realm=realm).values_list("recipient_id", flat=True),
        *Subscription.objects.filter(
            recipient__type=Recipient.DIRECT_MESSAGE_GROUP, user_profile__realm=realm
        ).values_list("recipient_id", flat=True),
    ]
    cross_realm_bot_message_ids = list(
        Message.objects.filter(
            # Filtering by both message.recipient and message.realm is
            # more robust for ensuring no messages belonging to
            # another realm will be deleted due to some bugs.
            #
            # Uses index: zerver_message_realm_sender_recipient
            sender__realm=internal_realm,
            recipient_id__in=all_recipient_ids_in_realm,
            realm=realm,
        ).values_list("id", flat=True)
    )
    move_messages_to_archive(cross_realm_bot_message_ids)

    do_remove_realm_custom_profile_fields(realm)
    do_delete_all_realm_attachments(realm)

    RealmAuditLog.objects.create(
        realm=realm,
        event_time=timezone_now(),
        acting_user=acting_user,
        event_type=AuditLogEventType.REALM_SCRUBBED,
    )
    realm.scheduled_deletion_date = None
    realm.save()


def scrub_deactivated_realm(realm_to_scrub: Realm) -> None:
    if (
        realm_to_scrub.scheduled_deletion_date is not None
        and realm_to_scrub.scheduled_deletion_date <= timezone_now()
    ):
        assert realm_to_scrub.deactivated, (
            "Non-deactivated realm unexpectedly scheduled for deletion."
        )
        do_scrub_realm(realm_to_scrub, acting_user=None)
        logging.info("Scrubbed realm %s", realm_to_scrub.id)


def clean_deactivated_realm_data() -> None:
    realms_to_scrub = Realm.objects.filter(
        deactivated=True,
        scheduled_deletion_date__lte=timezone_now(),
    )
    for realm in realms_to_scrub:
        scrub_deactivated_realm(realm)


@transaction.atomic(durable=True)
def do_change_realm_org_type(
    realm: Realm,
    org_type: int,
    acting_user: UserProfile | None,
) -> None:
    old_value = realm.org_type
    realm.org_type = org_type
    realm.save(update_fields=["org_type"])

    RealmAuditLog.objects.create(
        event_type=AuditLogEventType.REALM_ORG_TYPE_CHANGED,
        realm=realm,
        event_time=timezone_now(),
        acting_user=acting_user,
        extra_data={"old_value": old_value, "new_value": org_type},
    )

    event = dict(type="realm", op="update", property="org_type", value=org_type)
    send_event_on_commit(realm, event, active_user_ids(realm.id))


@transaction.atomic(durable=True)
def do_change_realm_max_invites(realm: Realm, max_invites: int, acting_user: UserProfile) -> None:
    old_value = realm.max_invites
    if max_invites == 0:
        # Reset to default maximum for plan type
        new_max = get_default_max_invites_for_realm_plan_type(realm.plan_type)
    else:
        new_max = max_invites
    realm.max_invites = new_max
    realm.save(update_fields=["_max_invites"])

    RealmAuditLog.objects.create(
        event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
        realm=realm,
        event_time=timezone_now(),
        acting_user=acting_user,
        extra_data={
            "old_value": old_value,
            "new_value": new_max,
            "property": "max_invites",
        },
    )


@transaction.atomic(savepoint=False)
def do_change_realm_plan_type(
    realm: Realm, plan_type: int, *, acting_user: UserProfile | None
) -> None:
    from zproject.backends import AUTH_BACKEND_NAME_MAP

    old_value = realm.plan_type
    if plan_type not in Realm.ALL_PLAN_TYPES:
        raise AssertionError("Invalid plan type")

    if plan_type == Realm.PLAN_TYPE_LIMITED:
        # We do not allow public access on limited plans.
        do_set_realm_property(realm, "enable_spectator_access", False, acting_user=acting_user)

    if old_value in [Realm.PLAN_TYPE_PLUS, Realm.PLAN_TYPE_SELF_HOSTED] and plan_type not in [
        Realm.PLAN_TYPE_PLUS,
        Realm.PLAN_TYPE_SELF_HOSTED,
    ]:
        # If downgrading to a plan that no longer has access to change
        # can_access_all_users_group, set it back to the default
        # value.
        everyone_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm=realm, is_system_group=True
        )
        if realm.can_access_all_users_group_id != everyone_system_group.id:
            do_change_realm_permission_group_setting(
                realm, "can_access_all_users_group", everyone_system_group, acting_user=acting_user
            )

    # If downgrading, disable authentication methods that are not available on the new plan.
    if settings.BILLING_ENABLED:
        realm_authentication_methods = realm.authentication_methods_dict()
        for backend_name, enabled in realm_authentication_methods.items():
            if enabled and plan_type < old_value:
                available_for = AUTH_BACKEND_NAME_MAP[backend_name].available_for_cloud_plans
                if available_for is not None and plan_type not in available_for:
                    realm_authentication_methods[backend_name] = False
        if realm_authentication_methods != realm.authentication_methods_dict():
            do_set_realm_authentication_methods(
                realm, realm_authentication_methods, acting_user=acting_user
            )

    realm.plan_type = plan_type
    realm.save(update_fields=["plan_type"])
    RealmAuditLog.objects.create(
        event_type=AuditLogEventType.REALM_PLAN_TYPE_CHANGED,
        realm=realm,
        event_time=timezone_now(),
        acting_user=acting_user,
        extra_data={"old_value": old_value, "new_value": plan_type},
    )

    realm.max_invites = get_default_max_invites_for_realm_plan_type(plan_type)
    if plan_type == Realm.PLAN_TYPE_LIMITED:
        realm.message_visibility_limit = Realm.MESSAGE_VISIBILITY_LIMITED
    else:
        realm.message_visibility_limit = None

    update_first_visible_message_id(realm)

    realm.save(update_fields=["_max_invites", "message_visibility_limit"])

    event = dict(
        type="realm",
        op="update_dict",
        property="default",
        data={
            "plan_type": plan_type,
            "upload_quota_mib": optional_bytes_to_mib(realm.upload_quota_bytes()),
            "max_file_upload_size_mib": realm.get_max_file_upload_size_mebibytes(),
        },
    )
    send_event_on_commit(realm, event, active_user_ids(realm.id))


def do_send_realm_reactivation_email(realm: Realm, *, acting_user: UserProfile | None) -> None:
    obj = RealmReactivationStatus.objects.create(realm=realm)

    url = create_confirmation_link(obj, Confirmation.REALM_REACTIVATION)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=AuditLogEventType.REALM_REACTIVATION_EMAIL_SENT,
        event_time=timezone_now(),
    )
    context = {
        "confirmation_url": url,
        "realm_url": realm.url,
        "realm_name": realm.name,
        "corporate_enabled": settings.CORPORATE_ENABLED,
    }
    language = realm.default_language
    send_email_to_admins(
        "zerver/emails/realm_reactivation",
        realm,
        from_address=FromAddress.tokenized_no_reply_address(),
        from_name=FromAddress.security_email_from_name(language=language),
        language=language,
        context=context,
    )


def do_send_realm_deactivation_email(
    realm: Realm, acting_user: UserProfile | None, deletion_delay_days: int | None
) -> None:
    shared_context: dict[str, Any] = {
        "realm_name": realm.name,
    }
    deactivation_time = timezone_now()
    owners = set(realm.get_human_owner_users())
    anonymous_deactivation = False
    data_deleted = False
    scheduled_data_deletion = None

    # The realm was deactivated via the deactivate_realm management command.
    if acting_user is None:
        anonymous_deactivation = True

    # This realm was deactivated from the support panel; we do not share the
    # deactivating user's information in this case.
    if acting_user is not None and acting_user not in owners:
        anonymous_deactivation = True

    # If realm data has been deleted or has a date set for it to be deleted,
    # we include that information in the deactivation email to owners.
    if deletion_delay_days is not None:
        if deletion_delay_days == 0:
            data_deleted = True
        else:
            scheduled_data_deletion = realm.scheduled_deletion_date

    for owner in owners:
        owner_tz = owner.timezone
        if owner_tz == "":
            owner_tz = timezone_get_current_timezone_name()
        local_date = deactivation_time.astimezone(
            zoneinfo.ZoneInfo(canonicalize_timezone(owner_tz))
        ).date()
        if scheduled_data_deletion:
            data_deletion_date = scheduled_data_deletion.astimezone(
                zoneinfo.ZoneInfo(canonicalize_timezone(owner_tz))
            ).date()
        else:
            data_deletion_date = None

        if anonymous_deactivation:
            context = dict(
                acting_user=False,
                initiated_deactivation=False,
                event_date=local_date,
                data_already_deleted=data_deleted,
                scheduled_deletion_date=data_deletion_date,
                **shared_context,
            )
        else:
            assert acting_user is not None
            if owner == acting_user:
                context = dict(
                    acting_user=True,
                    initiated_deactivation=True,
                    event_date=local_date,
                    data_already_deleted=data_deleted,
                    scheduled_deletion_date=data_deletion_date,
                    **shared_context,
                )
            else:
                context = dict(
                    acting_user=True,
                    initiated_deactivation=False,
                    deactivating_owner=acting_user.full_name,
                    event_date=local_date,
                    data_already_deleted=data_deleted,
                    scheduled_deletion_date=data_deletion_date,
                    **shared_context,
                )

        send_email(
            "zerver/emails/realm_deactivated",
            to_emails=[owner.delivery_email],
            from_name=FromAddress.security_email_from_name(language=owner.default_language),
            from_address=FromAddress.SUPPORT,
            language=owner.default_language,
            context=context,
            realm=realm,
        )
