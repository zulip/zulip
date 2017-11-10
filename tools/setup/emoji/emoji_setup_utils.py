# This file contains various helper functions used by `build_emoji` tool.
# See docs/subsystems/emoji.md for details on how this system works.

from collections import defaultdict

from typing import Any, Dict, List

# Emojisets that we currently support.
EMOJISETS = ['apple', 'emojione', 'google', 'twitter']

def emoji_names_for_picker(emoji_name_maps):
    # type: (Dict[str, Dict[str, Any]]) -> List[str]
    emoji_names = []  # type: List[str]
    for emoji_code, name_info in emoji_name_maps.items():
        emoji_names.append(name_info["canonical_name"])
        emoji_names.extend(name_info["aliases"])

    return sorted(emoji_names)

# Returns a dict from categories to list of codepoints. The list of
# codepoints are sorted according to the `sort_order` as defined in
# `emoji_data`.
def generate_emoji_catalog(emoji_data, emoji_name_maps):
    # type: (List[Dict[str, Any]], Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]
    sort_order = {}  # type: Dict[str, int]
    emoji_catalog = defaultdict(list)  # type: Dict[str, List[str]]

    for emoji_dict in emoji_data:
        emoji_code = emoji_dict["unified"].lower()
        if not emoji_is_universal(emoji_dict) or emoji_code not in emoji_name_maps:
            continue
        category = emoji_dict["category"]
        sort_order[emoji_code] = emoji_dict["sort_order"]
        emoji_catalog[category].append(emoji_code)

    # Sort the emojis according to iamcal's sort order. This sorting determines the
    # order in which emojis will be displayed in emoji picker.
    for category in emoji_catalog:
        emoji_catalog[category].sort(key=lambda emoji_code: sort_order[emoji_code])

    return dict(emoji_catalog)

# Use only those names for which images are present in all
# the emoji sets so that we can switch emoji sets seemlessly.
def emoji_is_universal(emoji_dict):
    # type: (Dict[str, Any]) -> bool
    for emoji_set in EMOJISETS:
        if not emoji_dict['has_img_' + emoji_set]:
            return False
    return True

def generate_codepoint_to_name_map(emoji_name_maps):
    # type: (Dict[str, Dict[str, Any]]) -> Dict[str, str]
    codepoint_to_name = {}  # type: Dict[str, str]
    for emoji_code, name_info in emoji_name_maps.items():
        codepoint_to_name[emoji_code] = name_info["canonical_name"]
    return codepoint_to_name

def generate_name_to_codepoint_map(emoji_name_maps):
    # type: (Dict[str, Dict[str, Any]]) -> Dict[str, str]
    name_to_codepoint = {}
    for emoji_code, name_info in emoji_name_maps.items():
        canonical_name = name_info["canonical_name"]
        aliases = name_info["aliases"]
        name_to_codepoint[canonical_name] = emoji_code
        for alias in aliases:
            name_to_codepoint[alias] = emoji_code
    return name_to_codepoint
