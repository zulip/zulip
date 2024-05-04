import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from django.conf import settings
from django.db import transaction
from django.utils.timezone import now as timezone_now

from confirmation import settings as confirmation_settings
from zerver.actions.message_send import internal_send_stream_message
from zerver.actions.realm_settings import (
    do_add_deactivated_redirect,
    do_change_realm_plan_type,
    do_deactivate_realm,
)
from zerver.lib.bulk_create import create_users
from zerver.lib.push_notifications import sends_notifications_directly
from zerver.lib.remote_server import maybe_enqueue_audit_log_upload
from zerver.lib.server_initialization import create_internal_realm, server_initialized
from zerver.lib.streams import ensure_stream, get_signups_stream
from zerver.lib.user_groups import (
    create_system_user_groups_for_realm,
    get_role_based_system_groups_dict,
)
from zerver.lib.zulip_update_announcements import get_latest_zulip_update_announcements_level
from zerver.models import (
    DefaultStream,
    PreregistrationRealm,
    Realm,
    RealmAuditLog,
    RealmAuthenticationMethod,
    RealmUserDefault,
    Stream,
    UserProfile,
)
from zerver.models.realms import get_org_type_display_name, get_realm
from zerver.models.users import get_system_bot
from zproject.backends import all_default_backend_names

if settings.CORPORATE_ENABLED:
    from corporate.lib.support import get_realm_support_url


