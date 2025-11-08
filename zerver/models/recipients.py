import hashlib
from collections import defaultdict
from typing import TYPE_CHECKING

from django.db import models, transaction
from django.db.models import QuerySet
from typing_extensions import override

from zerver.lib.display_recipient import get_display_recipient

if TYPE_CHECKING:
    from zerver.models import Subscription


class Recipient(models.Model):
    """Represents an audience that can potentially receive messages in Zulip.

    This table essentially functions as a generic foreign key that
    allows Message.recipient_id to be a simple ForeignKey representing
    the audience for a message, while supporting the different types
    of audiences Zulip supports for a message.

    Recipient has just two attributes: The enum type, and a type_id,
    which is the ID of the UserProfile/Stream/DirectMessageGroup object
    containing all the metadata for the audience. There are 3 recipient
    types:

    1. 1:1 direct message: The type_id is the ID of the UserProfile
       who will receive any message to this Recipient. The sender
       of such a message is represented separately.
    2. Stream message: The type_id is the ID of the associated Stream.
    3. Group direct message: In Zulip, group direct messages are
       represented by DirectMessageGroup objects, which encode the set of
       users in the conversation. The type_id is the ID of the associated
       DirectMessageGroup object; the set of users is usually retrieved
       via the Subscription table. See the DirectMessageGroup model for
       details.

    See also the Subscription model, which stores which UserProfile
    objects are subscribed to which Recipient objects.
    """

    id = models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")
    type_id = models.IntegerField(db_index=True)
    type = models.PositiveSmallIntegerField(db_index=True)
    # Valid types are {personal, stream, direct_message_group}

    # The type for 1:1 direct messages.
    PERSONAL = 1
    # The type for stream messages.
    STREAM = 2
    # The type group direct messages.
    DIRECT_MESSAGE_GROUP = 3

    class Meta:
        unique_together = ("type", "type_id")

    # N.B. If we used Django's choice=... we would get this for free (kinda)
    _type_names = {
        PERSONAL: "personal",
        STREAM: "stream",
        DIRECT_MESSAGE_GROUP: "direct_message_group",
    }

    @override
    def __str__(self) -> str:
        return f"{self.label()} ({self.type_id}, {self.type})"

    def label(self) -> str:
        from zerver.models import Stream

        if self.type == Recipient.STREAM:
            return Stream.objects.get(id=self.type_id).name
        else:
            return str(get_display_recipient(self))

    def type_name(self) -> str:
        # Raises KeyError if invalid
        return self._type_names[self.type]


def get_direct_message_group_user_ids(recipient: Recipient) -> QuerySet["Subscription", int]:
    from zerver.models import Subscription

    assert recipient.type == Recipient.DIRECT_MESSAGE_GROUP

    return (
        Subscription.objects.filter(
            recipient=recipient,
        )
        .order_by("user_profile_id")
        .values_list("user_profile_id", flat=True)
    )


def bulk_get_direct_message_group_user_ids(recipient_ids: list[int]) -> dict[int, set[int]]:
    """
    Takes a list of direct_message_group type recipient_ids, returns
    a dictmapping recipient id to list of user ids in the direct
    message group.

    We rely on our caller to pass us recipient_ids that correspond
    to direct_message_group, but technically this function is valid
    for any typeof subscription.
    """
    from zerver.models import Subscription

    if not recipient_ids:
        return {}

    subscriptions = Subscription.objects.filter(
        recipient_id__in=recipient_ids,
    ).only("user_profile_id", "recipient_id")

    result_dict: dict[int, set[int]] = defaultdict(set)
    for subscription in subscriptions:
        result_dict[subscription.recipient_id].add(subscription.user_profile_id)

    return result_dict


class DirectMessageGroup(models.Model):
    """
    Represents a group of individuals who may have a
    group direct message conversation together.

    The membership of the DirectMessageGroup is stored in the Subscription
    table just like with Streams - for each user in the DirectMessageGroup,
    there is a Subscription object tied to the UserProfile and the
    DirectMessageGroup's recipient object.

    A hash of the list of user IDs is stored in the huddle_hash field
    below, to support efficiently mapping from a set of users to the
    corresponding DirectMessageGroup object.
    """

    # TODO: We should consider whether using
    # CommaSeparatedIntegerField would be better.
    huddle_hash = models.CharField(max_length=40, db_index=True, unique=True)
    # Foreign key to the Recipient object for this DirectMessageGroup.
    recipient = models.ForeignKey(Recipient, null=True, on_delete=models.SET_NULL)

    group_size = models.IntegerField()

    # TODO: The model still uses the old "zerver_huddle" database table.
    # As a part of the migration of "Huddle" to "DirectMessageGroup"
    # it needs to be renamed to "zerver_directmessagegroup".
    class Meta:
        db_table = "zerver_huddle"


def get_direct_message_group_hash(id_list: list[int]) -> str:
    id_list = sorted(set(id_list))
    hash_key = ",".join(str(x) for x in id_list)
    return hashlib.sha1(hash_key.encode()).hexdigest()


def get_or_create_direct_message_group(id_list: list[int]) -> DirectMessageGroup:
    """
    Takes a list of user IDs and returns the DirectMessageGroup
    object for the group consisting of these users. If the
    DirectMessageGroup object does not yet exist, it will be
    transparently created.
    """
    from zerver.models import Subscription, UserProfile

    direct_message_group_hash = get_direct_message_group_hash(id_list)
    with transaction.atomic(savepoint=False):
        (direct_message_group, created) = DirectMessageGroup.objects.get_or_create(
            huddle_hash=direct_message_group_hash,
            group_size=len(id_list),
        )
        if created:
            recipient = Recipient.objects.create(
                type_id=direct_message_group.id, type=Recipient.DIRECT_MESSAGE_GROUP
            )
            direct_message_group.recipient = recipient
            direct_message_group.save(update_fields=["recipient"])
            subs_to_create = [
                Subscription(
                    recipient=recipient,
                    user_profile_id=user_profile_id,
                    is_user_active=is_active,
                )
                for user_profile_id, is_active in UserProfile.objects.filter(id__in=id_list)
                .distinct("id")
                .values_list("id", "is_active")
            ]
            Subscription.objects.bulk_create(subs_to_create)
        return direct_message_group


def get_direct_message_group(id_list: list[int]) -> DirectMessageGroup | None:
    """
    Takes a list of user IDs and returns the DirectMessageGroup
    object for the group consisting of these users if exists. If
    the DirectMessageGroup object does not yet exist, it will
    return None.
    """

    try:
        direct_message_group_hash = get_direct_message_group_hash(id_list)
        return DirectMessageGroup.objects.get(
            huddle_hash=direct_message_group_hash,
            group_size=len(id_list),
        )
    except DirectMessageGroup.DoesNotExist:
        return None
