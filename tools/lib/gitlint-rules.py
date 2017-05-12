from typing import Text, List

import gitlint
from gitlint.rules import LineRule, RuleViolation, CommitMessageTitle

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
    'requires', 'requiring', 'required',
    'restores', 'restoring', 'restored',
    'sends', 'sending', 'sent',
    'sets', 'setting',
    'separates', 'separating', 'separated',
    'shows', 'showing', 'showed',
    'skips', 'skipping', 'skipped',
    'sorts', 'sorting',
    'speeds', 'speeding', 'sped',
    'starts', 'starting', 'started',
    'supports', 'supporting', 'supported',
    'takes', 'taking', 'took',
    'testing', 'tested',  # 'tests' excluded to reduce false negative
    'truncates', 'truncating', 'truncated',
    'updates', 'updating', 'updated',
    'uses', 'using', 'used'
}

imperative_forms = sorted([
    'add', 'allow', 'amend', 'bump', 'calculate', 'change', 'clean', 'commit',
    'correct', 'create', 'darken', 'disable', 'dry', 'end', 'enforce',
    'enqueue', 'extract', 'finish', 'fix', 'format', 'guard', 'handle', 'hide',
    'ignore', 'implement', 'improve', 'increase', 'keep', 'kill', 'make',
    'merge', 'move', 'permit', 'prevent', 'push', 'rebase', 'refactor',
    'remove', 'rename', 'reorder', 'require', 'restore', 'send', 'separate',
    'set', 'show', 'skip', 'sort', 'speed', 'start', 'support', 'take', 'test',
    'truncate', 'update', 'use',
])


def head_binary_search(key, words):
    # type: (Text, List[str]) -> str
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
            raise Exception("Cannot find imperative mood of {}".format(key))

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
    mood. """

    name = "title-imperative-mood"
    id = "Z1"
    target = CommitMessageTitle

    error_msg = ('Title contains non imperative mood '
                 '("{word}" -> "{imperative}"): "{title}"')

    def validate(self, line, commit):
        # type: (Text, gitlint.commit) -> List[RuleViolation]
        violations = []
        words = line.lower().split(" ")

        for word in words:
            if word in WORD_SET:
                imperative = head_binary_search(word, imperative_forms)
                violation = RuleViolation(self.id, self.error_msg.format(
                    word=word,
                    imperative=imperative,
                    title=commit.message.title
                ))

                violations.append(violation)

        return violations
