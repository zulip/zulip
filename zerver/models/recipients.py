import hashlib
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Set

from django.db import models, transaction
from django_stubs_ext import ValuesQuerySet
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
    which is the ID of the UserProfile/Stream/Huddle object containing
    all the metadata for the audience. There are 3 recipient types:

    1. 1:1 direct message: The type_id is the ID of the UserProfile
       who will receive any message to this Recipient. The sender
       of such a message is represented separately.
    2. Stream message: The type_id is the ID of the associated Stream.
    3. Group direct message: In Zulip, group direct messages are
       represented by Huddle objects, which encode the set of users
       in the conversation. The type_id is the ID of the associated Huddle
       object; the set of users is usually retrieved via the Subscription
       table. See the Huddle model for details.

    See also the Subscription model, which stores which UserProfile
    objects are subscribed to which Recipient objects.
    """

    type_id = models.IntegerField(db_index=True)
    type = models.PositiveSmallIntegerField(db_index=True)
    # Valid types are {personal, stream, huddle}

    # The type for 1:1 direct messages.
    PERSONAL = 1
    # The type for stream messages.
    STREAM = 2
    # The type group direct messages.
    DIRECT_MESSAGE_GROUP = 3

    class Meta:
        unique_together = ("type", "type_id")

    # N.B. If we used Django's choice=... we would get this for free (kinda)
    _type_names = {PERSONAL: "personal", STREAM: "stream", DIRECT_MESSAGE_GROUP: "huddle"}

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


def get_huddle_user_ids(recipient: Recipient) -> ValuesQuerySet["Subscription", int]:
    from zerver.models import Subscription

    assert recipient.type == Recipient.DIRECT_MESSAGE_GROUP

    return (
        Subscription.objects.filter(
            recipient=recipient,
        )
        .order_by("user_profile_id")
        .values_list("user_profile_id", flat=True)
    )


def bulk_get_huddle_user_ids(recipient_ids: List[int]) -> Dict[int, Set[int]]:
    """
    Takes a list of huddle-type recipient_ids, returns a dict
    mapping recipient id to list of user ids in the huddle.

    We rely on our caller to pass us recipient_ids that correspond
    to huddles, but technically this function is valid for any type
    of subscription.
    """
    from zerver.models import Subscription

    if not recipient_ids:
        return {}

    subscriptions = Subscription.objects.filter(
        recipient_id__in=recipient_ids,
    ).only("user_profile_id", "recipient_id")

    result_dict: Dict[int, Set[int]] = defaultdict(set)
    for subscription in subscriptions:
        result_dict[subscription.recipient_id].add(subscription.user_profile_id)

    return result_dict


class Huddle(models.Model):
    """
    Represents a group of individuals who may have a
    group direct message conversation together.

    The membership of the Huddle is stored in the Subscription table just like with
    Streams - for each user in the Huddle, there is a Subscription object
    tied to the UserProfile and the Huddle's recipient object.

    A hash of the list of user IDs is stored in the huddle_hash field
    below, to support efficiently mapping from a set of users to the
    corresponding Huddle object.
    """

    # TODO: We should consider whether using
    # CommaSeparatedIntegerField would be better.
    huddle_hash = models.CharField(max_length=40, db_index=True, unique=True)
    # Foreign key to the Recipient object for this Huddle.
    recipient = models.ForeignKey(Recipient, null=True, on_delete=models.SET_NULL)


def get_huddle_hash(id_list: List[int]) -> str:
    id_list = sorted(set(id_list))
    hash_key = ",".join(str(x) for x in id_list)
    return hashlib.sha1(hash_key.encode()).hexdigest()


def get_or_create_huddle(id_list: List[int]) -> Huddle:
    """
    Takes a list of user IDs and returns the Huddle object for the
    group consisting of these users. If the Huddle object does not
    yet exist, it will be transparently created.
    """
    from zerver.models import Subscription, UserProfile

    huddle_hash = get_huddle_hash(id_list)
    with transaction.atomic():
        (huddle, created) = Huddle.objects.get_or_create(huddle_hash=huddle_hash)
        if created:
            recipient = Recipient.objects.create(
                type_id=huddle.id, type=Recipient.DIRECT_MESSAGE_GROUP
            )
            huddle.recipient = recipient
            huddle.save(update_fields=["recipient"])
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
        return huddle
