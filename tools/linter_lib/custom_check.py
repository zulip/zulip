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
    "zerver/lib/topic.py",
    # This is for backward compatibility.
    "zerver/tests/test_legacy_subject.py",
    # Other migration-related changes require extreme care.
    "zerver/lib/fix_unreads.py",
    "zerver/tests/test_migrations.py",
    # These use subject in the email sense, and will
    # probably always be exempt:
    "zerver/lib/email_mirror.py",
    "zerver/lib/email_notifications.py",
    "zerver/lib/send_email.py",
    "zerver/tests/test_new_users.py",
    "zerver/tests/test_email_mirror.py",
    "zerver/tests/test_email_notifications.py",
    # This uses subject in authentication protocols sense:
    "zerver/tests/test_auth_backends.py",
    # These are tied more to our API than our DB model.
    "zerver/openapi/python_examples.py",
    "zerver/tests/test_openapi.py",
    # This has lots of query data embedded, so it's hard
    # to fix everything until we migrate the DB to "topic".
    "zerver/tests/test_message_fetch.py",
}

shebang_rules: List["Rule"] = [
    {
        "pattern": r"\A#!",
        "description": "zerver library code shouldn't have a shebang line.",
        "include_only": {"zerver/"},
    },
    # /bin/sh and /usr/bin/env are the only two binaries
    # that NixOS provides at a fixed path (outside a
    # buildFHSUserEnv sandbox).
    {
        "pattern": r"\A#!(?! *(?:/usr/bin/env|/bin/sh)(?: |$))",
        "description": "Use `#!/usr/bin/env foo` instead of `#!/path/foo`"
        " for interpreters other than sh.",
    },
    {
        "pattern": r"\A#!/usr/bin/env python$",
        "description": "Use `#!/usr/bin/env python3` instead of `#!/usr/bin/env python`.",
    },
]

base_whitespace_rules: List["Rule"] = [
    {
        "pattern": r"[\t ]+$",
        "exclude": {"tools/ci/success-http-headers.template.txt"},
        "description": "Fix trailing whitespace",
    },
    {
        "pattern": r"[^\n]\Z",
        "description": "Missing newline at end of file",
    },
]
whitespace_rules: List["Rule"] = [
    *base_whitespace_rules,
    {
        "pattern": "http://zulip.readthedocs.io",
        "description": "Use HTTPS when linking to ReadTheDocs",
    },
    {
        "pattern": "\t",
        "description": "Fix tab-based whitespace",
    },
    {
        "pattern": r"(?i:webapp)",
        "description": "Web app should be two words",
    },
]
comma_whitespace_rule: List["Rule"] = [
    {
        "pattern": ", {2,}[^#/ ]",
        "exclude": {"zerver/tests", "web/tests", "corporate/tests"},
        "description": "Remove multiple whitespaces after ','",
        "good_lines": ["foo(1, 2, 3)", "foo = bar  # some inline comment"],
        "bad_lines": ["foo(1,  2, 3)", "foo(1,    2, 3)"],
    },
]
markdown_whitespace_rules: List["Rule"] = [
    *(rule for rule in whitespace_rules if rule["pattern"] != r"[\t ]+$"),
    # Two spaces trailing a line with other content is okay--it's a Markdown line break.
    # This rule finds one space trailing a non-space, three or more trailing spaces, and
    # spaces on an empty line.
    {
        "pattern": r"((?<![\t ])[\t ]$)|([\t ][\t ][\t ]+$)|(^[\t ]+$)",
        "description": "Fix trailing whitespace",
    },
    {
        "pattern": "^#+[A-Za-z0-9]",
        "description": "Missing space after # in heading",
        "exclude_line": {
            ("docs/subsystems/hotspots.md", "#hotspot_new_hotspot_name_icon {"),
        },
        "good_lines": ["### some heading", "# another heading"],
        "bad_lines": ["###some heading", "#another heading"],
    },
]


