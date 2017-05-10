import os.path

from typing import Dict, List, Optional, TypeVar, Any, Text
from django.conf import settings
from django.conf.urls import url
from django.core.urlresolvers import LocaleRegexProvider
from django.utils.module_loading import import_string
from django.utils.safestring import mark_safe
from django.template import loader

from zerver.templatetags.app_filters import render_markdown_path


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

Over time, we expect this registry to grow additional convenience
features for writing and configuring integrations efficiently.
"""

class Integration(object):
    DEFAULT_LOGO_STATIC_PATH_PNG = 'static/images/integrations/logos/{name}.png'
    DEFAULT_LOGO_STATIC_PATH_SVG = 'static/images/integrations/logos/{name}.svg'

    def __init__(self, name, client_name, logo=None, secondary_line_text=None, display_name=None, doc=None):
        # type: (str, str, Optional[str], Optional[str], Optional[str], Optional[str]) -> None
        self.name = name
        self.client_name = client_name
        self.secondary_line_text = secondary_line_text
        self.doc = doc
        self.doc_context = None  # type: Dict[Any, Any]

        if logo is None:
            if os.path.isfile(self.DEFAULT_LOGO_STATIC_PATH_SVG.format(name=name)):
                logo = self.DEFAULT_LOGO_STATIC_PATH_SVG.format(name=name)
            else:
                logo = self.DEFAULT_LOGO_STATIC_PATH_PNG.format(name=name)
        self.logo = logo

        if display_name is None:
            display_name = name.title()
        self.display_name = display_name

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

        if self.doc.endswith('.md'):
            return render_markdown_path(self.doc, doc_context)
        else:
            template = loader.get_template(self.doc)
            return mark_safe(template.render(doc_context))

class EmailIntegration(Integration):
    def is_enabled(self):
        # type: () -> bool
        return settings.EMAIL_GATEWAY_BOT != ""

class WebhookIntegration(Integration):
    DEFAULT_FUNCTION_PATH = 'zerver.webhooks.{name}.view.api_{name}_webhook'
    DEFAULT_URL = 'api/v1/external/{name}'
    DEFAULT_CLIENT_NAME = 'Zulip{name}Webhook'
    DEFAULT_DOC_PATH = '{name}/doc.{ext}'

    def __init__(self, name, client_name=None, logo=None, secondary_line_text=None,
                 function=None, url=None, display_name=None, doc=None):
        # type: (str, Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]) -> None
        if client_name is None:
            client_name = self.DEFAULT_CLIENT_NAME.format(name=name.title())
        super(WebhookIntegration, self).__init__(name, client_name, logo, secondary_line_text, display_name)

        if function is None:
            function = self.DEFAULT_FUNCTION_PATH.format(name=name)

        if isinstance(function, str):
            function = import_string(function)

        self.function = function

        if url is None:
            url = self.DEFAULT_URL.format(name=name)
        self.url = url

        if doc is None:
            path = os.path.join(settings.DEPLOY_ROOT, 'zerver', 'webhooks')
            md_doc = self.DEFAULT_DOC_PATH.format(name=name, ext='md')
            if os.path.exists(os.path.join(path, md_doc)):
                doc = md_doc
            else:
                doc = self.DEFAULT_DOC_PATH.format(name=name, ext='html')

        self.doc = doc

    @property
    def url_object(self):
        # type: () -> LocaleRegexProvider
        return url(self.url, self.function)

class HubotLozenge(Integration):
    GIT_URL_TEMPLATE = "https://github.com/hubot-scripts/hubot-{}"

    def __init__(self, name, display_name=None, logo=None, logo_alt=None, git_url=None):
        # type: (str, Optional[str], Optional[str], Optional[str], Optional[str]) -> None
        if logo_alt is None:
            logo_alt = "{} logo".format(name.title())
        self.logo_alt = logo_alt

        if git_url is None:
            git_url = self.GIT_URL_TEMPLATE.format(name)
        self.git_url = git_url
        super(HubotLozenge, self).__init__(name, name, logo, display_name=display_name)

class GithubIntegration(WebhookIntegration):
    """
    We need this class to don't creating url object for git integrations.
    We want to have one generic url with dispatch function for github service and github webhook.
    """
    @property
    def url_object(self):
        # type: () -> None
        return

WEBHOOK_INTEGRATIONS = [
    WebhookIntegration('airbrake'),
    WebhookIntegration('appfollow', display_name='AppFollow'),
    WebhookIntegration('beanstalk'),
    WebhookIntegration('basecamp'),
    WebhookIntegration('bitbucket2', logo='static/images/integrations/logos/bitbucket.svg', display_name='Bitbucket'),
    WebhookIntegration('bitbucket', display_name='Bitbucket', secondary_line_text='(Enterprise)'),
    WebhookIntegration('circleci', display_name='CircleCI'),
    WebhookIntegration('codeship'),
    WebhookIntegration('crashlytics'),
    WebhookIntegration('delighted', display_name='Delighted'),
    WebhookIntegration('deskdotcom', logo='static/images/integrations/logos/deskcom.png', display_name='Desk.com'),
    WebhookIntegration('freshdesk'),
    GithubIntegration(
        'github',
        function='zerver.webhooks.github.view.api_github_landing',
        display_name='GitHub',
        secondary_line_text='(deprecated)'
    ),
    GithubIntegration(
        'github_webhook',
        display_name='GitHub',
        logo='static/images/integrations/logos/github.svg',
        secondary_line_text='(webhook)',
        function='zerver.webhooks.github_webhook.view.api_github_webhook'
    ),
    WebhookIntegration('gitlab', display_name='GitLab'),
    WebhookIntegration('gogs'),
    WebhookIntegration('gosquared', display_name='GoSquared'),
    WebhookIntegration('greenhouse', display_name='Greenhouse'),
    WebhookIntegration('hellosign', display_name='HelloSign'),
    WebhookIntegration('helloworld', display_name='Hello World'),
    WebhookIntegration('heroku', display_name='Heroku'),
    WebhookIntegration('homeassistant', display_name='Home Assistant'),
    WebhookIntegration('ifttt', function='zerver.webhooks.ifttt.view.api_iftt_app_webhook', display_name='IFTTT'),
    WebhookIntegration('jira', secondary_line_text='(hosted or v5.2+)', display_name='JIRA'),
    WebhookIntegration('librato'),
    WebhookIntegration('mention', display_name='Mention'),
    WebhookIntegration('newrelic', display_name='New Relic'),
    WebhookIntegration('pagerduty'),
    WebhookIntegration('papertrail'),
    WebhookIntegration('pingdom'),
    WebhookIntegration('pivotal', display_name='Pivotal Tracker'),
    WebhookIntegration('semaphore'),
    WebhookIntegration('sentry'),
    WebhookIntegration('slack'),
    WebhookIntegration('solano', display_name='Solano Labs'),
    WebhookIntegration('splunk', display_name='Splunk'),
    WebhookIntegration('stripe', display_name='Stripe'),
    WebhookIntegration('taiga'),
    WebhookIntegration('teamcity'),
    WebhookIntegration('transifex'),
    WebhookIntegration('travis', display_name='Travis CI'),
    WebhookIntegration('trello', secondary_line_text='(webhook)'),
    WebhookIntegration('updown'),
    WebhookIntegration(
        'yo',
        function='zerver.webhooks.yo.view.api_yo_app_webhook',
        display_name='Yo App'
    ),
    WebhookIntegration('wordpress', display_name='WordPress'),
    WebhookIntegration('zapier'),
    WebhookIntegration('zendesk')
]  # type: List[WebhookIntegration]

INTEGRATIONS = {
    'asana': Integration('asana', 'asana', doc='zerver/integrations/asana.html'),
    'capistrano': Integration('capistrano', 'capistrano', doc='zerver/integrations/capistrano.html'),
    'codebase': Integration('codebase', 'codebase', doc='zerver/integrations/codebase.html'),
    'email': EmailIntegration('email', 'email', doc='zerver/integrations/email.html'),
    'git': Integration('git', 'git', doc='zerver/integrations/git.html'),
    'google-calendar': Integration(
        'google-calendar',
        'google-calendar',
        display_name='Google Calendar',
        doc='zerver/integrations/google-calendar.html'
    ),
    'hubot': Integration('hubot', 'hubot', doc='zerver/integrations/hubot.html'),
    'jenkins': Integration(
        'jenkins',
        'jenkins',
        secondary_line_text='(or Hudson)',
        doc='zerver/integrations/jenkins.html'
    ),
    'jira-plugin': Integration(
        'jira-plugin',
        'jira-plugin',
        logo='static/images/integrations/logos/jira.svg',
        secondary_line_text='(locally installed)',
        display_name='JIRA',
        doc='zerver/integrations/jira-plugin.html'
    ),
    'mercurial': Integration(
        'mercurial',
        'mercurial',
        display_name='Mercurial (hg)',
        doc='zerver/integrations/mercurial.html'
    ),
    'nagios': Integration('nagios', 'nagios', doc='zerver/integrations/nagios.html'),
    'openshift': Integration(
        'openshift',
        'openshift',
        display_name='OpenShift',
        doc='zerver/integrations/openshift.html'
    ),
    'perforce': Integration('perforce', 'perforce', doc='zerver/integrations/perforce.html'),
    'phabricator': Integration('phabricator', 'phabricator', doc='zerver/integrations/phabricator.html'),
    'puppet': Integration('puppet', 'puppet', doc='zerver/integrations/puppet.html'),
    'redmine': Integration('redmine', 'redmine', doc='zerver/integrations/redmine.html'),
    'rss': Integration('rss', 'rss', display_name='RSS', doc='zerver/integrations/rss.html'),
    'subversion': Integration('subversion', 'subversion', doc='zerver/integrations/subversion.html'),
    'trac': Integration('trac', 'trac', doc='zerver/integrations/trac.html'),
    'trello-plugin': Integration(
        'trello-plugin',
        'trello-plugin',
        logo='static/images/integrations/logos/trello.svg',
        secondary_line_text='(legacy)',
        display_name='Trello',
        doc='zerver/integrations/trello-plugin.html'
    ),
    'twitter': Integration('twitter', 'twitter', doc='zerver/integrations/twitter.html'),

}  # type: Dict[str, Integration]

HUBOT_LOZENGES = {
    'assembla': HubotLozenge('assembla'),
    'bonusly': HubotLozenge('bonusly'),
    'chartbeat': HubotLozenge('chartbeat'),
    'darksky': HubotLozenge('darksky', display_name='Dark Sky', logo_alt='Dark Sky logo'),
    'hangouts': HubotLozenge('google-hangouts', display_name="Hangouts"),
    'instagram': HubotLozenge('instagram', logo='static/images/integrations/logos/instagram.png'),
    'mailchimp': HubotLozenge('mailchimp', display_name='MailChimp', logo_alt='MailChimp logo'),
    'translate': HubotLozenge('google-translate', display_name="Translate", logo_alt='Google Translate logo'),
    'youtube': HubotLozenge('youtube', display_name='YouTube', logo_alt='YouTube logo')
}

for integration in WEBHOOK_INTEGRATIONS:
    INTEGRATIONS[integration.name] = integration
