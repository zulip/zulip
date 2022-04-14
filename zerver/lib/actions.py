import datetime
import logging
from typing import Any, Dict, List, Optional, Sequence

import orjson
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from confirmation.models import Confirmation, create_confirmation_link, generate_key
from zerver.actions.custom_profile_fields import do_remove_realm_custom_profile_fields
from zerver.actions.message_edit import do_delete_messages_by_sender
from zerver.actions.message_send import internal_send_stream_message
from zerver.actions.user_groups import update_users_in_full_members_system_group
from zerver.actions.user_settings import do_delete_avatar_image, send_user_email_update_event
from zerver.lib.bulk_create import create_users
from zerver.lib.cache import flush_user_profile
from zerver.lib.create_user import get_display_email_address
from zerver.lib.email_validation import email_reserved_for_system_bots_error
from zerver.lib.message import update_first_visible_message_id
from zerver.lib.send_email import FromAddress, send_email_to_admins
from zerver.lib.server_initialization import create_internal_realm, server_initialized
from zerver.lib.sessions import delete_user_sessions
from zerver.lib.streams import ensure_stream, get_signups_stream
from zerver.lib.topic import filter_by_topic_name_via_message
from zerver.lib.user_counts import realm_user_count_by_role
from zerver.lib.user_groups import create_system_user_groups_for_realm
from zerver.models import (
    Attachment,
    DefaultStream,
    Message,
    Realm,
    RealmAuditLog,
    RealmDomain,
    RealmUserDefault,
    ScheduledEmail,
    Stream,
    UserMessage,
    UserProfile,
    active_user_ids,
    get_realm,
    get_realm_domains,
    get_system_bot,
    is_cross_realm_bot_email,
)
from zerver.tornado.django_api import send_event

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import downgrade_now_without_creating_additional_invoices


def active_humans_in_realm(realm: Realm) -> Sequence[UserProfile]:
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


def do_set_realm_message_editing(
    realm: Realm,
    allow_message_editing: bool,
    message_content_edit_limit_seconds: int,
    edit_topic_policy: int,
    *,
    acting_user: Optional[UserProfile],
) -> None:
    old_values = dict(
        allow_message_editing=realm.allow_message_editing,
        message_content_edit_limit_seconds=realm.message_content_edit_limit_seconds,
        edit_topic_policy=realm.edit_topic_policy,
    )

    realm.allow_message_editing = allow_message_editing
    realm.message_content_edit_limit_seconds = message_content_edit_limit_seconds
    realm.edit_topic_policy = edit_topic_policy

    event_time = timezone_now()
    updated_properties = dict(
        allow_message_editing=allow_message_editing,
        message_content_edit_limit_seconds=message_content_edit_limit_seconds,
        edit_topic_policy=edit_topic_policy,
    )

    with transaction.atomic():
        for updated_property, updated_value in updated_properties.items():
            if updated_value == old_values[updated_property]:
                continue
            RealmAuditLog.objects.create(
                realm=realm,
                event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                event_time=event_time,
                acting_user=acting_user,
                extra_data=orjson.dumps(
                    {
                        RealmAuditLog.OLD_VALUE: old_values[updated_property],
                        RealmAuditLog.NEW_VALUE: updated_value,
                        "property": updated_property,
                    }
                ).decode(),
            )

        realm.save(update_fields=list(updated_properties.keys()))

    event = dict(
        type="realm",
        op="update_dict",
        property="default",
        data=updated_properties,
    )
    send_event(realm, event, active_user_ids(realm.id))


def do_set_realm_notifications_stream(
    realm: Realm, stream: Optional[Stream], stream_id: int, *, acting_user: Optional[UserProfile]
) -> None:
    old_value = realm.notifications_stream_id
    realm.notifications_stream = stream
    with transaction.atomic():
        realm.save(update_fields=["notifications_stream"])

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
                    "property": "notifications_stream",
                }
            ).decode(),
        )

    event = dict(
        type="realm",
        op="update",
        property="notifications_stream_id",
        value=stream_id,
    )
    send_event(realm, event, active_user_ids(realm.id))


def do_set_realm_signup_notifications_stream(
    realm: Realm, stream: Optional[Stream], stream_id: int, *, acting_user: Optional[UserProfile]
) -> None:
    old_value = realm.signup_notifications_stream_id
    realm.signup_notifications_stream = stream
    with transaction.atomic():
        realm.save(update_fields=["signup_notifications_stream"])

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
                    "property": "signup_notifications_stream",
                }
            ).decode(),
        )
    event = dict(
        type="realm",
        op="update",
        property="signup_notifications_stream_id",
        value=stream_id,
    )
    send_event(realm, event, active_user_ids(realm.id))


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
    realm.deactivated = False
    with transaction.atomic():
        realm.save(update_fields=["deactivated"])

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=RealmAuditLog.REALM_REACTIVATED,
            event_time=event_time,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(realm),
                }
            ).decode(),
        )


