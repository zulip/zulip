# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import

import os
import re
import traceback

from .printer import print_err, colors

from typing import cast, Any, Callable, Dict, List, Optional, Tuple

RuleList = List[Dict[str, Any]]  # mypy currently requires Aliases at global scope
# https://github.com/python/mypy/issues/3145

def custom_check_file(fn, identifier, rules, color, skip_rules=None, max_length=None):
    # type: (str, str, RuleList, str, Optional[Any], Optional[int]) -> bool
    failed = False

    line_tups = []
    for i, line in enumerate(open(fn)):
        line_newline_stripped = line.strip('\n')
        line_fully_stripped = line_newline_stripped.strip()
        skip = False
        for rule in skip_rules or []:
            if re.match(rule, line):
                skip = True
        if line_fully_stripped.endswith('  # nolint'):
            continue
        if skip:
            continue
        tup = (i, line, line_newline_stripped, line_fully_stripped)
        line_tups.append(tup)

    rules_to_apply = []
    fn_dirname = os.path.dirname(fn)
    for rule in rules:
        exclude_list = rule.get('exclude', set())
        if fn in exclude_list or fn_dirname in exclude_list:
            continue
        if rule.get("include_only"):
            found = False
            for item in rule.get("include_only", set()):
                if item in fn:
                    found = True
            if not found:
                continue
        rules_to_apply.append(rule)

    for rule in rules_to_apply:
        exclude_lines = {
            line for
            (exclude_fn, line) in rule.get('exclude_line', set())
            if exclude_fn == fn
        }

        pattern = rule['pattern']
        for (i, line, line_newline_stripped, line_fully_stripped) in line_tups:
            if line_fully_stripped in exclude_lines:
                exclude_lines.remove(line_fully_stripped)
                continue
            try:
                line_to_check = line_fully_stripped
                if rule.get('strip') is not None:
                    if rule['strip'] == '\n':
                        line_to_check = line_newline_stripped
                    else:
                        raise Exception("Invalid strip rule")
                if re.search(pattern, line_to_check):
                    print_err(identifier, color, '{} at {} line {}:'.format(
                        rule['description'], fn, i+1))
                    print_err(identifier, color, line)
                    failed = True
            except Exception:
                print("Exception with %s at %s line %s" % (rule['pattern'], fn, i+1))
                traceback.print_exc()

        if exclude_lines:
            print('Please remove exclusions for file %s: %s' % (fn, exclude_lines))

    lastLine = None
    for (i, line, line_newline_stripped, line_fully_stripped) in line_tups:
        if isinstance(line, bytes):
            line_length = len(line.decode("utf-8"))
        else:
            line_length = len(line)
        if (max_length is not None and line_length > max_length and
            '# type' not in line and 'test' not in fn and 'example' not in fn and
            not re.match("\[[ A-Za-z0-9_:,&()-]*\]: http.*", line) and
            not re.match("`\{\{ external_api_uri_subdomain \}\}[^`]+`", line) and
                "#ignorelongline" not in line and 'migrations' not in fn):
            print("Line too long (%s) at %s line %s: %s" % (len(line), fn, i+1, line_newline_stripped))
            failed = True
        lastLine = line

    if lastLine and ('\n' not in lastLine):
        print("No newline at the end of file.  Fix with `sed -i '$a\\' %s`" % (fn,))
        failed = True

    return failed

