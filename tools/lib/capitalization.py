from __future__ import absolute_import

from typing import List, Tuple, Set, Pattern, Match
import re

from bs4 import BeautifulSoup

# The phrases in this list will be ignored.
#
# Keep this list lexicographically sorted.
IGNORED_PHRASES = [re.compile(regex) for regex in [
    r".zuliprc",
    r"API",
    r"Dropbox",
    r"GitHub",
    r"Google",
    r"I say",
    r"I want",
    r"I'm",
    r"ID",
    r"IDs",
    r"JIRA",
    r"JSON",
    r"Kerberos",
    r"Mac",
    r"MiB",
    r"Pivotal",
    r"SSO",
    r"URL",
    r"Ubuntu",
    r"Webathena",
    r"Windows",
    r"WordPress",
    r"XML",
    r"Zephyr",
    r"Zulip",
    r"__\w+\.\w+__",
    r"and",
    r"bot",
    r"e.g.",
    r"etc.",
    r"iPhone",
    r"images",
    r"left",
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
        safe_text = get_safe_text(text)
        has_ignored_phrase = text != safe_text
        capitalized = is_capitalized(safe_text)
        if not capitalized:
            errors.append(text)
        elif capitalized and has_ignored_phrase:
            ignored.append(text)

    return sorted(errors), sorted(ignored)