def do_change_realm_subdomain(
    realm: Realm, new_subdomain: str, *, acting_user: Optional[UserProfile]
) -> None:
    """Changing a realm's subdomain is a highly disruptive operation,
    because all existing clients will need to be updated to point to
    the new URL.  Further, requests to fetch data from existing event
    queues will fail with an authentication error when this change
    happens (because the old subdomain is no longer associated with
    the realm), making it hard for us to provide a graceful update
    experience for clients.
    """
    old_subdomain = realm.subdomain
    old_uri = realm.uri
    # If the realm had been a demo organization scheduled for
    # deleting, clear that state.
    realm.demo_organization_scheduled_deletion_date = None
    realm.string_id = new_subdomain
    with transaction.atomic():
        realm.save(update_fields=["string_id", "demo_organization_scheduled_deletion_date"])
        RealmAuditLog.objects.create(
            realm=realm,
            event_type=RealmAuditLog.REALM_SUBDOMAIN_CHANGED,
            event_time=timezone_now(),
            acting_user=acting_user,
            extra_data={"old_subdomain": old_subdomain, "new_subdomain": new_subdomain},
        )

        # If a realm if being renamed multiple times, we should find all the placeholder
        # realms and reset their deactivated_redirect field to point to the new realm uri
        placeholder_realms = Realm.objects.filter(deactivated_redirect=old_uri, deactivated=True)
        for placeholder_realm in placeholder_realms:
            do_add_deactivated_redirect(placeholder_realm, realm.uri)

    # The below block isn't executed in a transaction with the earlier code due to
    # the functions called below being complex and potentially sending events,
    # which we don't want to do in atomic blocks.
    # When we change a realm's subdomain the realm with old subdomain is basically
    # deactivated. We are creating a deactivated realm using old subdomain and setting
    # it's deactivated redirect to new_subdomain so that we can tell the users that
    # the realm has been moved to a new subdomain.
    placeholder_realm = do_create_realm(old_subdomain, realm.name)
    do_deactivate_realm(placeholder_realm, acting_user=None)
    do_add_deactivated_redirect(placeholder_realm, realm.uri)


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
        scrubbed_email = f"scrubbed-{generate_key()[:15]}@{realm.host}"
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
        extra_data={"old_value": old_value, "new_value": org_type},
    )


@transaction.atomic(savepoint=False)
def do_change_realm_plan_type(
    realm: Realm, plan_type: int, *, acting_user: Optional[UserProfile]
) -> None:
    old_value = realm.plan_type
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
        realm.upload_quota_gb = Realm.UPLOAD_QUOTA_STANDARD
    elif plan_type == Realm.PLAN_TYPE_STANDARD:
        realm.max_invites = Realm.INVITES_STANDARD_REALM_DAILY_MAX
        realm.message_visibility_limit = None
        realm.upload_quota_gb = Realm.UPLOAD_QUOTA_STANDARD
    elif plan_type == Realm.PLAN_TYPE_SELF_HOSTED:
        realm.max_invites = None  # type: ignore[assignment] # Apparent mypy bug with Optional[int] setter.
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

    realm.save(update_fields=["_max_invites", "message_visibility_limit", "upload_quota_gb"])

    event = {
        "type": "realm",
        "op": "update",
        "property": "plan_type",
        "value": plan_type,
        "extra_data": {"upload_quota": realm.upload_quota_bytes()},
    }
    transaction.on_commit(lambda: send_event(realm, event, active_user_ids(realm.id)))


def set_realm_permissions_based_on_org_type(realm: Realm) -> None:
    """This function implements overrides for the default configuration
    for new organizations when the administrator selected specific
    organization types.

    This substantially simplifies our /help/ advice for folks setting
    up new organizations of these types.
    """

    # Custom configuration for educational organizations.  The present
    # defaults are designed for a single class, not a department or
    # larger institution, since those are more common.
    if (
        realm.org_type == Realm.ORG_TYPES["education_nonprofit"]["id"]
        or realm.org_type == Realm.ORG_TYPES["education"]["id"]
    ):
        # Limit email address visibility and user creation to administrators.
        realm.email_address_visibility = Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS
        realm.invite_to_realm_policy = Realm.POLICY_ADMINS_ONLY
        # Restrict public stream creation to staff, but allow private
        # streams (useful for study groups, etc.).
        realm.create_public_stream_policy = Realm.POLICY_ADMINS_ONLY
        # Don't allow members (students) to manage user groups or
        # stream subscriptions.
        realm.user_group_edit_policy = Realm.POLICY_MODERATORS_ONLY
        realm.invite_to_stream_policy = Realm.POLICY_MODERATORS_ONLY
        # Allow moderators (TAs?) to move topics between streams.
        realm.move_messages_between_streams_policy = Realm.POLICY_MODERATORS_ONLY