def build_custom_checkers(by_lang):
    # type: (Dict[str, List[str]]) -> Tuple[Callable[[], bool], Callable[[], bool]]

    # By default, a rule applies to all files within the extension for which it is specified (e.g. all .py files)
    # There are three operators we can use to manually include or exclude files from linting for a rule:
    # 'exclude': 'set([<path>, ...])' - if <path> is a filename, excludes that file.
    #                                   if <path> is a directory, excludes all files directly below the directory <path>.
    # 'exclude_line': 'set([(<path>, <line>), ...])' - excludes all lines matching <line> in the file <path> from linting.
    # 'include_only': 'set([<path>, ...])' - includes only those files where <path> is a substring of the filepath.
    trailing_whitespace_rule = {
        'pattern': '\s+$',
        'strip': '\n',
        'description': 'Fix trailing whitespace'
    }
    whitespace_rules = [
        # This linter should be first since bash_rules depends on it.
        trailing_whitespace_rule,
        {'pattern': '\t',
         'strip': '\n',
         'exclude': set(['tools/travis/success-http-headers.txt']),
         'description': 'Fix tab-based whitespace'},
    ]  # type: RuleList
    markdown_whitespace_rules = list([rule for rule in whitespace_rules if rule['pattern'] != '\s+$']) + [
        # Two spaces trailing a line with other content is okay--it's a markdown line break.
        # This rule finds one space trailing a non-space, three or more trailing spaces, and
        # spaces on an empty line.
        {'pattern': '((?<!\s)\s$)|(\s\s\s+$)|(^\s+$)',
         'strip': '\n',
         'description': 'Fix trailing whitespace'},
        {'pattern': '^#+[A-Za-z0-9]',
         'strip': '\n',
         'description': 'Missing space after # in heading',
         'good_lines': ['### some heading', '# another heading'],
         'bad_lines': ['###some heading', '#another heading']},
    ]  # type: RuleList
    js_rules = cast(RuleList, [
        {'pattern': '[^_]function\(',
         'description': 'The keyword "function" should be followed by a space'},
        {'pattern': '.*blueslip.warning\(.*',
         'description': 'The module blueslip has no function warning, try using blueslip.warn'},
        {'pattern': '[)]{$',
         'description': 'Missing space between ) and {'},
        {'pattern': 'i18n\.t\([^)]+[^,\{\)]$',
         'description': 'i18n string should not be a multiline string'},
        {'pattern': 'i18n\.t\([\'\"].+?[\'\"]\s*\+',
         'description': 'Do not concatenate arguments within i18n.t()'},
        {'pattern': 'i18n\.t\(.+\).*\+',
         'description': 'Do not concatenate i18n strings'},
        {'pattern': '\+.*i18n\.t\(.+\)',
         'description': 'Do not concatenate i18n strings'},
        {'pattern': '["\']json/',
         'description': 'Relative URL for JSON route not supported by i18n'},
        # This rule is constructed with + to avoid triggering on itself
        {'pattern': " =" + '[^ =>~"]',
         'description': 'Missing whitespace after "="'},
        {'pattern': '^[ ]*//[A-Za-z0-9]',
         'description': 'Missing space after // in comment'},
        {'pattern': 'if[(]',
         'description': 'Missing space between if and ('},
        {'pattern': 'else{$',
         'description': 'Missing space between else and {'},
        {'pattern': '^else {$',
         'description': 'Write JS else statements on same line as }'},
        {'pattern': '^else if',
         'description': 'Write JS else statements on same line as }'},
        {'pattern': 'console[.][a-z]',
         'exclude': set(['static/js/blueslip.js',
                         'frontend_tests/zjsunit',
                         'frontend_tests/casper_lib/common.js',
                         'frontend_tests/node_tests',
                         'static/js/debug.js']),
         'description': 'console.log and similar should not be used in webapp'},
        {'pattern': '[.]text\(["\'][a-zA-Z]',
         'description': 'Strings passed to $().text should be wrapped in i18n.t() for internationalization'},
        {'pattern': 'compose_error\(["\']',
         'description': 'Argument to compose_error should be a literal string enclosed '
                        'by i18n.t()'},
        {'pattern': 'ui.report_success\(',
         'description': 'Deprecated function, use ui_report.success.'},
        {'pattern': 'report.success\(["\']',
         'description': 'Argument to report_success should be a literal string enclosed '
                        'by i18n.t()'},
        {'pattern': 'ui.report_error\(',
         'description': 'Deprecated function, use ui_report.error.'},
        {'pattern': 'report.error\(["\']',
         'description': 'Argument to report_error should be a literal string enclosed '
                        'by i18n.t()'},
    ]) + whitespace_rules
    python_rules = cast(RuleList, [
        {'pattern': '^(?!#)@login_required',
         'description': '@login_required is unsupported; use @zulip_login_required'},
        {'pattern': '".*"%\([a-z_].*\)?$',
         'description': 'Missing space around "%"'},
        {'pattern': "'.*'%\([a-z_].*\)?$",
         'exclude': set(['analytics/lib/counts.py',
                         'analytics/tests/test_counts.py',
                         ]),
         'exclude_line': set([
             ('zerver/views/users.py',
              "return json_error(_(\"Email '%(email)s' not allowed for realm '%(realm)s'\") %"),
             ('zproject/settings.py',
              "'format': '%(asctime)s %(levelname)-8s %(message)s'"),
             ('static/templates/settings/bot-settings.handlebars',
              "'https://hostname.example.com/bots/followup'"),
         ]),
         'description': 'Missing space around "%"'},
        # This rule is constructed with + to avoid triggering on itself
        {'pattern': " =" + '[^ =>~"]',
         'description': 'Missing whitespace after "="'},
        {'pattern': '":\w[^"]*$',
         'description': 'Missing whitespace after ":"'},
        {'pattern': "':\w[^']*$",
         'description': 'Missing whitespace after ":"'},
        {'pattern': "^\s+[#]\w",
         'strip': '\n',
         'description': 'Missing whitespace after "#"'},
        {'pattern': "assertEquals[(]",
         'description': 'Use assertEqual, not assertEquals (which is deprecated).'},
        {'pattern': "== None",
         'description': 'Use `is None` to check whether something is None'},
        {'pattern': "type:[(]",
         'description': 'Missing whitespace after ":" in type annotation'},
        {'pattern': "type: ignore$",
         'exclude': set(['tools/tests',
                         'zerver/lib/test_runner.py',
                         'zerver/tests']),
         'description': '"type: ignore" should always end with "# type: ignore # explanation for why"'},
        {'pattern': "# type [(]",
         'description': 'Missing : after type in type annotation'},
        {'pattern': "#type",
         'description': 'Missing whitespace after "#" in type annotation'},
        {'pattern': 'if[(]',
         'description': 'Missing space between if and ('},
        {'pattern': ", [)]",
         'description': 'Unnecessary whitespace between "," and ")"'},
        {'pattern': "%  [(]",
         'description': 'Unnecessary whitespace between "%" and "("'},
        # This next check could have false positives, but it seems pretty
        # rare; if we find any, they can be added to the exclude list for
        # this rule.
        {'pattern': ' % [a-zA-Z0-9_.]*\)?$',
         'exclude_line': set([
             ('tools/tests/test_template_parser.py', '{% foo'),
         ]),
         'description': 'Used % comprehension without a tuple'},
        {'pattern': '.*%s.* % \([a-zA-Z0-9_.]*\)$',
         'description': 'Used % comprehension without a tuple'},
        {'pattern': 'django.utils.translation',
         'include_only': set(['test/']),
         'description': 'Test strings should not be tagged for translationx'},
        {'pattern': 'json_success\({}\)',
         'description': 'Use json_success() to return nothing'},
        # To avoid json_error(_variable) and json_error(_(variable))
        {'pattern': '\Wjson_error\(_\(?\w+\)',
         'exclude': set(['zerver/tests']),
         'description': 'Argument to json_error should be a literal string enclosed by _()'},
        {'pattern': '\Wjson_error\([\'"].+[),]$',
         'exclude': set(['zerver/tests']),
         'exclude_line': set([
             # We don't want this string tagged for translation.
             ('zerver/views/compatibility.py', 'return json_error("Client is too old")'),
         ]),
         'description': 'Argument to json_error should a literal string enclosed by _()'},
        # To avoid JsonableError(_variable) and JsonableError(_(variable))
        {'pattern': '\WJsonableError\(_\(?\w.+\)',
         'exclude': set(['zerver/tests']),
         'description': 'Argument to JsonableError should be a literal string enclosed by _()'},
        {'pattern': '\WJsonableError\(["\'].+\)',
         'exclude': set(['zerver/tests']),
         'description': 'Argument to JsonableError should be a literal string enclosed by _()'},
        {'pattern': '([a-zA-Z0-9_]+)=REQ\([\'"]\\1[\'"]',
         'description': 'REQ\'s first argument already defaults to parameter name'},
        {'pattern': 'self\.client\.(get|post|patch|put|delete)',
         'description': \
         '''Do not call self.client directly for put/patch/post/get.
    See WRAPPER_COMMENT in test_helpers.py for details.
    '''},
        # Directly fetching Message objects in e.g. views code is often a security bug.
        {'pattern': '[^r][M]essage.objects.get',
         'exclude': set(["zerver/tests",
                         "zerver/lib/onboarding.py",
                         "zilencer/management/commands/add_mock_conversation.py",
                         "zerver/worker/queue_processors.py"]),
         'description': 'Please use access_message() to fetch Message objects',
         },
        {'pattern': '[S]tream.objects.get',
         'include_only': set(["zerver/views/"]),
         'description': 'Please use access_stream_by_*() to fetch Stream objects',
         },
        {'pattern': 'get_stream[(]',
         'include_only': set(["zerver/views/", "zerver/lib/actions.py"]),
         'exclude_line': set([
             # This one in check_message is kinda terrible, since it's
             # how most instances are written, but better to exclude something than nothing
             ('zerver/lib/actions.py', 'stream = get_stream(stream_name, realm)'),
             ('zerver/lib/actions.py', 'get_stream(signups_stream, admin_realm)'),
             # Here we need get_stream to access streams you've since unsubscribed from.
             ('zerver/views/messages.py', 'stream = get_stream(operand, self.user_profile.realm)'),
             # Use stream_id to exclude mutes.
             ('zerver/views/messages.py', 'stream_id = get_stream(stream_name, user_profile.realm).id'),
         ]),
         'description': 'Please use access_stream_by_*() to fetch Stream objects',
         },
        {'pattern': '[S]tream.objects.filter',
         'include_only': set(["zerver/views/"]),
         'description': 'Please use access_stream_by_*() to fetch Stream objects',
         },
        {'pattern': '^from (zerver|analytics|confirmation)',
         'include_only': set(["/migrations/"]),
         'exclude': set([
             'zerver/migrations/0032_verify_all_medium_avatar_images.py',
             'zerver/migrations/0041_create_attachments_for_old_messages.py',
             'zerver/migrations/0060_move_avatars_to_be_uid_based.py',
             'zerver/migrations/0104_fix_unreads.py',
         ]),
         'description': "Don't import models or other code in migrations; see docs/schema-migrations.md",
         },
        {'pattern': 'datetime[.](now|utcnow)',
         'include_only': set(["zerver/", "analytics/"]),
         'description': "Don't use datetime in backend code.\n"
         "See https://zulip.readthedocs.io/en/latest/code-style.html#naive-datetime-objects",
         },
        {'pattern': 'render_to_response\(',
         'description': "Use render() instead of render_to_response().",
         },
        {'pattern': 'from os.path',
         'description': "Don't use from when importing from the standard library",
         },
        {'pattern': 'import os.path',
         'description': "Use import os instead of import os.path",
         },
    ]) + whitespace_rules
    bash_rules = [
        {'pattern': '#!.*sh [-xe]',
         'description': 'Fix shebang line with proper call to /usr/bin/env for Bash path, change -x|-e switches'
                        ' to set -x|set -e'},
    ] + whitespace_rules[0:1]  # type: RuleList
    css_rules = cast(RuleList, [
        {'pattern': '^[^:]*:\S[^:]*;$',
         'description': "Missing whitespace after : in CSS"},
        {'pattern': '[a-z]{',
         'description': "Missing whitespace before '{' in CSS."},
        {'pattern': 'https://',
         'description': "Zulip CSS should have no dependencies on external resources"},
        {'pattern': '^[ ][ ][a-zA-Z0-9]',
         'description': "Incorrect 2-space indentation in CSS",
         'exclude': set(['static/third/thirdparty-fonts.css']),
         'strip': '\n'},
        {'pattern': '{\w',
         'description': "Missing whitespace after '{' in CSS (should be newline)."},
        {'pattern': ' thin[; ]',
         'description': "thin CSS attribute is under-specified, please use 1px."},
        {'pattern': ' medium[; ]',
         'description': "medium CSS attribute is under-specified, please use pixels."},
        {'pattern': ' thick[; ]',
         'description': "thick CSS attribute is under-specified, please use pixels."},
    ]) + whitespace_rules  # type: RuleList
    prose_style_rules = [
        {'pattern': '[^\/\#\-\"]([jJ]avascript)',  # exclude usage in hrefs/divs
         'description': "javascript should be spelled JavaScript"},
        {'pattern': '[^\/\-\.\"\'\_\=\>]([gG]ithub)[^\.\-\_\"\<]',  # exclude usage in hrefs/divs
         'description': "github should be spelled GitHub"},
        {'pattern': '[oO]rganisation',  # exclude usage in hrefs/divs
         'description': "Organization is spelled with a z",
         'exclude_line': [('docs/french.md', '* organization - **organisation**')]},
        {'pattern': '!!! warning',
         'description': "!!! warning is invalid; it's spelled '!!! warn'"},
        {'pattern': 'Terms of service',
         'description': "The S in Terms of Service is capitalized"},
    ]  # type: RuleList
    html_rules = whitespace_rules + prose_style_rules + [
        {'pattern': 'placeholder="[^{]',
         'description': "`placeholder` value should be translatable.",
         'exclude_line': [('templates/zerver/register.html', 'placeholder="acme"'),
                          ('templates/zerver/register.html', 'placeholder="Acme or Aκμή"'),
                          ('static/templates/settings/realm-domains-modal.handlebars',
                           '<td><input type="text" class="new-realm-domain" placeholder="acme.com"></input></td>')],
         'exclude': set(["static/templates/settings/emoji-settings-admin.handlebars",
                         "static/templates/settings/realm-filter-settings-admin.handlebars",
                         "static/templates/settings/bot-settings.handlebars"])},
        {'pattern': "placeholder='[^{]",
         'description': "`placeholder` value should be translatable."},
        {'pattern': "aria-label='[^{]",
         'description': "`aria-label` value should be translatable."},
        {'pattern': 'aria-label="[^{]',
         'description': "`aria-label` value should be translatable."},
        {'pattern': 'script src="http',
         'description': "Don't directly load dependencies from CDNs.  See docs/front-end-build-process.md"},
        {'pattern': "title='[^{]",
         'description': "`title` value should be translatable."},
        {'pattern': 'title="[^{\:]',
         'exclude_line': set([
             ('templates/zerver/markdown_help.html',
              '<td><img alt=":heart:" class="emoji" src="/static/generated/emoji/images/emoji/heart.png" title=":heart:" /></td>')
         ]),
         'exclude': set(["templates/zerver/emails"]),
         'description': "`title` value should be translatable."},
        {'pattern': '\Walt=["\'][^{"\']',
         'description': "alt argument should be enclosed by _() or it should be an empty string.",
         'exclude': set(['static/templates/settings/display-settings.handlebars',
                         'templates/zerver/keyboard_shortcuts.html',
                         'templates/zerver/markdown_help.html']),
         },
        {'pattern': '\Walt=["\']{{ ?["\']',
         'description': "alt argument should be enclosed by _().",
         },
    ]  # type: RuleList
    handlebars_rules = html_rules + [
        {'pattern': "[<]script",
         'description': "Do not use inline <script> tags here; put JavaScript in static/js instead."},
        {'pattern': '{{ t ("|\')',
         'description': 'There should be no spaces before the "t" in a translation tag.'},
        {'pattern': "{{t '.*' }}[\.\?!]",
         'description': "Period should be part of the translatable string."},
        {'pattern': '{{t ".*" }}[\.\?!]',
         'description': "Period should be part of the translatable string."},
        {'pattern': "{{/tr}}[\.\?!]",
         'description': "Period should be part of the translatable string."},
        {'pattern': '{{t ("|\') ',
         'description': 'Translatable strings should not have leading spaces.'},
        {'pattern': "{{t '[^']+ ' }}",
         'description': 'Translatable strings should not have trailing spaces.'},
        {'pattern': '{{t "[^"]+ " }}',
         'description': 'Translatable strings should not have trailing spaces.'},
    ]
    jinja2_rules = html_rules + [
        {'pattern': "{% endtrans %}[\.\?!]",
         'description': "Period should be part of the translatable string."},
        {'pattern': "{{ _(.+) }}[\.\?!]",
         'description': "Period should be part of the translatable string."},
    ]
    json_rules = [
        # Since most json files are fixtures containing 3rd party json code,
        # we allow tab-based whitespaces.
        trailing_whitespace_rule,
    ]
    markdown_rules = markdown_whitespace_rules + prose_style_rules + [
        {'pattern': '\[(?P<url>[^\]]+)\]\((?P=url)\)',
         'description': 'Linkified markdown URLs should use cleaner <http://example.com> syntax.'}
    ]
    help_markdown_rules = markdown_rules + [
        {'pattern': '[a-z][.][A-Z]',
         'description': "Likely missing space after end of sentence"},
        {'pattern': '[rR]ealm',
         'description': "Realms are referred to as Organizations in user-facing docs."},
    ]
    txt_rules = whitespace_rules

    def check_custom_checks_py():
        # type: () -> bool
        failed = False
        color = next(colors)

        for fn in by_lang['py']:
            if 'custom_check.py' in fn:
                continue
            if custom_check_file(fn, 'py', python_rules, color, max_length=140):
                failed = True
        return failed

    def check_custom_checks_nonpy():
        # type: () -> bool
        failed = False

        color = next(colors)
        for fn in by_lang['js']:
            if custom_check_file(fn, 'js', js_rules, color):
                failed = True

        color = next(colors)
        for fn in by_lang['sh']:
            if custom_check_file(fn, 'sh', bash_rules, color):
                failed = True

        color = next(colors)
        for fn in by_lang['css']:
            if custom_check_file(fn, 'css', css_rules, color):
                failed = True

        color = next(colors)
        for fn in by_lang['handlebars']:
            if custom_check_file(fn, 'handlebars', handlebars_rules, color):
                failed = True

        color = next(colors)
        for fn in by_lang['html']:
            if custom_check_file(fn, 'html', jinja2_rules, color):
                failed = True

        color = next(colors)
        for fn in by_lang['json']:
            if custom_check_file(fn, 'json', json_rules, color):
                failed = True

        color = next(colors)
        markdown_docs_length_exclude = {
            "api/bots/converter/readme.md",
            "docs/bots-guide.md",
            "docs/dev-env-first-time-contributors.md",
            "docs/webhook-walkthrough.md",
            "docs/life-of-a-request.md",
            "docs/logging.md",
            "docs/migration-renumbering.md",
            "docs/readme-symlink.md",
            "README.md",
            "zerver/webhooks/helloworld/doc.md",
            "zerver/webhooks/trello/doc.md",
            "templates/zerver/integrations/perforce.md",
        }
        for fn in by_lang['md']:
            max_length = None
            if fn not in markdown_docs_length_exclude:
                max_length = 120
            rules = markdown_rules
            if fn.startswith("templates/zerver/help"):
                rules = help_markdown_rules
            if custom_check_file(fn, 'md', rules, color, max_length=max_length):
                failed = True

        color = next(colors)
        for fn in by_lang['txt'] + by_lang['text']:
            if custom_check_file(fn, 'txt', txt_rules, color):
                failed = True

        color = next(colors)
        for fn in by_lang['yaml']:
            if custom_check_file(fn, 'yaml', txt_rules, color):
                failed = True

        return failed

    return (check_custom_checks_py, check_custom_checks_nonpy)
