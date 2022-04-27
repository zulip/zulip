import datetime
import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.actions.message_send import internal_send_stream_message
from zerver.actions.realm_settings import (
    do_add_deactivated_redirect,
    do_change_realm_plan_type,
    do_deactivate_realm,
)
from zerver.lib.bulk_create import create_users
from zerver.lib.server_initialization import create_internal_realm, server_initialized
from zerver.lib.streams import ensure_stream, get_signups_stream
from zerver.lib.user_groups import create_system_user_groups_for_realm
from zerver.models import (
    DefaultStream,
    Realm,
    RealmAuditLog,
    RealmUserDefault,
    Stream,
    UserProfile,
    get_realm,
    get_system_bot,
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
    is_demo_organization: bool = False,
    enable_spectator_access: Optional[bool] = None,
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
            # acting_user will be set as the initial realm owner inside
            # do_create_user(..., realm_creation=True).
            acting_user=None,
            realm=realm,
            event_type=RealmAuditLog.REALM_CREATED,
            event_time=realm.date_created,
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
        # We use acting_user=None for setting the initial plan type.
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
