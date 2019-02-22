import os
import pathlib

from typing import Dict, List, Optional, Any
from django.conf import settings
from django.conf.urls import url
from django.urls.resolvers import LocaleRegexProvider
from django.utils.module_loading import import_string
from django.utils.translation import ugettext as _


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
    'meta-integration': _('Integration frameworks'),
    'continuous-integration': _('Continuous integration'),
    'customer-support': _('Customer support'),
    'deployment': _('Deployment'),
    'communication': _('Communication'),
    'financial': _('Financial'),
    'hr': _('HR'),
    'marketing': _('Marketing'),
    'misc': _('Miscellaneous'),
    'monitoring': _('Monitoring tools'),
    'project-management': _('Project management'),
    'productivity': _('Productivity'),
    'version-control': _('Version control'),
    'bots': _('Interactive bots'),
}  # type: Dict[str, str]

class Integration:
    DEFAULT_LOGO_STATIC_PATH_PNG = 'static/images/integrations/logos/{name}.png'
    DEFAULT_LOGO_STATIC_PATH_SVG = 'static/images/integrations/logos/{name}.svg'

    def __init__(self, name: str, client_name: str, categories: List[str],
                 logo: Optional[str]=None, secondary_line_text: Optional[str]=None,
                 display_name: Optional[str]=None, doc: Optional[str]=None,
                 stream_name: Optional[str]=None, legacy: Optional[bool]=False) -> None:
        self.name = name
        self.client_name = client_name
        self.secondary_line_text = secondary_line_text
        self.legacy = legacy
        self.doc = doc

        for category in categories:
            if category not in CATEGORIES:
                raise KeyError(  # nocoverage
                    'INTEGRATIONS: ' + name + ' - category \'' +
                    category + '\' is not a key in CATEGORIES.'
                )
        self.categories = list(map((lambda c: CATEGORIES[c]), categories))

        if logo is None:
            logo = self.get_logo_url()
        self.logo = logo

        if display_name is None:
            display_name = name.title()
        self.display_name = display_name

        if stream_name is None:
            stream_name = self.name
        self.stream_name = stream_name

    def is_enabled(self) -> bool:
        return True

    def get_logo_url(self) -> Optional[str]:
        logo_file_path_svg = str(pathlib.PurePath(
            settings.STATIC_ROOT,
            *self.DEFAULT_LOGO_STATIC_PATH_SVG.format(name=self.name).split('/')[1:]
        ))
        logo_file_path_png = str(pathlib.PurePath(
            settings.STATIC_ROOT,
            *self.DEFAULT_LOGO_STATIC_PATH_PNG.format(name=self.name).split('/')[1:]
        ))
        if os.path.isfile(logo_file_path_svg):
            return self.DEFAULT_LOGO_STATIC_PATH_SVG.format(name=self.name)
        elif os.path.isfile(logo_file_path_png):
            return self.DEFAULT_LOGO_STATIC_PATH_PNG.format(name=self.name)

        return None

class BotIntegration(Integration):
    DEFAULT_LOGO_STATIC_PATH_PNG = 'static/generated/bots/{name}/logo.png'
    DEFAULT_LOGO_STATIC_PATH_SVG = 'static/generated/bots/{name}/logo.svg'
    ZULIP_LOGO_STATIC_PATH_PNG = 'static/images/logo/zulip-icon-128x128.png'
    DEFAULT_DOC_PATH = '{name}/doc.md'

    def __init__(self, name: str, categories: List[str], logo: Optional[str]=None,
                 secondary_line_text: Optional[str]=None, display_name: Optional[str]=None,
                 doc: Optional[str]=None) -> None:
        super().__init__(
            name,
            client_name=name,
            categories=categories,
            secondary_line_text=secondary_line_text,
        )

        if logo is None:
            logo_url = self.get_logo_url()
            if logo_url is not None:
                logo = logo_url
            else:
                # TODO: Add a test for this by initializing one in a test.
                logo = self.ZULIP_LOGO_STATIC_PATH_PNG  # nocoverage
        self.logo = logo

        if display_name is None:
            display_name = "{} Bot".format(name.title())  # nocoverage
        else:
            display_name = "{} Bot".format(display_name)
        self.display_name = display_name

        if doc is None:
            doc = self.DEFAULT_DOC_PATH.format(name=name)
        self.doc = doc