def do_change_realm_subdomain(
    realm: Realm,
    new_subdomain: str,
    *,
    acting_user: Optional[UserProfile],
    add_deactivated_redirect: bool = True,
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
    if add_deactivated_redirect:
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
    if realm.org_type in (
        Realm.ORG_TYPES["education_nonprofit"]["id"],
        Realm.ORG_TYPES["education"]["id"],
    ):
        # Limit user creation to administrators.
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


@transaction.atomic(savepoint=False)
def set_default_for_realm_permission_group_settings(realm: Realm) -> None:
    system_groups_dict = get_role_based_system_groups_dict(realm)

    for setting_name, permission_configuration in Realm.REALM_PERMISSION_GROUP_SETTINGS.items():
        group_name = permission_configuration.default_group_name
        setattr(realm, setting_name, system_groups_dict[group_name].usergroup_ptr)

    realm.save(update_fields=list(Realm.REALM_PERMISSION_GROUP_SETTINGS.keys()))


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
    description: Optional[str] = None,
    invite_required: Optional[bool] = None,
    plan_type: Optional[int] = None,
    org_type: Optional[int] = None,
    default_language: Optional[str] = None,
    date_created: Optional[datetime] = None,
    is_demo_organization: bool = False,
    enable_read_receipts: Optional[bool] = None,
    enable_spectator_access: Optional[bool] = None,
    prereg_realm: Optional[PreregistrationRealm] = None,
    how_realm_creator_found_zulip: Optional[str] = None,
    how_realm_creator_found_zulip_extra_context: Optional[str] = None,
) -> Realm:
    if string_id in [settings.SOCIAL_AUTH_SUBDOMAIN, settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN]:
        raise AssertionError(
            "Creating a realm on SOCIAL_AUTH_SUBDOMAIN or SELF_HOSTING_MANAGEMENT_SUBDOMAIN is not allowed!"
        )
    if Realm.objects.filter(string_id=string_id).exists():
        raise AssertionError(f"Realm {string_id} already exists!")
    if not server_initialized():
        logging.info("Server not yet initialized. Creating the internal realm first.")
        create_internal_realm()

    kwargs: Dict[str, Any] = {}
    if emails_restricted_to_domains is not None:
        kwargs["emails_restricted_to_domains"] = emails_restricted_to_domains
    if description is not None:
        kwargs["description"] = description
    if invite_required is not None:
        kwargs["invite_required"] = invite_required
    if plan_type is not None:
        kwargs["plan_type"] = plan_type
    if org_type is not None:
        kwargs["org_type"] = org_type
    if default_language is not None:
        kwargs["default_language"] = default_language
    if enable_spectator_access is not None:
        if enable_spectator_access:
            # Realms with LIMITED plan cannot have spectators enabled.
            assert plan_type != Realm.PLAN_TYPE_LIMITED
            assert plan_type is not None or not settings.BILLING_ENABLED
        kwargs["enable_spectator_access"] = enable_spectator_access

    if date_created is not None:
        # The date_created parameter is intended only for use by test
        # suites that want to backdate the date of a realm's creation.
        assert not settings.PRODUCTION
        kwargs["date_created"] = date_created

    # Generally, closed organizations like companies want read
    # receipts, whereas it's unclear what an open organization's
    # preferences will be. We enable the setting by default only for
    # closed organizations.
    if enable_read_receipts is not None:
        kwargs["enable_read_receipts"] = enable_read_receipts
    else:
        # Hacky: The default of invited_required is True, so we need
        # to check for None too.
        kwargs["enable_read_receipts"] = (
            invite_required is None or invite_required is True or emails_restricted_to_domains
        )
    # Initialize this property correctly in the case that no network activity
    # is required to do so correctly.
    kwargs["push_notifications_enabled"] = sends_notifications_directly()

    with transaction.atomic():
        realm = Realm(string_id=string_id, name=name, **kwargs)
        if is_demo_organization:
            realm.demo_organization_scheduled_deletion_date = realm.date_created + timedelta(
                days=settings.DEMO_ORG_DEADLINE_DAYS
            )

        set_realm_permissions_based_on_org_type(realm)

        # For now a dummy value of -1 is given to groups fields which
        # is changed later before the transaction is committed.
        for permission_configuration in Realm.REALM_PERMISSION_GROUP_SETTINGS.values():
            setattr(realm, permission_configuration.id_field_name, -1)

        realm.save()

        RealmAuditLog.objects.create(
            # acting_user will be set as the initial realm owner inside
            # do_create_user(..., realm_creation=True).
            acting_user=None,
            realm=realm,
            event_type=RealmAuditLog.REALM_CREATED,
            event_time=realm.date_created,
            extra_data={
                "how_realm_creator_found_zulip": how_realm_creator_found_zulip,
                "how_realm_creator_found_zulip_extra_context": how_realm_creator_found_zulip_extra_context,
            },
        )

        realm_default_email_address_visibility = RealmUserDefault.EMAIL_ADDRESS_VISIBILITY_EVERYONE
        if realm.org_type in (
            Realm.ORG_TYPES["education_nonprofit"]["id"],
            Realm.ORG_TYPES["education"]["id"],
        ):
            # Email address of users should be initially visible to admins only.
            realm_default_email_address_visibility = (
                RealmUserDefault.EMAIL_ADDRESS_VISIBILITY_ADMINS
            )

        RealmUserDefault.objects.create(
            realm=realm, email_address_visibility=realm_default_email_address_visibility
        )

        create_system_user_groups_for_realm(realm)
        set_default_for_realm_permission_group_settings(realm)

        RealmAuthenticationMethod.objects.bulk_create(
            [
                RealmAuthenticationMethod(name=backend_name, realm=realm)
                for backend_name in all_default_backend_names()
            ]
        )

        maybe_enqueue_audit_log_upload(realm)

    # Create stream once Realm object has been saved
    new_stream_announcements_stream = ensure_stream(
        realm,
        Realm.DEFAULT_NOTIFICATION_STREAM_NAME,
        stream_description="Everyone is added to this stream by default. Welcome! :octopus:",
        acting_user=None,
    )
    # By default, 'New stream' & 'Zulip update' announcements are sent to the same stream.
    realm.new_stream_announcements_stream = new_stream_announcements_stream
    realm.zulip_update_announcements_stream = new_stream_announcements_stream

    # With the current initial streams situation, the only public
    # stream is the new_stream_announcements_stream.
    DefaultStream.objects.create(stream=new_stream_announcements_stream, realm=realm)

    signup_announcements_stream = ensure_stream(
        realm,
        Realm.INITIAL_PRIVATE_STREAM_NAME,
        invite_only=True,
        stream_description="A private stream for core team members.",
        acting_user=None,
    )
    realm.signup_announcements_stream = signup_announcements_stream

    # New realm is initialized with the latest zulip update announcements
    # level as it shouldn't receive a bunch of old updates.
    realm.zulip_update_announcements_level = get_latest_zulip_update_announcements_level()

    realm.save(
        update_fields=[
            "new_stream_announcements_stream",
            "signup_announcements_stream",
            "zulip_update_announcements_stream",
            "zulip_update_announcements_level",
        ]
    )

    if plan_type is None and settings.BILLING_ENABLED:
        # We use acting_user=None for setting the initial plan type.
        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_LIMITED, acting_user=None)

    if prereg_realm is not None:
        prereg_realm.status = confirmation_settings.STATUS_USED
        prereg_realm.created_realm = realm
        prereg_realm.save(update_fields=["status", "created_realm"])

    # Send a notification to the admin realm when a new organization registers.
    if settings.CORPORATE_ENABLED:
        admin_realm = get_realm(settings.SYSTEM_BOT_REALM)
        sender = get_system_bot(settings.NOTIFICATION_BOT, admin_realm.id)

        support_url = get_realm_support_url(realm)
        organization_type = get_org_type_display_name(realm.org_type)

        message = f"[{realm.name}]({support_url}) ([{realm.display_subdomain}]({realm.uri})). Organization type: {organization_type}"
        topic_name = "new organizations"

        try:
            signups_stream = get_signups_stream(admin_realm)

            internal_send_stream_message(
                sender,
                signups_stream,
                topic_name,
                message,
            )
        except Stream.DoesNotExist:  # nocoverage
            # If the signups stream hasn't been created in the admin
            # realm, don't auto-create it to send to it; just do nothing.
            pass

    setup_realm_internal_bots(realm)
    return realm