js_rules = RuleList(
    langs=["js", "ts"],
    rules=[
        {
            "pattern": "subject|SUBJECT",
            "exclude": {"web/src/types.ts", "web/src/util.ts", "web/tests/"},
            "exclude_pattern": "emails",
            "description": "avoid subject in JS code",
            "good_lines": ["topic_name"],
            "bad_lines": ['subject="foo"', " MAX_SUBJECT_LEN"],
        },
        {
            "pattern": "msgid|MSGID",
            "description": 'Avoid using "msgid" as a variable name; use "message_id" instead.',
        },
        {
            "pattern": r"\$t\(.+\).*\+",
            "description": "Do not concatenate i18n strings",
        },
        {"pattern": r"\+.*\$t\(.+\)", "description": "Do not concatenate i18n strings"},
        {
            "pattern": "[.]html[(]",
            "exclude_pattern": r"""\.html\(("|'|render_|html|message\.content|util\.clean_user_content_links|rendered_|$|\)|error_html|widget_elem|\$error|\$\("<p>"\))""",
            "exclude": {
                "web/src/portico",
                "web/src/lightbox.js",
                "web/src/ui_report.ts",
                "web/src/dialog_widget.ts",
                "web/tests/",
            },
            "description": "Setting HTML content with jQuery .html() can lead to XSS security bugs.  Consider .text() or using rendered_foo as a variable name if content comes from Handlebars and thus is already sanitized.",
        },
        {
            "pattern": "[\"']json/",
            "description": "Relative URL for JSON route not supported by i18n",
        },
        {
            "pattern": r"""[.]text\(["'][a-zA-Z]""",
            "description": "Strings passed to $().text should be wrapped in $t() for internationalization",
            "exclude": {"web/tests/"},
        },
        {
            "pattern": r"ui.report_success\(",
            "description": "Deprecated function, use ui_report.success.",
        },
        {
            "pattern": r"""report.success\(["']""",
            "description": "Argument to ui_report.success should be a literal string translated "
            "by $t_html()",
        },
        {
            "pattern": r"ui.report_error\(",
            "description": "Deprecated function, use ui_report.error.",
        },
        {
            "pattern": r"""report.error\(["'][^'"]""",
            "description": "Argument to ui_report.error should be a literal string translated "
            "by $t_html()",
            "good_lines": ['ui_report.error("")', 'ui_report.error(_("text"))'],
            "bad_lines": ['ui_report.error("test")'],
        },
        {
            "pattern": r"""report.client_error\(["'][^'"]""",
            "description": "Argument to ui_report.client_error should be a literal string translated "
            "by $t_html()",
            "good_lines": ['ui_report.client_error("")', 'ui_report.client_error(_("text"))'],
            "bad_lines": ['ui_report.client_error("test")'],
        },
        {
            "pattern": r"\$\(document\)\.ready\(",
            "description": "`Use $(f) rather than `$(document).ready(f)`",
            "good_lines": ["$(function () {foo();}"],
            "bad_lines": ["$(document).ready(function () {foo();}"],
        },
        {
            "pattern": "[$][.](get|post|patch|delete|ajax)[(]",
            "description": "Use channel module for AJAX calls",
            "exclude": {
                # Internal modules can do direct network calls
                "web/src/blueslip.ts",
                "web/src/channel.js",
                # External modules that don't include channel.js
                "web/src/stats/",
                "web/src/portico/",
                "web/src/billing/",
            },
            "good_lines": ["channel.get(...)"],
            "bad_lines": ["$.get()", "$.post()", "$.ajax()"],
        },
        {
            "pattern": "style ?=",
            "exclude_pattern": r"(const |\S)style ?=",
            "description": "Avoid using the `style=` attribute; we prefer styling in CSS files",
            "exclude": {
                "web/tests/copy_and_paste.test.js",
            },
            "good_lines": ["#my-style {color: blue;}", "const style =", 'some_style = "test"'],
            "bad_lines": ['<p style="color: blue;">Foo</p>', 'style = "color: blue;"'],
        },
        {
            "pattern": r"assert\(",
            "description": "Use 'assert.ok' instead of 'assert'. We avoid the use of 'assert' as it can easily be confused with 'assert.equal'.",
            "good_lines": ["assert.ok(...)"],
            "bad_lines": ["assert(...)"],
        },
        {
            "pattern": r"allowHTML|(?i:data-tippy-allowHTML)",
            "description": "Never use Tippy.js allowHTML; for an HTML tooltip, get a DocumentFragment with ui_util.parse_html.",
        },
        *whitespace_rules,
    ],
)

