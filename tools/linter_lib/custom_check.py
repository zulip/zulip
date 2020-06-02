from typing import List

from zulint.custom_rules import Rule, RuleList

# Rule help:
# By default, a rule applies to all files within the extension for which it is specified (e.g. all .py files)
# There are three operators we can use to manually include or exclude files from linting for a rule:
# 'exclude': 'set([<path>, ...])' - if <path> is a filename, excludes that file.
#                                   if <path> is a directory, excludes all files directly below the directory <path>.
# 'exclude_line': 'set([(<path>, <line>), ...])' - excludes all lines matching <line> in the file <path> from linting.
# 'include_only': 'set([<path>, ...])' - includes only those files where <path> is a substring of the filepath.

FILES_WITH_LEGACY_SUBJECT = {
    # This basically requires a big DB migration:
    'zerver/lib/topic.py',

    # This is for backward compatibility.
    'zerver/tests/test_legacy_subject.py',

    # Other migration-related changes require extreme care.
    'zerver/lib/fix_unreads.py',
    'zerver/tests/test_migrations.py',

    # These use subject in the email sense, and will
    # probably always be exempt:
    'zerver/lib/email_mirror.py',
    'zerver/lib/send_email.py',
    'zerver/tests/test_new_users.py',
    'zerver/tests/test_email_mirror.py',
    'zerver/tests/test_email_notifications.py',

    # These are tied more to our API than our DB model.
    'zerver/openapi/python_examples.py',
    'zerver/tests/test_openapi.py',

    # This has lots of query data embedded, so it's hard
    # to fix everything until we migrate the DB to "topic".
    'zerver/tests/test_narrow.py',
}

shebang_rules: List["Rule"] = [
    {'pattern': '^#!',
     'description': "zerver library code shouldn't have a shebang line.",
     'include_only': {'zerver/'}},
    # /bin/sh and /usr/bin/env are the only two binaries
    # that NixOS provides at a fixed path (outside a
    # buildFHSUserEnv sandbox).
    {'pattern': '^#!(?! *(?:/usr/bin/env|/bin/sh)(?: |$))',
     'description': "Use `#!/usr/bin/env foo` instead of `#!/path/foo`"
     " for interpreters other than sh."},
    {'pattern': '^#!/usr/bin/env python$',
     'description': "Use `#!/usr/bin/env python3` instead of `#!/usr/bin/env python`."},
]

trailing_whitespace_rule: "Rule" = {
    'pattern': r'\s+$',
    'strip': '\n',
    'description': 'Fix trailing whitespace',
}
whitespace_rules: List["Rule"] = [
    # This linter should be first since bash_rules depends on it.
    trailing_whitespace_rule,
    {'pattern': 'http://zulip.readthedocs.io',
     'description': 'Use HTTPS when linking to ReadTheDocs',
     },
    {'pattern': '\t',
     'strip': '\n',
     'exclude': {'tools/ci/success-http-headers-bionic.txt', 'tools/ci/success-http-headers-focal.txt'},
     'description': 'Fix tab-based whitespace'},
]
comma_whitespace_rule: List["Rule"] = [
    {'pattern': ', {2,}[^#/ ]',
     'exclude': {'zerver/tests', 'frontend_tests/node_tests', 'corporate/tests'},
     'description': "Remove multiple whitespaces after ','",
     'good_lines': ['foo(1, 2, 3)', 'foo = bar  # some inline comment'],
     'bad_lines': ['foo(1,  2, 3)', 'foo(1,    2, 3)']},
]
markdown_whitespace_rules = list([rule for rule in whitespace_rules if rule['pattern'] != r'\s+$']) + [
    # Two spaces trailing a line with other content is okay--it's a markdown line break.
    # This rule finds one space trailing a non-space, three or more trailing spaces, and
    # spaces on an empty line.
    {'pattern': r'((?<!\s)\s$)|(\s\s\s+$)|(^\s+$)',
     'strip': '\n',
     'description': 'Fix trailing whitespace'},
    {'pattern': '^#+[A-Za-z0-9]',
     'strip': '\n',
     'description': 'Missing space after # in heading',
     'good_lines': ['### some heading', '# another heading'],
     'bad_lines': ['###some heading', '#another heading']},
]


