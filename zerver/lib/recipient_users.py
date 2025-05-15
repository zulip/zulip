from collections.abc import Sequence

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from zerver.models import DirectMessageGroup, Recipient, UserProfile
from zerver.models.recipients import (
    get_direct_message_group,
    get_direct_message_group_hash,
    get_or_create_direct_message_group,
)
from zerver.models.users import is_cross_realm_bot_email


def get_recipient_from_user_profiles(
    recipient_profiles: Sequence[UserProfile],
    forwarded_mirror_message: bool,
    forwarder_user_profile: UserProfile | None,
    sender: UserProfile,
    create: bool = True,
) -> Recipient:
    # Avoid mutating the passed in list of recipient_profiles.
    recipient_profiles_map = {user_profile.id: user_profile for user_profile in recipient_profiles}

    if forwarded_mirror_message:
        # In our mirroring integrations with some third-party
        # protocols, bots subscribed to the third-party protocol
        # forward to Zulip messages that they received in the
        # third-party service.  The permissions model for that
        # forwarding is that users can only submit to Zulip private
        # messages they personally received, and here we do the check
        # for whether forwarder_user_profile is among the private
        # message recipients of the message.
        assert forwarder_user_profile is not None
        if forwarder_user_profile.id not in recipient_profiles_map:
            raise ValidationError(_("User not authorized for this query"))

    # Make sure the sender is included in the group direct messages.
    recipient_profiles_map[sender.id] = sender
    user_ids = list(recipient_profiles_map)

    # Important note: We are transitioning 1:1 DMs and self DMs to use
    # DirectMessageGroup as the Recipient type. If a
    # DirectMessageGroup exists for the collection of user IDs, it is
    # guaranteed to contain that entire DM conversation. If none
    # exists, we use the legacy personal recipient (which may or may
    # not exist). Once the migration completes, this code path should
    # just call get_or_create_direct_message_group.
    if len(recipient_profiles_map) <= 2:
        direct_message_group = get_direct_message_group(user_ids)
        if direct_message_group:
            # Use the existing direct message group as the preferred recipient.
            return Recipient(
                id=direct_message_group.recipient_id,
                type=Recipient.DIRECT_MESSAGE_GROUP,
                type_id=direct_message_group.id,
            )

        # if no direct message group recipient exists, we need to
        # force the direct message to be a personal internally.
        del recipient_profiles_map[sender.id]
        if len(recipient_profiles_map) == 1:
            [recipient_user_profile] = recipient_profiles_map.values()
        else:
            recipient_user_profile = sender
        return Recipient(
            id=recipient_user_profile.recipient_id,
            type=Recipient.PERSONAL,
            type_id=recipient_user_profile.id,
        )

    if create:
        direct_message_group = get_or_create_direct_message_group(user_ids)
    else:
        # We intentionally let the DirectMessageGroup.DoesNotExist escape,
        # in the case that there is no such direct message group, and the
        # user passed create=False
        direct_message_group = DirectMessageGroup.objects.get(
            huddle_hash=get_direct_message_group_hash(user_ids)
        )
    return Recipient(
        id=direct_message_group.recipient_id,
        type=Recipient.DIRECT_MESSAGE_GROUP,
        type_id=direct_message_group.id,
    )


def validate_recipient_user_profiles(
    user_profiles: Sequence[UserProfile], sender: UserProfile, allow_deactivated: bool = False
) -> Sequence[UserProfile]:
    recipient_profiles_map: dict[int, UserProfile] = {}

    # We exempt cross-realm bots from the check that all the recipients
    # are in the same realm.
    realms = set()
    if not is_cross_realm_bot_email(sender.email):
        realms.add(sender.realm_id)

    for user_profile in user_profiles:
        if (
            not user_profile.is_active
            and not user_profile.is_mirror_dummy
            and not allow_deactivated
        ) or user_profile.realm.deactivated:
            raise ValidationError(
                _("'{email}' is no longer using Zulip.").format(email=user_profile.email)
            )
        recipient_profiles_map[user_profile.id] = user_profile
        if not is_cross_realm_bot_email(user_profile.email):
            realms.add(user_profile.realm_id)

    if len(realms) > 1:
        raise ValidationError(_("You can't send direct messages outside of your organization."))

    return list(recipient_profiles_map.values())


def recipient_for_user_profiles(
    user_profiles: Sequence[UserProfile],
    forwarded_mirror_message: bool,
    forwarder_user_profile: UserProfile | None,
    sender: UserProfile,
    *,
    allow_deactivated: bool = False,
    create: bool = True,
) -> Recipient:
    recipient_profiles = validate_recipient_user_profiles(
        user_profiles, sender, allow_deactivated=allow_deactivated
    )

    return get_recipient_from_user_profiles(
        recipient_profiles, forwarded_mirror_message, forwarder_user_profile, sender, create=create
    )
