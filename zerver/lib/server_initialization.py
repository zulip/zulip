from typing import Iterable, Optional, Tuple

from django.conf import settings

from zerver.lib.bulk_create import bulk_create_users
from zerver.models import Realm, UserProfile, get_client, get_system_bot


def server_initialized() -> bool:
    return Realm.objects.exists()

def create_internal_realm() -> None:
    from zerver.lib.actions import do_change_is_api_super_user

    realm = Realm.objects.create(string_id=settings.SYSTEM_BOT_REALM)

    # Create some client objects for common requests.  Not required;
    # just ensures these get low IDs in production, and in development
    # avoids an extra database write for the first HTTP requset in
    # most tests.
    get_client("website")
    get_client("ZulipMobile")
    get_client("ZulipElectron")

    internal_bots = [(bot['name'], bot['email_template'] % (settings.INTERNAL_BOT_DOMAIN,))
                     for bot in settings.INTERNAL_BOTS]
    create_users(realm, internal_bots, bot_type=UserProfile.DEFAULT_BOT)
    # Set the owners for these bots to the bots themselves
    bots = UserProfile.objects.filter(email__in=[bot_info[1] for bot_info in internal_bots])
    for bot in bots:
        bot.bot_owner = bot
        bot.save()

    # Initialize the email gateway bot as an API Super User
    email_gateway_bot = get_system_bot(settings.EMAIL_GATEWAY_BOT)
    do_change_is_api_super_user(email_gateway_bot, True)

def create_users(realm: Realm, name_list: Iterable[Tuple[str, str]],
                 tos_version: Optional[str]=None,
                 bot_type: Optional[int]=None,
                 bot_owner: Optional[UserProfile]=None) -> None:
    user_set = set()
    for full_name, email in name_list:
        user_set.add((email, full_name, True))
    bulk_create_users(realm, user_set, bot_type=bot_type, bot_owner=bot_owner, tos_version=tos_version)