js_rules = RuleList(
    langs=['js', 'ts'],
    rules=[
        {'pattern': 'subject|SUBJECT',
         'exclude': {'static/js/util.ts',
                     'frontend_tests/', 'static/js/zulip.d.ts'},
         'exclude_pattern': 'emails',
         'description': 'avoid subject in JS code',
         'good_lines': ['topic_name'],
         'bad_lines': ['subject="foo"', ' MAX_SUBJECT_LEN']},
        {'pattern': r'[^_]function\(',
         'description': 'The keyword "function" should be followed by a space'},
        {'pattern': 'msgid|MSGID',
         'description': 'Avoid using "msgid" as a variable name; use "message_id" instead.'},
        {'pattern': r'.*blueslip.warning\(.*',
         'description': 'The module blueslip has no function warning, try using blueslip.warn'},
        {'pattern': r'i18n\.t\([^)]+[^,\{\)]$',
         'description': 'i18n string should not be a multiline string'},
        {'pattern': r'''i18n\.t\(['"].+?['"]\s*\+''',
         'description': 'Do not concatenate arguments within i18n.t()'},
        {'pattern': r'''i18n\.t\([a-zA-Z]''',
         'exclude': {'static/js/templates.js'},
         'description': 'Do not pass a variable into i18n.t; it will not be exported to Transifex for translation.'},
        {'pattern': r'i18n\.t\(.+\).*\+',
         'description': 'Do not concatenate i18n strings'},
        {'pattern': r'\+.*i18n\.t\(.+\)',
         'description': 'Do not concatenate i18n strings'},
        {'pattern': '[.]html[(]',
         'exclude_pattern': r'''\.html\(("|'|render_|html|message\.content|util\.clean_user_content_links|i18n\.t|rendered_|$|\)|error_text|widget_elem|\$error|\$\("<p>"\))''',
         'exclude': {'static/js/portico', 'static/js/lightbox.js', 'static/js/ui_report.js',
                     'static/js/confirm_dialog.js',
                     'frontend_tests/'},
         'description': 'Setting HTML content with jQuery .html() can lead to XSS security bugs.  Consider .text() or using rendered_foo as a variable name if content comes from handlebars and thus is already sanitized.'},
        {'pattern': '["\']json/',
         'description': 'Relative URL for JSON route not supported by i18n'},
        # This rule is constructed with + to avoid triggering on itself
        {'pattern': '^[ ]*//[A-Za-z0-9]',
         'description': 'Missing space after // in comment'},
        {'pattern': r'''[.]text\(["'][a-zA-Z]''',
         'description': 'Strings passed to $().text should be wrapped in i18n.t() for internationalization',
         'exclude': {'frontend_tests/node_tests/'}},
        {'pattern': r'''compose_error\(["']''',
         'description': 'Argument to compose_error should be a literal string enclosed '
                        'by i18n.t()'},
        {'pattern': r'ui.report_success\(',
         'description': 'Deprecated function, use ui_report.success.'},
        {'pattern': r'''report.success\(["']''',
         'description': 'Argument to report_success should be a literal string enclosed '
                        'by i18n.t()'},
        {'pattern': r'ui.report_error\(',
         'description': 'Deprecated function, use ui_report.error.'},
        {'pattern': r'''report.error\(["'][^'"]''',
         'description': 'Argument to ui_report.error should be a literal string enclosed '
                        'by i18n.t()',
         'good_lines': ['ui_report.error("")', 'ui_report.error(_("text"))'],
         'bad_lines': ['ui_report.error("test")']},
        {'pattern': r'\$\(document\)\.ready\(',
         'description': "`Use $(f) rather than `$(document).ready(f)`",
         'good_lines': ['$(function () {foo();}'],
         'bad_lines': ['$(document).ready(function () {foo();}']},
        {'pattern': '[$][.](get|post|patch|delete|ajax)[(]',
         'description': "Use channel module for AJAX calls",
         'exclude': {
             # Internal modules can do direct network calls
             'static/js/blueslip.js',
             'static/js/channel.js',
             # External modules that don't include channel.js
             'static/js/stats/',
             'static/js/portico/',
             'static/js/billing/',
         },
         'good_lines': ['channel.get(...)'],
         'bad_lines': ['$.get()', '$.post()', '$.ajax()']},
        {'pattern': 'style ?=',
         'description': "Avoid using the `style=` attribute; we prefer styling in CSS files",
         'exclude': {
             'frontend_tests/node_tests/copy_and_paste.js',
             'frontend_tests/node_tests/upload.js',
             'static/js/upload.js',
             'static/js/stream_color.js',
         },
         'good_lines': ['#my-style {color: blue;}'],
         'bad_lines': ['<p style="color: blue;">Foo</p>', 'style = "color: blue;"']},
        *whitespace_rules,
        *comma_whitespace_rule,
    ],
)

