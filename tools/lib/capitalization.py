import re
from typing import List, Match, Tuple

from bs4 import BeautifulSoup

# The phrases in this list will be ignored. The longest phrase is
# tried first; this removes the chance of smaller phrases changing
# the text before longer phrases are tried.
# The errors shown by `tools/check-capitalization` can be added to
# this list without any modification.
IGNORED_PHRASES = [
    # Proper nouns and acronyms
    r"API",
    r"APNS",
    r"Botserver",
    r"Cookie Bot",
    r"DevAuthBackend",
    r"DSN",
    r"Esc",
    r"GCM",
    r"GitHub",
    r"Gravatar",
    r"Help Center",
    r"HTTP",
    r"ID",
    r"IDs",
    r"Inbox",
    r"IP",
    r"JSON",
    r"Jitsi",
    r"Kerberos",
    r"LinkedIn",
    r"LDAP",
    r"Markdown",
    r"OTP",
    r"Pivotal",
    r"Recent conversations",
    r"DM",
    r"DMs",
    r"Slack",
    r"Google",
    r"Terms of Service",
    r"Tuesday",
    r"URL",
    r"UUID",
    r"Webathena",
    r"WordPress",
    r"Zephyr",
    r"Zoom",
    r"Zulip",
    r"Zulip Server",
    r"Zulip Account Security",
    r"Zulip Security",
    r"Zulip Cloud",
    r"Zulip Cloud Standard",
    r"Zulip Cloud Plus",
    r"BigBlueButton",
    # Code things
    r"\.zuliprc",
    # BeautifulSoup will remove <z-user> which is horribly confusing,
    # so we need more of the sentence.
    r"<z-user></z-user> will have the same role",
    r"<z-user></z-user> will have the same properties",
    # Things using "I"
    r"I understand",
    r"I'm",
    r"I've",
    r"Topics I participate in",
    r"Topics I send a message to",
    r"Topics I start",
    # Specific short words
    r"beta",
    r"and",
    r"bot",
    r"e\.g\.",
    r"enabled",
    r"signups",
    # Placeholders
    r"keyword",
    r"streamname",
    r"user@example\.com",
    r"example\.com",
    r"acme",
    # Fragments of larger strings
    r"is …",
    r"your subscriptions on your Channels page",
    r"Add global time<br />Everyone sees global times in their own time zone\.",
    r"user",
    r"an unknown operating system",
    r"Go to Settings",
    r"find accounts for another email address",
    # SPECIAL CASES
    # Because topics usually are lower-case, this would look weird if it were capitalized
    r"more topics",
    # Used alone in a parenthetical where capitalized looks worse.
    r"^deprecated$",
    # We want the similar text in the Private Messages section to have the same capitalization.
    r"more conversations",
    r"back to channels",
    # Capital 'i' looks weird in reminders popover
    r"in 1 hour",
    r"in 20 minutes",
    r"in 3 hours",
    # these are used as topics
    r"^new channels$",
    r"^channel events$",
    # These are used as example short names (e.g. an uncapitalized context):
    r"^marketing$",
    r"^cookie$",
    # Used to refer custom time limits
    r"\bN\b",
    # Capital c feels obtrusive in clear status option
    r"clear",
    r"group direct messages with \{recipient\}",
    r"direct messages with \{recipient\}",
    r"direct messages with yourself",
    r"GIF",
    # Emoji name placeholder
    r"leafy green vegetable",
    # Subdomain placeholder
    r"your-organization-url",
    # Used in invite modal
    r"or",
    # Used in GIPHY integration setting. GIFs Rating.
    r"rated Y",
    r"rated G",
    r"rated PG",
    r"rated PG13",
    r"rated R",
    # Used in GIPHY popover.
    r"GIFs",
    r"GIPHY",
    # Used in our case studies
    r"Technical University of Munich",
    r"University of California San Diego",
    # Used in stream creation form
    r"email hidden",
    # Use in compose box.
    r"to send",
    r"to add a new line",
    # Used in showing Notification Bot read receipts message
    "Notification Bot",
    # Used in presence_enabled setting label
    r"invisible mode off",
    # Typeahead suggestions for "Pronouns" custom field type.
    r"he/him",
    r"she/her",
    r"they/them",
    # Used in message-move-time-limit setting label
    r"does not apply to moderators and administrators",
    # Used in message-delete-time-limit setting label
    r"does not apply to administrators",
    # Used as indicator with names for guest users.
    r"guest",
    # Used in pills for deactivated users.
    r"deactivated",
    # This is a reference to a setting/secret and should be lowercase.
    r"zulip_org_id",
]