python_rules = RuleList(
    langs=["py"],
    rules=[
        {
            "pattern": "subject|SUBJECT",
            "exclude_pattern": "subject to the|email|outbox|account deactivation",
            "description": "avoid subject as a var",
            "good_lines": ["topic_name"],
            "bad_lines": ['subject="foo"', " MAX_SUBJECT_LEN"],
            "exclude": FILES_WITH_LEGACY_SUBJECT,
            "include_only": {
                "zerver/data_import/",
                "zerver/lib/",
                "zerver/tests/",
                "zerver/views/",
            },
        },
        {
            "pattern": "msgid|MSGID",
            "exclude": {"tools/check-capitalization"},
            "description": 'Avoid using "msgid" as a variable name; use "message_id" instead.',
        },
        {
            "pattern": r"^[\t ]*(?!#)@login_required",
            "description": "@login_required is unsupported; use @zulip_login_required",
            "good_lines": ["@zulip_login_required", "# foo @login_required"],
            "bad_lines": ["@login_required", " @login_required"],
        },
        {
            "pattern": r"^[\t ]*user_profile[.]save[(][)]",
            "description": "Always pass update_fields when saving user_profile objects",
            "exclude_line": {
                (
                    "zerver/actions/bots.py",
                    "user_profile.save()  # Can't use update_fields because of how the foreign key works.",
                ),
            },
            "exclude": {"zerver/tests", "zerver/lib/create_user.py"},
            "good_lines": ['user_profile.save(update_fields=["pointer"])'],
            "bad_lines": ["user_profile.save()"],
        },
        {
            "pattern": "self: Any",
            "description": "you can omit Any annotation for self",
            "good_lines": ["def foo (self):"],
            "bad_lines": ["def foo(self: Any):"],
        },
        {
            "pattern": r"assertEqual[(]len[(][^\n ]*[)],",
            "description": "Use the assert_length helper instead of assertEqual(len(..), ..).",
            "good_lines": ["assert_length(data, 2)"],
            "bad_lines": ["assertEqual(len(data), 2)"],
            "exclude_line": {
                ("zerver/tests/test_decorators.py", "self.assertEqual(len(x), 2)"),
                ("zerver/tests/test_decorators.py", 'self.assertEqual(len(x["b"]), 3)'),
            },
        },
        {
            "pattern": r"assertTrue[(]len[(][^\n ]*[)]",
            "description": "Use assert_length or assertGreater helper instead of assertTrue(len(..) ..).",
            "good_lines": ["assert_length(data, 2)", "assertGreater(len(data), 2)"],
            "bad_lines": [
                "assertTrue(len(data) == 2)",
                "assertTrue(len(data) >= 2)",
                "assertTrue(len(data) > 2)",
            ],
        },
        {
            "pattern": r"#[\t ]*type:[\t ]*ignore(?!\[[^]\n[]+\] +# +\S)",
            "exclude": {"tools/tests", "zerver/lib/test_runner.py", "zerver/tests"},
            "description": '"type: ignore" should always end with "# type: ignore[code] # explanation for why"',
            "good_lines": ["foo = bar  # type: ignore[code] # explanation"],
            "bad_lines": [
                "foo = bar  # type: ignore",
                "foo = bar  # type: ignore[code]",
                "foo = bar  # type: ignore # explanation",
            ],
        },
        {
            "pattern": r"\bsudo\b",
            "include_only": {"scripts/"},
            "exclude": {"scripts/lib/setup_venv.py"},
            "exclude_line": {
                ("scripts/lib/zulip_tools.py", 'args = ["sudo", *sudo_args, "--", *args]'),
            },
            "description": "Most scripts are intended to run on systems without sudo.",
            "good_lines": ['subprocess.check_call(["ls"])'],
            "bad_lines": ['subprocess.check_call(["sudo", "ls"])'],
        },
        {
            "pattern": "django.utils.translation",
            "include_only": {"test/", "zerver/views/development/"},
            "exclude": {"zerver/views/development/dev_login.py"},
            "description": "Test strings should not be tagged for translation",
            "good_lines": [""],
            "bad_lines": ["django.utils.translation"],
        },
        {
            "pattern": "userid",
            "description": "We prefer user_id over userid.",
            "good_lines": ["id = alice.user_id"],
            "bad_lines": ["id = alice.userid"],
        },
        # To avoid JsonableError(_variable) and JsonableError(_(variable))
        {
            "pattern": r"\WJsonableError\(_\(?\w.+\)",
            "exclude": {"zerver/tests", "zerver/views/development/"},
            "description": "Argument to JsonableError should be a literal string enclosed by _()",
        },
        {
            "pattern": r"""\WJsonableError\(["'].+\)""",
            "exclude": {"zerver/tests", "zerver/views/development/"},
            "description": "Argument to JsonableError should be a literal string enclosed by _()",
        },
        {
            "pattern": r"""([a-zA-Z0-9_]+)=REQ\(['"]\1['"]""",
            "description": "REQ's first argument already defaults to parameter name",
        },
        {
            "pattern": r"self\.client\.(get|post|patch|put|delete)",
            "description": """Do not call self.client directly for put/patch/post/get.
    See WRAPPER_COMMENT in test_helpers.py for details.
    """,
        },
        # Directly fetching Message objects in e.g. views code is often a security bug.
        {
            "pattern": "[^r]Message.objects.get",
            "exclude": {
                "zerver/tests",
                "zerver/lib/onboarding.py",
                "zilencer/management/commands/add_mock_conversation.py",
                "zerver/worker/queue_processors.py",
                "zerver/management/commands/export.py",
                "zerver/lib/export.py",
            },
            "description": "Please use access_message() to fetch Message objects",
        },
        {
            "pattern": "Stream.objects.get",
            "include_only": {"zerver/views/"},
            "description": "Please use access_stream_by_*() to fetch Stream objects",
        },
        {
            "pattern": "get_stream[(]",
            "include_only": {"zerver/views/", "zerver/actions/"},
            "exclude_line": {
                # This one in check_message is kinda terrible, since it's
                # how most instances are written, but better to exclude something than nothing
                ("zerver/actions/message_send.py", "stream = get_stream(stream_name, realm)"),
            },
            "description": "Please use access_stream_by_*() to fetch Stream objects",
        },
        {
            "pattern": "from os.path",
            "description": "Don't use from when importing from the standard library",
        },
        {
            "pattern": "import os.path",
            "description": "Use import os instead of import os.path",
        },
        {
            "pattern": r"\.pk",
            "exclude_pattern": "[.]_meta[.]pk",
            "description": "Use `id` instead of `pk`.",
            "good_lines": ["if my_django_model.id == 42", "self.user_profile._meta.pk"],
            "bad_lines": ["if my_django_model.pk == 42"],
        },
        {
            "pattern": r"^[\t ]*#[\t ]*type:",
            "description": "Comment-style function type annotation. Use Python3 style annotations instead.",
        },
        {
            "pattern": r"\S[\t ]*#[\t ]*type:(?![\t ]*ignore)",
            "description": "Comment-style variable type annotation. Use Python 3.6 style annotations instead.",
            "good_lines": ["a: List[int] = []"],
            "bad_lines": ["a = []  # type: List[int]"],
        },
        {
            "pattern": r": *(?!Optional)[^\n ].*= models[.].*null=True",
            "include_only": {"zerver/models.py"},
            "description": "Model variable with null=true not annotated as Optional.",
            "good_lines": [
                "desc: Optional[Text] = models.TextField(null=True)",
                "stream: Optional[Stream] = models.ForeignKey(Stream, null=True, on_delete=CASCADE)",
                "desc: Text = models.TextField()",
                "stream: Stream = models.ForeignKey(Stream, on_delete=CASCADE)",
            ],
            "bad_lines": [
                "desc: Text = models.CharField(null=True)",
                "stream: Stream = models.ForeignKey(Stream, null=True, on_delete=CASCADE)",
            ],
        },
        {
            "pattern": r": *Optional.*= models[.].*\)",
            "exclude_pattern": "null=True",
            "include_only": {"zerver/models.py"},
            "description": "Model variable annotated with Optional but variable does not have null=true.",
            "good_lines": [
                "desc: Optional[Text] = models.TextField(null=True)",
                "stream: Optional[Stream] = models.ForeignKey(Stream, null=True, on_delete=CASCADE)",
                "desc: Text = models.TextField()",
                "stream: Stream = models.ForeignKey(Stream, on_delete=CASCADE)",
            ],
            "bad_lines": [
                "desc: Optional[Text] = models.TextField()",
                "stream: Optional[Stream] = models.ForeignKey(Stream, on_delete=CASCADE)",
            ],
        },
        {
            "pattern": r"exit[(][1-9]\d*[)]",
            "include_only": {"/management/commands/"},
            "description": "Raise CommandError to exit with failure in management commands",
            "exclude": {"zerver/management/commands/process_queue.py"},
        },
        {
            "pattern": r"\.is_realm_admin =",
            "description": "Use do_change_user_role function rather than setting UserProfile's is_realm_admin attribute directly.",
            "exclude": {
                "zerver/migrations/0248_userprofile_role_start.py",
                "zerver/tests/test_users.py",
            },
        },
        {
            "pattern": r"\.is_guest =",
            "description": "Use do_change_user_role function rather than setting UserProfile's is_guest attribute directly.",
            "exclude": {
                "zerver/migrations/0248_userprofile_role_start.py",
                "zerver/tests/test_users.py",
            },
        },
        {
            "pattern": "\\.(called(_once|_with|_once_with)?|not_called|has_calls|not_called)[(]",
            "description": 'A mock function is missing a leading "assert_"',
        },
        {
            "pattern": "@transaction.atomic\\(\\)",
            "description": "Use @transaction.atomic as function decorator for consistency.",
        },
        *whitespace_rules,
        *shebang_rules,
    ],
)

