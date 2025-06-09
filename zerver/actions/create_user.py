from collections import defaultdict
from collections.abc import Iterable, Sequence
from contextlib import suppress
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language

from confirmation import settings as confirmation_settings
from zerver.actions.message_send import (
    internal_send_group_direct_message,
    internal_send_private_message,
    internal_send_stream_message,
)
from zerver.actions.streams import bulk_add_subscriptions, send_peer_subscriber_events
from zerver.actions.user_groups import (
    bulk_add_members_to_user_groups,
    do_send_user_group_members_update_event,
)
from zerver.actions.users import (
    change_user_is_active,
    get_service_dicts_for_bot,
    send_update_events_for_anonymous_group_settings,
)
from zerver.lib.avatar import avatar_url
from zerver.lib.create_user import create_user
from zerver.lib.default_streams import get_slim_realm_default_streams
from zerver.lib.email_notifications import enqueue_welcome_emails, send_account_registered_email
from zerver.lib.exceptions import JsonableError
from zerver.lib.invites import notify_invites_changed
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.remote_server import maybe_enqueue_audit_log_upload
from zerver.lib.send_email import clear_scheduled_invitation_emails
from zerver.lib.streams import can_access_stream_history
from zerver.lib.subscription_info import bulk_get_subscriber_peer_info
from zerver.lib.user_counts import realm_user_count, realm_user_count_by_role
from zerver.lib.user_groups import get_system_user_group_for_user
from zerver.lib.users import (
    can_access_delivery_email,
    format_user_row,
    get_data_for_inaccessible_user,
    get_user_ids_who_can_access_user,
    user_access_restricted_in_realm,
    user_profile_to_user_row,
)
from zerver.models import (
    DefaultStreamGroup,
    Message,
    NamedUserGroup,
    OnboardingStep,
    OnboardingUserMessage,
    PreregistrationRealm,
    PreregistrationUser,
    Realm,
    RealmAuditLog,
    Recipient,
    Stream,
    Subscription,
    UserGroupMembership,
    UserMessage,
    UserProfile,
)
from zerver.models.groups import SystemGroups
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.users import ExternalAuthID, active_user_ids, bot_owner_user_ids, get_system_bot
from zerver.tornado.django_api import send_event_on_commit

MAX_NUM_RECENT_MESSAGES = 1000
MAX_NUM_RECENT_UNREAD_MESSAGES = 20


def send_message_to_signup_notification_stream(
    sender: UserProfile, realm: Realm, message: str
) -> None:
    signup_announcements_stream = realm.signup_announcements_stream
    if signup_announcements_stream is None:
        return

    with override_language(realm.default_language):
        topic_name = _("signups")

    internal_send_stream_message(sender, signup_announcements_stream, topic_name, message)


def send_group_direct_message_to_admins(sender: UserProfile, realm: Realm, content: str) -> None:
    administrators = list(realm.get_human_admin_users())
    internal_send_group_direct_message(
        realm,
        sender,
        content,
        recipient_users=administrators,
    )


def notify_new_user(user_profile: UserProfile) -> None:
    user_count = realm_user_count(user_profile.realm)
    sender_email = settings.NOTIFICATION_BOT
    sender = get_system_bot(sender_email, user_profile.realm_id)

    is_first_user = user_count == 1
    if not is_first_user:
        with override_language(user_profile.realm.default_language):
            message = _("{user} joined this organization.").format(
                user=silent_mention_syntax_for_user(user_profile), user_count=user_count
            )
            send_message_to_signup_notification_stream(sender, user_profile.realm, message)

        if settings.BILLING_ENABLED:
            from corporate.lib.registration import generate_licenses_low_warning_message_if_required

            licenses_low_warning_message = generate_licenses_low_warning_message_if_required(
                user_profile.realm
            )
            if licenses_low_warning_message is not None:
                message += "\n"
                message += licenses_low_warning_message
                send_group_direct_message_to_admins(sender, user_profile.realm, message)


