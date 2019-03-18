from zerver.models import Realm
from zerver.lib.cache import cache_with_key, realm_rendered_description_cache_key
from zerver.lib.bugdown import convert as bugdown_convert

@cache_with_key(realm_rendered_description_cache_key, timeout=3600*24*7)
def get_realm_rendered_description(realm: Realm) -> str:
    realm_description_raw = realm.description or "The coolest place in the universe."
    return bugdown_convert(realm_description_raw, message_realm=realm,
                           no_previews=True)