python_rules = RuleList(
    langs=['py'],
    rules=[
        {'pattern': 'subject|SUBJECT',
         'exclude_pattern': 'subject to the|email|outbox',
         'description': 'avoid subject as a var',
         'good_lines': ['topic_name'],
         'bad_lines': ['subject="foo"', ' MAX_SUBJECT_LEN'],
         'exclude': FILES_WITH_LEGACY_SUBJECT,
         'include_only': {
             'zerver/data_import/',
             'zerver/lib/',
             'zerver/tests/',
             'zerver/views/'}},
        {'pattern': 'msgid|MSGID',
         'exclude': {'tools/check-capitalization',
                     'tools/i18n/tagmessages'},
         'description': 'Avoid using "msgid" as a variable name; use "message_id" instead.'},
        {'pattern': '^(?!#)@login_required',
         'description': '@login_required is unsupported; use @zulip_login_required',
         'good_lines': ['@zulip_login_required', '# foo @login_required'],
         'bad_lines': ['@login_required', ' @login_required']},
        {'pattern': '^user_profile[.]save[(][)]',
         'description': 'Always pass update_fields when saving user_profile objects',
         'exclude_line': {
             ('zerver/lib/actions.py', "user_profile.save()  # Can't use update_fields because of how the foreign key works."),
         },
         'exclude': {'zerver/tests', 'zerver/lib/create_user.py'},
         'good_lines': ['user_profile.save(update_fields=["pointer"])'],
         'bad_lines': ['user_profile.save()']},
        {'pattern': 'self: Any',
         'description': 'you can omit Any annotation for self',
         'good_lines': ['def foo (self):'],
         'bad_lines': ['def foo(self: Any):']},
        {'pattern': r"^\s+#\w",
         'strip': '\n',
         'exclude': {'tools/droplets/create.py'},
         'description': 'Missing whitespace after "#"',
         'good_lines': ['a = b # some operation', '1+2 #  3 is the result'],
         'bad_lines': [' #some operation', '  #not valid!!!']},
        {'pattern': "assertEquals[(]",
         'description': 'Use assertEqual, not assertEquals (which is deprecated).',
         'good_lines': ['assertEqual(1, 2)'],
         'bad_lines': ['assertEquals(1, 2)']},
        {'pattern': r"#\s*type:\s*ignore(?!\[[^][]+\] +# +\S)",
         'exclude': {'tools/tests',
                     'zerver/lib/test_runner.py',
                     'zerver/tests'},
         'description': '"type: ignore" should always end with "# type: ignore[code] # explanation for why"',
         'good_lines': ['foo = bar  # type: ignore[code] # explanation'],
         'bad_lines': ['foo = bar  # type: ignore',
                       'foo = bar  # type: ignore[code]',
                       'foo = bar  # type: ignore # explanation']},
        {'pattern': r'\b(if|else|while)[(]',
         'description': 'Put a space between statements like if, else, etc. and (.',
         'good_lines': ['if (1 == 2):', 'while (foo == bar):'],
         'bad_lines': ['if(1 == 2):', 'while(foo == bar):']},
        {'pattern': ", [)]",
         'description': 'Unnecessary whitespace between "," and ")"',
         'good_lines': ['foo = (1, 2, 3,)', 'foo(bar, 42)'],
         'bad_lines': ['foo = (1, 2, 3, )']},
        {'pattern': 'sudo',
         'include_only': {'scripts/'},
         'exclude': {'scripts/lib/setup_venv.py'},
         'exclude_line': {
             ('scripts/lib/zulip_tools.py', 'sudo_args = kwargs.pop(\'sudo_args\', [])'),
             ('scripts/lib/zulip_tools.py', 'args = [\'sudo\'] + sudo_args + [\'--\'] + args'),
         },
         'description': 'Most scripts are intended to run on systems without sudo.',
         'good_lines': ['subprocess.check_call(["ls"])'],
         'bad_lines': ['subprocess.check_call(["sudo", "ls"])']},
        {'pattern': 'django.utils.translation',
         'include_only': {'test/', 'zerver/views/development/'},
         'description': 'Test strings should not be tagged for translation',
         'good_lines': [''],
         'bad_lines': ['django.utils.translation']},
        {'pattern': 'userid',
         'description': 'We prefer user_id over userid.',
         'good_lines': ['id = alice.user_id'],
         'bad_lines': ['id = alice.userid']},
        {'pattern': r'json_success\({}\)',
         'description': 'Use json_success() to return nothing',
         'good_lines': ['return json_success()'],
         'bad_lines': ['return json_success({})']},
        {'pattern': r'\Wjson_error\(_\(?\w+\)',
         'exclude': {'zerver/tests', 'zerver/views/development/'},
         'description': 'Argument to json_error should be a literal string enclosed by _()',
         'good_lines': ['return json_error(_("string"))'],
         'bad_lines': ['return json_error(_variable)', 'return json_error(_(variable))']},
        {'pattern': r'''\Wjson_error\(['"].+[),]$''',
         'exclude': {'zerver/tests'},
         'description': 'Argument to json_error should a literal string enclosed by _()'},
        # To avoid JsonableError(_variable) and JsonableError(_(variable))
        {'pattern': r'\WJsonableError\(_\(?\w.+\)',
         'exclude': {'zerver/tests', 'zerver/views/development/'},
         'description': 'Argument to JsonableError should be a literal string enclosed by _()'},
        {'pattern': r'''\WJsonableError\(["'].+\)''',
         'exclude': {'zerver/tests', 'zerver/views/development/'},
         'description': 'Argument to JsonableError should be a literal string enclosed by _()'},
        {'pattern': r'''([a-zA-Z0-9_]+)=REQ\(['"]\1['"]''',
         'description': 'REQ\'s first argument already defaults to parameter name'},
        {'pattern': r'self\.client\.(get|post|patch|put|delete)',
         'description': \
         '''Do not call self.client directly for put/patch/post/get.
    See WRAPPER_COMMENT in test_helpers.py for details.
    '''},
        # Directly fetching Message objects in e.g. views code is often a security bug.
        {'pattern': '[^r]Message.objects.get',
         'exclude': {"zerver/tests",
                     "zerver/lib/onboarding.py",
                     "zilencer/management/commands/add_mock_conversation.py",
                     "zerver/worker/queue_processors.py",
                     "zerver/management/commands/export.py",
                     "zerver/lib/export.py"},
         'description': 'Please use access_message() to fetch Message objects',
         },
        {'pattern': 'Stream.objects.get',
         'include_only': {"zerver/views/"},
         'description': 'Please use access_stream_by_*() to fetch Stream objects',
         },
        {'pattern': 'get_stream[(]',
         'include_only': {"zerver/views/", "zerver/lib/actions.py"},
         'exclude_line': {
             # This one in check_message is kinda terrible, since it's
             # how most instances are written, but better to exclude something than nothing
             ('zerver/lib/actions.py', 'stream = get_stream(stream_name, realm)'),
             ('zerver/lib/actions.py', 'return get_stream("signups", realm)'),
         },
         'description': 'Please use access_stream_by_*() to fetch Stream objects',
         },
        {'pattern': 'datetime[.](now|utcnow)',
         'include_only': {"zerver/", "analytics/"},
         'description': "Don't use datetime in backend code.\n"
         "See https://zulip.readthedocs.io/en/latest/contributing/code-style.html#naive-datetime-objects",
         },
        {'pattern': 'from os.path',
         'description': "Don't use from when importing from the standard library",
         },
        {'pattern': 'import os.path',
         'description': "Use import os instead of import os.path",
         },
        {'pattern': r'(logging|logger)\.warn\W',
         'description': "Logger.warn is a deprecated alias for Logger.warning; Use 'warning' instead of 'warn'.",
         'good_lines': ["logging.warning('I am a warning.')", "logger.warning('warning')"],
         'bad_lines': ["logging.warn('I am a warning.')", "logger.warn('warning')"]},
        {'pattern': r'\.pk',
         'exclude_pattern': '[.]_meta[.]pk',
         'description': "Use `id` instead of `pk`.",
         'good_lines': ['if my_django_model.id == 42', 'self.user_profile._meta.pk'],
         'bad_lines': ['if my_django_model.pk == 42']},
        {'pattern': r'^\s*#\s*type:',
         'exclude': {
             # thumbor is (currently) python2 only
             'zthumbor/',
         },
         'description': 'Comment-style function type annotation. Use Python3 style annotations instead.',
         },
        {'pattern': r"\S\s*#\s*type:(?!\s*ignore)",
         'exclude': {'scripts/lib/hash_reqs.py',
                     'scripts/lib/setup_venv.py',
                     'scripts/lib/zulip_tools.py',
                     'tools/lib/provision.py',
                     'zproject/dev_settings.py',
                     'zproject/prod_settings_template.py',
                     'zthumbor'},
         'description': 'Comment-style variable type annotation. Use Python 3.6 style annotations instead.',
         'good_lines': ['a: List[int] = []'],
         'bad_lines': ['a = []  # type: List[int]']},
        {'pattern': r': *(?!Optional)[^ ].*= models[.].*null=True',
         'include_only': {"zerver/models.py"},
         'description': 'Model variable with null=true not annotated as Optional.',
         'good_lines': ['desc: Optional[Text] = models.TextField(null=True)',
                        'stream: Optional[Stream] = models.ForeignKey(Stream, null=True, on_delete=CASCADE)',
                        'desc: Text = models.TextField()',
                        'stream: Stream = models.ForeignKey(Stream, on_delete=CASCADE)'],
         'bad_lines': ['desc: Text = models.CharField(null=True)',
                       'stream: Stream = models.ForeignKey(Stream, null=True, on_delete=CASCADE)'],
         },
        {'pattern': r': *Optional.*= models[.].*\)',
         'exclude_pattern': 'null=True',
         'include_only': {"zerver/models.py"},
         'description': 'Model variable annotated with Optional but variable does not have null=true.',
         'good_lines': ['desc: Optional[Text] = models.TextField(null=True)',
                        'stream: Optional[Stream] = models.ForeignKey(Stream, null=True, on_delete=CASCADE)',
                        'desc: Text = models.TextField()',
                        'stream: Stream = models.ForeignKey(Stream, on_delete=CASCADE)'],
         'bad_lines': ['desc: Optional[Text] = models.TextField()',
                       'stream: Optional[Stream] = models.ForeignKey(Stream, on_delete=CASCADE)'],
         },
        {'pattern': r'[\s([]Text([^\s\w]|$)',
         'exclude': {
             # We are likely to want to keep these dirs Python 2+3 compatible,
             # since the plan includes extracting them to a separate project eventually.
             'tools/lib',
             # TODO: Update our migrations from Text->str.
             'zerver/migrations/',
             # thumbor is (currently) python2 only
             'zthumbor/',
         },
         'description': "Now that we're a Python 3 only codebase, we don't need to use typing.Text. Please use str instead.",
         },
        {'pattern': 'exit[(]1[)]',
         'include_only': {"/management/commands/"},
         'description': 'Raise CommandError to exit with failure in management commands',
         },
        {'pattern': '.is_realm_admin =',
         'description': 'Use do_change_user_role function rather than setting UserProfile\'s is_realm_admin attribute directly.',
         'exclude': {
             'zerver/migrations/0248_userprofile_role_start.py',
             'zerver/tests/test_users.py',
         },
         },
        {'pattern': '.is_guest =',
         'description': 'Use do_change_user_role function rather than setting UserProfile\'s is_guest attribute directly.',
         'exclude': {
             'zerver/migrations/0248_userprofile_role_start.py',
             'zerver/tests/test_users.py',
         },
         },
        *whitespace_rules,
        *comma_whitespace_rule,
    ],
    max_length=110,
    shebang_rules=shebang_rules,
)