def set_up_streams_and_groups_for_new_human_user(
    *,
    user_profile: UserProfile,
    prereg_user: PreregistrationUser | None = None,
    default_stream_groups: Sequence[DefaultStreamGroup] = [],
    add_initial_stream_subscriptions: bool = True,
    realm_creation: bool = False,
) -> None:
    realm = user_profile.realm

    if prereg_user is not None:
        streams: list[Stream] = list(prereg_user.streams.all())
        user_groups: list[NamedUserGroup] = list(prereg_user.groups.all())
        acting_user: UserProfile | None = prereg_user.referred_by

        # A PregistrationUser should not be used for another UserProfile
        assert prereg_user.created_user is None, "PregistrationUser should not be reused"
    else:
        streams = []
        user_groups = []
        acting_user = None

    if add_initial_stream_subscriptions:
        # If prereg_user.include_realm_default_subscriptions is true, we
        # add the default streams for the realm to the list of streams.
        # Note that we are fine with "slim" Stream objects for calling
        # bulk_add_subscriptions and add_new_user_history, which we verify
        # in StreamSetupTest tests that check query counts.
        if prereg_user is None or prereg_user.include_realm_default_subscriptions:
            default_streams = get_slim_realm_default_streams(realm.id)
            streams = list(set(streams) | default_streams)

        for default_stream_group in default_stream_groups:
            default_stream_group_streams = default_stream_group.streams.all()
            for stream in default_stream_group_streams:
                if stream not in streams:
                    streams.append(stream)
    else:
        streams = []

    bulk_add_subscriptions(
        realm,
        streams,
        [user_profile],
        from_user_creation=True,
        acting_user=acting_user,
    )

    bulk_add_members_to_user_groups(
        user_groups,
        [user_profile.id],
        acting_user=acting_user,
    )

    add_new_user_history(user_profile, streams, realm_creation=realm_creation)


def add_new_user_history(
    user_profile: UserProfile,
    streams: Iterable[Stream],
    *,
    realm_creation: bool = False,
) -> None:
    """
    Give the user some messages in their feed, so that they can learn
    how to use the home view in a realistic way.

    For realms having older onboarding messages, mark the very
    most recent messages as unread. Otherwise, ONLY mark the
    messages tracked in 'OnboardingUserMessage' as unread.
    """

    realm = user_profile.realm
    # Find recipient ids for the user's streams, limiting to just
    # those where we can access the streams' full history.
    #
    # TODO: This will do database queries in a loop if many private
    # streams are involved.
    recipient_ids = [
        stream.recipient_id for stream in streams if can_access_stream_history(user_profile, stream)
    ]

    # Start by finding recent messages matching those recipients.
    recent_message_ids = set(
        Message.objects.filter(
            # Uses index: zerver_message_realm_recipient_id
            realm_id=realm.id,
            recipient_id__in=recipient_ids,
        )
        .order_by("-id")
        .values_list("id", flat=True)[0:MAX_NUM_RECENT_MESSAGES]
    )

    tracked_onboarding_message_ids = set()
    message_id_to_onboarding_user_message = {}
    onboarding_user_messages_queryset = OnboardingUserMessage.objects.filter(realm_id=realm.id)
    for onboarding_user_message in onboarding_user_messages_queryset:
        tracked_onboarding_message_ids.add(onboarding_user_message.message_id)
        message_id_to_onboarding_user_message[onboarding_user_message.message_id] = (
            onboarding_user_message
        )
    tracked_onboarding_messages_exist = len(tracked_onboarding_message_ids) > 0

    message_history_ids = recent_message_ids.union(tracked_onboarding_message_ids)

    if len(message_history_ids) > 0:
        # Handle the race condition where a message arrives between
        # bulk_add_subscriptions above and the recent message query just above
        already_used_ids = set(
            UserMessage.objects.filter(
                message_id__in=recent_message_ids, user_profile=user_profile
            ).values_list("message_id", flat=True)
        )

        # Exclude the already-used ids and sort them.
        backfill_message_ids = sorted(message_history_ids - already_used_ids)

        # Find which message ids we should mark as read.
        # (We don't want too many unread messages.)
        older_message_ids = set()
        if not tracked_onboarding_messages_exist:
            older_message_ids = set(backfill_message_ids[:-MAX_NUM_RECENT_UNREAD_MESSAGES])

        # Create UserMessage rows for the backfill.
        ums_to_create = []
        for message_id in backfill_message_ids:
            um = UserMessage(user_profile=user_profile, message_id=message_id)
            # Only onboarding messages are available for realm creator.
            # They are not marked as historical.
            if not realm_creation:
                um.flags = UserMessage.flags.historical
            if tracked_onboarding_messages_exist:
                if message_id not in tracked_onboarding_message_ids:
                    um.flags |= UserMessage.flags.read
                elif message_id_to_onboarding_user_message[message_id].flags.starred.is_set:
                    um.flags |= UserMessage.flags.starred
            elif message_id in older_message_ids:
                um.flags |= UserMessage.flags.read
            ums_to_create.append(um)

        UserMessage.objects.bulk_create(ums_to_create)


