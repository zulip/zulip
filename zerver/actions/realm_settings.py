import logging
from email.headerregistry import Address
from typing import Any, Dict, Literal, Optional, Tuple, Union

from django.conf import settings
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from confirmation.models import Confirmation, create_confirmation_link, generate_key
from zerver.actions.custom_profile_fields import do_remove_realm_custom_profile_fields
from zerver.actions.message_delete import do_delete_messages_by_sender
from zerver.actions.user_groups import update_users_in_full_members_system_group
from zerver.actions.user_settings import do_delete_avatar_image
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import parse_message_time_limit_setting, update_first_visible_message_id
from zerver.lib.retention import move_messages_to_archive
from zerver.lib.send_email import FromAddress, send_email_to_admins
from zerver.lib.sessions import delete_realm_user_sessions
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.upload import delete_message_attachments
from zerver.lib.user_counts import realm_user_count_by_role
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
from zerver.models.realms import get_realm
from zerver.models.users import active_user_ids
from zerver.tornado.django_api import send_event, send_event_on_commit

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import RealmBillingSession


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

    send_event_on_commit(realm, event, active_user_ids(realm.id))

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm,
        event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
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


def do_set_push_notifications_enabled_end_timestamp(
    realm: Realm, value: Optional[int], *, acting_user: Optional[UserProfile]
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

    with transaction.atomic():
        new_datetime = None
        if value is not None:
            new_datetime = timestamp_to_datetime(value)
        setattr(realm, name, new_datetime)
        realm.save(update_fields=[name])

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
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
    send_event(realm, event, active_user_ids(realm.id))


@transaction.atomic(savepoint=False)
def do_change_realm_permission_group_setting(
    realm: Realm, setting_name: str, user_group: UserGroup, *, acting_user: Optional[UserProfile]
) -> None:
    """Takes in a realm object, the name of an attribute to update, the
    user_group to update and and the user who initiated the update.
    """
    assert setting_name in Realm.REALM_PERMISSION_GROUP_SETTINGS
    old_user_group_id = getattr(realm, setting_name).id

    setattr(realm, setting_name, user_group)
    realm.save(update_fields=[setting_name])

    event = dict(
        type="realm",
        op="update_dict",
        property="default",
        data={setting_name: user_group.id},
    )

    send_event_on_commit(realm, event, active_user_ids(realm.id))

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm,
        event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
        event_time=event_time,
        acting_user=acting_user,
        extra_data={
            RealmAuditLog.OLD_VALUE: old_user_group_id,
            RealmAuditLog.NEW_VALUE: user_group.id,
            "property": setting_name,
        },
    )


def parse_and_set_setting_value_if_required(
    realm: Realm, setting_name: str, value: Union[int, str], *, acting_user: Optional[UserProfile]
) -> Tuple[Optional[int], bool]:
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
    realm: Realm, authentication_methods: Dict[str, bool]
) -> Dict[str, Any]:
    # To avoid additional queries, this expects passing in the authentication_methods
    # dictionary directly, which is useful when the caller already has to fetch it
    # for other purposes - and that's the circumstance in which this function is
    # currently used. We can trivially make this argument optional if needed.

    from zproject.backends import AUTH_BACKEND_NAME_MAP

    result_dict: Dict[str, Dict[str, Union[str, bool]]] = {
        backend_name: {"enabled": enabled, "available": True}
        for backend_name, enabled in authentication_methods.items()
    }

    if not settings.BILLING_ENABLED:
        return result_dict

    # The rest of the function is only for the mechanism of restricting
    # certain backends based on the realm's plan type on Zulip Cloud.

    from corporate.models import CustomerPlan

    for backend_name in result_dict:
        available_for = AUTH_BACKEND_NAME_MAP[backend_name].available_for_cloud_plans

        if available_for is not None and realm.plan_type not in available_for:
            result_dict[backend_name]["available"] = False

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

            result_dict[backend_name]["unavailable_reason"] = _(
                "You need to upgrade to the {required_upgrade_plan_name} plan to use this authentication method."
            ).format(required_upgrade_plan_name=required_upgrade_plan_name)
        else:
            result_dict[backend_name]["available"] = True

    return result_dict


