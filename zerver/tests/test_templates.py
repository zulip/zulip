# -*- coding: utf-8 -*-
from __future__ import absolute_import

import re
from typing import Any, Dict, Iterable
import logging

from django.conf import settings
from django.test import override_settings
from django.template import Template, Context
from django.template.loader import get_template

from zerver.lib.test_helpers import get_all_templates
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.context_processors import common_context


class get_form_value(object):
    def __init__(self, value):
        # type: (Any) -> None
        self._value = value

    def value(self):
        # type: () -> Any
        return self._value


class DummyForm(dict):
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
    @override_settings(TERMS_OF_SERVICE=None)
    def test_templates(self):
        # type: () -> None

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
            'zerver/emails/confirm_new_email.subject',
            'zerver/emails/confirm_new_email.html',
            'zerver/emails/confirm_new_email.txt',
            'zerver/emails/notify_change_in_email.subject',
            'zerver/emails/notify_change_in_email.html',
            'zerver/emails/digest.subject',
            'zerver/emails/digest.html',
            'zerver/emails/digest.txt',
            'zerver/emails/followup_day1.subject',
            'zerver/emails/followup_day1.html',
            'zerver/emails/followup_day1.txt',
            'zerver/emails/followup_day2.subject',
            'zerver/emails/followup_day2.txt',
            'zerver/emails/followup_day2.html',
            'zerver/emails/password_reset.html',
            'corporate/mit.html',
            'corporate/zephyr.html',
            'corporate/zephyr-mirror.html',
            'pipeline/css.jinja',
            'pipeline/inline_js.jinja',
            'pipeline/js.jinja',
            'zilencer/enterprise_tos_accept_body.txt',
            'zerver/zulipchat_migration_tos.html',
            'zilencer/enterprise_tos_accept_body.txt',
            'zerver/closed_realm.html',
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
        ]

        integrations_regexp = re.compile('zerver/integrations/.*.html')

        # Since static/generated/bots/ is searched by Jinja2 for templates,
        # it mistakes logo files under that directory for templates.
        bot_logos_regexp = re.compile('\w+\/logo\.(svg|png)$')

        skip = covered + defer + logged_out + logged_in + unusual + ['tests/test_markdown.html',
                                                                     'zerver/terms.html',
                                                                     'zerver/privacy.html']

        templates = [t for t in get_all_templates() if not (
            t in skip or integrations_regexp.match(t) or bot_logos_regexp.match(t))]
        self.render_templates(templates, self.get_context())

        # Test the deferred templates with updated context.
        update = {'data': [('one', 'two')]}
        self.render_templates(defer, self.get_context(**update))

    def render_templates(self, templates, context):
        # type: (Iterable[str], Dict[str, Any]) -> None
        for template_name in templates:
            template = get_template(template_name)
            try:
                template.render(context)
            except Exception:  # nocoverage # nicer error handler
                logging.error("Exception while rendering '{}'".format(template.template.name))
                raise

    def get_context(self, **kwargs):
        # type: (**Any) -> Dict[str, Any]
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
            article="zerver/help/index.md",
            shallow_tested=True,
            user_profile=user_profile,
            user=user_profile,
            form=DummyForm(
                full_name=get_form_value('John Doe'),
                terms=get_form_value(True),
                email=get_form_value(email),
                emails=get_form_value(email),
            ),
            current_url=lambda: 'www.zulip.com',
            hubot_lozenges_dict={},
            integrations_dict={},
            referrer=dict(
                full_name='John Doe',
                realm=dict(name='zulip.com'),
            ),
            uid='uid',
            token='token',
            message_count=0,
            messages=[dict(header='Header')],
            new_streams=dict(html=''),
            data=dict(title='Title'),
            device_info={"device_browser": "Chrome",
                         "device_os": "Windows",
                         "device_ip": "127.0.0.1",
                         "login_time": "9:33am NewYork, NewYork",
                         },
        )

        context.update(kwargs)
        return context

    def test_markdown_in_template(self):
        # type: () -> None
        template = get_template("tests/test_markdown.html")
        context = {
            'markdown_test_file': "zerver/tests/markdown/test_markdown.md"
        }
        content = template.render(context)

        content_sans_whitespace = content.replace(" ", "").replace('\n', '')
        self.assertEqual(content_sans_whitespace,
                         'header<h1id="hello">Hello!</h1><p>Thisissome<em>boldtext</em>.</p>footer')

    def test_custom_tos_template(self):
        # type: () -> None
        response = self.client_get("/terms/")

        self.assert_in_success_response([u"Thanks for using our products and services (\"Services\"). ",
                                         u"By using our Services, you are agreeing to these terms"],
                                        response)

    def test_custom_terms_of_service_template(self):
        # type: () -> None
        not_configured_message = 'This installation of Zulip does not have a configured ' \
                                 'terms of service'
        with self.settings(TERMS_OF_SERVICE=None):
            response = self.client_get('/terms/')
        self.assert_in_success_response([not_configured_message], response)
        with self.settings(TERMS_OF_SERVICE='zerver/tests/markdown/test_markdown.md'):
            response = self.client_get('/terms/')
        self.assert_in_success_response(['This is some <em>bold text</em>.'], response)
        self.assert_not_in_success_response([not_configured_message], response)

    def test_custom_privacy_policy_template(self):
        # type: () -> None
        not_configured_message = 'This installation of Zulip does not have a configured ' \
                                 'privacy policy'
        with self.settings(PRIVACY_POLICY=None):
            response = self.client_get('/privacy/')
        self.assert_in_success_response([not_configured_message], response)
        with self.settings(PRIVACY_POLICY='zerver/tests/markdown/test_markdown.md'):
            response = self.client_get('/privacy/')
        self.assert_in_success_response(['This is some <em>bold text</em>.'], response)
        self.assert_not_in_success_response([not_configured_message], response)