# Does the processing for a new user account:
# * Subscribes to default/invitation streams
# * Adds to initial user groups
# * Fills in some recent historical messages
# * Notifies other users in realm and Zulip about the signup
# * Deactivates PreregistrationUser objects
# * Mark 'visibility_policy_banner' as read
def process_new_human_user(
    user_profile: UserProfile,
    prereg_user: PreregistrationUser | None = None,
    default_stream_groups: Sequence[DefaultStreamGroup] = [],
    realm_creation: bool = False,
    add_initial_stream_subscriptions: bool = True,
) -> None:
    # subscribe to default/invitation streams, add to groups and
    # fill in some recent historical messages
    set_up_streams_and_groups_for_new_human_user(
        user_profile=user_profile,
        prereg_user=prereg_user,
        default_stream_groups=default_stream_groups,
        add_initial_stream_subscriptions=add_initial_stream_subscriptions,
        realm_creation=realm_creation,
    )

    realm = user_profile.realm
    mit_beta_user = realm.is_zephyr_mirror_realm

    # mit_beta_users don't have a referred_by field
    if (
        not mit_beta_user
        and prereg_user is not None
        and prereg_user.referred_by is not None
        and prereg_user.referred_by.is_active
        and prereg_user.notify_referrer_on_join
    ):
        # This is a cross-realm direct message.
        with override_language(prereg_user.referred_by.default_language):
            internal_send_private_message(
                get_system_bot(settings.NOTIFICATION_BOT, prereg_user.referred_by.realm_id),
                prereg_user.referred_by,
                _("{user} accepted your invitation to join Zulip!").format(
                    user=silent_mention_syntax_for_user(user_profile)
                ),
            )

    # For the sake of tracking the history of UserProfiles,
    # we want to tie the newly created user to the PreregistrationUser
    # it was created from.
    if prereg_user is not None:
        prereg_user.status = confirmation_settings.STATUS_USED
        prereg_user.created_user = user_profile
        prereg_user.save(update_fields=["status", "created_user"])

    # Mark any other PreregistrationUsers in the realm that are STATUS_USED as
    # inactive so we can keep track of the PreregistrationUser we
    # actually used for analytics.
    if prereg_user is not None:
        PreregistrationUser.objects.filter(
            email__iexact=user_profile.delivery_email, realm=user_profile.realm
        ).exclude(id=prereg_user.id).update(status=confirmation_settings.STATUS_REVOKED)
    else:
        PreregistrationUser.objects.filter(
            email__iexact=user_profile.delivery_email, realm=user_profile.realm
        ).update(status=confirmation_settings.STATUS_REVOKED)

    if prereg_user is not None and prereg_user.referred_by is not None:
        notify_invites_changed(user_profile.realm, changed_invite_referrer=prereg_user.referred_by)

    notify_new_user(user_profile)
    # Clear any scheduled invitation emails to prevent them
    # from being sent after the user is created.
    clear_scheduled_invitation_emails(user_profile.delivery_email)
    if realm.send_welcome_emails:
        enqueue_welcome_emails(user_profile, realm_creation)

    # Schedule an initial email with the user's
    # new account details and log-in information.
    send_account_registered_email(user_profile, realm_creation)

    # We have an import loop here; it's intentional, because we want
    # to keep all the onboarding code in zerver/lib/onboarding.py.
    from zerver.lib.onboarding import send_initial_direct_message

    message_id = send_initial_direct_message(user_profile)
    UserMessage.objects.filter(user_profile=user_profile, message_id=message_id).update(
        flags=F("flags").bitor(UserMessage.flags.starred)
    )

    # The 'visibility_policy_banner' is only displayed to existing users.
    # Mark it as read for a new user.
    #
    # If the new user opted to import settings from an existing account, and
    # 'visibility_policy_banner' is already marked as read for the existing account,
    # 'copy_onboarding_steps' function already did the needed copying.
    # Simply ignore the IntegrityError in that case.
    #
    # The extremely brief nature of this subtransaction makes a savepoint safe.
    # See https://postgres.ai/blog/20210831-postgresql-subtransactions-considered-harmful
    # for context on risks around savepoints.
    with suppress(IntegrityError), transaction.atomic(savepoint=True):
        OnboardingStep.objects.create(user=user_profile, onboarding_step="visibility_policy_banner")


