import secrets
from collections import defaultdict
from email.headerregistry import Address
from typing import Any, Dict, List, Optional

import orjson
from django.conf import settings
from django.db import transaction
from django.utils.timezone import now as timezone_now

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from zerver.actions.invites import revoke_invites_generated_by_user
from zerver.actions.user_groups import (
    do_send_user_group_members_update_event,
    update_users_in_full_members_system_group,
)
from zerver.lib.avatar import avatar_url_from_dict
from zerver.lib.bot_config import ConfigError, get_bot_config, get_bot_configs, set_bot_config
from zerver.lib.cache import bot_dict_fields
from zerver.lib.create_user import create_user
from zerver.lib.send_email import clear_scheduled_emails
from zerver.lib.sessions import delete_user_sessions
from zerver.lib.user_counts import realm_user_count_by_role
from zerver.lib.user_groups import get_system_user_group_for_user
from zerver.lib.users import get_active_bots_owned_by_user
from zerver.models import (
    Message,
    Realm,
    RealmAuditLog,
    Recipient,
    Service,
    Subscription,
    UserGroupMembership,
    UserProfile,
    active_user_ids,
    bot_owner_user_ids,
    get_bot_dicts_in_realm,
    get_bot_services,
    get_fake_email_domain,
    get_user_profile_by_id,
)
from zerver.tornado.django_api import send_event

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import update_license_ledger_if_needed


def do_delete_user(user_profile: UserProfile, *, acting_user: Optional[UserProfile]) -> None:
    if user_profile.realm.is_zephyr_mirror_realm:
        raise AssertionError("Deleting zephyr mirror users is not supported")

    do_deactivate_user(user_profile, acting_user=acting_user)

    subscribed_huddle_recipient_ids = set(
        Subscription.objects.filter(
            user_profile=user_profile, recipient__type=Recipient.HUDDLE
        ).values_list("recipient_id", flat=True)
    )
    user_id = user_profile.id
    realm = user_profile.realm
    date_joined = user_profile.date_joined
    personal_recipient = user_profile.recipient

    with transaction.atomic():
        user_profile.delete()
        # Recipient objects don't get deleted through CASCADE, so we need to handle
        # the user's personal recipient manually. This will also delete all Messages pointing
        # to this recipient (all private messages sent to the user).
        assert personal_recipient is not None
        personal_recipient.delete()
        replacement_user = create_user(
            force_id=user_id,
            email=Address(
                username=f"deleteduser{user_id}", domain=get_fake_email_domain(realm)
            ).addr_spec,
            password=None,
            realm=realm,
            full_name=f"Deleted User {user_id}",
            active=False,
            is_mirror_dummy=True,
            force_date_joined=date_joined,
        )
        subs_to_recreate = [
            Subscription(
                user_profile=replacement_user,
                recipient=recipient,
                is_user_active=replacement_user.is_active,
            )
            for recipient in Recipient.objects.filter(id__in=subscribed_huddle_recipient_ids)
        ]
        Subscription.objects.bulk_create(subs_to_recreate)

        RealmAuditLog.objects.create(
            realm=replacement_user.realm,
            modified_user=replacement_user,
            acting_user=acting_user,
            event_type=RealmAuditLog.USER_DELETED,
            event_time=timezone_now(),
        )