class EmailIntegration(Integration):
    def is_enabled(self) -> bool:
        return settings.EMAIL_GATEWAY_PATTERN != ""

class WebhookIntegration(Integration):
    DEFAULT_FUNCTION_PATH = 'zerver.webhooks.{name}.view.api_{name}_webhook'
    DEFAULT_URL = 'api/v1/external/{name}'
    DEFAULT_CLIENT_NAME = 'Zulip{name}Webhook'
    DEFAULT_DOC_PATH = '{name}/doc.{ext}'

    def __init__(self, name: str, categories: List[str], client_name: Optional[str]=None,
                 logo: Optional[str]=None, secondary_line_text: Optional[str]=None,
                 function: Optional[str]=None, url: Optional[str]=None,
                 display_name: Optional[str]=None, doc: Optional[str]=None,
                 stream_name: Optional[str]=None, legacy: Optional[bool]=None) -> None:
        if client_name is None:
            client_name = self.DEFAULT_CLIENT_NAME.format(name=name.title())
        super().__init__(
            name,
            client_name,
            categories,
            logo=logo,
            secondary_line_text=secondary_line_text,
            display_name=display_name,
            stream_name=stream_name,
            legacy=legacy
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
    def url_object(self) -> LocaleRegexProvider:
        return url(self.url, self.function)

class HubotIntegration(Integration):
    GIT_URL_TEMPLATE = "https://github.com/hubot-scripts/hubot-{}"

    def __init__(self, name: str, categories: List[str],
                 display_name: Optional[str]=None, logo: Optional[str]=None,
                 logo_alt: Optional[str]=None, git_url: Optional[str]=None,
                 legacy: bool=False) -> None:
        if logo_alt is None:
            logo_alt = "{} logo".format(name.title())
        self.logo_alt = logo_alt

        if git_url is None:
            git_url = self.GIT_URL_TEMPLATE.format(name)
        self.hubot_docs_url = git_url

        super().__init__(
            name, name, categories,
            logo=logo, display_name=display_name,
            doc = 'zerver/integrations/hubot_common.md',
            legacy=legacy
        )

class GithubIntegration(WebhookIntegration):
    """
    We need this class to don't creating url object for git integrations.
    We want to have one generic url with dispatch function for github service and github webhook.
    """
    def __init__(self, name: str, categories: List[str], client_name: Optional[str]=None,
                 logo: Optional[str]=None, secondary_line_text: Optional[str]=None,
                 function: Optional[str]=None, url: Optional[str]=None,
                 display_name: Optional[str]=None, doc: Optional[str]=None,
                 stream_name: Optional[str]=None, legacy: Optional[bool]=False) -> None:
        url = self.DEFAULT_URL.format(name='github')

        super().__init__(
            name,
            categories,
            client_name=client_name,
            logo=logo,
            secondary_line_text=secondary_line_text,
            function=function,
            url=url,
            display_name=display_name,
            doc=doc,
            stream_name=stream_name,
            legacy=legacy
        )

    @property
    def url_object(self) -> None:
        return

class EmbeddedBotIntegration(Integration):
    '''
    This class acts as a registry for bots verified as safe
    and valid such that these are capable of being deployed on the server.
    '''
    DEFAULT_CLIENT_NAME = 'Zulip{name}EmbeddedBot'

    def __init__(self, name: str, *args: Any, **kwargs: Any) -> None:
        assert kwargs.get("client_name") is None
        client_name = self.DEFAULT_CLIENT_NAME.format(name=name.title())
        super().__init__(
            name, client_name, *args, **kwargs)

EMBEDDED_BOTS = [
    EmbeddedBotIntegration('converter', []),
    EmbeddedBotIntegration('encrypt', []),
    EmbeddedBotIntegration('helloworld', []),
    EmbeddedBotIntegration('virtual_fs', []),
    EmbeddedBotIntegration('giphy', []),
    EmbeddedBotIntegration('followup', []),
]  # type: List[EmbeddedBotIntegration]

WEBHOOK_INTEGRATIONS = [
    WebhookIntegration('airbrake', ['monitoring']),
    WebhookIntegration('ansibletower', ['deployment'], display_name='Ansible Tower'),
    WebhookIntegration('appfollow', ['customer-support'], display_name='AppFollow'),
    WebhookIntegration('appveyor', ['continuous-integration'], display_name='AppVeyor'),
    WebhookIntegration('beanstalk', ['version-control'], stream_name='commits'),
    WebhookIntegration('basecamp', ['project-management']),
    WebhookIntegration('beeminder', ['misc'], display_name='Beeminder'),
    WebhookIntegration(
        'bitbucket2',
        ['version-control'],
        logo='static/images/integrations/logos/bitbucket.svg',
        display_name='Bitbucket',
        stream_name='bitbucket'
    ),
    WebhookIntegration(
        'bitbucket',
        ['version-control'],
        display_name='Bitbucket',
        secondary_line_text='(Enterprise)',
        stream_name='commits',
        legacy=True
    ),
    WebhookIntegration('circleci', ['continuous-integration'], display_name='CircleCI'),
    WebhookIntegration('clubhouse', ['project-management']),
    WebhookIntegration('codeship', ['continuous-integration', 'deployment']),
    WebhookIntegration('crashlytics', ['monitoring']),
    WebhookIntegration('dialogflow', ['customer-support'], display_name='Dialogflow'),
    WebhookIntegration('delighted', ['customer-support', 'marketing'], display_name='Delighted'),
    WebhookIntegration(
        'deskdotcom',
        ['customer-support'],
        logo='static/images/integrations/logos/deskcom.png',
        display_name='Desk.com',
        stream_name='desk'
    ),
    WebhookIntegration('dropbox', ['productivity'], display_name='Dropbox'),
    WebhookIntegration('flock', ['customer-support'], display_name='Flock'),
    WebhookIntegration('freshdesk', ['customer-support']),
    WebhookIntegration('front', ['customer-support'], display_name='Front'),
    GithubIntegration(
        'github',
        ['version-control'],
        display_name='GitHub',
        logo='static/images/integrations/logos/github.svg',
        function='zerver.webhooks.github.view.api_github_webhook',
        stream_name='github'
    ),
    WebhookIntegration('gitlab', ['version-control'], display_name='GitLab'),
    WebhookIntegration('gocd', ['continuous-integration'], display_name='GoCD'),
    WebhookIntegration('gogs', ['version-control'], stream_name='commits'),
    WebhookIntegration('gosquared', ['marketing'], display_name='GoSquared'),
    WebhookIntegration('greenhouse', ['hr'], display_name='Greenhouse'),
    WebhookIntegration('groove', ['customer-support'], display_name='Groove'),
    WebhookIntegration('hellosign', ['productivity', 'hr'], display_name='HelloSign'),
    WebhookIntegration('helloworld', ['misc'], display_name='Hello World'),
    WebhookIntegration('heroku', ['deployment'], display_name='Heroku'),
    WebhookIntegration('homeassistant', ['misc'], display_name='Home Assistant'),
    WebhookIntegration(
        'ifttt',
        ['meta-integration'],
        function='zerver.webhooks.ifttt.view.api_iftt_app_webhook',
        display_name='IFTTT'
    ),
    WebhookIntegration('insping', ['monitoring'], display_name='Insping'),
    WebhookIntegration('intercom', ['customer-support'], display_name='Intercom'),
    WebhookIntegration('jira', ['project-management'], display_name='JIRA'),
    WebhookIntegration('librato', ['monitoring']),
    WebhookIntegration('mention', ['marketing'], display_name='Mention'),
    WebhookIntegration('netlify', ['continuous-integration', 'deployment'], display_name='Netlify'),
    WebhookIntegration('newrelic', ['monitoring'], display_name='New Relic'),
    WebhookIntegration(
        'opbeat',
        ['monitoring'],
        display_name='Opbeat',
        stream_name='opbeat',
        function='zerver.webhooks.opbeat.view.api_opbeat_webhook'
    ),
    WebhookIntegration('opsgenie', ['meta-integration', 'monitoring']),
    WebhookIntegration('pagerduty', ['monitoring'], display_name='PagerDuty'),
    WebhookIntegration('papertrail', ['monitoring']),
    WebhookIntegration('pingdom', ['monitoring']),
    WebhookIntegration('pivotal', ['project-management'], display_name='Pivotal Tracker'),
    WebhookIntegration('raygun', ['monitoring'], display_name="Raygun"),
    WebhookIntegration('reviewboard', ['version-control'], display_name="ReviewBoard"),
    WebhookIntegration('semaphore', ['continuous-integration', 'deployment'], stream_name='builds'),
    WebhookIntegration('sentry', ['monitoring']),
    WebhookIntegration('slack', ['communication']),
    WebhookIntegration('solano', ['continuous-integration'], display_name='Solano Labs'),
    WebhookIntegration('splunk', ['monitoring'], display_name='Splunk'),
    WebhookIntegration('statuspage', ['customer-support'], display_name='Statuspage'),
    WebhookIntegration('stripe', ['financial'], display_name='Stripe'),
    WebhookIntegration('taiga', ['project-management']),
    WebhookIntegration('teamcity', ['continuous-integration']),
    WebhookIntegration('transifex', ['misc']),
    WebhookIntegration('travis', ['continuous-integration'], display_name='Travis CI'),
    WebhookIntegration('trello', ['project-management']),
    WebhookIntegration('updown', ['monitoring']),
    WebhookIntegration(
        'yo',
        ['communication'],
        function='zerver.webhooks.yo.view.api_yo_app_webhook',
        display_name='Yo App'
    ),
    WebhookIntegration('wordpress', ['marketing'], display_name='WordPress'),
    WebhookIntegration('zapier', ['meta-integration']),
    WebhookIntegration('zendesk', ['customer-support']),
    WebhookIntegration('zabbix', ['monitoring'], display_name='Zabbix'),
    WebhookIntegration('gci', ['misc'], display_name='Google Code-in',
                       stream_name='gci'),
]  # type: List[WebhookIntegration]

INTEGRATIONS = {
    'asana': Integration('asana', 'asana', ['project-management'], doc='zerver/integrations/asana.md'),
    'capistrano': Integration(
        'capistrano',
        'capistrano',
        ['deployment'],
        display_name='Capistrano',
        doc='zerver/integrations/capistrano.md'
    ),
    'codebase': Integration('codebase', 'codebase', ['version-control'],
                            doc='zerver/integrations/codebase.md'),
    'discourse': Integration('discourse', 'discourse', ['communication'],
                             doc='zerver/integrations/discourse.md'),
    'email': EmailIntegration('email', 'email', ['communication'],
                              doc='zerver/integrations/email.md'),
    'errbot': Integration('errbot', 'errbot', ['meta-integration', 'bots'],
                          doc='zerver/integrations/errbot.md'),
    'git': Integration('git', 'git', ['version-control'],
                       stream_name='commits', doc='zerver/integrations/git.md'),
    'google-calendar': Integration(
        'google-calendar',
        'google-calendar',
        ['productivity'],
        display_name='Google Calendar',
        doc='zerver/integrations/google-calendar.md'
    ),
    'hubot': Integration('hubot', 'hubot', ['meta-integration', 'bots'], doc='zerver/integrations/hubot.md'),
    'irc': Integration('irc', 'irc', ['communication'], display_name='IRC',
                       doc='zerver/integrations/irc.md'),
    'jenkins': Integration(
        'jenkins',
        'jenkins',
        ['continuous-integration'],
        secondary_line_text='(or Hudson)',
        doc='zerver/integrations/jenkins.md'
    ),
    'jira-plugin': Integration(
        'jira-plugin',
        'jira-plugin',
        ['project-management'],
        logo='static/images/integrations/logos/jira.svg',
        secondary_line_text='(locally installed)',
        display_name='JIRA',
        doc='zerver/integrations/jira-plugin.md',
        stream_name='jira',
        legacy=True
    ),
    'matrix': Integration('matrix', 'matrix', ['communication'],
                          doc='zerver/integrations/matrix.md'),
    'mercurial': Integration(
        'mercurial',
        'mercurial',
        ['version-control'],
        display_name='Mercurial (hg)',
        doc='zerver/integrations/mercurial.md',
        stream_name='commits',
    ),
    'nagios': Integration('nagios', 'nagios', ['monitoring'], doc='zerver/integrations/nagios.md'),
    'openshift': Integration(
        'openshift',
        'openshift',
        ['deployment'],
        display_name='OpenShift',
        doc='zerver/integrations/openshift.md',
        stream_name='deployments',
    ),
    'perforce': Integration('perforce', 'perforce', ['version-control'],
                            doc='zerver/integrations/perforce.md'),
    'phabricator': Integration('phabricator', 'phabricator', ['version-control'],
                               doc='zerver/integrations/phabricator.md'),
    'puppet': Integration('puppet', 'puppet', ['deployment'], doc='zerver/integrations/puppet.md'),
    'redmine': Integration('redmine', 'redmine', ['project-management'],
                           doc='zerver/integrations/redmine.md'),
    'rss': Integration('rss', 'rss', ['communication'],
                       display_name='RSS', doc='zerver/integrations/rss.md'),
    'svn': Integration('svn', 'svn', ['version-control'], doc='zerver/integrations/svn.md'),
    'trac': Integration('trac', 'trac', ['project-management'], doc='zerver/integrations/trac.md'),
    'trello-plugin': Integration(
        'trello-plugin',
        'trello-plugin',
        ['project-management'],
        logo='static/images/integrations/logos/trello.svg',
        secondary_line_text='(legacy)',
        display_name='Trello',
        doc='zerver/integrations/trello-plugin.md',
        stream_name='trello',
        legacy=True
    ),
    'twitter': Integration('twitter', 'twitter', ['customer-support', 'marketing'],
                           # _ needed to get around adblock plus
                           logo='static/images/integrations/logos/twitte_r.svg',
                           doc='zerver/integrations/twitter.md'),
}  # type: Dict[str, Integration]

BOT_INTEGRATIONS = [
    BotIntegration('github_detail', ['version-control', 'bots'],
                   display_name='GitHub Detail'),
    BotIntegration('xkcd', ['bots', 'misc'], display_name='xkcd',
                   logo='static/images/integrations/logos/xkcd.png'),
]  # type: List[BotIntegration]

HUBOT_INTEGRATIONS = [
    HubotIntegration('assembla', ['version-control', 'project-management'],
                     display_name='Assembla', logo_alt='Assembla'),
    HubotIntegration('bonusly', ['hr']),
    HubotIntegration('chartbeat', ['marketing'], display_name='Chartbeat'),
    HubotIntegration('darksky', ['misc'], display_name='Dark Sky',
                     logo_alt='Dark Sky logo'),
    HubotIntegration('google-hangouts', ['communication'], display_name='Google Hangouts',
                     logo_alt='Google Hangouts logo'),
    HubotIntegration('instagram', ['misc'], display_name='Instagram',
                     # _ needed to get around adblock plus
                     logo='static/images/integrations/logos/instagra_m.svg'),
    HubotIntegration('mailchimp', ['communication', 'marketing'],
                     display_name='MailChimp'),
    HubotIntegration('google-translate', ['misc'],
                     display_name="Google Translate", logo_alt='Google Translate logo'),
    HubotIntegration('youtube', ['misc'], display_name='YouTube',
                     # _ needed to get around adblock plus
                     logo='static/images/integrations/logos/youtub_e.svg'),
]  # type: List[HubotIntegration]

for hubot_integration in HUBOT_INTEGRATIONS:
    INTEGRATIONS[hubot_integration.name] = hubot_integration

for webhook_integration in WEBHOOK_INTEGRATIONS:
    INTEGRATIONS[webhook_integration.name] = webhook_integration

for bot_integration in BOT_INTEGRATIONS:
    INTEGRATIONS[bot_integration.name] = bot_integration
