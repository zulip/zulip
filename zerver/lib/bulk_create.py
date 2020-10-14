import random
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

from django.db.models import Model

from zerver.lib.create_user import create_user_profile, get_display_email_address
from zerver.lib.initial_password import initial_password
from zerver.lib.streams import render_stream_description
from zerver.models import (
    Message,
    Reaction,
    Realm,
    RealmAuditLog,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
)


def bulk_create_users(realm: Realm,
                      users_raw: Set[Tuple[str, str, bool]],
                      bot_type: Optional[int]=None,
                      bot_owner: Optional[UserProfile]=None,
                      tos_version: Optional[str]=None,
                      timezone: str="") -> None:
    """
    Creates and saves a UserProfile with the given email.
    Has some code based off of UserManage.create_user, but doesn't .save()
    """
    existing_users = frozenset(UserProfile.objects.filter(
        realm=realm).values_list('email', flat=True))
    users = sorted(user_raw for user_raw in users_raw if user_raw[0] not in existing_users)

    # Now create user_profiles
    profiles_to_create: List[UserProfile] = []
    for (email, full_name, active) in users:
        profile = create_user_profile(realm, email,
                                      initial_password(email), active, bot_type,
                                      full_name, bot_owner, False, tos_version,
                                      timezone, tutorial_status=UserProfile.TUTORIAL_FINISHED,
                                      enter_sends=True)
        profiles_to_create.append(profile)

    if realm.email_address_visibility == Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE:
        UserProfile.objects.bulk_create(profiles_to_create)
    else:
        for user_profile in profiles_to_create:
            user_profile.email = user_profile.delivery_email

        UserProfile.objects.bulk_create(profiles_to_create)

        for user_profile in profiles_to_create:
            user_profile.email = get_display_email_address(user_profile, realm)
        UserProfile.objects.bulk_update(profiles_to_create, ['email'])

    user_ids = {user.id for user in profiles_to_create}

    RealmAuditLog.objects.bulk_create(
        RealmAuditLog(realm=realm, modified_user=profile_,
                      event_type=RealmAuditLog.USER_CREATED, event_time=profile_.date_joined)
        for profile_ in profiles_to_create)

    recipients_to_create: List[Recipient] = []
    for user_id in user_ids:
        recipient = Recipient(type_id=user_id, type=Recipient.PERSONAL)
        recipients_to_create.append(recipient)

    Recipient.objects.bulk_create(recipients_to_create)

    bulk_set_users_or_streams_recipient_fields(UserProfile, profiles_to_create, recipients_to_create)

    recipients_by_user_id: Dict[int, Recipient] = {}
    for recipient in recipients_to_create:
        recipients_by_user_id[recipient.type_id] = recipient

    subscriptions_to_create: List[Subscription] = []
    for user_id in user_ids:
        recipient = recipients_by_user_id[user_id]
        subscription = Subscription(user_profile_id=user_id, recipient=recipient)
        subscriptions_to_create.append(subscription)

    Subscription.objects.bulk_create(subscriptions_to_create)

def bulk_set_users_or_streams_recipient_fields(model: Model,
                                               objects: Union[Iterable[UserProfile], Iterable[Stream]],
                                               recipients: Optional[Iterable[Recipient]]=None) -> None:
    assert model in [UserProfile, Stream]
    for obj in objects:
        assert isinstance(obj, model)

    if model == UserProfile:
        recipient_type = Recipient.PERSONAL
    elif model == Stream:
        recipient_type = Recipient.STREAM

    if recipients is None:
        object_ids = [obj.id for obj in objects]
        recipients = Recipient.objects.filter(type=recipient_type, type_id__in=object_ids)

    objects_dict = {obj.id: obj for obj in objects}

    objects_to_update = set()
    for recipient in recipients:
        assert recipient.type == recipient_type
        result = objects_dict.get(recipient.type_id)
        if result is not None:
            result.recipient = recipient
            objects_to_update.add(result)
    model.objects.bulk_update(objects_to_update, ['recipient'])