def do_delete_user_preserving_messages(user_profile: UserProfile) -> None:
    """This is a version of do_delete_user which does not delete messages
    that the user was a participant in, and thus is less potentially
    disruptive to other users.

    The code is a bit tricky, because we want to, at some point, call
    user_profile.delete() to trigger cascading deletions of related
    models - but we need to avoid the cascades deleting all messages
    sent by the user to avoid messing up history of public stream
    conversations that they may have participated in.

    Not recommended for general use due to the following quirks:
    * Does not live-update other clients via `send_event` about the
      user's new name, email, or other attributes.
    * Not guaranteed to clear caches containing the deleted users. The
      temporary user may be visible briefly in caches due to the
      UserProfile model's post_save hook.
    * Deletes `acting_user`/`modified_user` entries in RealmAuditLog,
      potentially leading to corruption in audit tables if the user had,
      for example, changed organization-level settings previously.
    * May violate invariants like deleting the only subscriber to a
      stream/group or the last owner in a realm.
    * Will remove MutedUser records for other users who might have
      muted this user.
    * Will destroy Attachment/ArchivedAttachment records for files
      uploaded by the user, making them inaccessible.
    * Will destroy ArchivedMessage records associated with the user,
      making them impossible to restore from backups.
    * Will destroy Reaction/Submessage objects for reactions/poll
      votes done by the user.

    Most of these issues are not relevant for the common case that the
    user being deleted hasn't used Zulip extensively.

    It is possible a different algorithm that worked via overwriting
    the UserProfile's values with RealmUserDefault values, as well as
    a targeted set of deletions of cascading models (`Subscription`,
    `UserMessage`, `CustomProfileFieldValue`, etc.) would be a cleaner
    path to a high quality system.

    Other lesser quirks to be aware of:
    * The deleted user will disappear from all "Read receipts"
      displays, as all UserMessage rows will have been deleted.
    * Raw Markdown syntax mentioning the user still contain their
      original name (though modern clients will look up the user via
      `data-user-id` and display the current name). This is hard to
      change, and not important, since nothing prevents other users from
      just typing the user's name in their own messages.
    * Consumes a user ID sequence number, resulting in gaps in the
      space of user IDs that contain actual users.

    """
    if user_profile.realm.is_zephyr_mirror_realm:
        raise AssertionError("Deleting zephyr mirror users is not supported")

    do_deactivate_user(user_profile, acting_user=None)

    user_id = user_profile.id
    personal_recipient = user_profile.recipient
    realm = user_profile.realm
    date_joined = user_profile.date_joined

    with transaction.atomic():
        # The strategy is that before calling user_profile.delete(), we need to
        # reassign Messages  sent by the user to a dummy user, so that they don't
        # get affected by CASCADE. We cannot yet create a dummy user with .id
        # matching that of the user_profile, so the general scheme is:
        # 1. We create a *temporary* dummy for the initial re-assignment of messages.
        # 2. We delete the UserProfile.
        # 3. We create a replacement dummy user with its id matching what the UserProfile had.
        # 4. This is the intended, final replacement UserProfile, so we re-assign
        #    the messages from step (1) to it and delete the temporary dummy.
        #
        # We also do the same for Subscriptions - while they could be handled like
        # in do_delete_user by re-creating the objects after CASCADE deletion, the code
        # is cleaner by using the same re-assignment approach for them together with Messages.
        random_token = secrets.token_hex(16)
        temp_replacement_user = create_user(
            email=f"temp_deleteduser{random_token}@{get_fake_email_domain(realm)}",
            password=None,
            realm=realm,
            full_name=f"Deleted User {user_id} (temp)",
            active=False,
            is_mirror_dummy=True,
            force_date_joined=date_joined,
            create_personal_recipient=False,
        )
        Message.objects.filter(sender=user_profile).update(sender=temp_replacement_user)
        Subscription.objects.filter(
            user_profile=user_profile, recipient__type=Recipient.HUDDLE
        ).update(user_profile=temp_replacement_user)
        user_profile.delete()

        replacement_user = create_user(
            force_id=user_id,
            email=f"deleteduser{user_id}@{get_fake_email_domain(realm)}",
            password=None,
            realm=realm,
            full_name=f"Deleted User {user_id}",
            active=False,
            is_mirror_dummy=True,
            force_date_joined=date_joined,
            create_personal_recipient=False,
        )
        # We don't delete the personal recipient to preserve  personal messages!
        # Now, the personal recipient belong to replacement_user, because
        # personal_recipient.type_id is equal to replacement_user.id.
        replacement_user.recipient = personal_recipient
        replacement_user.save(update_fields=["recipient"])

        Message.objects.filter(sender=temp_replacement_user).update(sender=replacement_user)
        Subscription.objects.filter(
            user_profile=temp_replacement_user, recipient__type=Recipient.HUDDLE
        ).update(user_profile=replacement_user, is_user_active=replacement_user.is_active)
        temp_replacement_user.delete()

        RealmAuditLog.objects.create(
            realm=replacement_user.realm,
            modified_user=replacement_user,
            acting_user=None,
            event_type=RealmAuditLog.USER_DELETED_PRESERVING_MESSAGES,
            event_time=timezone_now(),
        )


def change_user_is_active(user_profile: UserProfile, value: bool) -> None:
    """
    Helper function for changing the .is_active field. Not meant as a standalone function
    in production code as properly activating/deactivating users requires more steps.
    This changes the is_active value and saves it, while ensuring
    Subscription.is_user_active values are updated in the same db transaction.
    """
    with transaction.atomic(savepoint=False):
        user_profile.is_active = value
        user_profile.save(update_fields=["is_active"])
        Subscription.objects.filter(user_profile=user_profile).update(is_user_active=value)