bash_rules = RuleList(
    langs=["bash"],
    rules=[
        {
            "pattern": "#!.*sh [-xe]",
            "description": "Fix shebang line with proper call to /usr/bin/env for Bash path, change -x|-e switches"
            " to set -x|set -e",
        },
        {
            "pattern": "sudo",
            "description": "Most scripts are intended to work on systems without sudo",
            "include_only": {"scripts/"},
            "exclude": {
                "scripts/lib/install",
            },
        },
        *base_whitespace_rules,
        *shebang_rules,
    ],
)

css_rules = RuleList(
    langs=["css"],
    rules=[
        *whitespace_rules,
    ],
)

prose_style_rules: List["Rule"] = [
    {
        "pattern": r'^[\t ]*[^\n{].*?[^\n\/\#\-"]([jJ]avascript)',  # exclude usage in hrefs/divs/custom-markdown
        "exclude": {"docs/documentation/api.md", "templates/corporate/policies/privacy.md"},
        "description": "javascript should be spelled JavaScript",
    },
    {
        "pattern": r"""[^\n\/\-\."'\_\=\>]([gG]ithub)[^\n\.\-\_"\<]""",  # exclude usage in hrefs/divs
        "description": "github should be spelled GitHub",
    },
    {
        "pattern": "[oO]rganisation",  # exclude usage in hrefs/divs
        "description": "Organization is spelled with a z",
        "exclude_line": {("docs/translating/french.md", "- organization - **organisation**")},
    },
    {"pattern": "!!! warning", "description": "!!! warning is invalid; it's spelled '!!! warn'"},
    {"pattern": "Terms of service", "description": "The S in Terms of Service is capitalized"},
    {
        "pattern": "[^-_p]botserver(?!rc)|bot server",
        "description": "Use Botserver instead of botserver or bot server.",
    },
    *comma_whitespace_rule,
]
html_rules: List["Rule"] = [
    *whitespace_rules,
    *prose_style_rules,
    {
        "pattern": "subject|SUBJECT",
        "exclude": {
            "templates/zerver/email.html",
            "zerver/tests/fixtures/email",
            "templates/corporate/for/business.html",
            "templates/corporate/support_request.html",
            "templates/corporate/support_request_thanks.html",
            "templates/zerver/emails/support_request.html",
        },
        "exclude_pattern": "email subject",
        "description": "avoid subject in templates",
        "good_lines": ["topic_name"],
        "bad_lines": ['subject="foo"', " MAX_SUBJECT_LEN"],
    },
    {
        "pattern": r'placeholder="[^{#](?:(?!\.com).)+$',
        "description": "`placeholder` value should be translatable.",
        "exclude_line": {
            ("templates/zerver/realm_creation_form.html", 'placeholder="acme"'),
            ("templates/zerver/realm_creation_form.html", 'placeholder="Acme or Ακμή"'),
        },
        "exclude": {
            "templates/analytics/support.html",
            # We have URL prefix and Pygments language name as placeholders
            # in the below template which we don't want to be translatable.
            "web/templates/settings/playground_settings_admin.hbs",
        },
        "good_lines": [
            '<input class="stream-list-filter" type="text" placeholder="{{ _(\'Filter streams\') }}" />'
        ],
        "bad_lines": ['<input placeholder="foo">'],
    },
    {
        "pattern": "={",
        "description": "Likely missing quoting in HTML attribute",
        "good_lines": ['<a href="{{variable}}">'],
        "bad_lines": ["<a href={{variable}}>"],
    },
    {
        "pattern": " '}}",
        "description": "Likely misplaced quoting in translation tags",
        "good_lines": ["{{t 'translatable string' }}"],
        "bad_lines": ["{{t 'translatable string '}}"],
    },
    {
        "pattern": "placeholder='[^{]",
        "description": "`placeholder` value should be translatable.",
        "good_lines": [
            '<input class="stream-list-filter" type="text" placeholder="{{ _(\'Filter streams\') }}" />'
        ],
        "bad_lines": ["<input placeholder='foo'>"],
    },
    {
        "pattern": "aria-label='[^{]",
        "description": "`aria-label` value should be translatable.",
        "good_lines": [
            '<button type="button" class="close close-alert-word-status" aria-label="{{t \'Close\' }}">'
        ],
        "bad_lines": ["<button aria-label='foo'></button>"],
    },
    {
        "pattern": 'aria-label="[^{]',
        "description": "`aria-label` value should be translatable.",
        "good_lines": [
            '<button type="button" class="close close-alert-word-status" aria-label="{{t \'Close\' }}">'
        ],
        "bad_lines": ['<button aria-label="foo"></button>'],
    },
    {
        "pattern": 'script src="http',
        "description": "Don't directly load dependencies from CDNs.  See docs/subsystems/html-css.md",
        "exclude": {
            "templates/corporate/billing.html",
            "templates/corporate/hello.html",
            "templates/corporate/upgrade.html",
            "templates/corporate/event_status.html",
        },
        "bad_lines": [
            '<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.2.1/jquery.min.js"></script>'
        ],
    },
    {
        "pattern": "title='[^{]",
        "description": "`title` value should be translatable.",
        "good_lines": ['<link rel="author" title="{{ _(\'About these documents\') }}" />'],
        "bad_lines": ["<p title='foo'></p>"],
    },
    {
        "pattern": r'title="[^{\:]',
        "exclude": {
            "templates/zerver/emails",
            "templates/analytics/realm_details.html",
            "templates/analytics/support.html",
        },
        "description": "`title` value should be translatable.",
    },
    {
        "pattern": r"""\Walt=["'][^{"']""",
        "description": "alt argument should be enclosed by _() or it should be an empty string.",
        "exclude_line": {
            (
                # Emoji should not be tagged for translation.
                "web/templates/keyboard_shortcuts.hbs",
                '<img alt=":thumbs_up:"',
            ),
        },
        "good_lines": ['<img src="{{source_url}}" alt="{{ _(name) }}" />', '<img alg="" />'],
        "bad_lines": ['<img alt="Foo Image" />'],
    },
    {
        "pattern": r"""\Walt=["']{{ ?["']""",
        "description": "alt argument should be enclosed by _().",
        "good_lines": ['<img src="{{source_url}}" alt="{{ _(name) }}" />'],
        "bad_lines": ['<img alt="{{ " />'],
    },
    {
        "pattern": r"link=\"help/",
        "description": "Relative links to Help Center should start with /help/",
        "good_lines": ['link="/help/foo"'],
        "bad_lines": ['link="help/foo"'],
    },
    {
        "pattern": r"\bon\w+ ?=",
        "description": "Don't use inline event handlers (onclick=, etc. attributes) in HTML. Instead, "
        "attach a jQuery event handler ($('#foo').on('click', function () {...})) when "
        "the DOM is ready (inside a $(function () {...}) block).",
        "exclude": {
            "templates/zerver/development/dev_login.html",
            "templates/corporate/upgrade.html",
        },
        "good_lines": ["($('#foo').on('click', function () {}"],
        "bad_lines": [
            "<button id='foo' onclick='myFunction()'>Foo</button>",
            "<input onchange='myFunction()'>",
        ],
    },
    {
        "pattern": "style ?=",
        "description": "Avoid using the `style=` attribute; we prefer styling in CSS files",
        "exclude_pattern": r""".*style ?=["'](display: ?none|background: {{|color: {{|background-color: {{).*""",
        "exclude": {
            # 5xx page doesn't have external CSS
            "web/html/5xx.html",
            # exclude_pattern above handles color, but have other issues:
            "web/templates/draft.hbs",
            "web/templates/stream_settings/browse_streams_list_item.hbs",
            "web/templates/user_group_settings/browse_user_groups_list_item.hbs",
            "web/templates/single_message.hbs",
            # Old-style email templates need to use inline style
            # attributes; it should be possible to clean these up
            # when we convert these templates to use premailer.
            "templates/zerver/emails/email_base_messages.html",
            # Email log templates; should clean up.
            "templates/zerver/email.html",
            "templates/zerver/development/email_log.html",
            # Social backend logos are dynamically loaded
            "templates/zerver/accounts_home.html",
            "templates/zerver/login.html",
            # Needs the width cleaned up; display: none is fine
            "web/templates/dialog_change_password.hbs",
            # background image property is dynamically generated
            "web/templates/user_profile_modal.hbs",
            "web/templates/pm_list_item.hbs",
            # Inline styling for an svg; could be moved to CSS files?
            "templates/zerver/landing_nav.html",
            "templates/zerver/billing_nav.html",
            "templates/corporate/features.html",
            "templates/zerver/portico-header.html",
            "templates/corporate/billing.html",
            "templates/corporate/upgrade.html",
            # Miscellaneous violations to be cleaned up
            "web/templates/user_info_popover_title.hbs",
            "web/templates/confirm_dialog/confirm_subscription_invites_warning.hbs",
            "templates/zerver/reset_confirm.html",
            "templates/zerver/config_error.html",
            "templates/zerver/dev_env_email_access_details.html",
            "templates/zerver/confirm_continue_registration.html",
            "templates/zerver/register.html",
            "templates/zerver/accounts_send_confirm.html",
            "templates/zerver/integrations/index.html",
            "templates/zerver/documentation_main.html",
            "templates/analytics/realm_summary_table.html",
            "templates/corporate/zephyr.html",
            "templates/corporate/zephyr-mirror.html",
        },
        "good_lines": ["#my-style {color: blue;}", 'style="display: none"', "style='display: none"],
        "bad_lines": ['<p style="color: blue;">Foo</p>', 'style = "color: blue;"'],
    },
    {
        "pattern": r"(?i:data-tippy-allowHTML)",
        "description": "Never use data-tippy-allowHTML; for an HTML tooltip, set data-tooltip-template-id to the id of a <template> containing the tooltip content.",
    },
]

