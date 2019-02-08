# -*- coding: utf-8 -*-

import os
import re
from typing import Any, Dict, Iterable
import logging

from django.test import override_settings
from django.template.loader import get_template
from django.test.client import RequestFactory

from zerver.lib.exceptions import InvalidMarkdownIncludeStatement
from zerver.lib.test_helpers import get_all_templates
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.test_runner import slow


class get_form_value:
    def __init__(self, value: Any) -> None:
        self._value = value

    def value(self) -> Any:
        return self._value


class DummyForm(Dict[str, Any]):
    pass


class TemplateTestCase(ZulipTestCase):
    """
    Tests that backend template rendering doesn't crash.

    This renders all the Zulip backend templates, passing dummy data
    as the context, which allows us to verify whether any of the
    templates are broken enough to not render at all (no verification
    is done that the output looks right).  Please see `get_context`
    function documentation for more information.
    """
    @slow("Tests a large number of different templates")
    @override_settings(TERMS_OF_SERVICE=None)
    def test_templates(self) -> None:

        # Just add the templates whose context has a conflict with other
        # templates' context in `defer`.
        defer = ['analytics/activity.html']

        # Django doesn't send template_rendered signal for parent templates
        # https://code.djangoproject.com/ticket/24622
        covered = [
            'zerver/portico.html',
            'zerver/portico_signup.html',
        ]

        logged_out = [
            'confirmation/confirm.html',  # seems unused
            'zerver/compare.html',
            'zerver/footer.html',
        ]

        logged_in = [
            'analytics/stats.html',
            'zerver/drafts.html',
            'zerver/home.html',
            'zerver/invite_user.html',
            'zerver/keyboard_shortcuts.html',
            'zerver/left_sidebar.html',
            'zerver/landing_nav.html',
            'zerver/logout.html',
            'zerver/markdown_help.html',
            'zerver/navbar.html',
            'zerver/right_sidebar.html',
            'zerver/search_operators.html',
            'zerver/settings_overlay.html',
            'zerver/settings_sidebar.html',
            'zerver/stream_creation_prompt.html',
            'zerver/subscriptions.html',
            'zerver/message_history.html',
            'zerver/delete_message.html',
        ]
        unusual = [
            'zerver/emails/confirm_new_email.subject.txt',
            'zerver/emails/compiled/confirm_new_email.html',
            'zerver/emails/confirm_new_email.txt',
            'zerver/emails/notify_change_in_email.subject.txt',
            'zerver/emails/compiled/notify_change_in_email.html',
            'zerver/emails/digest.subject.txt',
            'zerver/emails/digest.html',
            'zerver/emails/digest.txt',
            'zerver/emails/followup_day1.subject.txt',
            'zerver/emails/compiled/followup_day1.html',
            'zerver/emails/followup_day1.txt',
            'zerver/emails/followup_day2.subject.txt',
            'zerver/emails/followup_day2.txt',
            'zerver/emails/compiled/followup_day2.html',
            'zerver/emails/compiled/password_reset.html',
            'corporate/mit.html',
            'corporate/zephyr.html',
            'corporate/zephyr-mirror.html',
            'pipeline/css.jinja',
            'pipeline/inline_js.jinja',
            'pipeline/js.jinja',
            'zilencer/enterprise_tos_accept_body.txt',
            'zerver/zulipchat_migration_tos.html',
            'zilencer/enterprise_tos_accept_body.txt',
            'zerver/invalid_email.html',
            'zerver/topic_is_muted.html',
            'zerver/bankruptcy.html',
            'zerver/lightbox_overlay.html',
            'zerver/invalid_realm.html',
            'zerver/compose.html',
            'zerver/debug.html',
            'zerver/base.html',
            'zerver/api_content.json',
            'zerver/handlebars_compilation_failed.html',
            'zerver/portico-header.html',
            'zerver/deprecation_notice.html',
            'two_factor/_wizard_forms.html',
        ]

        integrations_regexp = re.compile('zerver/integrations/.*.html')

        # Since static/generated/bots/ is searched by Jinja2 for templates,
        # it mistakes logo files under that directory for templates.
        bot_logos_regexp = re.compile(r'\w+\/logo\.(svg|png)$')

        skip = covered + defer + logged_out + logged_in + unusual + ['tests/test_markdown.html',
                                                                     'zerver/terms.html',
                                                                     'zerver/privacy.html']

        templates = [t for t in get_all_templates() if not (
            t in skip or integrations_regexp.match(t) or bot_logos_regexp.match(t))]
        self.render_templates(templates, self.get_context())

        # Test the deferred templates with updated context.
        update = {'data': [('one', 'two')]}
        self.render_templates(defer, self.get_context(**update))

    def render_templates(self, templates: Iterable[str], context: Dict[str, Any]) -> None:
        for template_name in templates:
            template = get_template(template_name)
            try:
                template.render(context)
            except Exception:  # nocoverage # nicer error handler
                logging.error("Exception while rendering '{}'".format(template.template.name))
                raise

    def get_context(self, **kwargs: Any) -> Dict[str, Any]:
        """Get the dummy context for shallow testing.

        The context returned will always contain a parameter called
        `shallow_tested`, which tells the signal receiver that the
        test was not rendered in an actual logical test (so we can
        still do coverage reporting on which templates have a logical
        test).

        Note: `context` just holds dummy values used to make the test
        pass. This context only ensures that the templates do not
        throw a 500 error when rendered using dummy data.  If new
        required parameters are added to a template, this test will
        fail; the usual fix is to just update the context below to add
        the new parameter to the dummy data.

        :param kwargs: Keyword arguments can be used to update the base
            context.

        """
        user_profile = self.example_user('hamlet')
        email = user_profile.email

        context = dict(
            sidebar_index="zerver/help/include/sidebar_index.md",
            doc_root="/help/",
            article="zerver/help/index.md",
            shallow_tested=True,
            user_profile=user_profile,
            user=user_profile,
            form=DummyForm(
                full_name=get_form_value('John Doe'),
                terms=get_form_value(True),
                email=get_form_value(email),
                emails=get_form_value(email),
                subdomain=get_form_value("zulip"),
                next_param=get_form_value("billing")
            ),
            current_url=lambda: 'www.zulip.com',
            integrations_dict={},
            referrer=dict(
                full_name='John Doe',
                realm=dict(name='zulip.com'),
            ),
            message_count=0,
            messages=[dict(header='Header')],
            new_streams=dict(html=''),
            data=dict(title='Title'),
            device_info={"device_browser": "Chrome",
                         "device_os": "Windows",
                         "device_ip": "127.0.0.1",
                         "login_time": "9:33am NewYork, NewYork",
                         },
            api_uri_context={},
            cloud_annual_price=80,
            seat_count=8,
            request=RequestFactory().get("/"),
            invite_as={"MEMBER": 1},
        )

        context.update(kwargs)
        return context

    def test_markdown_in_template(self) -> None:
        template = get_template("tests/test_markdown.html")
        context = {
            'markdown_test_file': "zerver/tests/markdown/test_markdown.md"
        }
        content = template.render(context)

        content_sans_whitespace = content.replace(" ", "").replace('\n', '')
        self.assertEqual(content_sans_whitespace,
                         'header<h1id="hello">Hello!</h1><p>Thisissome<em>boldtext</em>.</p>footer')

    def test_markdown_tabbed_sections_extension(self) -> None:
        template = get_template("tests/test_markdown.html")
        context = {
            'markdown_test_file': "zerver/tests/markdown/test_tabbed_sections.md"
        }
        content = template.render(context)
        content_sans_whitespace = content.replace(" ", "").replace('\n', '')

        # Note that the expected HTML has a lot of stray <p> tags. This is a
        # consequence of how the Markdown renderer converts newlines to HTML
        # and how elements are delimited by newlines and so forth. However,
        # stray <p> tags are usually matched with closing tags by HTML renderers
        # so this doesn't affect the final rendered UI in any visible way.
        expected_html = """
header

<h1 id="heading">Heading</h1>
<p>
  <div class="code-section has-tabs" markdown="1">
    <ul class="nav">
      <li data-language="ios">iOS</li>
      <li data-language="desktop-web">Desktop/Web</li>
    </ul>
    <div class="blocks">
      <div data-language="ios" markdown="1"></p>
        <p>iOS instructions</p>
      <p></div>
      <div data-language="desktop-web" markdown="1"></p>
        <p>Desktop/browser instructions</p>
      <p></div>
    </div>
  </div>
</p>

<h2 id="heading-2">Heading 2</h2>
<p>
  <div class="code-section has-tabs" markdown="1">
    <ul class="nav">
      <li data-language="desktop-web">Desktop/Web</li>
      <li data-language="android">Android</li>
    </ul>
    <div class="blocks">
      <div data-language="desktop-web" markdown="1"></p>
        <p>Desktop/browser instructions</p>
      <p></div>
      <div data-language="android" markdown="1"></p>
        <p>Android instructions</p>
      <p></div>
    </div>
  </div>
</p>

<h2 id="heading-3">Heading 3</h2>
<p>
  <div class="code-section no-tabs" markdown="1">
    <ul class="nav">
      <li data-language="null_tab">None</li>
    </ul>
    <div class="blocks">
      <div data-language="null_tab" markdown="1"></p>
        <p>Instructions for all platforms</p>
      <p></div>
    </div>
  </div>
</p>

footer
"""

        expected_html_sans_whitespace = expected_html.replace(" ", "").replace('\n', '')
        self.assertEqual(content_sans_whitespace,
                         expected_html_sans_whitespace)

    def test_encoded_unicode_decimals_in_markdown_template(self) -> None:
        template = get_template("tests/test_unicode_decimals.html")
        context = {'unescape_rendered_html': False}
        content = template.render(context)

        content_sans_whitespace = content.replace(" ", "").replace('\n', '')
        self.assertEqual(content_sans_whitespace,
                         'header<p>&#123;&#125;</p>footer')

        context = {'unescape_rendered_html': True}
        content = template.render(context)

        content_sans_whitespace = content.replace(" ", "").replace('\n', '')
        self.assertEqual(content_sans_whitespace,
                         'header<p>{}</p>footer')

    def test_markdown_nested_code_blocks(self) -> None:
        template = get_template("tests/test_markdown.html")
        context = {
            'markdown_test_file': "zerver/tests/markdown/test_nested_code_blocks.md"
        }
        content = template.render(context)

        content_sans_whitespace = content.replace(" ", "").replace('\n', '')
        expected = ('header<h1id="this-is-a-heading">Thisisaheading.</h1><ol>'
                    '<li><p>Alistitemwithanindentedcodeblock:</p><divclass="codehilite">'
                    '<pre>indentedcodeblockwithmultiplelines</pre></div></li></ol>'
                    '<divclass="codehilite"><pre><span></span>'
                    'non-indentedcodeblockwithmultiplelines</pre></div>footer')
        self.assertEqual(content_sans_whitespace, expected)

    def test_custom_markdown_include_extension(self) -> None:
        template = get_template("tests/test_markdown.html")
        context = {
            'markdown_test_file': "zerver/tests/markdown/test_custom_include_extension.md"
        }

        with self.assertRaisesRegex(InvalidMarkdownIncludeStatement, "Invalid markdown include statement"):
            template.render(context)

    def test_custom_markdown_include_extension_empty_macro(self) -> None:
        template = get_template("tests/test_markdown.html")
        context = {
            'markdown_test_file': "zerver/tests/markdown/test_custom_include_extension_empty.md"
        }
        content = template.render(context)
        content_sans_whitespace = content.replace(" ", "").replace('\n', '')
        expected = 'headerfooter'
        self.assertEqual(content_sans_whitespace, expected)

    def test_custom_tos_template(self) -> None:
        response = self.client_get("/terms/")

        self.assert_in_success_response([u"Thanks for using our products and services (\"Services\"). ",
                                         u"By using our Services, you are agreeing to these terms"],
                                        response)

    def test_custom_terms_of_service_template(self) -> None:
        not_configured_message = 'This installation of Zulip does not have a configured ' \
                                 'terms of service'
        with self.settings(TERMS_OF_SERVICE=None):
            response = self.client_get('/terms/')
        self.assert_in_success_response([not_configured_message], response)
        with self.settings(TERMS_OF_SERVICE='zerver/tests/markdown/test_markdown.md'):
            response = self.client_get('/terms/')
        self.assert_in_success_response(['This is some <em>bold text</em>.'], response)
        self.assert_not_in_success_response([not_configured_message], response)

    def test_custom_privacy_policy_template(self) -> None:
        not_configured_message = 'This installation of Zulip does not have a configured ' \
                                 'privacy policy'
        with self.settings(PRIVACY_POLICY=None):
            response = self.client_get('/privacy/')
        self.assert_in_success_response([not_configured_message], response)
        with self.settings(PRIVACY_POLICY='zerver/tests/markdown/test_markdown.md'):
            response = self.client_get('/privacy/')
        self.assert_in_success_response(['This is some <em>bold text</em>.'], response)
        self.assert_not_in_success_response([not_configured_message], response)

    def test_custom_privacy_policy_template_with_absolute_url(self) -> None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        abs_path = os.path.join(current_dir, '..', '..',
                                'templates/zerver/tests/markdown/test_markdown.md')
        with self.settings(PRIVACY_POLICY=abs_path):
            response = self.client_get('/privacy/')
        self.assert_in_success_response(['This is some <em>bold text</em>.'], response)