# This is only sed in populate_db, so doesn't really need tests
def bulk_create_streams(realm: Realm,
                        stream_dict: Dict[str, Dict[str, Any]]) -> None:  # nocoverage
    existing_streams = {
        name.lower()
        for name in Stream.objects.filter(realm=realm).values_list('name', flat=True)
    }
    streams_to_create: List[Stream] = []
    for name, options in stream_dict.items():
        if 'history_public_to_subscribers' not in options:
            options['history_public_to_subscribers'] = (
                not options.get("invite_only", False) and not realm.is_zephyr_mirror_realm)
        if name.lower() not in existing_streams:
            streams_to_create.append(
                Stream(
                    realm=realm,
                    name=name,
                    description=options["description"],
                    rendered_description=render_stream_description(options["description"]),
                    invite_only=options.get("invite_only", False),
                    stream_post_policy=options.get("stream_post_policy",
                                                   Stream.STREAM_POST_POLICY_EVERYONE),
                    history_public_to_subscribers=options["history_public_to_subscribers"],
                    is_web_public=options.get("is_web_public", False),
                    is_in_zephyr_realm=realm.is_zephyr_mirror_realm,
                ),
            )
    # Sort streams by name before creating them so that we can have a
    # reliable ordering of `stream_id` across different python versions.
    # This is required for test fixtures which contain `stream_id`. Prior
    # to python 3.3 hashes were not randomized but after a security fix
    # hash randomization was enabled in python 3.3 which made iteration
    # of dictionaries and sets completely unpredictable. Here the order
    # of elements while iterating `stream_dict` will be completely random
    # for python 3.3 and later versions.
    streams_to_create.sort(key=lambda x: x.name)
    Stream.objects.bulk_create(streams_to_create)

    recipients_to_create: List[Recipient] = []
    for stream in Stream.objects.filter(realm=realm).values('id', 'name'):
        if stream['name'].lower() not in existing_streams:
            recipients_to_create.append(Recipient(type_id=stream['id'],
                                                  type=Recipient.STREAM))
    Recipient.objects.bulk_create(recipients_to_create)

    bulk_set_users_or_streams_recipient_fields(Stream, streams_to_create, recipients_to_create)

DEFAULT_EMOJIS = [
    ('+1', '1f44d'),
    ('smiley', '1f603'),
    ('eyes', '1f440'),
    ('crying_cat_face', '1f63f'),
    ('arrow_up', '2b06'),
    ('confetti_ball', '1f38a'),
    ('hundred_points', '1f4af'),
]

def bulk_create_reactions(
        messages: Iterable[Message],
        users: Optional[List[UserProfile]] = None,
        emojis: Optional[List[Tuple[str, str]]] = None
) -> None:
    messages = list(messages)
    if not emojis:
        emojis = DEFAULT_EMOJIS
    emojis = list(emojis)

    reactions: List[Reaction] = []
    for message in messages:
        reactions.extend(_add_random_reactions_to_message(
            message, emojis, users))
    Reaction.objects.bulk_create(reactions)

def _add_random_reactions_to_message(
        message: Message,
        emojis: List[Tuple[str, str]],
        users: Optional[List[UserProfile]] = None,
        prob_reaction: float = 0.075,
        prob_upvote: float = 0.5,
        prob_repeat: float = 0.5) -> List[Reaction]:
    '''Randomly add emoji reactions to each message from a list.

    Algorithm:

    Give the message at least one reaction with probability `prob_reaction`.
    Once the first reaction is added, have another user upvote it with probability
    `prob_upvote`, provided there is another recipient of the message left to upvote.
    Repeat the process for a different emoji with probability `prob_repeat`.

    If the number of emojis or users is small, there is a chance the above process
    will produce multiple reactions with the same user and emoji, so group the
    reactions by emoji code and user profile and then return one reaction from
    each group.
    '''
    for p in (prob_reaction, prob_repeat, prob_upvote):
        # Prevent p=1 since for prob_repeat and prob_upvote, this will
        # lead to an infinite loop.
        if p >= 1 or p < 0:
            raise ValueError('Probability argument must be between 0 and 1.')

    # Avoid performing database queries if there will be no reactions.
    compute_next_reaction: bool = random.random() < prob_reaction
    if not compute_next_reaction:
        return []

    if users is None:
        users = []
    user_ids: Sequence[int] = [user.id for user in users]
    if not user_ids:
        user_ids = UserMessage.objects.filter(message=message) \
            .values_list("user_profile_id", flat=True)
        if not user_ids:
            return []

    emojis = list(emojis)

    reactions = []
    while compute_next_reaction:
        # We do this O(users) operation only if we've decided to do a
        # reaction, to avoid performance issues with large numbers of
        # users.
        users_available = set(user_ids)

        (emoji_name, emoji_code) = random.choice(emojis)
        while True:
            # Handle corner case where all the users have reacted.
            if not users_available:
                break

            user_id = random.choice(list(users_available))
            reactions.append(Reaction(
                user_profile_id=user_id,
                message=message,
                emoji_name=emoji_name,
                emoji_code=emoji_code,
                reaction_type=Reaction.UNICODE_EMOJI
            ))
            users_available.remove(user_id)

            # Add an upvote with the defined probability.
            if not random.random() < prob_upvote:
                break

        # Repeat with a possibly different random emoji with the
        # defined probability.
        compute_next_reaction = random.random() < prob_repeat

    # Avoid returning duplicate reactions by deduplicating on
    # (user_profile_id, emoji_code).
    grouped_reactions = defaultdict(list)
    for reaction in reactions:
        k = (str(reaction.user_profile_id), str(reaction.emoji_code))
        grouped_reactions[k].append(reaction)
    return [reactions[0] for reactions in grouped_reactions.values()]