def setup_realm_internal_bots(realm: Realm) -> None:
    """Create this realm's internal bots.

    This function is idempotent; it does nothing for a bot that
    already exists.
    """
    internal_bots = [
        (bot["name"], bot["email_template"] % (settings.INTERNAL_BOT_DOMAIN,))
        for bot in settings.REALM_INTERNAL_BOTS
    ]
    create_users(realm, internal_bots, bot_type=UserProfile.DEFAULT_BOT)
    bots = UserProfile.objects.filter(
        realm=realm,
        email__in=[bot_info[1] for bot_info in internal_bots],
        bot_owner__isnull=True,
    )
    for bot in bots:
        bot.bot_owner = bot
        bot.save()


def do_create_realm(
    string_id: str,
    name: str,
    *,
    emails_restricted_to_domains: Optional[bool] = None,
    email_address_visibility: Optional[int] = None,
    description: Optional[str] = None,
    invite_required: Optional[bool] = None,
    plan_type: Optional[int] = None,
    org_type: Optional[int] = None,
    date_created: Optional[datetime.datetime] = None,
    is_demo_organization: Optional[bool] = False,
    enable_spectator_access: Optional[bool] = False,
) -> Realm:
    if string_id == settings.SOCIAL_AUTH_SUBDOMAIN:
        raise AssertionError("Creating a realm on SOCIAL_AUTH_SUBDOMAIN is not allowed!")
    if Realm.objects.filter(string_id=string_id).exists():
        raise AssertionError(f"Realm {string_id} already exists!")
    if not server_initialized():
        logging.info("Server not yet initialized. Creating the internal realm first.")
        create_internal_realm()

    kwargs: Dict[str, Any] = {}
    if emails_restricted_to_domains is not None:
        kwargs["emails_restricted_to_domains"] = emails_restricted_to_domains
    if email_address_visibility is not None:
        kwargs["email_address_visibility"] = email_address_visibility
    if description is not None:
        kwargs["description"] = description
    if invite_required is not None:
        kwargs["invite_required"] = invite_required
    if plan_type is not None:
        kwargs["plan_type"] = plan_type
    if org_type is not None:
        kwargs["org_type"] = org_type
    if enable_spectator_access is not None:
        kwargs["enable_spectator_access"] = enable_spectator_access

    if date_created is not None:
        # The date_created parameter is intended only for use by test
        # suites that want to backdate the date of a realm's creation.
        assert not settings.PRODUCTION
        kwargs["date_created"] = date_created

    with transaction.atomic():
        realm = Realm(string_id=string_id, name=name, **kwargs)
        if is_demo_organization:
            realm.demo_organization_scheduled_deletion_date = (
                realm.date_created + datetime.timedelta(days=settings.DEMO_ORG_DEADLINE_DAYS)
            )

        set_realm_permissions_based_on_org_type(realm)
        realm.save()

        RealmAuditLog.objects.create(
            realm=realm, event_type=RealmAuditLog.REALM_CREATED, event_time=realm.date_created
        )

        RealmUserDefault.objects.create(realm=realm)

        create_system_user_groups_for_realm(realm)

    # Create stream once Realm object has been saved
    notifications_stream = ensure_stream(
        realm,
        Realm.DEFAULT_NOTIFICATION_STREAM_NAME,
        stream_description="Everyone is added to this stream by default. Welcome! :octopus:",
        acting_user=None,
    )
    realm.notifications_stream = notifications_stream

    # With the current initial streams situation, the only public
    # stream is the notifications_stream.
    DefaultStream.objects.create(stream=notifications_stream, realm=realm)

    signup_notifications_stream = ensure_stream(
        realm,
        Realm.INITIAL_PRIVATE_STREAM_NAME,
        invite_only=True,
        stream_description="A private stream for core team members.",
        acting_user=None,
    )
    realm.signup_notifications_stream = signup_notifications_stream

    realm.save(update_fields=["notifications_stream", "signup_notifications_stream"])

    if plan_type is None and settings.BILLING_ENABLED:
        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_LIMITED, acting_user=None)

    admin_realm = get_realm(settings.SYSTEM_BOT_REALM)
    sender = get_system_bot(settings.NOTIFICATION_BOT, admin_realm.id)
    # Send a notification to the admin realm
    signup_message = _("Signups enabled")

    try:
        signups_stream = get_signups_stream(admin_realm)
        topic = realm.display_subdomain

        internal_send_stream_message(
            sender,
            signups_stream,
            topic,
            signup_message,
        )
    except Stream.DoesNotExist:  # nocoverage
        # If the signups stream hasn't been created in the admin
        # realm, don't auto-create it to send to it; just do nothing.
        pass

    setup_realm_internal_bots(realm)
    return realm