def do_deactivate_user(
    user_profile: UserProfile, _cascade: bool = True, *, acting_user: Optional[UserProfile]
) -> None:
    if not user_profile.is_active:
        return

    if _cascade:
        # We need to deactivate bots before the target user, to ensure
        # that a failure partway through this function cannot result
        # in only the user being deactivated.
        bot_profiles = get_active_bots_owned_by_user(user_profile)
        for profile in bot_profiles:
            do_deactivate_user(profile, _cascade=False, acting_user=acting_user)

    with transaction.atomic():
        if user_profile.realm.is_zephyr_mirror_realm:  # nocoverage
            # For zephyr mirror users, we need to make them a mirror dummy
            # again; otherwise, other users won't get the correct behavior
            # when trying to send messages to this person inside Zulip.
            #
            # Ideally, we need to also ensure their zephyr mirroring bot
            # isn't running, but that's a separate issue.
            user_profile.is_mirror_dummy = True
            user_profile.save(update_fields=["is_mirror_dummy"])

        change_user_is_active(user_profile, False)

        clear_scheduled_emails(user_profile.id)
        revoke_invites_generated_by_user(user_profile)

        event_time = timezone_now()
        RealmAuditLog.objects.create(
            realm=user_profile.realm,
            modified_user=user_profile,
            acting_user=acting_user,
            event_type=RealmAuditLog.USER_DEACTIVATED,
            event_time=event_time,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
                }
            ).decode(),
        )
        do_increment_logging_stat(
            user_profile.realm,
            COUNT_STATS["active_users_log:is_bot:day"],
            user_profile.is_bot,
            event_time,
            increment=-1,
        )
        if settings.BILLING_ENABLED:
            update_license_ledger_if_needed(user_profile.realm, event_time)

        transaction.on_commit(lambda: delete_user_sessions(user_profile))

        event_remove_user = dict(
            type="realm_user",
            op="remove",
            person=dict(user_id=user_profile.id, full_name=user_profile.full_name),
        )
        transaction.on_commit(
            lambda: send_event(
                user_profile.realm, event_remove_user, active_user_ids(user_profile.realm_id)
            )
        )

        if user_profile.is_bot:
            event_remove_bot = dict(
                type="realm_bot",
                op="remove",
                bot=dict(user_id=user_profile.id, full_name=user_profile.full_name),
            )
            transaction.on_commit(
                lambda: send_event(
                    user_profile.realm, event_remove_bot, bot_owner_user_ids(user_profile)
                )
            )


@transaction.atomic(durable=True)
def do_change_user_role(
    user_profile: UserProfile, value: int, *, acting_user: Optional[UserProfile]
) -> None:
    old_value = user_profile.role
    old_system_group = get_system_user_group_for_user(user_profile)

    user_profile.role = value
    user_profile.save(update_fields=["role"])
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        modified_user=user_profile,
        acting_user=acting_user,
        event_type=RealmAuditLog.USER_ROLE_CHANGED,
        event_time=timezone_now(),
        extra_data=orjson.dumps(
            {
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: value,
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
            }
        ).decode(),
    )
    event = dict(
        type="realm_user", op="update", person=dict(user_id=user_profile.id, role=user_profile.role)
    )
    transaction.on_commit(
        lambda: send_event(user_profile.realm, event, active_user_ids(user_profile.realm_id))
    )

    UserGroupMembership.objects.filter(
        user_profile=user_profile, user_group=old_system_group
    ).delete()

    system_group = get_system_user_group_for_user(user_profile)
    UserGroupMembership.objects.create(user_profile=user_profile, user_group=system_group)

    do_send_user_group_members_update_event("remove_members", old_system_group, [user_profile.id])

    do_send_user_group_members_update_event("add_members", system_group, [user_profile.id])

    if UserProfile.ROLE_MEMBER in [old_value, value]:
        update_users_in_full_members_system_group(
            user_profile.realm, [user_profile.id], acting_user=acting_user
        )


def do_make_user_billing_admin(user_profile: UserProfile) -> None:
    user_profile.is_billing_admin = True
    user_profile.save(update_fields=["is_billing_admin"])
    event = dict(
        type="realm_user", op="update", person=dict(user_id=user_profile.id, is_billing_admin=True)
    )
    send_event(user_profile.realm, event, active_user_ids(user_profile.realm_id))


def do_change_can_forge_sender(user_profile: UserProfile, value: bool) -> None:
    user_profile.can_forge_sender = value
    user_profile.save(update_fields=["can_forge_sender"])


def do_change_can_create_users(user_profile: UserProfile, value: bool) -> None:
    user_profile.can_create_users = value
    user_profile.save(update_fields=["can_create_users"])