handlebars_rules = RuleList(
    langs=["hbs"],
    rules=[
        *html_rules,
        {
            "pattern": "[<]script",
            "description": "Do not use inline <script> tags here; put JavaScript in web/src instead.",
        },
        {
            "pattern": "{{ t (\"|')",
            "description": 'There should be no spaces before the "t" in a translation tag.',
        },
        {
            "pattern": r"{{t '.*' }}[\.\?!]",
            "description": "Period should be part of the translatable string.",
        },
        {
            "pattern": r'{{t ".*" }}[\.\?!]',
            "description": "Period should be part of the translatable string.",
        },
        {
            "pattern": r"{{/tr}}[\.\?!]",
            "description": "Period should be part of the translatable string.",
        },
        {
            "pattern": "{{t (\"|') ",
            "description": "Translatable strings should not have leading spaces.",
        },
        {
            "pattern": "{{t '[^']+ ' }}",
            "description": "Translatable strings should not have trailing spaces.",
        },
        {
            "pattern": '{{t "[^"]+ " }}',
            "description": "Translatable strings should not have trailing spaces.",
        },
        {
            "pattern": r'"{{t "',
            "description": "Invalid quoting for HTML element with translated string.",
        },
        {
            "pattern": r'href="#"',
            "description": 'Avoid href="#" for elements with a JavaScript click handler.',
            "exclude": {"web/templates/navbar.hbs"},
        },
    ],
)