def email_not_system_bot(email: str) -> None:
    if is_cross_realm_bot_email(email):
        msg = email_reserved_for_system_bots_error(email)
        code = msg
        raise ValidationError(
            msg,
            code=code,
            params=dict(deactivated=False),
        )


@transaction.atomic(durable=True)
def do_add_realm_domain(
    realm: Realm, domain: str, allow_subdomains: bool, *, acting_user: Optional[UserProfile]
) -> (RealmDomain):
    realm_domain = RealmDomain.objects.create(
        realm=realm, domain=domain, allow_subdomains=allow_subdomains
    )

    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_DOMAIN_ADDED,
        event_time=timezone_now(),
        extra_data=orjson.dumps(
            {
                "realm_domains": get_realm_domains(realm),
                "added_domain": {"domain": domain, "allow_subdomains": allow_subdomains},
            }
        ).decode(),
    )

    event = dict(
        type="realm_domains",
        op="add",
        realm_domain=dict(
            domain=realm_domain.domain, allow_subdomains=realm_domain.allow_subdomains
        ),
    )
    transaction.on_commit(lambda: send_event(realm, event, active_user_ids(realm.id)))

    return realm_domain


@transaction.atomic(durable=True)
def do_change_realm_domain(
    realm_domain: RealmDomain, allow_subdomains: bool, *, acting_user: Optional[UserProfile]
) -> None:
    realm_domain.allow_subdomains = allow_subdomains
    realm_domain.save(update_fields=["allow_subdomains"])

    RealmAuditLog.objects.create(
        realm=realm_domain.realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_DOMAIN_CHANGED,
        event_time=timezone_now(),
        extra_data=orjson.dumps(
            {
                "realm_domains": get_realm_domains(realm_domain.realm),
                "changed_domain": {
                    "domain": realm_domain.domain,
                    "allow_subdomains": realm_domain.allow_subdomains,
                },
            }
        ).decode(),
    )

    event = dict(
        type="realm_domains",
        op="change",
        realm_domain=dict(
            domain=realm_domain.domain, allow_subdomains=realm_domain.allow_subdomains
        ),
    )
    transaction.on_commit(
        lambda: send_event(realm_domain.realm, event, active_user_ids(realm_domain.realm_id))
    )


@transaction.atomic(durable=True)
def do_remove_realm_domain(
    realm_domain: RealmDomain, *, acting_user: Optional[UserProfile]
) -> None:
    realm = realm_domain.realm
    domain = realm_domain.domain
    realm_domain.delete()

    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_DOMAIN_REMOVED,
        event_time=timezone_now(),
        extra_data=orjson.dumps(
            {
                "realm_domains": get_realm_domains(realm),
                "removed_domain": {
                    "domain": realm_domain.domain,
                    "allow_subdomains": realm_domain.allow_subdomains,
                },
            }
        ).decode(),
    )

    if RealmDomain.objects.filter(realm=realm).count() == 0 and realm.emails_restricted_to_domains:
        # If this was the last realm domain, we mark the realm as no
        # longer restricted to domain, because the feature doesn't do
        # anything if there are no domains, and this is probably less
        # confusing than the alternative.
        do_set_realm_property(realm, "emails_restricted_to_domains", False, acting_user=acting_user)
    event = dict(type="realm_domains", op="remove", domain=domain)
    transaction.on_commit(lambda: send_event(realm, event, active_user_ids(realm.id)))


def do_send_realm_reactivation_email(realm: Realm, *, acting_user: Optional[UserProfile]) -> None:
    url = create_confirmation_link(realm, Confirmation.REALM_REACTIVATION)
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


def get_topic_messages(user_profile: UserProfile, stream: Stream, topic_name: str) -> List[Message]:
    query = UserMessage.objects.filter(
        user_profile=user_profile,
        message__recipient=stream.recipient,
    ).order_by("id")
    return [um.message for um in filter_by_topic_name_via_message(query, topic_name)]
