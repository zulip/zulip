from __future__ import absolute_import
import os.path

from typing import Dict, List, Optional, TypeVar, Any, Text
from django.conf import settings
from django.conf.urls import url
from django.core.urlresolvers import LocaleRegexProvider
from django.utils.module_loading import import_string
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.template import loader

from zerver.templatetags.app_filters import render_markdown_path
from six.moves import map


"""This module declares all of the (documented) integrations available
in the Zulip server.  The Integration class is used as part of
generating the documentation on the /integrations page, while the
WebhookIntegration class is also used to generate the URLs in
`zproject/urls.py` for webhook integrations.

To add a new non-webhook integration, add code to the INTEGRATIONS
dictionary below.

To add a new webhook integration, declare a WebhookIntegration in the
WEBHOOK_INTEGRATIONS list below (it will be automatically added to
INTEGRATIONS).

To add a new integration category, add to the CATEGORIES dict.

Over time, we expect this registry to grow additional convenience
features for writing and configuring integrations efficiently.
"""

CATEGORIES = {
    'customer_support': _('Customer support'),
    'analytics': _('Analytics'),
    'email': _('Email'),
    'project_management': _('Project management'),
    'version_control': _('Version control'),
    'continuous_integration': _('Continuous integration'),
}  # type: Dict[str, str]

class Integration(object):
    DEFAULT_LOGO_STATIC_PATH_PNG = 'static/images/integrations/logos/{name}.png'
    DEFAULT_LOGO_STATIC_PATH_SVG = 'static/images/integrations/logos/{name}.svg'

    def __init__(self, name, client_name, categories, logo=None, secondary_line_text=None,
                 display_name=None, doc=None, stream_name=None):
        # type: (str, str, List[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]) -> None
        self.name = name
        self.client_name = client_name
        self.secondary_line_text = secondary_line_text
        self.doc = doc
        self.doc_context = None  # type: Dict[Any, Any]

        for category in categories:
            if category not in CATEGORIES:
                raise KeyError(  # nocoverage
                    'INTEGRATIONS: ' + name + ' - category \'' +
                    category + '\' is not a key in CATEGORIES.'
                )
        self.categories = list(map((lambda c: CATEGORIES[c]), categories))

        if logo is None:
            if os.path.isfile(self.DEFAULT_LOGO_STATIC_PATH_SVG.format(name=name)):
                logo = self.DEFAULT_LOGO_STATIC_PATH_SVG.format(name=name)
            else:
                logo = self.DEFAULT_LOGO_STATIC_PATH_PNG.format(name=name)
        self.logo = logo

        if display_name is None:
            display_name = name.title()
        self.display_name = display_name

        if stream_name is None:
            stream_name = self.name
        self.stream_name = stream_name

    def is_enabled(self):
        # type: () -> bool
        return True

    def add_doc_context(self, context):
        # type: (Dict[Any, Any]) -> None
        self.doc_context = context

    @property
    def help_content(self):
        # type: () -> Text
        doc_context = self.doc_context or {}
        return render_markdown_path(self.doc, doc_context)

class EmailIntegration(Integration):
    def is_enabled(self):
        # type: () -> bool
        return settings.EMAIL_GATEWAY_BOT != ""

class WebhookIntegration(Integration):
    DEFAULT_FUNCTION_PATH = 'zerver.webhooks.{name}.view.api_{name}_webhook'
    DEFAULT_URL = 'api/v1/external/{name}'
    DEFAULT_CLIENT_NAME = 'Zulip{name}Webhook'
    DEFAULT_DOC_PATH = '{name}/doc.{ext}'

    def __init__(self, name, categories, client_name=None, logo=None, secondary_line_text=None,
                 function=None, url=None, display_name=None, doc=None, stream_name=None):
        # type: (str, List[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]) -> None
        if client_name is None:
            client_name = self.DEFAULT_CLIENT_NAME.format(name=name.title())
        super(WebhookIntegration, self).__init__(
            name,
            client_name,
            categories,
            logo=logo,
            secondary_line_text=secondary_line_text,
            display_name=display_name,
            stream_name=stream_name
        )

        if function is None:
            function = self.DEFAULT_FUNCTION_PATH.format(name=name)

        if isinstance(function, str):
            function = import_string(function)

        self.function = function

        if url is None:
            url = self.DEFAULT_URL.format(name=name)
        self.url = url

        if doc is None:
            doc = self.DEFAULT_DOC_PATH.format(name=name, ext='md')

        self.doc = doc

    @property
    def url_object(self):
        # type: () -> LocaleRegexProvider
        return url(self.url, self.function)

class HubotLozenge(Integration):
    GIT_URL_TEMPLATE = "https://github.com/hubot-scripts/hubot-{}"

    def __init__(self, name, categories, display_name=None, logo=None, logo_alt=None, git_url=None):
        # type: (str, List[str], Optional[str], Optional[str], Optional[str], Optional[str]) -> None
        if logo_alt is None:
            logo_alt = "{} logo".format(name.title())
        self.logo_alt = logo_alt

        if git_url is None:
            git_url = self.GIT_URL_TEMPLATE.format(name)
        self.git_url = git_url
        super(HubotLozenge, self).__init__(
            name, name, categories,
            logo=logo, display_name=display_name
        )