jinja2_rules = RuleList(
    langs=["html"],
    rules=[
        *html_rules,
        {
            "pattern": r"{% endtrans %}[\.\?!]",
            "description": "Period should be part of the translatable string.",
        },
        {
            "pattern": r"{{ _(.+) }}[\.\?!]",
            "description": "Period should be part of the translatable string.",
        },
        {
            "pattern": r'{% set entrypoint = "dev-',
            "exclude": {"templates/zerver/development/"},
            "description": "Development entry points (dev-) must not be imported in production.",
        },
    ],
)

json_rules = RuleList(
    langs=["json"],
    rules=[
        # Here, we don't use `whitespace_rules`, because the tab-based
        # whitespace rule flags a lot of third-party JSON fixtures
        # under zerver/webhooks that we want preserved verbatim.  So
        # we just include the trailing whitespace rule and a modified
        # version of the tab-based whitespace rule (we can't just use
        # exclude in whitespace_rules, since we only want to ignore
        # JSON files with tab-based whitespace, not webhook code).
        *base_whitespace_rules,
        {
            "pattern": "\t",
            "exclude": {"zerver/webhooks/"},
            "description": "Fix tab-based whitespace",
        },
        {
            "pattern": r'":["\[\{]',
            "exclude": {"zerver/webhooks/", "zerver/tests/fixtures/"},
            "description": "Require space after : in JSON",
        },
    ],
)

