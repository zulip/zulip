from typing import Iterable, Optional, Tuple

from django.conf import settings
from django.db import transaction

from zerver.lib.bulk_create import bulk_create_users
from zerver.lib.user_groups import create_system_user_groups_for_realm
from zerver.models import (
    Realm,
    RealmAuditLog,
    RealmAuthenticationMethod,
    RealmUserDefault,
    UserProfile,
    get_client,
    get_system_bot,
)
from zproject.backends import all_implemented_backend_names


def server_initialized() -> bool:
    return Realm.objects.exists()


@transaction.atomic(durable=True)
def create_internal_realm() -> None:
    from zerver.actions.create_realm import set_default_for_realm_permission_group_settings
    from zerver.actions.users import do_change_can_forge_sender

    realm = Realm(string_id=settings.SYSTEM_BOT_REALM, name="System bot realm")

    # For now a dummy value of -1 is given to groups fields which
    # is changed later before the transaction is committed.
    for permissions_configuration in Realm.REALM_PERMISSION_GROUP_SETTINGS.values():
        setattr(realm, permissions_configuration.id_field_name, -1)
    realm.save()

    RealmAuditLog.objects.create(
        realm=realm, event_type=RealmAuditLog.REALM_CREATED, event_time=realm.date_created
    )
    RealmUserDefault.objects.create(realm=realm)
    create_system_user_groups_for_realm(realm)
    set_default_for_realm_permission_group_settings(realm)

    # We create realms with all authentications methods enabled by default.
    RealmAuthenticationMethod.objects.bulk_create(
        [
            RealmAuthenticationMethod(name=backend_name, realm=realm)
            for backend_name in all_implemented_backend_names()
        ]
    )

    # Create some client objects for common requests.  Not required;
    # just ensures these get low IDs in production, and in development
    # avoids an extra database write for the first HTTP request in
    # most tests.
    get_client("website")
    get_client("ZulipMobile")
    get_client("ZulipElectron")

    internal_bots = [
        (bot["name"], bot["email_template"] % (settings.INTERNAL_BOT_DOMAIN,))
        for bot in settings.INTERNAL_BOTS
    ]
    create_users(realm, internal_bots, bot_type=UserProfile.DEFAULT_BOT)
    # Set the owners for these bots to the bots themselves
    bots = UserProfile.objects.filter(email__in=[bot_info[1] for bot_info in internal_bots])
    for bot in bots:
        bot.bot_owner = bot
        bot.save()

    # Initialize the email gateway bot as able to forge senders.
    email_gateway_bot = get_system_bot(settings.EMAIL_GATEWAY_BOT, realm.id)
    do_change_can_forge_sender(email_gateway_bot, True)


def create_users(
    realm: Realm,
    name_list: Iterable[Tuple[str, str]],
    tos_version: Optional[str] = None,
    bot_type: Optional[int] = None,
    bot_owner: Optional[UserProfile] = None,
) -> None:
    user_set = set()
    for full_name, email in name_list:
        user_set.add((email, full_name, True))
    bulk_create_users(
        realm, user_set, bot_type=bot_type, bot_owner=bot_owner, tos_version=tos_version
    )
