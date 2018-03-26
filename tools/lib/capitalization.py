
from typing import List, Tuple, Set, Pattern, Match
import re

from bs4 import BeautifulSoup

# The phrases in this list will be ignored. The longest phrase is
# tried first; this removes the chance of smaller phrases changing
# the text before longer phrases are tried.
# The errors shown by `tools/check-capitalization` can be added to
# this list without any modification.
IGNORED_PHRASES = [
    # Proper nouns and acronyms
    r"Android",
    r"API",
    r"APNS",
    r"App Store",
    r"Botserver",
    r"Cookie Bot",
    r"Dropbox",
    r"GitHub",
    r"Google",
    r"Gravatar",
    r"Hamlet",
    r"HTTP",
    r"ID",
    r"IDs",
    r"JIRA",
    r"JSON",
    r"Kerberos",
    r"LDAP",
    r"Mac",
    r"macOS",
    r"MiB",
    r"OTP",
    r"Pivotal",
    r"Play Store",
    r'REMOTE_USER',
    r'Slack',
    r"SSO",
    r'Terms of Service',
    r"URL",
    r"Ubuntu",
    r"Updown",
    r"V5",
    r"Webathena",
    r"Windows",
    r"WordPress",
    r"XML",
    r"Zephyr",
    r"Zulip",
    r"iPhone",
    r"iOS",
    r"Emoji One",
    r"mailinator.com",
    # Code things
    r".zuliprc",
    r"__\w+\.\w+__",
    # Things using "I"
    r"I say",
    r"I want",
    r"I'm",
    # Specific short words
    r"and",
    r"bot",
    r"e.g.",
    r"etc.",
    r"images",
    r"enabled",
    r"disabled",

    # Fragments of larger strings
    (r'your subscriptions on your Streams page'),
    (r'Change notification settings for individual streams on your '
     '<a href="/#streams">Streams page</a>.'),
    (r'Looking for our '
     '<a href="/integrations" target="_blank">Integrations</a> or '
     '<a href="/api" target="_blank">API</a> documentation?'),
    r'Most stream administration is done on the <a href="/#streams">Streams page</a>.',
    r"one or more people...",
    r"confirmation email",
    r"invites remaining",
    r"was too large; the maximum file size is 25MiB.",
    r"selected message",
    r"a-z",

    # SPECIAL CASES
    # Enter is usually capitalized
    r"Press Enter to send",
    # Because topics usually are lower-case, this would look weird if it were capitalized
    r"more topics",
    # For consistency with "more topics"
    r"more conversations",
    # We should probably just delete this string from translations
    r'activation key',
    # this is used as a topic
    r'^hello$',
    # These are used as example short names (e.g. an uncapitalized context):
    r"^marketing$",
    r"^cookie$",
    r"^new_emoji$",

    # TO CLEAN UP
    # Just want to avoid churning login.html right now
    r"or Choose a user",
    # This is a parsing bug in the tool
    r"argument ",
    # I can't find this one
    r"text",
]

# Sort regexes in descending order of their lengths. As a result, the
# longer phrases will be ignored first.
IGNORED_PHRASES.sort(key=lambda regex: len(regex), reverse=True)

# Compile regexes to improve performance. This also extracts the
# text using BeautifulSoup and then removes extra whitespaces from
# it. This step enables us to add HTML in our regexes directly.
COMPILED_IGNORED_PHRASES = [
    re.compile(' '.join(BeautifulSoup(regex, 'lxml').text.split()))
    for regex in IGNORED_PHRASES
]

SPLIT_BOUNDARY = '?.!'  # Used to split string into sentences.
SPLIT_BOUNDARY_REGEX = re.compile(r'[{}]'.format(SPLIT_BOUNDARY))

# Regexes which check capitalization in sentences.
DISALLOWED_REGEXES = [re.compile(regex) for regex in [
    r'^[a-z]',  # Checks if the sentence starts with a lower case character.
    r'^[A-Z][a-z]+[\sa-z0-9]+[A-Z]',  # Checks if an upper case character exists
    # after a lower case character when the first character is in upper case.
]]

BANNED_WORDS = {
    'realm': ('The term realm should not appear in user-facing strings. '
              'Use organization instead.'),
}

def get_safe_phrase(phrase):
    # type: (str) -> str
    """
    Safe phrase is in lower case and doesn't contain characters which can
    conflict with split boundaries. All conflicting characters are replaced
    with low dash (_).
    """
    phrase = SPLIT_BOUNDARY_REGEX.sub('_', phrase)
    return phrase.lower()

def replace_with_safe_phrase(matchobj):
    # type: (Match[str]) -> str
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

def get_safe_text(text):
    # type: (str) -> str
    """
    This returns text which is rendered by BeautifulSoup and is in the
    form that can be split easily and has all IGNORED_PHRASES processed.
    """
    soup = BeautifulSoup(text, 'lxml')
    text = ' '.join(soup.text.split())  # Remove extra whitespaces.
    for phrase_regex in COMPILED_IGNORED_PHRASES:
        text = phrase_regex.sub(replace_with_safe_phrase, text)

    return text

def is_capitalized(safe_text):
    # type: (str) -> bool
    sentences = SPLIT_BOUNDARY_REGEX.split(safe_text)
    sentences = [sentence.strip()
                 for sentence in sentences if sentence.strip()]

    if not sentences:
        return False

    for sentence in sentences:
        for regex in DISALLOWED_REGEXES:
            if regex.search(sentence):
                return False

    return True

def check_banned_words(text: str) -> List[str]:
    lower_cased_text = text.lower()
    errors = []
    for word, reason in BANNED_WORDS.items():
        if word in lower_cased_text:
            # Hack: Should move this into BANNED_WORDS framework; for
            # now, just hand-code the skips:
            if 'realm_name' in lower_cased_text:
                continue
            kwargs = dict(word=word, text=text, reason=reason)
            msg = "{word} found in '{text}'. {reason}".format(**kwargs)
            errors.append(msg)

    return errors

def check_capitalization(strings):
    # type: (List[str]) -> Tuple[List[str], List[str], List[str]]
    errors = []
    ignored = []
    banned_word_errors = []
    for text in strings:
        text = ' '.join(text.split())  # Remove extra whitespaces.
        safe_text = get_safe_text(text)
        has_ignored_phrase = text != safe_text
        capitalized = is_capitalized(safe_text)
        if not capitalized:
            errors.append(text)
        elif capitalized and has_ignored_phrase:
            ignored.append(text)

        banned_word_errors.extend(check_banned_words(text))

    return sorted(errors), sorted(ignored), sorted(banned_word_errors)