markdown_rules = RuleList(
    langs=["md"],
    rules=[
        *markdown_whitespace_rules,
        *prose_style_rules,
        {
            "pattern": r"\[(?P<url>[^\]]+)\]\((?P=url)\)",
            "description": "Linkified Markdown URLs should use cleaner <http://example.com> syntax.",
        },
        {
            "pattern": "https://zulip.readthedocs.io/en/latest/[a-zA-Z0-9]",
            "exclude": {
                "api_docs/",
                "docs/contributing/contributing.md",
                "docs/overview/readme.md",
                "docs/README.md",
                "docs/subsystems/email.md",
            },
            "exclude_line": {
                (
                    "docs/overview/changelog.md",
                    "[latest-changelog]: https://zulip.readthedocs.io/en/latest/overview/changelog.html",
                ),
            },
            "include_only": {"docs/"},
            "description": "Use relative links (../foo/bar.html) to other documents in docs/",
        },
        {
            "pattern": "su zulip -c [^']",
            "include_only": {"docs/"},
            "description": "Always quote arguments using `su zulip -c '` to avoid confusion about how su works.",
        },
        {
            "pattern": r"\][(][^#h]",
            "exclude_pattern": "mailto:",
            "include_only": {"README.md", "CONTRIBUTING.md"},
            "description": "Use absolute links from docs served by GitHub",
        },
        {
            "pattern": r"\.(py|js)#L\d+",
            "include_only": {"docs/"},
            "description": "Don't link directly to line numbers",
        },
    ],
)