class GithubIntegration(WebhookIntegration):
    """
    We need this class to don't creating url object for git integrations.
    We want to have one generic url with dispatch function for github service and github webhook.
    """
    def __init__(self, name, categories, client_name=None, logo=None, secondary_line_text=None,
                 function=None, url=None, display_name=None, doc=None, stream_name=None):
        # type: (str, List[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]) -> None
        url = self.DEFAULT_URL.format(name='github')

        super(GithubIntegration, self).__init__(
            name,
            categories,
            client_name=client_name,
            logo=logo,
            secondary_line_text=secondary_line_text,
            function=function,
            url=url,
            display_name=display_name,
            doc=doc,
            stream_name=stream_name
        )

    @property
    def url_object(self):
        # type: () -> None
        return

WEBHOOK_INTEGRATIONS = [
    WebhookIntegration('airbrake', ['analytics']),
    WebhookIntegration('appfollow', ['analytics'], display_name='AppFollow'),
    WebhookIntegration('beanstalk', ['analytics']),
    WebhookIntegration('basecamp', ['analytics']),
    WebhookIntegration(
        'bitbucket2',
        ['analytics'],
        logo='static/images/integrations/logos/bitbucket.svg',
        display_name='Bitbucket',
        stream_name='bitbucket'
    ),
    WebhookIntegration(
        'bitbucket',
        ['analytics'],
        display_name='Bitbucket',
        secondary_line_text='(Enterprise)',
        stream_name='commits'
    ),
    WebhookIntegration('circleci', ['continuous_integration'], display_name='CircleCI'),
    WebhookIntegration('codeship', ['analytics']),
    WebhookIntegration('crashlytics', ['analytics']),
    WebhookIntegration('delighted', ['analytics'], display_name='Delighted'),
    WebhookIntegration(
        'deskdotcom',
        ['analytics'],
        logo='static/images/integrations/logos/deskcom.png',
        display_name='Desk.com',
        stream_name='desk'
    ),
    WebhookIntegration('freshdesk', ['analytics']),
    GithubIntegration(
        'github',
        ['analytics'],
        function='zerver.webhooks.github.view.api_github_landing',
        display_name='GitHub',
        secondary_line_text='(deprecated)',
        stream_name='commits'
    ),
    GithubIntegration(
        'github_webhook',
        ['analytics'],
        display_name='GitHub',
        logo='static/images/integrations/logos/github.svg',
        secondary_line_text='(webhook)',
        function='zerver.webhooks.github_webhook.view.api_github_webhook',
        stream_name='github'
    ),
    WebhookIntegration('gitlab', ['analytics'], display_name='GitLab'),
    WebhookIntegration('gogs', ['analytics']),
    WebhookIntegration('gosquared', ['analytics'], display_name='GoSquared'),
    WebhookIntegration('greenhouse', ['analytics'], display_name='Greenhouse'),
    WebhookIntegration('hellosign', ['analytics'], display_name='HelloSign'),
    WebhookIntegration('helloworld', ['analytics'], display_name='Hello World'),
    WebhookIntegration('heroku', ['analytics'], display_name='Heroku'),
    WebhookIntegration('homeassistant', ['analytics'], display_name='Home Assistant'),
    WebhookIntegration(
        'ifttt',
        ['analytics'],
        function='zerver.webhooks.ifttt.view.api_iftt_app_webhook',
        display_name='IFTTT'
    ),
    WebhookIntegration('jira', ['analytics'], secondary_line_text='(hosted or v5.2+)', display_name='JIRA'),
    WebhookIntegration('librato', ['analytics']),
    WebhookIntegration('mention', ['analytics'], display_name='Mention'),
    WebhookIntegration('newrelic', ['analytics'], display_name='New Relic'),
    WebhookIntegration('pagerduty', ['analytics']),
    WebhookIntegration('papertrail', ['analytics']),
    WebhookIntegration('pingdom', ['analytics']),
    WebhookIntegration('pivotal', ['analytics'], display_name='Pivotal Tracker'),
    WebhookIntegration('semaphore', ['analytics'], stream_name='builds'),
    WebhookIntegration('sentry', ['analytics']),
    WebhookIntegration('slack', ['analytics']),
    WebhookIntegration('solano', ['analytics'], display_name='Solano Labs'),
    WebhookIntegration('splunk', ['analytics'], display_name='Splunk'),
    WebhookIntegration('stripe', ['analytics'], display_name='Stripe'),
    WebhookIntegration('taiga', ['analytics']),
    WebhookIntegration('teamcity', ['analytics']),
    WebhookIntegration('transifex', ['analytics']),
    WebhookIntegration('travis', ['analytics'], display_name='Travis CI'),
    WebhookIntegration('trello', ['analytics'], secondary_line_text='(webhook)'),
    WebhookIntegration('updown', ['analytics']),
    WebhookIntegration(
        'yo',
        ['analytics'],
        function='zerver.webhooks.yo.view.api_yo_app_webhook',
        display_name='Yo App'
    ),
    WebhookIntegration('wordpress', ['analytics'], display_name='WordPress'),
    WebhookIntegration('zapier', ['analytics']),
    WebhookIntegration('zendesk', ['analytics'])
]  # type: List[WebhookIntegration]