def validate_authentication_methods_dict_from_api(
    realm: Realm, authentication_methods: Dict[str, bool]
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
    realm: Realm, authentication_methods: Dict[str, bool]
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


def do_set_realm_authentication_methods(
    realm: Realm, authentication_methods: Dict[str, bool], *, acting_user: Optional[UserProfile]
) -> None:
    old_value = realm.authentication_methods_dict()
    with transaction.atomic():
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
            event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
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
    send_event(realm, event, active_user_ids(realm.id))


def do_set_realm_stream(
    realm: Realm,
    field: Literal[
        "new_stream_announcements_stream",
        "signup_announcements_stream",
        "zulip_update_announcements_stream",
    ],
    stream: Optional[Stream],
    stream_id: int,
    *,
    acting_user: Optional[UserProfile],
) -> None:
    # We could calculate more of these variables from `field`, but
    # it's probably more readable to not do so.
    if field == "new_stream_announcements_stream":
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

    with transaction.atomic():
        realm.save(update_fields=[field])

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
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
    send_event(realm, event, active_user_ids(realm.id))


def do_set_realm_new_stream_announcements_stream(
    realm: Realm, stream: Optional[Stream], stream_id: int, *, acting_user: Optional[UserProfile]
) -> None:
    do_set_realm_stream(
        realm, "new_stream_announcements_stream", stream, stream_id, acting_user=acting_user
    )


def do_set_realm_signup_announcements_stream(
    realm: Realm, stream: Optional[Stream], stream_id: int, *, acting_user: Optional[UserProfile]
) -> None:
    do_set_realm_stream(
        realm, "signup_announcements_stream", stream, stream_id, acting_user=acting_user
    )


def do_set_realm_zulip_update_announcements_stream(
    realm: Realm, stream: Optional[Stream], stream_id: int, *, acting_user: Optional[UserProfile]
) -> None:
    do_set_realm_stream(
        realm, "zulip_update_announcements_stream", stream, stream_id, acting_user=acting_user
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

    with transaction.atomic():
        realm.deactivated = True
        realm.save(update_fields=["deactivated"])

        if settings.BILLING_ENABLED:
            billing_session = RealmBillingSession(user=acting_user, realm=realm)
            billing_session.downgrade_now_without_creating_additional_invoices()

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=RealmAuditLog.REALM_DEACTIVATED,
            event_time=event_time,
            acting_user=acting_user,
            extra_data={
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(realm),
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


def do_scrub_realm(realm: Realm, *, acting_user: Optional[UserProfile]) -> None:
    if settings.BILLING_ENABLED:
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
        extra_data={"old_value": old_value, "new_value": org_type},
    )

    event = dict(type="realm", op="update", property="org_type", value=org_type)
    send_event_on_commit(realm, event, active_user_ids(realm.id))


@transaction.atomic(savepoint=False)
def do_change_realm_plan_type(
    realm: Realm, plan_type: int, *, acting_user: Optional[UserProfile]
) -> None:
    from zproject.backends import AUTH_BACKEND_NAME_MAP

    old_value = realm.plan_type

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
        event_type=RealmAuditLog.REALM_PLAN_TYPE_CHANGED,
        realm=realm,
        event_time=timezone_now(),
        acting_user=acting_user,
        extra_data={"old_value": old_value, "new_value": plan_type},
    )

    if plan_type == Realm.PLAN_TYPE_PLUS:
        realm.max_invites = Realm.INVITES_STANDARD_REALM_DAILY_MAX
        realm.message_visibility_limit = None
    elif plan_type == Realm.PLAN_TYPE_STANDARD:
        realm.max_invites = Realm.INVITES_STANDARD_REALM_DAILY_MAX
        realm.message_visibility_limit = None
    elif plan_type == Realm.PLAN_TYPE_SELF_HOSTED:
        realm.max_invites = None  # type: ignore[assignment] # https://github.com/python/mypy/issues/3004
        realm.message_visibility_limit = None
    elif plan_type == Realm.PLAN_TYPE_STANDARD_FREE:
        realm.max_invites = Realm.INVITES_STANDARD_REALM_DAILY_MAX
        realm.message_visibility_limit = None
    elif plan_type == Realm.PLAN_TYPE_LIMITED:
        realm.max_invites = settings.INVITES_DEFAULT_REALM_DAILY_MAX
        realm.message_visibility_limit = Realm.MESSAGE_VISIBILITY_LIMITED
    else:
        raise AssertionError("Invalid plan type")

    update_first_visible_message_id(realm)

    realm.save(
        update_fields=[
            "_max_invites",
            "enable_spectator_access",
            "message_visibility_limit",
        ]
    )

    event = {
        "type": "realm",
        "op": "update",
        "property": "plan_type",
        "value": plan_type,
        "extra_data": {"upload_quota": realm.upload_quota_bytes()},
    }
    send_event_on_commit(realm, event, active_user_ids(realm.id))


def do_send_realm_reactivation_email(realm: Realm, *, acting_user: Optional[UserProfile]) -> None:
    obj = RealmReactivationStatus.objects.create(realm=realm)

    url = create_confirmation_link(obj, Confirmation.REALM_REACTIVATION)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_REACTIVATION_EMAIL_SENT,
        event_time=timezone_now(),
    )
    context = {
        "confirmation_url": url,
        "realm_uri": realm.uri,
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