def notify_created_user(user_profile: UserProfile, notify_user_ids: list[int]) -> None:
    user_row = user_profile_to_user_row(user_profile)

    format_user_row_kwargs: dict[str, Any] = {
        "realm_id": user_profile.realm_id,
        "row": user_row,
        # Since we don't know what the client
        # supports at this point in the code, we
        # just assume client_gravatar and
        # user_avatar_url_field_optional = False :(
        "client_gravatar": False,
        "user_avatar_url_field_optional": False,
        # We assume there's no custom profile
        # field data for a new user; initial
        # values are expected to be added in a
        # later event.
        "custom_profile_field_data": {},
    }

    user_ids_without_access_to_created_user: list[int] = []
    users_with_access_to_created_users: list[UserProfile] = []

    if notify_user_ids:
        # This is currently used to send creation event when a guest
        # gains access to a user, so we depend on the caller to make
        # sure that only accessible users receive the user data.
        users_with_access_to_created_users = list(
            user_profile.realm.get_active_users().filter(id__in=notify_user_ids)
        )
    else:
        active_realm_users = list(user_profile.realm.get_active_users())

        if user_access_restricted_in_realm(user_profile):
            for user in active_realm_users:
                if user.is_guest:
                    # This logic assumes that can_access_all_users_group
                    # setting can only be set to EVERYONE or MEMBERS.
                    user_ids_without_access_to_created_user.append(user.id)
                else:
                    users_with_access_to_created_users.append(user)
        else:
            users_with_access_to_created_users = active_realm_users

    user_ids_with_real_email_access = []
    user_ids_without_real_email_access = []

    person_for_real_email_access_users = None
    person_for_without_real_email_access_users = None
    for recipient_user in users_with_access_to_created_users:
        if can_access_delivery_email(
            recipient_user, user_profile.id, user_row["email_address_visibility"]
        ):
            user_ids_with_real_email_access.append(recipient_user.id)
            if person_for_real_email_access_users is None:
                # This caller assumes that "format_user_row" only depends on
                # specific value of "acting_user" among users in a realm in
                # email_address_visibility.
                person_for_real_email_access_users = format_user_row(
                    **format_user_row_kwargs,
                    acting_user=recipient_user,
                )
        else:
            user_ids_without_real_email_access.append(recipient_user.id)
            if person_for_without_real_email_access_users is None:
                person_for_without_real_email_access_users = format_user_row(
                    **format_user_row_kwargs,
                    acting_user=recipient_user,
                )

    if user_ids_with_real_email_access:
        assert person_for_real_email_access_users is not None
        event: dict[str, Any] = dict(
            type="realm_user", op="add", person=person_for_real_email_access_users
        )
        send_event_on_commit(user_profile.realm, event, user_ids_with_real_email_access)

    if user_ids_without_real_email_access:
        assert person_for_without_real_email_access_users is not None
        event = dict(type="realm_user", op="add", person=person_for_without_real_email_access_users)
        send_event_on_commit(user_profile.realm, event, user_ids_without_real_email_access)

    if user_ids_without_access_to_created_user:
        event = dict(
            type="realm_user",
            op="add",
            person=get_data_for_inaccessible_user(user_profile.realm, user_profile.id),
            inaccessible_user=True,
        )
        send_event_on_commit(user_profile.realm, event, user_ids_without_access_to_created_user)