bash_rules = RuleList(
    langs=['bash'],
    rules=[
        {'pattern': '#!.*sh [-xe]',
         'description': 'Fix shebang line with proper call to /usr/bin/env for Bash path, change -x|-e switches'
                        ' to set -x|set -e'},
        {'pattern': 'sudo',
         'description': 'Most scripts are intended to work on systems without sudo',
         'include_only': {'scripts/'},
         'exclude': {
             'scripts/lib/install',
             'scripts/setup/configure-rabbitmq',
         }},
        *whitespace_rules[0:1],
    ],
    shebang_rules=shebang_rules,
)

css_rules = RuleList(
    langs=['css', 'scss'],
    rules=[
        {'pattern': r'^[^:]*:\S[^:]*;$',
         'description': "Missing whitespace after : in CSS",
         'good_lines': ["background-color: white;", "text-size: 16px;"],
         'bad_lines': ["background-color:white;", "text-size:16px;"]},
        {'pattern': '[a-z]{',
         'description': "Missing whitespace before '{' in CSS.",
         'good_lines': ["input {", "body {"],
         'bad_lines': ["input{", "body{"]},
        {'pattern': r'^(?:(?!/\*).)*https?://',
         'description': "Zulip CSS should have no dependencies on external resources",
         'good_lines': ['background: url(/static/images/landing-page/pycon.jpg);'],
         'bad_lines': ['background: url(https://example.com/image.png);']},
        {'pattern': '^[ ][ ][a-zA-Z0-9]',
         'description': "Incorrect 2-space indentation in CSS",
         'strip': '\n',
         'good_lines': ["    color: white;", "color: white;"],
         'bad_lines': ["  color: white;"]},
        {'pattern': r'{\w',
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
        {'pattern': r'rgba?\(',
         'description': 'Use of rgb(a) format is banned, Please use hsl(a) instead',
         'good_lines': ['hsl(0, 0%, 0%)', 'hsla(0, 0%, 100%, 0.1)'],
         'bad_lines': ['rgb(0, 0, 0)', 'rgba(255, 255, 255, 0.1)']},
        *whitespace_rules,
        *comma_whitespace_rule,
    ],
)

prose_style_rules: List["Rule"] = [
    {'pattern': r'^[^{].*?[^\/\#\-"]([jJ]avascript)',  # exclude usage in hrefs/divs/custom-markdown
     'exclude': {"docs/documentation/api.md"},
     'description': "javascript should be spelled JavaScript"},
    {'pattern': r'''[^\/\-\."'\_\=\>]([gG]ithub)[^\.\-\_"\<]''',  # exclude usage in hrefs/divs
     'description': "github should be spelled GitHub"},
    {'pattern': '[oO]rganisation',  # exclude usage in hrefs/divs
     'description': "Organization is spelled with a z",
     'exclude_line': {('docs/translating/french.md', '* organization - **organisation**')}},
    {'pattern': '!!! warning',
     'description': "!!! warning is invalid; it's spelled '!!! warn'"},
    {'pattern': 'Terms of service',
     'description': "The S in Terms of Service is capitalized"},
    {'pattern': '[^-_p]botserver(?!rc)|bot server',
     'description': "Use Botserver instead of botserver or bot server."},
    *comma_whitespace_rule,
]
html_rules: List["Rule"] = whitespace_rules + prose_style_rules + [
    {'pattern': 'subject|SUBJECT',
     'exclude': {'templates/zerver/email.html'},
     'exclude_pattern': 'email subject',
     'description': 'avoid subject in templates',
     'good_lines': ['topic_name'],
     'bad_lines': ['subject="foo"', ' MAX_SUBJECT_LEN']},
    {'pattern': r'placeholder="[^{#](?:(?!\.com).)+$',
     'description': "`placeholder` value should be translatable.",
     'exclude_line': {('templates/zerver/register.html', 'placeholder="acme"'),
                      ('templates/zerver/register.html', 'placeholder="Acme or Ακμή"')},
     'exclude': {"templates/analytics/support.html"},
     'good_lines': ['<input class="stream-list-filter" type="text" placeholder="{{ _(\'Search streams\') }}" />'],
     'bad_lines': ['<input placeholder="foo">']},
    {'pattern': '={',
     'description': "Likely missing quoting in HTML attribute",
     'good_lines': ['<a href="{{variable}}">'],
     'bad_lines': ['<a href={{variable}}>']},
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
     'description': "Don't directly load dependencies from CDNs.  See docs/subsystems/html-css.md",
     'exclude': {"templates/corporate/billing.html", "templates/zerver/hello.html",
                 "templates/corporate/upgrade.html"},
     'good_lines': ["{{ render_entrypoint('landing-page') }}"],
     'bad_lines': ['<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.2.1/jquery.min.js"></script>']},
    {'pattern': "title='[^{]",
     'description': "`title` value should be translatable.",
     'good_lines': ['<link rel="author" title="{{ _(\'About these documents\') }}" />'],
     'bad_lines': ["<p title='foo'></p>"]},
    {'pattern': r'title="[^{\:]',
     'exclude_line': {
         ('templates/zerver/app/markdown_help.html',
             '<td class="rendered_markdown"><img alt=":heart:" class="emoji" src="/static/generated/emoji/images/emoji/heart.png" title=":heart:" /></td>'),
     },
     'exclude': {"templates/zerver/emails", "templates/analytics/realm_details.html", "templates/analytics/support.html"},
     'description': "`title` value should be translatable."},
    {'pattern': r'''\Walt=["'][^{"']''',
     'description': "alt argument should be enclosed by _() or it should be an empty string.",
     'exclude': {'static/templates/settings/display_settings.hbs',
                 'templates/zerver/app/keyboard_shortcuts.html',
                 'templates/zerver/app/markdown_help.html'},
     'good_lines': ['<img src="{{source_url}}" alt="{{ _(name) }}" />', '<img alg="" />'],
     'bad_lines': ['<img alt="Foo Image" />']},
    {'pattern': r'''\Walt=["']{{ ?["']''',
     'description': "alt argument should be enclosed by _().",
     'good_lines': ['<img src="{{source_url}}" alt="{{ _(name) }}" />'],
     'bad_lines': ['<img alt="{{ " />']},
    {'pattern': r'\bon\w+ ?=',
     'description': "Don't use inline event handlers (onclick=, etc. attributes) in HTML. Instead,"
     "attach a jQuery event handler ($('#foo').on('click', function () {...})) when "
     "the DOM is ready (inside a $(function () {...}) block).",
     'exclude': {'templates/zerver/dev_login.html', 'templates/corporate/upgrade.html'},
     'good_lines': ["($('#foo').on('click', function () {}"],
     'bad_lines': ["<button id='foo' onclick='myFunction()'>Foo</button>", "<input onchange='myFunction()'>"]},
    {'pattern': 'style ?=',
     'description': "Avoid using the `style=` attribute; we prefer styling in CSS files",
     'exclude_pattern': r'.*style ?=["' + "'" + '](display: ?none|background: {{|color: {{|background-color: {{).*',
     'exclude': {
         # KaTeX output uses style attribute
         'templates/zerver/app/markdown_help.html',
         # 5xx page doesn't have external CSS
         'static/html/5xx.html',

         # exclude_pattern above handles color, but have other issues:
         'static/templates/draft.hbs',
         'static/templates/subscription.hbs',
         'static/templates/single_message.hbs',

         # Old-style email templates need to use inline style
         # attributes; it should be possible to clean these up
         # when we convert these templates to use premailer.
         'templates/zerver/emails/email_base_messages.html',

         # Email log templates; should clean up.
         'templates/zerver/email.html',
         'templates/zerver/email_log.html',

         # Social backend logos are dynamically loaded
         'templates/zerver/accounts_home.html',
         'templates/zerver/login.html',

         # Probably just needs to be changed to display: none so the exclude works
         'templates/zerver/app/navbar.html',

         # Needs the width cleaned up; display: none is fine
         'static/templates/settings/account_settings.hbs',

         # background image property is dynamically generated
         'static/templates/user_profile_modal.hbs',
         'static/templates/pm_list_item.hbs',

         # Inline styling for an svg; could be moved to CSS files?
         'templates/zerver/landing_nav.html',
         'templates/zerver/billing_nav.html',
         'templates/zerver/app/home.html',
         'templates/zerver/features.html',
         'templates/zerver/portico-header.html',
         'templates/corporate/billing.html',
         'templates/corporate/upgrade.html',

         # Miscellaneous violations to be cleaned up
         'static/templates/user_info_popover_title.hbs',
         'static/templates/subscription_invites_warning_modal.hbs',
         'templates/zerver/reset_confirm.html',
         'templates/zerver/config_error.html',
         'templates/zerver/dev_env_email_access_details.html',
         'templates/zerver/confirm_continue_registration.html',
         'templates/zerver/register.html',
         'templates/zerver/accounts_send_confirm.html',
         'templates/zerver/integrations/index.html',
         'templates/zerver/documentation_main.html',
         'templates/analytics/realm_summary_table.html',
         'templates/corporate/zephyr.html',
         'templates/corporate/zephyr-mirror.html',
     },
     'good_lines': ['#my-style {color: blue;}', 'style="display: none"', "style='display: none"],
     'bad_lines': ['<p style="color: blue;">Foo</p>', 'style = "color: blue;"']},
]

