# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import

import re
import traceback

from zulint.printer import print_err

from typing import Any, Dict, List, Optional, Tuple, Iterable

Rule = Dict[str, Any]
RuleList = List[Dict[str, Any]]
LineTup = Tuple[int, str, str, str]

def get_line_info_from_file(fn: str) -> List[LineTup]:
    line_tups = []
    for i, line in enumerate(open(fn)):
        line_newline_stripped = line.strip('\n')
        line_fully_stripped = line_newline_stripped.strip()
        if line_fully_stripped.endswith('  # nolint'):
            continue
        tup = (i, line, line_newline_stripped, line_fully_stripped)
        line_tups.append(tup)
    return line_tups

def get_rules_applying_to_fn(fn: str, rules: RuleList) -> RuleList:
    rules_to_apply = []
    for rule in rules:
        excluded = False
        for item in rule.get('exclude', set()):
            if fn.startswith(item):
                excluded = True
                break
        if excluded:
            continue
        if rule.get("include_only"):
            found = False
            for item in rule.get("include_only", set()):
                if item in fn:
                    found = True
            if not found:
                continue
        rules_to_apply.append(rule)

    return rules_to_apply

def check_file_for_pattern(fn: str,
                           line_tups: List[LineTup],
                           identifier: str,
                           color: Optional[Iterable[str]],
                           rule: Rule) -> bool:

    '''
    DO NOT MODIFY THIS FUNCTION WITHOUT PROFILING.

    This function gets called ~40k times, once per file per regex.

    Inside it's doing a regex check for every line in the file, so
    it's important to do things like pre-compiling regexes.

    DO NOT INLINE THIS FUNCTION.

    We need to see it show up in profiles, and the function call
    overhead will never be a bottleneck.
    '''
    exclude_lines = {
        line for
        (exclude_fn, line) in rule.get('exclude_line', set())
        if exclude_fn == fn
    }

    pattern = re.compile(rule['pattern'])
    strip_rule = rule.get('strip')  # type: Optional[str]

    ok = True
    for (i, line, line_newline_stripped, line_fully_stripped) in line_tups:
        if line_fully_stripped in exclude_lines:
            exclude_lines.remove(line_fully_stripped)
            continue
        try:
            line_to_check = line_fully_stripped
            if strip_rule is not None:
                if strip_rule == '\n':
                    line_to_check = line_newline_stripped
                else:
                    raise Exception("Invalid strip rule")
            if pattern.search(line_to_check):
                if rule.get("exclude_pattern"):
                    if re.search(rule['exclude_pattern'], line_to_check):
                        continue
                print_err(identifier, color, '{} at {} line {}:'.format(
                    rule['description'], fn, i+1))
                print_err(identifier, color, line)
                ok = False
        except Exception:
            print("Exception with %s at %s line %s" % (rule['pattern'], fn, i+1))
            traceback.print_exc()

    if exclude_lines:
        print('Please remove exclusions for file %s: %s' % (fn, exclude_lines))

    return ok

def check_file_for_long_lines(fn: str,
                              max_length: int,
                              line_tups: List[LineTup]) -> bool:
    ok = True
    for (i, line, line_newline_stripped, line_fully_stripped) in line_tups:
        if isinstance(line, bytes):
            line_length = len(line.decode("utf-8"))
        else:
            line_length = len(line)
        if (line_length > max_length and
            '# type' not in line and 'test' not in fn and 'example' not in fn and
            # Don't throw errors for markdown format URLs
            not re.search(r"^\[[ A-Za-z0-9_:,&()-]*\]: http.*", line) and
            # Don't throw errors for URLs in code comments
            not re.search(r"[#].*http.*", line) and
            not re.search(r"`\{\{ api_url \}\}[^`]+`", line) and
                "# ignorelongline" not in line and 'migrations' not in fn):
            print("Line too long (%s) at %s line %s: %s" % (len(line), fn, i+1, line_newline_stripped))
            ok = False
    return ok

def custom_check_file(fn: str,
                      identifier: str,
                      rules: RuleList,
                      color: Optional[Iterable[str]],
                      max_length: Optional[int]=None) -> bool:
    failed = False

    line_tups = get_line_info_from_file(fn=fn)

    rules_to_apply = get_rules_applying_to_fn(fn=fn, rules=rules)

    for rule in rules_to_apply:
        ok = check_file_for_pattern(
            fn=fn,
            line_tups=line_tups,
            identifier=identifier,
            color=color,
            rule=rule,
        )
        if not ok:
            failed = True

    # TODO: Move the below into more of a framework.
    firstline = None
    lastLine = None
    if line_tups:
        firstline = line_tups[0][3]  # line_fully_stripped for the first line.
        lastLine = line_tups[-1][1]

    if max_length is not None:
        ok = check_file_for_long_lines(
            fn=fn,
            max_length=max_length,
            line_tups=line_tups,
        )
        if not ok:
            failed = True

    if firstline:
        shebang_rules = [
            {'pattern': '^#!',
             'description': "zerver library code shouldn't have a shebang line.",
             'include_only': set(['zerver/'])},
            # /bin/sh and /usr/bin/env are the only two binaries
            # that NixOS provides at a fixed path (outside a
            # buildFHSUserEnv sandbox).
            {'pattern': '^#!(?! *(?:/usr/bin/env|/bin/sh)(?: |$))',
             'description': "Use `#!/usr/bin/env foo` instead of `#!/path/foo` for interpreters other than sh."},
            {'pattern': '^#!/usr/bin/env python$',
             'description': "Use `#!/usr/bin/env python3` instead of `#!/usr/bin/env python`."}
        ]  # type: RuleList
        shebang_rules_to_apply = get_rules_applying_to_fn(fn=fn, rules=shebang_rules)
        for rule in shebang_rules_to_apply:
            if re.search(rule['pattern'], firstline):
                print_err(identifier, color,
                          '{} at {} line 1:'.format(rule['description'], fn))
                print_err(identifier, color, firstline)
                failed = True

    if lastLine and ('\n' not in lastLine):
        print("No newline at the end of file.  Fix with `sed -i '$a\\' %s`" % (fn,))
        failed = True

    return failed