def created_bot_event(user_profile: UserProfile) -> dict[str, Any]:
    def stream_name(stream: Stream | None) -> str | None:
        if not stream:
            return None
        return stream.name

    default_sending_stream_name = stream_name(user_profile.default_sending_stream)
    default_events_register_stream_name = stream_name(user_profile.default_events_register_stream)

    bot = dict(
        email=user_profile.email,
        user_id=user_profile.id,
        full_name=user_profile.full_name,
        bot_type=user_profile.bot_type,
        is_active=user_profile.is_active,
        api_key=user_profile.api_key,
        default_sending_stream=default_sending_stream_name,
        default_events_register_stream=default_events_register_stream_name,
        default_all_public_streams=user_profile.default_all_public_streams,
        avatar_url=avatar_url(user_profile),
        services=get_service_dicts_for_bot(user_profile.id),
    )

    # Set the owner key only when the bot has an owner.
    # The default bots don't have an owner. So don't
    # set the owner key while reactivating them.
    if user_profile.bot_owner_id is not None:
        bot["owner_id"] = user_profile.bot_owner_id

    return dict(type="realm_bot", op="add", bot=bot)


def notify_created_bot(user_profile: UserProfile) -> None:
    event = created_bot_event(user_profile)
    send_event_on_commit(user_profile.realm, event, bot_owner_user_ids(user_profile))


@transaction.atomic(savepoint=False)
def do_create_user(
    email: str,
    password: str | None,
    realm: Realm,
    full_name: str,
    bot_type: int | None = None,
    role: int | None = None,
    bot_owner: UserProfile | None = None,
    tos_version: str | None = None,
    timezone: str = "",
    avatar_source: str = UserProfile.AVATAR_FROM_GRAVATAR,
    default_language: str | None = None,
    default_sending_stream: Stream | None = None,
    default_events_register_stream: Stream | None = None,
    default_all_public_streams: bool | None = None,
    prereg_user: PreregistrationUser | None = None,
    prereg_realm: PreregistrationRealm | None = None,
    default_stream_groups: Sequence[DefaultStreamGroup] = [],
    source_profile: UserProfile | None = None,
    realm_creation: bool = False,
    *,
    acting_user: UserProfile | None,
    enable_marketing_emails: bool = True,
    email_address_visibility: int | None = None,
    add_initial_stream_subscriptions: bool = True,
    external_auth_id_dict: dict[str, str] | None = None,
) -> UserProfile:
    if settings.BILLING_ENABLED:
        from corporate.lib.stripe import RealmBillingSession

    user_profile = create_user(
        email=email,
        password=password,
        realm=realm,
        full_name=full_name,
        role=role,
        bot_type=bot_type,
        bot_owner=bot_owner,
        tos_version=tos_version,
        timezone=timezone,
        avatar_source=avatar_source,
        default_language=default_language,
        default_sending_stream=default_sending_stream,
        default_events_register_stream=default_events_register_stream,
        default_all_public_streams=default_all_public_streams,
        source_profile=source_profile,
        enable_marketing_emails=enable_marketing_emails,
        email_address_visibility=email_address_visibility,
    )

    event_time = user_profile.date_joined
    if not acting_user:
        acting_user = user_profile
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=acting_user,
        modified_user=user_profile,
        event_type=AuditLogEventType.USER_CREATED,
        event_time=event_time,
        extra_data={
            RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
        },
    )
    maybe_enqueue_audit_log_upload(user_profile.realm)

    if realm_creation:
        # If this user just created a realm, make sure they are
        # properly tagged as the creator of the realm.
        realm_creation_audit_log = (
            RealmAuditLog.objects.filter(event_type=AuditLogEventType.REALM_CREATED, realm=realm)
            .order_by("id")
            .last()
        )
        assert realm_creation_audit_log is not None
        realm_creation_audit_log.acting_user = user_profile
        realm_creation_audit_log.save(update_fields=["acting_user"])

    if settings.BILLING_ENABLED:
        billing_session = RealmBillingSession(user=user_profile, realm=user_profile.realm)
        billing_session.update_license_ledger_if_needed(event_time)

    system_user_group = get_system_user_group_for_user(user_profile)
    UserGroupMembership.objects.create(user_profile=user_profile, user_group=system_user_group)
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        modified_user=user_profile,
        modified_user_group=system_user_group,
        event_type=AuditLogEventType.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
        event_time=event_time,
        acting_user=acting_user,
    )

    if user_profile.role == UserProfile.ROLE_MEMBER and not user_profile.is_provisional_member:
        full_members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.FULL_MEMBERS,
            realm=user_profile.realm,
            is_system_group=True,
        )
        UserGroupMembership.objects.create(
            user_profile=user_profile, user_group=full_members_system_group
        )
        RealmAuditLog.objects.create(
            realm=user_profile.realm,
            modified_user=user_profile,
            modified_user_group=full_members_system_group,
            event_type=AuditLogEventType.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
            event_time=event_time,
            acting_user=acting_user,
        )

    # Note that for bots, the caller will send an additional event
    # with bot-specific info like services.
    notify_created_user(user_profile, [])

    do_send_user_group_members_update_event("add_members", system_user_group, [user_profile.id])
    if user_profile.role == UserProfile.ROLE_MEMBER and not user_profile.is_provisional_member:
        do_send_user_group_members_update_event(
            "add_members", full_members_system_group, [user_profile.id]
        )

    if external_auth_id_dict:
        for external_auth_method_name, external_auth_id in external_auth_id_dict.items():
            ExternalAuthID.objects.create(
                user=user_profile,
                realm=user_profile.realm,
                external_auth_method_name=external_auth_method_name,
                external_auth_id=external_auth_id,
            )

    if prereg_realm is not None:
        prereg_realm.created_user = user_profile
        prereg_realm.save(update_fields=["created_user"])

    if realm_creation:
        from zerver.lib.onboarding import send_initial_realm_messages

        with override_language(realm.default_language):
            send_initial_realm_messages(realm)

    if bot_type is None:
        process_new_human_user(
            user_profile,
            prereg_user=prereg_user,
            default_stream_groups=default_stream_groups,
            realm_creation=realm_creation,
            add_initial_stream_subscriptions=add_initial_stream_subscriptions,
        )

    return user_profile