handlebars_rules = RuleList(
    langs=['hbs'],
    rules=html_rules + [
        {'pattern': "[<]script",
         'description': "Do not use inline <script> tags here; put JavaScript in static/js instead."},
        {'pattern': '{{ t ("|\')',
         'description': 'There should be no spaces before the "t" in a translation tag.'},
        {'pattern': r"{{t '.*' }}[\.\?!]",
         'description': "Period should be part of the translatable string."},
        {'pattern': r'{{t ".*" }}[\.\?!]',
         'description': "Period should be part of the translatable string."},
        {'pattern': r"{{/tr}}[\.\?!]",
         'description': "Period should be part of the translatable string."},
        {'pattern': '{{t ("|\') ',
         'description': 'Translatable strings should not have leading spaces.'},
        {'pattern': "{{t '[^']+ ' }}",
         'description': 'Translatable strings should not have trailing spaces.'},
        {'pattern': '{{t "[^"]+ " }}',
         'description': 'Translatable strings should not have trailing spaces.'},
    ],
)

jinja2_rules = RuleList(
    langs=['html'],
    rules=html_rules + [
        {'pattern': r"{% endtrans %}[\.\?!]",
         'description': "Period should be part of the translatable string."},
        {'pattern': r"{{ _(.+) }}[\.\?!]",
         'description': "Period should be part of the translatable string."},
    ],
)