# Sort regexes in descending order of their lengths. As a result, the
# longer phrases will be ignored first.
IGNORED_PHRASES.sort(key=len, reverse=True)

# Compile regexes to improve performance. This also extracts the
# text using BeautifulSoup and then removes extra whitespaces from
# it. This step enables us to add HTML in our regexes directly.
COMPILED_IGNORED_PHRASES = [
    re.compile(r" ".join(BeautifulSoup(regex, "lxml").text.split())) for regex in IGNORED_PHRASES
]

SPLIT_BOUNDARY = r"?.!"  # Used to split string into sentences.
SPLIT_BOUNDARY_REGEX = re.compile(rf"[{SPLIT_BOUNDARY}]")

# Regexes which check capitalization in sentences.
DISALLOWED = [
    r"^[a-z](?!\})",  # Checks if the sentence starts with a lower case character.
    r"^[A-Z][a-z]+[\sa-z0-9]+[A-Z]",  # Checks if an upper case character exists
    # after a lower case character when the first character is in upper case.
]
DISALLOWED_REGEX = re.compile(r"|".join(DISALLOWED))

BANNED_WORDS = {
    "realm": "The term realm should not appear in user-facing strings. Use organization instead.",
}


def get_safe_phrase(phrase: str) -> str:
    """
    Safe phrase is in lower case and doesn't contain characters which can
    conflict with split boundaries. All conflicting characters are replaced
    with low dash (_).
    """
    phrase = SPLIT_BOUNDARY_REGEX.sub("_", phrase)
    return phrase.lower()


def replace_with_safe_phrase(matchobj: Match[str]) -> str:
    """
    The idea is to convert IGNORED_PHRASES into safe phrases, see
    `get_safe_phrase()` function. The only exception is when the
    IGNORED_PHRASE is at the start of the text or after a split
    boundary; in this case, we change the first letter of the phrase
    to upper case.
    """
    ignored_phrase = matchobj.group(0)
    safe_string = get_safe_phrase(ignored_phrase)

    start_index = matchobj.start()
    complete_string = matchobj.string

    is_string_start = start_index == 0
    # We expect that there will be one space between split boundary
    # and the next word.
    punctuation = complete_string[max(start_index - 2, 0)]
    is_after_split_boundary = punctuation in SPLIT_BOUNDARY
    if is_string_start or is_after_split_boundary:
        return safe_string.capitalize()

    return safe_string


def get_safe_text(text: str) -> str:
    """
    This returns text which is rendered by BeautifulSoup and is in the
    form that can be split easily and has all IGNORED_PHRASES processed.
    """
    soup = BeautifulSoup(text, "lxml")
    text = " ".join(soup.text.split())  # Remove extra whitespaces.
    for phrase_regex in COMPILED_IGNORED_PHRASES:
        text = phrase_regex.sub(replace_with_safe_phrase, text)

    return text


def is_capitalized(safe_text: str) -> bool:
    sentences = SPLIT_BOUNDARY_REGEX.split(safe_text)
    return not any(DISALLOWED_REGEX.search(sentence.strip()) for sentence in sentences)


def check_banned_words(text: str) -> List[str]:
    lower_cased_text = text.lower()
    errors = []
    for word, reason in BANNED_WORDS.items():
        if word in lower_cased_text:
            # Hack: Should move this into BANNED_WORDS framework; for
            # now, just hand-code the skips:
            if (
                "realm_name" in lower_cased_text
                or "realm_uri" in lower_cased_text
                or "remote_realm_host" in lower_cased_text
            ):
                continue
            kwargs = dict(word=word, text=text, reason=reason)
            msg = "{word} found in '{text}'. {reason}".format(**kwargs)
            errors.append(msg)

    return errors


def check_capitalization(strings: List[str]) -> Tuple[List[str], List[str], List[str]]:
    errors = []
    ignored = []
    banned_word_errors = []
    for text in strings:
        text = " ".join(text.split())  # Remove extra whitespaces.
        safe_text = get_safe_text(text)
        has_ignored_phrase = text != safe_text
        capitalized = is_capitalized(safe_text)
        if not capitalized:
            errors.append(text)
        elif has_ignored_phrase:
            ignored.append(text)

        banned_word_errors.extend(check_banned_words(text))

    return sorted(errors), sorted(ignored), sorted(banned_word_errors)
