# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import

import os
import re
import traceback

from .printer import print_err, colors

from typing import cast, Any, Callable, Dict, List, Optional, Tuple, Iterable

RuleList = List[Dict[str, Any]]

def custom_check_file(fn, identifier, rules, color, skip_rules=None, max_length=None):
    # type: (str, str, RuleList, str, Optional[Iterable[str]], Optional[int]) -> bool
    failed = False

    line_tups = []
    for i, line in enumerate(open(fn)):
        line_newline_stripped = line.strip('\n')
        line_fully_stripped = line_newline_stripped.strip()
        skip = False
        for skip_rule in skip_rules or []:
            if re.match(skip_rule, line):
                skip = True
        if line_fully_stripped.endswith('  # nolint'):
            continue
        if skip:
            continue
        tup = (i, line, line_newline_stripped, line_fully_stripped)
        line_tups.append(tup)

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
                    if rule.get("exclude_pattern"):
                        if re.search(rule['exclude_pattern'], line_to_check):
                            continue
                    print_err(identifier, color, '{} at {} line {}:'.format(
                        rule['description'], fn, i+1))
                    print_err(identifier, color, line)
                    failed = True
            except Exception:
                print("Exception with %s at %s line %s" % (rule['pattern'], fn, i+1))
                traceback.print_exc()

        if exclude_lines:
            print('Please remove exclusions for file %s: %s' % (fn, exclude_lines))

    # TODO: Move the below into more of a framework.
    firstline = None
    if line_tups:
        firstline = line_tups[0][3]  # line_fully_stripped for the first line.
    lastLine = None
    for (i, line, line_newline_stripped, line_fully_stripped) in line_tups:
        if isinstance(line, bytes):
            line_length = len(line.decode("utf-8"))
        else:
            line_length = len(line)
        if (max_length is not None and line_length > max_length and
            '# type' not in line and 'test' not in fn and 'example' not in fn and
            # Don't throw errors for markdown format URLs
            not re.search("^\[[ A-Za-z0-9_:,&()-]*\]: http.*", line) and
            # Don't throw errors for URLs in code comments
            not re.search("[#].*http.*", line) and
            not re.search("`\{\{ api_url \}\}[^`]+`", line) and
                "# ignorelongline" not in line and 'migrations' not in fn):
            print("Line too long (%s) at %s line %s: %s" % (len(line), fn, i+1, line_newline_stripped))
            failed = True
        lastLine = line

    if firstline:
        if os.path.splitext(fn)[1] and 'zerver/' in fn:
            shebang_rules = [{'pattern': '^#!',
                              'description': "zerver library code shouldn't have a shebang line."}]
        else:
            shebang_rules = [{'pattern': '#!/usr/bin/python',
                              'description': "Use `#!/usr/bin/env python3` instead of `#!/usr/bin/python`"},
                             {'pattern': '#!/usr/bin/env python$',
                              'description': "Use `#!/usr/bin/env python3` instead of `#!/usr/bin/env python`."}]
        for rule in shebang_rules:
            if re.search(rule['pattern'], firstline):
                print_err(identifier, color,
                          '{} at {} line 1:'.format(rule['description'], fn))
                print_err(identifier, color, firstline)
                failed = True

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
        {'pattern': 'http://zulip.readthedocs.io',
         'description': 'Use HTTPS when linking to ReadTheDocs',
         },
        {'pattern': '\t',
         'strip': '\n',
         'exclude': set(['tools/travis/success-http-headers.txt']),
         'description': 'Fix tab-based whitespace'},
    ]  # type: RuleList
    comma_whitespace_rule = [
        {'pattern': ', {2,}[^#/ ]',
         'exclude': set(['zerver/tests', 'frontend_tests/node_tests']),
         'description': "Remove multiple whitespaces after ','",
         'good_lines': ['foo(1, 2, 3)', 'foo = bar  # some inline comment'],
         'bad_lines': ['foo(1,  2, 3)', 'foo(1,    2, 3)']},
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
        {'pattern': '[.]html[(]',
         'exclude_pattern': '[.]html[(]("|\'|templates|html|message.content|sub.rendered_description|i18n.t|rendered_|$|[)]|error_text|[$]error|[$][(]"<p>"[)])',
         'exclude': ['static/js/portico', 'static/js/lightbox.js', 'static/js/ui_report.js',
                     'frontend_tests/'],
         'description': 'Setting HTML content with jQuery .html() can lead to XSS security bugs.  Consider .text() or using rendered_foo as a variable name if content comes from handlebars and thus is already sanitized.'},
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
                         'static/js/debug.js',
                         'tools/generate-custom-icon-webfont']),
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
        {'pattern': '\$\(document\)\.ready\(',
         'description': "`Use $(f) rather than `$(document).ready(f)`",
         'good_lines': ['$(function () {foo();}'],
         'bad_lines': ['$(document).ready(function () {foo();}']},
        {'pattern': '[$][.](get|post|patch|delete|ajax)[(]',
         'description': "Use channel module for AJAX calls",
         'exclude': set([
             # Internal modules can do direct network calls
             'static/js/blueslip.js',
             'static/js/channel.js',
             # External modules that don't include channel.js
             'static/js/stats/',
             'static/js/portico/',
         ]),
         'good_lines': ['channel.get(...)'],
         'bad_lines': ['$.get()', '$.post()', '$.ajax()']},
        {'pattern': 'style ?=',
         'description': "Avoid using the `style=` attribute; we prefer styling in CSS files",
         'exclude': set([
             'frontend_tests/node_tests/copy_and_paste.js',
             'frontend_tests/node_tests/upload.js',
             'frontend_tests/node_tests/templates.js',
             'static/js/upload.js',
             'static/js/dynamic_text.js',
             'static/js/stream_color.js',
         ]),
         'good_lines': ['#my-style {color: blue;}'],
         'bad_lines': ['<p style="color: blue;">Foo</p>', 'style = "color: blue;"']},
    ]) + whitespace_rules + comma_whitespace_rule
    python_rules = cast(RuleList, [
        {'pattern': '^(?!#)@login_required',
         'description': '@login_required is unsupported; use @zulip_login_required',
         'good_lines': ['@zulip_login_required', '# foo @login_required'],
         'bad_lines': ['@login_required', ' @login_required']},
        {'pattern': '^user_profile[.]save[(][)]',
         'description': 'Always pass update_fields when saving user_profile objects',
         'exclude_line': set([
             ('zerver/lib/actions.py', "user_profile.save()  # Can't use update_fields because of how the foreign key works."),
         ]),
         'exclude': set(['zerver/tests', 'zerver/lib/create_user.py']),
         'good_lines': ['user_profile.save(update_fields=["pointer"])'],
         'bad_lines': ['user_profile.save()']},
        {'pattern': '^[^"]*"[^"]*"%\(',
         'description': 'Missing space around "%"',
         'good_lines': ['"%s" % ("foo")', '"%s" % (foo)'],
         'bad_lines': ['"%s"%("foo")', '"%s"%(foo)']},
        {'pattern': "^[^']*'[^']*'%\(",
         'description': 'Missing space around "%"',
         'good_lines': ["'%s' % ('foo')", "'%s' % (foo)"],
         'bad_lines': ["'%s'%('foo')", "'%s'%(foo)"]},
        {'pattern': 'self: Any',
         'description': 'you can omit Any annotation for self',
         'good_lines': ['def foo (self):'],
         'bad_lines': ['def foo(self: Any):']},
        # This rule is constructed with + to avoid triggering on itself
        {'pattern': " =" + '[^ =>~"]',
         'description': 'Missing whitespace after "="',
         'good_lines': ['a = b', '5 == 6'],
         'bad_lines': ['a =b', 'asdf =42']},
        {'pattern': '":\w[^"]*$',
         'description': 'Missing whitespace after ":"',
         'good_lines': ['"foo": bar', '"some:string:with:colons"'],
         'bad_lines': ['"foo":bar', '"foo":1']},
        {'pattern': "':\w[^']*$",
         'description': 'Missing whitespace after ":"',
         'good_lines': ["'foo': bar", "'some:string:with:colons'"],
         'bad_lines': ["'foo':bar", "'foo':1"]},
        {'pattern': "^\s+#\w",
         'strip': '\n',
         'exclude': set(['tools/droplets/create.py']),
         'description': 'Missing whitespace after "#"',
         'good_lines': ['a = b # some operation', '1+2 #  3 is the result'],
         'bad_lines': [' #some operation', '  #not valid!!!']},
        {'pattern': "assertEquals[(]",
         'description': 'Use assertEqual, not assertEquals (which is deprecated).',
         'good_lines': ['assertEqual(1, 2)'],
         'bad_lines': ['assertEquals(1, 2)']},
        {'pattern': "== None",
         'description': 'Use `is None` to check whether something is None',
         'good_lines': ['if foo is None'],
         'bad_lines': ['foo == None']},
        {'pattern': "type:[(]",
         'description': 'Missing whitespace after ":" in type annotation',
         'good_lines': ['# type: (Any, Any)', 'colon:separated:string:containing:type:as:keyword'],
         'bad_lines': ['# type:(Any, Any)']},
        {'pattern': "type: ignore$",
         'exclude': set(['tools/tests',
                         'zerver/lib/test_runner.py',
                         'zerver/tests']),
         'description': '"type: ignore" should always end with "# type: ignore # explanation for why"',
         'good_lines': ['foo = bar  # type: ignore # explanation'],
         'bad_lines': ['foo = bar  # type: ignore']},
        {'pattern': "# type [(]",
         'description': 'Missing : after type in type annotation',
         'good_lines': ['foo = 42  # type: int', '# type: (str, int) -> None'],
         'bad_lines': ['# type (str, int) -> None']},
        {'pattern': "#type",
         'description': 'Missing whitespace after "#" in type annotation',
         'good_lines': ['foo = 42  # type: int'],
         'bad_lines': ['foo = 42  #type: int']},
        {'pattern': r'\b(if|else|while)[(]',
         'description': 'Put a space between statements like if, else, etc. and (.',
         'good_lines': ['if (1 == 2):', 'while (foo == bar):'],
         'bad_lines': ['if(1 == 2):', 'while(foo == bar):']},
        {'pattern': ", [)]",
         'description': 'Unnecessary whitespace between "," and ")"',
         'good_lines': ['foo = (1, 2, 3,)', 'foo(bar, 42)'],
         'bad_lines': ['foo = (1, 2, 3, )']},
        {'pattern': "%  [(]",
         'description': 'Unnecessary whitespace between "%" and "("',
         'good_lines': ['"foo %s bar" % ("baz",)'],
         'bad_lines': ['"foo %s bar" %  ("baz",)']},
        # This next check could have false positives, but it seems pretty
        # rare; if we find any, they can be added to the exclude list for
        # this rule.
        {'pattern': ' % [a-zA-Z0-9_."\']*\)?$',
         'exclude_line': set([
             ('tools/tests/test_template_parser.py', '{% foo'),
         ]),
         'description': 'Used % comprehension without a tuple',
         'good_lines': ['"foo %s bar" % ("baz",)'],
         'bad_lines': ['"foo %s bar" % "baz"']},
        {'pattern': '.*%s.* % \([a-zA-Z0-9_."\']*\)$',
         'description': 'Used % comprehension without a tuple',
         'good_lines': ['"foo %s bar" % ("baz",)"'],
         'bad_lines': ['"foo %s bar" % ("baz")']},
        {'pattern': 'sudo',
         'include_only': set(['scripts/']),
         'exclude': set(['scripts/lib/setup_venv.py']),
         'exclude_line': set([
             ('scripts/lib/zulip_tools.py', '# We need sudo here, since the path will be under /srv/ in the'),
             ('scripts/lib/zulip_tools.py', 'subprocess.check_call(["sudo", "/bin/bash", "-c",'),
             ('scripts/lib/zulip_tools.py', 'subprocess.check_call(["sudo", "rm", "-rf", directory])'),
         ]),
         'description': 'Most scripts are intended to run on systems without sudo.',
         'good_lines': ['subprocess.check_call(["ls"])'],
         'bad_lines': ['subprocess.check_call(["sudo", "ls"])']},
        {'pattern': 'django.utils.translation',
         'include_only': set(['test/']),
         'description': 'Test strings should not be tagged for translation',
         'good_lines': [''],
         'bad_lines': ['django.utils.translation']},
        {'pattern': 'userid',
         'description': 'We prefer user_id over userid.',
         'good_lines': ['id = alice.user_id'],
         'bad_lines': ['id = alice.userid']},
        {'pattern': 'json_success\({}\)',
         'description': 'Use json_success() to return nothing',
         'good_lines': ['return json_success()'],
         'bad_lines': ['return json_success({})']},
        {'pattern': '\Wjson_error\(_\(?\w+\)',
         'exclude': set(['zerver/tests']),
         'description': 'Argument to json_error should be a literal string enclosed by _()',
         'good_lines': ['return json_error(_("string"))'],
         'bad_lines': ['return json_error(_variable)', 'return json_error(_(variable))']},
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
        {'pattern': '[^r]Message.objects.get',
         'exclude': set(["zerver/tests",
                         "zerver/lib/onboarding.py",
                         "zilencer/management/commands/add_mock_conversation.py",
                         "zerver/worker/queue_processors.py"]),
         'description': 'Please use access_message() to fetch Message objects',
         },
        {'pattern': 'Stream.objects.get',
         'include_only': set(["zerver/views/"]),
         'description': 'Please use access_stream_by_*() to fetch Stream objects',
         },
        {'pattern': 'get_stream[(]',
         'include_only': set(["zerver/views/", "zerver/lib/actions.py"]),
         'exclude_line': set([
             # This one in check_message is kinda terrible, since it's
             # how most instances are written, but better to exclude something than nothing
             ('zerver/lib/actions.py', 'stream = get_stream(stream_name, realm)'),
             ('zerver/lib/actions.py', 'get_stream(admin_realm_signup_notifications_stream, admin_realm)'),
             # Here we need get_stream to access streams you've since unsubscribed from.
             ('zerver/views/messages.py', 'stream = get_stream(operand, self.user_profile.realm)'),
             # Use stream_id to exclude mutes.
             ('zerver/views/messages.py', 'stream_id = get_stream(stream_name, user_profile.realm).id'),
         ]),
         'description': 'Please use access_stream_by_*() to fetch Stream objects',
         },
        {'pattern': 'Stream.objects.filter',
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
         'description': "Don't import models or other code in migrations; see docs/subsystems/schema-migrations.md",
         },
        {'pattern': 'datetime[.](now|utcnow)',
         'include_only': set(["zerver/", "analytics/"]),
         'description': "Don't use datetime in backend code.\n"
         "See https://zulip.readthedocs.io/en/latest/contributing/code-style.html#naive-datetime-objects",
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
        {'pattern': '(logging|logger)\.warn\W',
         'description': "Logger.warn is a deprecated alias for Logger.warning; Use 'warning' instead of 'warn'.",
         'good_lines': ["logging.warning('I am a warning.')", "logger.warning('warning')"],
         'bad_lines': ["logging.warn('I am a warning.')", "logger.warn('warning')"]},
        {'pattern': '\.pk',
         'exclude_pattern': '[.]_meta[.]pk',
         'description': "Use `id` instead of `pk`.",
         'good_lines': ['if my_django_model.id == 42', 'self.user_profile._meta.pk'],
         'bad_lines': ['if my_django_model.pk == 42']},
        {'pattern': '^[ ]*# type: \(',
         'exclude': set([
             # These directories, especially scripts/ and puppet/,
             # have tools that need to run before a Zulip environment
             # is provisioned; in some of those, the `typing` module
             # might not be available yet, so care is required.
             'scripts/',
             'tools/',
             'puppet/',
             # Zerver files that we should just clean.
             'zerver/tests',
             'zerver/lib/api_test_helpers.py',
             'zerver/lib/request.py',
             'zerver/views/streams.py',
             # thumbor is (currently) python2 only
             'zthumbor/',
         ]),
         'description': 'Comment-style function type annotation. Use Python3 style annotations instead.',
         },
        {'pattern': ' = models[.].*null=True.*\)  # type: (?!Optional)',
         'include_only': {"zerver/models.py"},
         'description': 'Model variable with null=true not annotated as Optional.',
         'good_lines': ['desc = models.TextField(null=True)  # type: Optional[Text]',
                        'stream = models.ForeignKey(Stream, null=True, on_delete=CASCADE)  # type: Optional[Stream]',
                        'desc = models.TextField()  # type: Text',
                        'stream = models.ForeignKey(Stream, on_delete=CASCADE)  # type: Stream'],
         'bad_lines': ['desc = models.CharField(null=True)  # type: Text',
                       'stream = models.ForeignKey(Stream, null=True, on_delete=CASCADE)  # type: Stream'],
         },
        {'pattern': ' = models[.](?!NullBoolean).*\)  # type: Optional',  # Optional tag, except NullBoolean(Field)
         'exclude_pattern': 'null=True',
         'include_only': {"zerver/models.py"},
         'description': 'Model variable annotated with Optional but variable does not have null=true.',
         'good_lines': ['desc = models.TextField(null=True)  # type: Optional[Text]',
                        'stream = models.ForeignKey(Stream, null=True, on_delete=CASCADE)  # type: Optional[Stream]',
                        'desc = models.TextField()  # type: Text',
                        'stream = models.ForeignKey(Stream, on_delete=CASCADE)  # type: Stream'],
         'bad_lines': ['desc = models.TextField()  # type: Optional[Text]',
                       'stream = models.ForeignKey(Stream, on_delete=CASCADE)  # type: Optional[Stream]'],
         },
    ]) + whitespace_rules + comma_whitespace_rule
    bash_rules = cast(RuleList, [
        {'pattern': '#!.*sh [-xe]',
         'description': 'Fix shebang line with proper call to /usr/bin/env for Bash path, change -x|-e switches'
                        ' to set -x|set -e'},
        {'pattern': 'sudo',
         'description': 'Most scripts are intended to work on systems without sudo',
         'include_only': set(['scripts/']),
         'exclude': set([
             'scripts/lib/install',
             'scripts/lib/create-zulip-admin',
             'scripts/setup/terminate-psql-sessions',
             'scripts/setup/configure-rabbitmq'
         ]), },
    ]) + whitespace_rules[0:1]
    css_rules = cast(RuleList, [
        {'pattern': 'calc\([^+]+\+[^+]+\)',
         'description': "Avoid using calc with '+' operator. See #8403 : in CSS.",
         'good_lines': ["width: calc(20% - -14px);"],
         'bad_lines': ["width: calc(20% + 14px);"]},
        {'pattern': '^[^:]*:\S[^:]*;$',
         'description': "Missing whitespace after : in CSS",
         'good_lines': ["background-color: white;", "text-size: 16px;"],
         'bad_lines': ["background-color:white;", "text-size:16px;"]},
        {'pattern': '[a-z]{',
         'description': "Missing whitespace before '{' in CSS.",
         'good_lines': ["input {", "body {"],
         'bad_lines': ["input{", "body{"]},
        {'pattern': 'https://',
         'description': "Zulip CSS should have no dependencies on external resources",
         'good_lines': ['background: url(/static/images/landing-page/pycon.jpg);'],
         'bad_lines': ['background: url(https://example.com/image.png);']},
        {'pattern': '^[ ][ ][a-zA-Z0-9]',
         'description': "Incorrect 2-space indentation in CSS",
         'exclude': set(['static/third/thirdparty-fonts.css']),
         'strip': '\n',
         'good_lines': ["    color: white;", "color: white;"],
         'bad_lines': ["  color: white;"]},
        {'pattern': '{\w',
         'description': "Missing whitespace after '{' in CSS (should be newline).",
         'good_lines': ["{\n"],
         'bad_lines': ["{color: LightGoldenRodYellow;"]},
        {'pattern': ' thin[ ;]',
         'description': "thin CSS attribute is under-specified, please use 1px.",
         'good_lines': ["border-width: 1px;"],
         'bad_lines': ["border-width: thin;", "border-width: thin solid black;"]},
        {'pattern': ' medium[ ;]',
         'description': "medium CSS attribute is under-specified, please use pixels.",
         'good_lines': ["border-width: 3px;"],
         'bad_lines': ["border-width: medium;", "border: medium solid black;"]},
        {'pattern': ' thick[ ;]',
         'description': "thick CSS attribute is under-specified, please use pixels.",
         'good_lines': ["border-width: 5px;"],
         'bad_lines': ["border-width: thick;", "border: thick solid black;"]},
    ]) + whitespace_rules + comma_whitespace_rule
    prose_style_rules = cast(RuleList, [
        {'pattern': '[^\/\#\-\"]([jJ]avascript)',  # exclude usage in hrefs/divs
         'description': "javascript should be spelled JavaScript"},
        {'pattern': '[^\/\-\.\"\'\_\=\>]([gG]ithub)[^\.\-\_\"\<]',  # exclude usage in hrefs/divs
         'description': "github should be spelled GitHub"},
        {'pattern': '[oO]rganisation',  # exclude usage in hrefs/divs
         'description': "Organization is spelled with a z",
         'exclude_line': [('docs/translating/french.md', '* organization - **organisation**')]},
        {'pattern': '!!! warning',
         'description': "!!! warning is invalid; it's spelled '!!! warn'"},
        {'pattern': 'Terms of service',
         'description': "The S in Terms of Service is capitalized"},
    ]) + comma_whitespace_rule
    html_rules = whitespace_rules + prose_style_rules + [
        {'pattern': 'placeholder="[^{#](?:(?!\.com).)+$',
         'description': "`placeholder` value should be translatable.",
         'exclude_line': [('templates/zerver/register.html', 'placeholder="acme"'),
                          ('templates/zerver/register.html', 'placeholder="Acme or Aκμή"')],
         'good_lines': ['<input class="stream-list-filter" type="text" placeholder="{{ _(\'Search streams\') }}" />'],
         'bad_lines': ['<input placeholder="foo">']},
        {'pattern': "placeholder='[^{]",
         'description': "`placeholder` value should be translatable.",
         'good_lines': ['<input class="stream-list-filter" type="text" placeholder="{{ _(\'Search streams\') }}" />'],
         'bad_lines': ["<input placeholder='foo'>"]},
        {'pattern': "aria-label='[^{]",
         'description': "`aria-label` value should be translatable.",
         'good_lines': ['<button type="button" class="close close-alert-word-status" aria-label="{{t \'Close\' }}">'],
         'bad_lines': ["<button aria-label='foo'></button>"]},
        {'pattern': 'aria-label="[^{]',
         'description': "`aria-label` value should be translatable.",
         'good_lines': ['<button type="button" class="close close-alert-word-status" aria-label="{{t \'Close\' }}">'],
         'bad_lines': ['<button aria-label="foo"></button>']},
        {'pattern': 'script src="http',
         'description': "Don't directly load dependencies from CDNs.  See docs/subsystems/front-end-build-process.md",
         'exclude': set(["templates/zilencer/billing.html"]),
         'good_lines': ["{{ render_bundle('landing-page') }}"],
         'bad_lines': ['<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.2.1/jquery.min.js"></script>']},
        {'pattern': "title='[^{]",
         'description': "`title` value should be translatable.",
         'good_lines': ['<link rel="author" title="{{ _(\'About these documents\') }}" />'],
         'bad_lines': ["<p title='foo'></p>"]},
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
         'good_lines': ['<img src="{{source_url}}" alt="{{ _(name) }}" />', '<img alg="" />'],
         'bad_lines': ['<img alt="Foo Image" />']},
        {'pattern': '\Walt=["\']{{ ?["\']',
         'description': "alt argument should be enclosed by _().",
         'good_lines': ['<img src="{{source_url}}" alt="{{ _(name) }}" />'],
         'bad_lines': ['<img alt="{{ " />']},
        {'pattern': r'\bon\w+ ?=',
         'description': "Don't use inline event handlers (onclick=, etc. attributes) in HTML. Instead,"
                        "attach a jQuery event handler ($('#foo').on('click', function () {...})) when "
                        "the DOM is ready (inside a $(function () {...}) block).",
         'exclude': set(['templates/zerver/dev_login.html']),
         'good_lines': ["($('#foo').on('click', function () {}"],
         'bad_lines': ["<button id='foo' onclick='myFunction()'>Foo</button>", "<input onchange='myFunction()'>"]},
        {'pattern': 'style ?=',
         'description': "Avoid using the `style=` attribute; we prefer styling in CSS files",
         'exclude_pattern': r'.*style ?=["' + "'" + '](display: ?none|background: {{|color: {{|background-color: {{).*',
         'exclude': set([
             # KaTeX output uses style attribute
             'templates/zerver/markdown_help.html',
             # 5xx page doesn't have external CSS
             'static/html/5xx.html',
             # Group PMs color is dynamically calculated
             'static/templates/group_pms.handlebars',

             # exclude_pattern above handles color, but have other issues:
             'static/templates/draft.handlebars',
             'static/templates/subscription.handlebars',
             'static/templates/single_message.handlebars',

             # Old-style email templates need to use inline style
             # attributes; it should be possible to clean these up
             # when we convert these templates to use premailer.
             'templates/zerver/emails/digest.html',
             'templates/zerver/emails/missed_message.html',
             'templates/zerver/emails/email_base_messages.html',

             # Email log templates; should clean up.
             'templates/zerver/email.html',
             'templates/zerver/email_log.html',

             # Probably just needs to be changed to display: none so the exclude works
             'templates/zerver/navbar.html',

             # Needs the width cleaned up; display: none is fine
             'static/templates/settings/account-settings.handlebars',

             # Inline styling for an svg; could be moved to CSS files?
             'templates/zerver/landing_nav.html',
             'templates/zerver/home.html',
             'templates/zerver/features.html',
             'templates/zerver/portico-header.html',

             # Miscellaneous violations to be cleaned up
             'static/templates/user_info_popover_title.handlebars',
             'static/templates/subscription_invites_warning_modal.handlebars',
             'templates/zerver/reset_confirm.html',
             'templates/zerver/config_error.html',
             'templates/zerver/dev_env_email_access_details.html',
             'templates/zerver/confirm_continue_registration.html',
             'templates/zerver/register.html',
             'templates/zerver/accounts_send_confirm.html',
             'templates/zerver/integrations/index.html',
             'templates/zerver/help/main.html',
             'templates/zerver/api/main.html',
             'templates/analytics/realm_summary_table.html',
             'templates/corporate/zephyr.html',
             'templates/corporate/zephyr-mirror.html',
         ]),
         'good_lines': ['#my-style {color: blue;}', 'style="display: none"', "style='display: none"],
         'bad_lines': ['<p style="color: blue;">Foo</p>', 'style = "color: blue;"']},
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
        # Here, we don't use `whitespace_rules`, because the tab-based
        # whitespace rule flags a lot of third-party JSON fixtures
        # under zerver/webhooks that we want preserved verbatim.  So
        # we just include the trailing whitespace rule and a modified
        # version of the tab-based whitespace rule (we can't just use
        # exclude in whitespace_rules, since we only want to ignore
        # JSON files with tab-based whitespace, not webhook code).
        trailing_whitespace_rule,
        {'pattern': '\t',
         'strip': '\n',
         'exclude': set(['zerver/webhooks/']),
         'description': 'Fix tab-based whitespace'},
        {'pattern': ':[\"\[\{]',
         'exclude': set(['zerver/webhooks/', 'zerver/fixtures/']),
         'description': 'Require space after : in JSON'},
    ]  # type: RuleList
    markdown_rules = markdown_whitespace_rules + prose_style_rules + [
        {'pattern': '\[(?P<url>[^\]]+)\]\((?P=url)\)',
         'description': 'Linkified markdown URLs should use cleaner <http://example.com> syntax.'},
        {'pattern': 'https://zulip.readthedocs.io/en/latest/[a-zA-Z0-9]',
         'exclude': ['docs/overview/contributing.md', 'docs/overview/readme.md'],
         'include_only': set(['docs/']),
         'description': "Use relatve links (../foo/bar.html) to other documents in docs/",
         },
        {'pattern': '\][(][^#h]',
         'include_only': set(['README.md', 'CONTRIBUTING.md']),
         'description': "Use absolute links from docs served by GitHub",
         },
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
            if custom_check_file(fn, 'py', python_rules, color, max_length=110):
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
            # Has some example Vagrant output that's very long
            "docs/development/setup-vagrant.md",
            # Have wide output in code blocks
            "docs/subsystems/logging.md",
            "docs/subsystems/migration-renumbering.md",
            # Have curl commands with JSON that would be messy to wrap
            "zerver/webhooks/helloworld/doc.md",
            "zerver/webhooks/trello/doc.md",
            # Has a very long configuration line
            "templates/zerver/integrations/perforce.md",
            # Has some example code that could perhaps be wrapped
            "templates/zerver/api/webhook-walkthrough.md",
            # This macro has a long indented URL
            "templates/zerver/help/include/git-webhook-url-with-branches-indented.md",
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
        for fn in by_lang['rst']:
            if custom_check_file(fn, 'rst', txt_rules, color):
                failed = True

        color = next(colors)
        for fn in by_lang['yaml']:
            if custom_check_file(fn, 'yaml', txt_rules, color):
                failed = True

        return failed

    return (check_custom_checks_py, check_custom_checks_nonpy)