json_rules = RuleList(
    langs=['json'],
    rules=[
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
         'exclude': {'zerver/webhooks/'},
         'description': 'Fix tab-based whitespace'},
        {'pattern': r'":["\[\{]',
         'exclude': {'zerver/webhooks/', 'zerver/tests/fixtures/'},
         'description': 'Require space after : in JSON'},
    ],
)

markdown_docs_length_exclude = {
    # Has some example Vagrant output that's very long
    "docs/development/setup-vagrant.md",
    # Have wide output in code blocks
    "docs/subsystems/logging.md",
    "docs/subsystems/schema-migrations.md",
    # Have curl commands with JSON that would be messy to wrap
    "zerver/webhooks/helloworld/doc.md",
    "zerver/webhooks/trello/doc.md",
    # Has a very long configuration line
    "templates/zerver/integrations/perforce.md",
    # Has some example code that could perhaps be wrapped
    "templates/zerver/api/incoming-webhooks-walkthrough.md",
    "templates/zerver/api/get-messages.md",
    # This macro has a long indented URL
    "templates/zerver/help/include/git-webhook-url-with-branches-indented.md",
    "templates/zerver/api/update-notification-settings.md",
    # These two are the same file and have some too-long lines for GitHub badges
    "README.md",
    "docs/overview/readme.md",
}