def do_activate_mirror_dummy_user(
    user_profile: UserProfile, *, acting_user: UserProfile | None
) -> None:
    """Called to have a user "take over" a "mirror dummy" user
    (i.e. is_mirror_dummy=True) account when they sign up with the
    same email address.

    Essentially, the result should be as though we had created the
    UserProfile just now with do_create_user, except that the mirror
    dummy user may appear as the recipient or sender of messages from
    before their account was fully created.

    TODO: This function likely has bugs resulting from this being a
    parallel code path to do_create_user; e.g. it likely does not
    handle preferences or default streams properly.
    """
    assert user_profile.is_mirror_dummy

    if settings.BILLING_ENABLED:
        from corporate.lib.stripe import RealmBillingSession

    with transaction.atomic(savepoint=False):
        change_user_is_active(user_profile, True)
        user_profile.is_mirror_dummy = False
        user_profile.set_unusable_password()
        user_profile.date_joined = timezone_now()
        user_profile.tos_version = settings.TERMS_OF_SERVICE_VERSION
        user_profile.save(
            update_fields=["date_joined", "password", "is_mirror_dummy", "tos_version"]
        )

        event_time = user_profile.date_joined
        RealmAuditLog.objects.create(
            realm=user_profile.realm,
            modified_user=user_profile,
            acting_user=acting_user,
            event_type=AuditLogEventType.USER_ACTIVATED,
            event_time=event_time,
            extra_data={
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
            },
        )
        maybe_enqueue_audit_log_upload(user_profile.realm)
        if settings.BILLING_ENABLED:
            billing_session = RealmBillingSession(user=user_profile, realm=user_profile.realm)
            billing_session.update_license_ledger_if_needed(event_time)

    notify_created_user(user_profile, [])


