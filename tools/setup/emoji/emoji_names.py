import os
from typing import Any, Dict

import orjson

TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ZULIP_PATH = os.path.dirname(TOOLS_DIR)
EMOJI_DATA_FILE_PATH = os.path.join(
    ZULIP_PATH, "node_modules", "emoji-datasource-google", "emoji.json"
)


def reformat_name(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")


# TODO this is copied verbatim from emoji_setup_utils.py. We should use that
# function instead when refactoring the code cruft for our emoji system.
def get_emoji_code(emoji_dict: Dict[str, Any]) -> str:
    emoji_code = emoji_dict.get("non_qualified") or emoji_dict["unified"]
    return emoji_code.lower()


with open(EMOJI_DATA_FILE_PATH, "rb") as emoji_data_file:
    emoji_data = orjson.loads(emoji_data_file.read())

EMOJI_NAME_MAPS: Dict[str, Dict[str, Any]] = {}
for emoji_dict in emoji_data:
    emoji_code = get_emoji_code(emoji_dict)
    canonical_name = reformat_name(emoji_dict["name"])
    aliases = [
        reformat_name(a) for a in emoji_dict["short_names"] if reformat_name(a) != canonical_name
    ]
    EMOJI_NAME_MAPS[emoji_code] = {"canonical_name": canonical_name, "aliases": aliases}
