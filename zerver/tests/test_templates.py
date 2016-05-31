# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

from django.test import TestCase
from django.template.loader import get_template

from zerver.models import get_user_profile_by_email
from zerver.lib.test_helpers import get_all_templates


class get_form_value(object):
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value


class DummyForm(dict):
    pass


class TemplateTestCase(TestCase):
    """Makes sure that the backend templates render properly

    This test case doesn't test the logic of the templatess. The context
    it provides to the tests is dummy. Please see `get_context` function
    documentation for more information.
    """

    def test_templates(self):
        # Just add the templates whose context has a conflict with other
        # templates' context in `exclude`.
        exclude = ['analytics/activity.html']
        templates = [t for t in get_all_templates() if t not in exclude]
        self.render_templates(templates, self.get_context())

        # Test the excluded templates with updated context.
        update = {'data': [('one', 'two')]}
        self.render_templates(exclude, self.get_context(**update))

    def render_templates(self, templates, context):
        for template in templates:
            template = get_template(template)
            try:
                template.render(context)
            except Exception:
                logging.exception("Exception while rendering '{}'".format(template.template.name))

    def get_context(self, **kwargs):
        """ Get the dummy context for shallow testing.

        The context returned will always contain a paramter called
        `shallow_tested` which tells the signal receiver that the test
        was not rendered in an actual logical test.

        Note: `context` just holds dummy values to make the test
        pass. This context only ensures that the templates do not
        return a 500 error. It doesn't test the logic of the
        templates. Make sure that when you update templates the context
        used in these tests is also updated if there is a need.

        :param kwargs: Keyword arguments can be used to update the base
            context.
        """
        email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(email)

        context = dict(
            shallow_tested=True,
            user_profile=user_profile,
            product_name='testing',
            form=DummyForm(
                full_name=get_form_value('John Doe'),
                terms=get_form_value(True),
                email=get_form_value(email),
            ),
            current_url=lambda: 'www.zulip.com',
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
        )

        context.update(kwargs)
        return context