@transaction.atomic(savepoint=False)
def do_reactivate_user(user_profile: UserProfile, *, acting_user: UserProfile | None) -> None:
    """Reactivate a user that had previously been deactivated"""
    if user_profile.is_mirror_dummy:
        raise JsonableError(
            _("Cannot activate a placeholder account; ask the user to sign up, instead.")
        )
    change_user_is_active(user_profile, True)

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        modified_user=user_profile,
        acting_user=acting_user,
        event_type=AuditLogEventType.USER_REACTIVATED,
        event_time=event_time,
        extra_data={
            RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
        },
    )
    maybe_enqueue_audit_log_upload(user_profile.realm)

    bot_owner_changed = False
    if (
        user_profile.is_bot
        and user_profile.bot_owner is not None
        and not user_profile.bot_owner.is_active
        and acting_user is not None
    ):
        previous_owner = user_profile.bot_owner
        user_profile.bot_owner = acting_user
        user_profile.save()  # Can't use update_fields because of how the foreign key works.
        RealmAuditLog.objects.create(
            realm=user_profile.realm,
            acting_user=acting_user,
            modified_user=user_profile,
            event_type=AuditLogEventType.USER_BOT_OWNER_CHANGED,
            event_time=event_time,
        )
        bot_owner_changed = True

    if settings.BILLING_ENABLED:
        from corporate.lib.stripe import RealmBillingSession

        billing_session = RealmBillingSession(user=user_profile, realm=user_profile.realm)
        billing_session.update_license_ledger_if_needed(event_time)

    event = dict(
        type="realm_user", op="update", person=dict(user_id=user_profile.id, is_active=True)
    )
    send_event_on_commit(user_profile.realm, event, get_user_ids_who_can_access_user(user_profile))

    if not user_profile.is_bot:
        realm_export_consent_event = dict(
            type="realm_export_consent",
            user_id=user_profile.id,
            consented=user_profile.allow_private_data_export,
        )
        send_event_on_commit(
            user_profile.realm,
            realm_export_consent_event,
            list(user_profile.realm.get_human_admin_users().values_list("id", flat=True)),
        )

    if user_profile.is_bot:
        event = dict(
            type="realm_bot",
            op="update",
            bot=dict(
                user_id=user_profile.id,
                is_active=True,
            ),
        )
        send_event_on_commit(user_profile.realm, event, bot_owner_user_ids(user_profile))

        if bot_owner_changed:
            from zerver.actions.bots import send_bot_owner_update_events

            assert acting_user is not None
            send_bot_owner_update_events(user_profile, acting_user, previous_owner)

    subscribed_recipient_ids = Subscription.objects.filter(
        user_profile_id=user_profile.id, active=True, recipient__type=Recipient.STREAM
    ).values_list("recipient__type_id", flat=True)
    subscribed_streams = Stream.objects.filter(id__in=subscribed_recipient_ids, deactivated=False)
    subscriber_peer_info = bulk_get_subscriber_peer_info(
        realm=user_profile.realm,
        streams=subscribed_streams,
    )

    altered_user_dict: dict[int, set[int]] = defaultdict(set)
    for stream in subscribed_streams:
        altered_user_dict[stream.id] = {user_profile.id}

    stream_dict = {stream.id: stream for stream in subscribed_streams}

    send_peer_subscriber_events(
        op="peer_add",
        realm=user_profile.realm,
        altered_user_dict=altered_user_dict,
        stream_dict=stream_dict,
        subscriber_peer_info=subscriber_peer_info,
    )

    member_user_groups = user_profile.direct_groups.select_related("named_user_group").order_by(
        "id"
    )
    named_user_groups = []
    setting_user_groups = []
    for group in member_user_groups:
        if hasattr(group, "named_user_group"):
            named_user_groups.append(group)
        else:
            setting_user_groups.append(group)

    for user_group in named_user_groups:
        do_send_user_group_members_update_event(
            "add_members", user_group.named_user_group, [user_profile.id]
        )

    if setting_user_groups:
        notify_user_ids = active_user_ids(user_profile.realm_id)
        send_update_events_for_anonymous_group_settings(
            setting_user_groups, user_profile.realm, list(notify_user_ids)
        )
