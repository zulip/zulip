# This file doesn't import from django so that we can use it in `build_emoji`


def unqualify_emoji(emoji: str) -> str:
    # Starting from version 4.0.0, `emoji_datasource` package has started to
    # add an emoji presentation variation selector for certain emojis which
    # have defined variation sequences. The emoji presentation selector
    # "qualifies" an emoji, and an "unqualified" version of an emoji does
    # not have an emoji presentation selector.
    #
    # Since in informal environments(like texting and chat), it is more
    # appropriate for an emoji to have a colorful display so until emoji
    # characters have a text presentation selector, it should have a
    # colorful display. Hence we can continue using emoji characters
    # without appending emoji presentation selector.
    # (http://unicode.org/reports/tr51/index.html#Presentation_Style)
    return emoji.replace("\ufe0f", "")


def emoji_to_hex_codepoint(emoji: str) -> str:
    return "-".join(f"{ord(c):04x}" for c in emoji)


def hex_codepoint_to_emoji(hex: str) -> str:
    return "".join(chr(int(h, 16)) for h in hex.split("-"))
