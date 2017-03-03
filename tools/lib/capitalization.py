from __future__ import absolute_import

from typing import List, Tuple, Set, Pattern, Match
import re

from bs4 import BeautifulSoup

# The phrases in this list will be ignored.
#
# Keep the sublists lexicographically sorted.
IGNORED_PHRASES = [re.compile(regex) for regex in [
    # Proper nouns and acronyms
    r"API",
    r"Cookie Bot",
    r"Dropbox",
    r"GitHub",
    r"Google",
    r"HTTP",
    r"ID",
    r"IDs",
    r"JIRA",
    r"JSON",
    r"Kerberos",
    r"Mac",
    r"MiB",
    r"Pivotal",
    r'REMOTE_USER',
    r"SSO",
    r'Terms of Service',
    r"URL",
    r"Ubuntu",
    r"V5",
    r"Webathena",
    r"Windows",
    r"WordPress",
    r"XML",
    r"Zephyr",
    r"Zulip",
    r"iPhone",
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

    # Fragments of larger strings
    r"one or more people...",
    r"confirmation email",
    r"invites remaining",
    r"^left$",
    r"^right$",

    # SPECIAL CASES
    # Enter is usually capitalized
    r"Press Enter to send",
    # Because topics usually are lower-case, this would look weird if it were capitalized
    r"more topics",
    # For consistency with "more topics"
    r"more conversations",
    # We should probably just delete this string from translations
    r'activation key',

    # TO CLEAN UP
    # Just want to avoid churning login.html right now
    r"or Choose a user",
    # This is a parsing bug in the tool
    r"argument ",
    # I can't find this one
    r"text",
]]

SPLIT_BOUNDARY = '?.!'  # Used to split string into sentences.
SPLIT_BOUNDARY_REGEX = re.compile(r'[{}]'.format(SPLIT_BOUNDARY))

# Regexes which check capitalization in sentences.
DISALLOWED_REGEXES = [re.compile(regex) for regex in [
    r'^[a-z]',  # Checks if the sentence starts with a lower case character.
    r'^[A-Z][a-z]+[\sa-z0-9]+[A-Z]',  # Checks if an upper case character exists
    # after a lower case character when the first character is in upper case.
]]

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
    for phrase_regex in IGNORED_PHRASES:
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

def check_capitalization(strings):
    # type: (List[str]) -> Tuple[List[str], List[str]]
    errors = []
    ignored = []
    for text in strings:
        # Hand-skip a few that break the tool
        if 'Change notification settings for individual streams' in text:
            continue
        if 'was too large; the maximum file size is 25MiB.' in text:
            continue
        if 'Most stream administration is done on the' in text:
            continue
        if 'bot-settings-note padded-container' in text:
            continue
        safe_text = get_safe_text(text)
        has_ignored_phrase = text != safe_text
        capitalized = is_capitalized(safe_text)
        if not capitalized:
            errors.append(text)
        elif capitalized and has_ignored_phrase:
            ignored.append(text)

    return sorted(errors), sorted(ignored)
