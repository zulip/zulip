import os
import re
from dataclasses import dataclass

import orjson
from django.contrib.staticfiles.storage import staticfiles_storage
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.storage import static_path
from zerver.lib.upload import upload_backend
from zerver.models import Reaction, Realm, RealmEmoji, UserProfile
from zerver.models.realm_emoji import (
    get_all_custom_emoji_for_realm,
    get_name_keyed_dict_for_active_realm_emoji,
)

emoji_codes_path = static_path("generated/emoji/emoji_codes.json")
if not os.path.exists(emoji_codes_path):  # nocoverage
    # During the collectstatic step of build-release-tarball,
    # prod-static/serve/generated/emoji won't exist yet.
    emoji_codes_path = os.path.join(
        os.path.dirname(__file__),
        "../../static/generated/emoji/emoji_codes.json",
    )

with open(emoji_codes_path, "rb") as fp:
    emoji_codes = orjson.loads(fp.read())

name_to_codepoint = emoji_codes["name_to_codepoint"]
codepoint_to_name = emoji_codes["codepoint_to_name"]
EMOTICON_CONVERSIONS = emoji_codes["emoticon_conversions"]

possible_emoticons = EMOTICON_CONVERSIONS.keys()
possible_emoticon_regexes = (re.escape(emoticon) for emoticon in possible_emoticons)
terminal_symbols = r",.;?!()\[\] \"'\n\t"  # from composebox_typeahead.js
EMOTICON_RE = (
    rf"(?<![^{terminal_symbols}])(?P<emoticon>("
    + r")|(".join(possible_emoticon_regexes)
    + rf"))(?![^{terminal_symbols}])"
)


def data_url() -> str:
    # This bakes a hash into the URL, which looks something like
    # static/webpack-bundles/files/64.0cdafdf0b6596657a9be.png
    # This is how Django deals with serving static files in a cacheable way.
    # See PR #22275 for details.
    return staticfiles_storage.url("generated/emoji/emoji_api.json")


# Translates emoticons to their colon syntax, e.g. `:smiley:`.
def translate_emoticons(text: str) -> str:
    translated = text

    for emoticon in EMOTICON_CONVERSIONS:
        translated = re.sub(re.escape(emoticon), EMOTICON_CONVERSIONS[emoticon], translated)

    return translated


@dataclass
class EmojiData:
    emoji_code: str
    reaction_type: str


def get_emoji_data(realm_id: int, emoji_name: str) -> EmojiData:
    # Even if emoji_name is either in name_to_codepoint or named "zulip",
    # we still need to call get_realm_active_emoji.
    realm_emoji_dict = get_name_keyed_dict_for_active_realm_emoji(realm_id)
    realm_emoji = realm_emoji_dict.get(emoji_name)

    if realm_emoji is not None:
        emoji_code = str(realm_emoji["id"])
        return EmojiData(emoji_code=emoji_code, reaction_type=Reaction.REALM_EMOJI)

    if emoji_name == "zulip":
        return EmojiData(emoji_code=emoji_name, reaction_type=Reaction.ZULIP_EXTRA_EMOJI)

    if emoji_name in name_to_codepoint:
        emoji_code = name_to_codepoint[emoji_name]
        return EmojiData(emoji_code=emoji_code, reaction_type=Reaction.UNICODE_EMOJI)

    raise JsonableError(_("Emoji '{emoji_name}' does not exist").format(emoji_name=emoji_name))


def check_emoji_request(realm: Realm, emoji_name: str, emoji_code: str, emoji_type: str) -> None:
    # For a given realm and emoji type, checks whether an emoji
    # code is valid for new reactions, or not.
    if emoji_type == "realm_emoji":
        # We cache emoji, so this generally avoids a round trip,
        # but it does require deserializing a bigger data structure
        # than we need.
        realm_emojis = get_all_custom_emoji_for_realm(realm.id)
        realm_emoji = realm_emojis.get(emoji_code)
        if realm_emoji is None:
            raise JsonableError(_("Invalid custom emoji."))
        if realm_emoji["name"] != emoji_name:
            raise JsonableError(_("Invalid custom emoji name."))
        if realm_emoji["deactivated"]:
            raise JsonableError(_("This custom emoji has been deactivated."))
    elif emoji_type == "zulip_extra_emoji":
        if emoji_code not in ["zulip"]:
            raise JsonableError(_("Invalid emoji code."))
        if emoji_name != emoji_code:
            raise JsonableError(_("Invalid emoji name."))
    elif emoji_type == "unicode_emoji":
        if emoji_code not in codepoint_to_name:
            raise JsonableError(_("Invalid emoji code."))
        if name_to_codepoint.get(emoji_name) != emoji_code:
            raise JsonableError(_("Invalid emoji name."))
    else:
        # The above are the only valid emoji types
        raise JsonableError(_("Invalid emoji type."))


def check_remove_custom_emoji(user_profile: UserProfile, emoji_name: str) -> None:
    # normal users can remove emoji they themselves added
    if user_profile.is_realm_admin:
        return

    emoji = RealmEmoji.objects.filter(
        realm=user_profile.realm, name=emoji_name, deactivated=False
    ).first()
    current_user_is_author = (
        emoji is not None and emoji.author is not None and emoji.author.id == user_profile.id
    )
    if not current_user_is_author:
        raise JsonableError(_("Must be an organization administrator or emoji author"))


def check_valid_emoji_name(emoji_name: str) -> None:
    if emoji_name:
        if re.match(r"^[0-9a-z\-_]+(?<![\-_])$", emoji_name):
            return
        if re.match(r"^[0-9a-z\-_]+$", emoji_name):
            raise JsonableError(_("Emoji names must end with either a letter or digit."))
        raise JsonableError(
            _(
                "Emoji names must contain only lowercase English letters, digits, spaces, dashes, and underscores.",
            )
        )
    raise JsonableError(_("Emoji name is missing"))


def get_emoji_url(emoji_file_name: str, realm_id: int, still: bool = False) -> str:
    return upload_backend.get_emoji_url(emoji_file_name, realm_id, still)


def get_emoji_file_name(emoji_file_name: str, emoji_id: int) -> str:
    _, image_ext = os.path.splitext(emoji_file_name)
    return "".join((str(emoji_id), image_ext))
