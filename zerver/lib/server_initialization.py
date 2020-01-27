from django.conf import settings

from zerver.lib.actions import do_change_is_admin
from zerver.lib.bulk_create import bulk_create_users
from zerver.models import Realm, UserProfile, email_to_username, get_client, \
    get_system_bot

from typing import Iterable, Optional, Set, Tuple

def create_internal_realm() -> None:
    internal_realm = Realm.objects.create(string_id=settings.SYSTEM_BOT_REALM)

    # Create the "website" and "API" clients:
    get_client("website")
    get_client("API")

    internal_realm_bots = [(bot['name'], bot['email_template'] % (settings.INTERNAL_BOT_DOMAIN,))
                           for bot in settings.INTERNAL_BOTS]
    create_users(internal_realm, internal_realm_bots, bot_type=UserProfile.DEFAULT_BOT)

    # Initialize the email gateway bot as an API Super User
    email_gateway_bot = get_system_bot(settings.EMAIL_GATEWAY_BOT)
    do_change_is_admin(email_gateway_bot, True, permission="api_super_user")

def create_users(realm: Realm, name_list: Iterable[Tuple[str, str]],
                 bot_type: Optional[int]=None,
                 bot_owner: Optional[UserProfile]=None) -> None:
    user_set = set()  # type: Set[Tuple[str, str, str, bool]]
    for full_name, email in name_list:
        short_name = email_to_username(email)
        user_set.add((email, full_name, short_name, True))
    tos_version = settings.TOS_VERSION if bot_type is None else None
    bulk_create_users(realm, user_set, bot_type=bot_type, bot_owner=bot_owner, tos_version=tos_version)