help_markdown_rules = RuleList(
    langs=["md"],
    rules=[
        *markdown_rules.rules,
        {
            "pattern": "[a-z][.][A-Z]",
            "description": "Likely missing space after end of sentence",
            "include_only": {"help/"},
            "exclude_pattern": "Rocket.Chat",
        },
        {
            "pattern": r"\b[rR]ealm[s]?\b",
            "include_only": {"help/"},
            "exclude": {"help/change-organization-url.md"},
            "good_lines": ["Organization", "deactivate_realm", "realm_filter"],
            "bad_lines": ["Users are in a realm", "Realm is the best model"],
            "description": "Realms are referred to as Organizations in user-facing docs.",
            # Keycloak uses the term realm as well.
            # Additionally, we allow -realm- as that appears in /api/ doc URLs.
            "exclude_pattern": "(-realm-|[kK]eycloak)",
        },
    ],
)

puppet_rules = RuleList(
    langs=["pp"],
    rules=[
        *whitespace_rules,
        {
            "pattern": r"(include[\t ]+|\$)zulip::(profile|base)\b",
            "exclude": {
                "puppet/zulip/manifests/profile/",
                "puppet/zulip_ops/manifests/",
                "puppet/zulip/manifests/dockervoyager.pp",
            },
            "description": "Abstraction layering violation; only profiles should reference profiles or zulip::base",
        },
        {
            "pattern": r"(include[\t ]+|\$)zulip_ops::(profile|base)\b",
            "exclude": {
                "puppet/zulip/manifests/",
                "puppet/zulip_ops/manifests/profile/",
            },
            "description": "Abstraction layering violation; only profiles should reference profiles or zulip_ops::base",
        },
    ],
)

txt_rules = RuleList(
    langs=["txt", "text", "yaml", "rst", "yml"],
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
    puppet_rules,
]
