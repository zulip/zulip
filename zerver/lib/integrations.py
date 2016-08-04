from typing import Dict, List, Optional
from django.conf import settings
from django.conf.urls import url

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
    DEFAULT_LOGO_STATIC_PATH = 'static/images/integrations/logos/{name}.png'

    def __init__(self, name, client_name, logo=None, secondary_line_text=None, display_name=None):
        # type: (str, str, Optional[str], Optional[str], Optional[str]) -> None
        self.name = name
        self.client_name = client_name
        self.secondary_line_text = secondary_line_text

        if logo is None:
            logo = self.DEFAULT_LOGO_STATIC_PATH.format(name=name)
        self.logo = logo

        if display_name is None:
            display_name = name.title()
        self.display_name = display_name

    def is_enabled(self):
        # type: () -> bool
        return True

class EmailIntegration(Integration):
    def is_enabled(self):
        return settings.EMAIL_GATEWAY_BOT != ""

class WebhookIntegration(Integration):
    DEFAULT_FUNCTION_PATH = 'zerver.views.webhooks.{name}.api_{name}_webhook'
    DEFAULT_URL = 'api/v1/external/{name}'
    DEFAULT_CLIENT_NAME = 'Zulip{name}Webhook'

    def __init__(self, name, client_name=None, logo=None, secondary_line_text=None,
                 function=None, url=None, display_name=None):
        # type: (str, Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]) -> None
        if client_name is None:
            client_name = self.DEFAULT_CLIENT_NAME.format(name=name.title())
        super(WebhookIntegration, self).__init__(name, client_name, logo, secondary_line_text, display_name)

        if function is None:
            function = self.DEFAULT_FUNCTION_PATH.format(name=name)
        self.function = function

        if url is None:
            url = self.DEFAULT_URL.format(name=name)
        self.url = url

    @property
    def url_object(self):
        return url(self.url, self.function)


WEBHOOK_INTEGRATIONS = [
    WebhookIntegration('airbrake'),
    WebhookIntegration('beanstalk'),
    WebhookIntegration('bitbucket2', logo='static/images/integrations/logos/bitbucket.png', display_name='Bitbucket'),
    WebhookIntegration('bitbucket', secondary_line_text='(Enterprise)'),
    WebhookIntegration('circleci', display_name='CircleCI'),
    WebhookIntegration('codeship'),
    WebhookIntegration('crashlytics'),
    WebhookIntegration('deskdotcom', logo='static/images/integrations/logos/deskcom.png', display_name='Desk.com'),
    WebhookIntegration('freshdesk'),
    WebhookIntegration('github', function='zerver.views.webhooks.github.api_github_landing', display_name='GitHub'),
    WebhookIntegration('helloworld', display_name='Hello World'),
    WebhookIntegration('ifttt', function='zerver.views.webhooks.ifttt.api_iftt_app_webhook', display_name='IFTTT'),
    WebhookIntegration('jira', secondary_line_text='(hosted or v5.2+)', display_name='JIRA'),
    WebhookIntegration('newrelic', display_name='New Relic'),
    WebhookIntegration('pagerduty'),
    WebhookIntegration('pingdom'),
    WebhookIntegration('pivotal', display_name='Pivotal Tracker'),
    WebhookIntegration('semaphore'),
    WebhookIntegration('stash'),
    WebhookIntegration('taiga'),
    WebhookIntegration('teamcity'),
    WebhookIntegration('transifex'),
    WebhookIntegration('travis', display_name='Travis CI'),
    WebhookIntegration('trello', secondary_line_text='(webhook)'),
    WebhookIntegration('updown'),
    WebhookIntegration(
        'yo',
        function='zerver.views.webhooks.yo.api_yo_app_webhook',
        logo='static/images/integrations/logos/yo-app.png',
        display_name='Yo App'
    ),
    WebhookIntegration('zendesk')
]  # type: List[WebhookIntegration]

INTEGRATIONS = {
    'asana': Integration('asana', 'asana'),
    'basecamp': Integration('basecamp', 'basecamp'),
    'capistrano': Integration('capistrano', 'capistrano'),
    'codebase': Integration('codebase', 'codebase'),
    'email': Integration('email', 'email'),
    'git': Integration('git', 'git'),
    'hubot': Integration('hubot', 'hubot'),
    'jenkins': Integration('jenkins', 'jenkins', secondary_line_text='(or Hudson)'),
    'jira-plugin': Integration(
        'jira-plugin',
        'jira-plugin',
        logo='static/images/integrations/logos/jira.png',
        secondary_line_text='(locally installed)',
        display_name='JIRA'
    ),
    'mercurial': Integration('mercurial', 'mercurial', display_name='Mercurial (hg)'),
    'nagios': Integration('nagios', 'nagios'),
    'perforce': Integration('perforce', 'perforce'),
    'phabricator': Integration('phabricator', 'phabricator'),
    'puppet': Integration('puppet', 'puppet'),
    'redmine': Integration('redmine', 'redmine'),
    'rss': Integration('rss', 'rss', display_name='RSS'),
    'subversion': Integration('subversion', 'subversion'),
    'trac': Integration('trac', 'trac'),
    'trello-plugin': Integration(
        'trello-plugin',
        'trello-plugin',
        logo='static/images/integrations/logos/trello.png',
        secondary_line_text='(legacy)',
        display_name='Trello'
    ),
    'twitter': Integration('twitter', 'twitter'),

}  # type: Dict[str, Integration]

for integration in WEBHOOK_INTEGRATIONS:
    INTEGRATIONS[integration.name] = integration