INTEGRATIONS = {
    'asana': Integration('asana', 'asana', ['analytics'], doc='zerver/integrations/asana.md'),
    'capistrano': Integration(
        'capistrano',
        'capistrano',
        ['analytics'],
        display_name='Capistrano',
        doc='zerver/integrations/capistrano.md'
    ),
    'codebase': Integration('codebase', 'codebase', ['analytics'], doc='zerver/integrations/codebase.md'),
    'email': EmailIntegration('email', 'email', ['analytics'], doc='zerver/integrations/email.md'),
    'git': Integration('git', 'git', ['analytics'], doc='zerver/integrations/git.md'),
    'google-calendar': Integration(
        'google-calendar',
        'google-calendar',
        ['analytics'],
        display_name='Google Calendar',
        doc='zerver/integrations/google-calendar.md'
    ),
    'hubot': Integration('hubot', 'hubot', ['analytics'], doc='zerver/integrations/hubot.md'),
    'jenkins': Integration(
        'jenkins',
        'jenkins',
        ['analytics'],
        secondary_line_text='(or Hudson)',
        doc='zerver/integrations/jenkins.md'
    ),
    'jira-plugin': Integration(
        'jira-plugin',
        'jira-plugin',
        ['analytics'],
        logo='static/images/integrations/logos/jira.svg',
        secondary_line_text='(locally installed)',
        display_name='JIRA',
        doc='zerver/integrations/jira-plugin.md',
        stream_name='jira',
    ),
    'mercurial': Integration(
        'mercurial',
        'mercurial',
        ['analytics'],
        display_name='Mercurial (hg)',
        doc='zerver/integrations/mercurial.md',
        stream_name='commits',
    ),
    'nagios': Integration('nagios', 'nagios', ['analytics'], doc='zerver/integrations/nagios.md'),
    'openshift': Integration(
        'openshift',
        'openshift',
        ['analytics'],
        display_name='OpenShift',
        doc='zerver/integrations/openshift.md',
        stream_name='deployments',
    ),
    'perforce': Integration('perforce', 'perforce', ['analytics'], doc='zerver/integrations/perforce.md'),
    'phabricator': Integration('phabricator', 'phabricator', ['analytics'], doc='zerver/integrations/phabricator.md'),
    'puppet': Integration('puppet', 'puppet', ['analytics'], doc='zerver/integrations/puppet.md'),
    'redmine': Integration('redmine', 'redmine', ['analytics'], doc='zerver/integrations/redmine.md'),
    'rss': Integration('rss', 'rss', ['analytics'], display_name='RSS', doc='zerver/integrations/rss.md'),
    'svn': Integration('svn', 'svn', ['analytics'], doc='zerver/integrations/svn.md'),
    'trac': Integration('trac', 'trac', ['analytics'], doc='zerver/integrations/trac.md'),
    'trello-plugin': Integration(
        'trello-plugin',
        'trello-plugin',
        ['analytics'],
        logo='static/images/integrations/logos/trello.svg',
        secondary_line_text='(legacy)',
        display_name='Trello',
        doc='zerver/integrations/trello-plugin.md',
        stream_name='trello',
    ),
    'twitter': Integration('twitter', 'twitter', ['analytics'], doc='zerver/integrations/twitter.md'),
}  # type: Dict[str, Integration]

HUBOT_LOZENGES = {
    'assembla': HubotLozenge('assembla', ['analytics']),
    'bonusly': HubotLozenge('bonusly', ['analytics']),
    'chartbeat': HubotLozenge('chartbeat', ['analytics']),
    'darksky': HubotLozenge('darksky', ['analytics'], display_name='Dark Sky', logo_alt='Dark Sky logo'),
    'hangouts': HubotLozenge('google-hangouts', ['analytics'], display_name="Hangouts"),
    'instagram': HubotLozenge('instagram', ['analytics'], logo='static/images/integrations/logos/instagram.png'),
    'mailchimp': HubotLozenge('mailchimp', ['analytics'], display_name='MailChimp', logo_alt='MailChimp logo'),
    'translate': HubotLozenge('google-translate', ['analytics'], display_name="Translate", logo_alt='Google Translate logo'),
    'youtube': HubotLozenge('youtube', ['analytics'], display_name='YouTube', logo_alt='YouTube logo')
}

for integration in WEBHOOK_INTEGRATIONS:
    INTEGRATIONS[integration.name] = integration