def do_update_outgoing_webhook_service(
    bot_profile: UserProfile, service_interface: int, service_payload_url: str
) -> None:
    # TODO: First service is chosen because currently one bot can only have one service.
    # Update this once multiple services are supported.
    service = get_bot_services(bot_profile.id)[0]
    service.base_url = service_payload_url
    service.interface = service_interface
    service.save()
    send_event(
        bot_profile.realm,
        dict(
            type="realm_bot",
            op="update",
            bot=dict(
                user_id=bot_profile.id,
                services=[
                    dict(
                        base_url=service.base_url, interface=service.interface, token=service.token
                    )
                ],
            ),
        ),
        bot_owner_user_ids(bot_profile),
    )


def do_update_bot_config_data(bot_profile: UserProfile, config_data: Dict[str, str]) -> None:
    for key, value in config_data.items():
        set_bot_config(bot_profile, key, value)
    updated_config_data = get_bot_config(bot_profile)
    send_event(
        bot_profile.realm,
        dict(
            type="realm_bot",
            op="update",
            bot=dict(
                user_id=bot_profile.id,
                services=[dict(config_data=updated_config_data)],
            ),
        ),
        bot_owner_user_ids(bot_profile),
    )


def get_service_dicts_for_bot(user_profile_id: int) -> List[Dict[str, Any]]:
    user_profile = get_user_profile_by_id(user_profile_id)
    services = get_bot_services(user_profile_id)
    if user_profile.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
        return [
            {
                "base_url": service.base_url,
                "interface": service.interface,
                "token": service.token,
            }
            for service in services
        ]
    elif user_profile.bot_type == UserProfile.EMBEDDED_BOT:
        try:
            return [
                {
                    "config_data": get_bot_config(user_profile),
                    "service_name": services[0].name,
                }
            ]
        # A ConfigError just means that there are no config entries for user_profile.
        except ConfigError:
            return []
    else:
        return []


def get_service_dicts_for_bots(
    bot_dicts: List[Dict[str, Any]], realm: Realm
) -> Dict[int, List[Dict[str, Any]]]:
    bot_profile_ids = [bot_dict["id"] for bot_dict in bot_dicts]
    bot_services_by_uid: Dict[int, List[Service]] = defaultdict(list)
    for service in Service.objects.filter(user_profile_id__in=bot_profile_ids):
        bot_services_by_uid[service.user_profile_id].append(service)

    embedded_bot_ids = [
        bot_dict["id"] for bot_dict in bot_dicts if bot_dict["bot_type"] == UserProfile.EMBEDDED_BOT
    ]
    embedded_bot_configs = get_bot_configs(embedded_bot_ids)

    service_dicts_by_uid: Dict[int, List[Dict[str, Any]]] = {}
    for bot_dict in bot_dicts:
        bot_profile_id = bot_dict["id"]
        bot_type = bot_dict["bot_type"]
        services = bot_services_by_uid[bot_profile_id]
        service_dicts: List[Dict[str, Any]] = []
        if bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
            service_dicts = [
                {
                    "base_url": service.base_url,
                    "interface": service.interface,
                    "token": service.token,
                }
                for service in services
            ]
        elif bot_type == UserProfile.EMBEDDED_BOT and bot_profile_id in embedded_bot_configs:
            bot_config = embedded_bot_configs[bot_profile_id]
            service_dicts = [
                {
                    "config_data": bot_config,
                    "service_name": services[0].name,
                }
            ]
        service_dicts_by_uid[bot_profile_id] = service_dicts
    return service_dicts_by_uid


def get_owned_bot_dicts(
    user_profile: UserProfile, include_all_realm_bots_if_admin: bool = True
) -> List[Dict[str, Any]]:
    if user_profile.is_realm_admin and include_all_realm_bots_if_admin:
        result = get_bot_dicts_in_realm(user_profile.realm)
    else:
        result = UserProfile.objects.filter(
            realm=user_profile.realm, is_bot=True, bot_owner=user_profile
        ).values(*bot_dict_fields)
    services_by_ids = get_service_dicts_for_bots(result, user_profile.realm)
    return [
        {
            "email": botdict["email"],
            "user_id": botdict["id"],
            "full_name": botdict["full_name"],
            "bot_type": botdict["bot_type"],
            "is_active": botdict["is_active"],
            "api_key": botdict["api_key"],
            "default_sending_stream": botdict["default_sending_stream__name"],
            "default_events_register_stream": botdict["default_events_register_stream__name"],
            "default_all_public_streams": botdict["default_all_public_streams"],
            "owner_id": botdict["bot_owner_id"],
            "avatar_url": avatar_url_from_dict(botdict),
            "services": services_by_ids[botdict["id"]],
        }
        for botdict in result
    ]
