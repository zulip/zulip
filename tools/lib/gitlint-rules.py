import re
from typing import List

from gitlint.git import GitCommit
from gitlint.options import StrOption
from gitlint.rules import CommitMessageTitle, LineRule, RuleViolation

# Word list from https://github.com/m1foley/fit-commit
# Copyright (c) 2015 Mike Foley
# License: MIT
# Ref: fit_commit/validators/tense.rb
WORD_SET = {
    'adds', 'adding', 'added',
    'allows', 'allowing', 'allowed',
    'amends', 'amending', 'amended',
    'bumps', 'bumping', 'bumped',
    'calculates', 'calculating', 'calculated',
    'changes', 'changing', 'changed',
    'cleans', 'cleaning', 'cleaned',
    'commits', 'committing', 'committed',
    'corrects', 'correcting', 'corrected',
    'creates', 'creating', 'created',
    'darkens', 'darkening', 'darkened',
    'disables', 'disabling', 'disabled',
    'displays', 'displaying', 'displayed',
    'documents', 'documenting', 'documented',
    'drys', 'drying', 'dryed',
    'ends', 'ending', 'ended',
    'enforces', 'enforcing', 'enforced',
    'enqueues', 'enqueuing', 'enqueued',
    'extracts', 'extracting', 'extracted',
    'finishes', 'finishing', 'finished',
    'fixes', 'fixing', 'fixed',
    'formats', 'formatting', 'formatted',
    'guards', 'guarding', 'guarded',
    'handles', 'handling', 'handled',
    'hides', 'hiding', 'hid',
    'increases', 'increasing', 'increased',
    'ignores', 'ignoring', 'ignored',
    'implements', 'implementing', 'implemented',
    'improves', 'improving', 'improved',
    'keeps', 'keeping', 'kept',
    'kills', 'killing', 'killed',
    'makes', 'making', 'made',
    'merges', 'merging', 'merged',
    'moves', 'moving', 'moved',
    'permits', 'permitting', 'permitted',
    'prevents', 'preventing', 'prevented',
    'pushes', 'pushing', 'pushed',
    'rebases', 'rebasing', 'rebased',
    'refactors', 'refactoring', 'refactored',
    'removes', 'removing', 'removed',
    'renames', 'renaming', 'renamed',
    'reorders', 'reordering', 'reordered',
    'replaces', 'replacing', 'replaced',
    'requires', 'requiring', 'required',
    'restores', 'restoring', 'restored',
    'sends', 'sending', 'sent',
    'sets', 'setting',
    'separates', 'separating', 'separated',
    'shows', 'showing', 'showed',
    'simplifies', 'simplifying', 'simplified',
    'skips', 'skipping', 'skipped',
    'sorts', 'sorting',
    'speeds', 'speeding', 'sped',
    'starts', 'starting', 'started',
    'supports', 'supporting', 'supported',
    'takes', 'taking', 'took',
    'testing', 'tested',  # 'tests' excluded to reduce false negative
    'truncates', 'truncating', 'truncated',
    'updates', 'updating', 'updated',
    'uses', 'using', 'used',
}

imperative_forms = [
    'add', 'allow', 'amend', 'bump', 'calculate', 'change', 'clean', 'commit',
    'correct', 'create', 'darken', 'disable', 'display', 'document', 'dry',
    'end', 'enforce', 'enqueue', 'extract', 'finish', 'fix', 'format', 'guard',
    'handle', 'hide', 'ignore', 'implement', 'improve', 'increase', 'keep',
    'kill', 'make', 'merge', 'move', 'permit', 'prevent', 'push', 'rebase',
    'refactor', 'remove', 'rename', 'reorder', 'replace', 'require', 'restore',
    'send', 'separate', 'set', 'show', 'simplify', 'skip', 'sort', 'speed',
    'start', 'support', 'take', 'test', 'truncate', 'update', 'use',
]
imperative_forms.sort()


def head_binary_search(key: str, words: List[str]) -> str:
    """ Find the imperative mood version of `word` by looking at the first
    3 characters. """

    # Edge case: 'disable' and 'display' have the same 3 starting letters.
    if key in ['displays', 'displaying', 'displayed']:
        return 'display'

    lower = 0
    upper = len(words) - 1

    while True:
        if lower > upper:
            # Should not happen
            raise Exception(f"Cannot find imperative mood of {key}")

        mid = (lower + upper) // 2
        imperative_form = words[mid]

        if key[:3] == imperative_form[:3]:
            return imperative_form
        elif key < imperative_form:
            upper = mid - 1
        elif key > imperative_form:
            lower = mid + 1


class ImperativeMood(LineRule):
    """ This rule will enforce that the commit message title uses imperative
    mood. This is done by checking if the first word is in `WORD_SET`, if so
    show the word in the correct mood. """

    name = "title-imperative-mood"
    id = "Z1"
    target = CommitMessageTitle

    error_msg = ('The first word in commit title should be in imperative mood '
                 '("{word}" -> "{imperative}"): "{title}"')

    def validate(self, line: str, commit: GitCommit) -> List[RuleViolation]:
        violations = []

        # Ignore the section tag (ie `<section tag>: <message body>.`)
        words = line.split(': ', 1)[-1].split()
        first_word = words[0].lower()

        if first_word in WORD_SET:
            imperative = head_binary_search(first_word, imperative_forms)
            violation = RuleViolation(self.id, self.error_msg.format(
                word=first_word,
                imperative=imperative,
                title=commit.message.title,
            ))

            violations.append(violation)

        return violations


class TitleMatchRegexAllowException(LineRule):
    """Allows revert commits contrary to the built-in title-match-regex rule"""

    name = 'title-match-regex-allow-exception'
    id = 'Z2'
    target = CommitMessageTitle
    options_spec = [StrOption('regex', ".*", "Regex the title should match")]

    def validate(self, title: str, commit: GitCommit) -> List[RuleViolation]:

        regex = self.options['regex'].value
        pattern = re.compile(regex, re.UNICODE)
        if not pattern.search(title) and not title.startswith("Revert \""):
            violation_msg = f"Title does not match regex ({regex})"
            return [RuleViolation(self.id, violation_msg, title)]

        return []