markdown_rules = RuleList(
    langs=['md'],
    rules=markdown_whitespace_rules + prose_style_rules + [
        {'pattern': r'\[(?P<url>[^\]]+)\]\((?P=url)\)',
         'description': 'Linkified markdown URLs should use cleaner <http://example.com> syntax.'},
        {'pattern': 'https://zulip.readthedocs.io/en/latest/[a-zA-Z0-9]',
         'exclude': {'docs/overview/contributing.md', 'docs/overview/readme.md', 'docs/README.md'},
         'include_only': {'docs/'},
         'description': "Use relative links (../foo/bar.html) to other documents in docs/",
         },
        {'pattern': "su zulip -c [^']",
         'include_only': {'docs/'},
         'description': "Always quote arguments using `su zulip -c '` to avoid confusion about how su works.",
         },
        {'pattern': r'\][(][^#h]',
         'include_only': {'README.md', 'CONTRIBUTING.md'},
         'description': "Use absolute links from docs served by GitHub",
         },
    ],
    max_length=120,
    length_exclude=markdown_docs_length_exclude,
    exclude_files_in='templates/zerver/help/',
)

help_markdown_rules = RuleList(
    langs=['md'],
    rules=[
        *markdown_rules.rules,
        {'pattern': '[a-z][.][A-Z]',
         'description': "Likely missing space after end of sentence",
         'include_only': {'templates/zerver/help/'},
         },
        {'pattern': r'\b[rR]ealm[s]?\b',
         'include_only': {'templates/zerver/help/'},
         'good_lines': ['Organization', 'deactivate_realm', 'realm_filter'],
         'bad_lines': ['Users are in a realm', 'Realm is the best model'],
         'description': "Realms are referred to as Organizations in user-facing docs."},
    ],
    length_exclude=markdown_docs_length_exclude,
)

txt_rules = RuleList(
    langs=['txt', 'text', 'yaml', 'rst', 'yml'],
    rules=whitespace_rules,
)
non_py_rules = [
    handlebars_rules,
    jinja2_rules,
    css_rules,
    js_rules,
    json_rules,
    markdown_rules,
    help_markdown_rules,
    bash_rules,
    txt_rules,
]
