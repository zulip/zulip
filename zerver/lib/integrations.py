import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from django.conf.urls import url
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls.resolvers import RegexPattern
from django.utils.functional import Promise
from django.utils.module_loading import import_string
from django.utils.translation import ugettext as ugettext_lazy

from zerver.lib.storage import static_path
from zerver.lib.types import Validator

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

CATEGORIES: Dict[str, Promise] = {
    'meta-integration': ugettext_lazy('Integration frameworks'),
    'continuous-integration': ugettext_lazy('Continuous integration'),
    'customer-support': ugettext_lazy('Customer support'),
    'deployment': ugettext_lazy('Deployment'),
    'communication': ugettext_lazy('Communication'),
    'financial': ugettext_lazy('Financial'),
    'hr': ugettext_lazy('HR'),
    'marketing': ugettext_lazy('Marketing'),
    'misc': ugettext_lazy('Miscellaneous'),
    'monitoring': ugettext_lazy('Monitoring tools'),
    'project-management': ugettext_lazy('Project management'),
    'productivity': ugettext_lazy('Productivity'),
    'version-control': ugettext_lazy('Version control'),
    'bots': ugettext_lazy('Interactive bots'),
}

class Integration:
    DEFAULT_LOGO_STATIC_PATH_PNG = 'images/integrations/logos/{name}.png'
    DEFAULT_LOGO_STATIC_PATH_SVG = 'images/integrations/logos/{name}.svg'
    DEFAULT_BOT_AVATAR_PATH = 'images/integrations/bot_avatars/{name}.png'

    def __init__(self, name: str, client_name: str, categories: List[str],
                 logo: Optional[str]=None, secondary_line_text: Optional[str]=None,
                 display_name: Optional[str]=None, doc: Optional[str]=None,
                 stream_name: Optional[str]=None, legacy: bool=False,
                 config_options: Sequence[Tuple[str, str, Validator[object]]]=[]) -> None:
        self.name = name
        self.client_name = client_name
        self.secondary_line_text = secondary_line_text
        self.legacy = legacy
        self.doc = doc

        # Note: Currently only incoming webhook type bots use this list for
        # defining how the bot's BotConfigData should be. Embedded bots follow
        # a different approach.
        self.config_options = config_options

        for category in categories:
            if category not in CATEGORIES:
                raise KeyError(  # nocoverage
                    'INTEGRATIONS: ' + name + ' - category \'' +
                    category + '\' is not a key in CATEGORIES.',
                )
        self.categories = list(map((lambda c: CATEGORIES[c]), categories))

        self.logo_path = logo if logo is not None else self.get_logo_path()
        self.logo_url = self.get_logo_url()

        if display_name is None:
            display_name = name.title()
        self.display_name = display_name

        if stream_name is None:
            stream_name = self.name
        self.stream_name = stream_name

    def is_enabled(self) -> bool:
        return True

    def get_logo_path(self) -> Optional[str]:
        logo_file_path_svg = self.DEFAULT_LOGO_STATIC_PATH_SVG.format(name=self.name)
        logo_file_path_png = self.DEFAULT_LOGO_STATIC_PATH_PNG.format(name=self.name)
        if os.path.isfile(static_path(logo_file_path_svg)):
            return logo_file_path_svg
        elif os.path.isfile(static_path(logo_file_path_png)):
            return logo_file_path_png

        return None

    def get_bot_avatar_path(self) -> Optional[str]:
        if self.logo_path is not None:
            name = os.path.splitext(os.path.basename(self.logo_path))[0]
            return self.DEFAULT_BOT_AVATAR_PATH.format(name=name)

        return None

    def get_logo_url(self) -> Optional[str]:
        if self.logo_path is not None:
            return staticfiles_storage.url(self.logo_path)

        return None

class BotIntegration(Integration):
    DEFAULT_LOGO_STATIC_PATH_PNG = 'generated/bots/{name}/logo.png'
    DEFAULT_LOGO_STATIC_PATH_SVG = 'generated/bots/{name}/logo.svg'
    ZULIP_LOGO_STATIC_PATH_PNG = 'images/logo/zulip-icon-128x128.png'
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
            self.logo_url = self.get_logo_url()
            if self.logo_url is None:
                # TODO: Add a test for this by initializing one in a test.
                logo = staticfiles_storage.url(self.ZULIP_LOGO_STATIC_PATH_PNG)  # nocoverage
        else:
            self.logo_url = staticfiles_storage.url(logo)

        if display_name is None:
            display_name = f"{name.title()} Bot"  # nocoverage
        else:
            display_name = f"{display_name} Bot"
        self.display_name = display_name

        if doc is None:
            doc = self.DEFAULT_DOC_PATH.format(name=name)
        self.doc = doc

class WebhookIntegration(Integration):
    DEFAULT_FUNCTION_PATH = 'zerver.webhooks.{name}.view.api_{name}_webhook'
    DEFAULT_URL = 'api/v1/external/{name}'
    DEFAULT_CLIENT_NAME = 'Zulip{name}Webhook'
    DEFAULT_DOC_PATH = '{name}/doc.{ext}'

    def __init__(self, name: str, categories: List[str], client_name: Optional[str]=None,
                 logo: Optional[str]=None, secondary_line_text: Optional[str]=None,
                 function: Optional[str]=None, url: Optional[str]=None,
                 display_name: Optional[str]=None, doc: Optional[str]=None,
                 stream_name: Optional[str]=None, legacy: bool=False,
                 config_options: Sequence[Tuple[str, str, Validator[object]]]=[]) -> None:
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
            legacy=legacy,
            config_options=config_options,
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
    def url_object(self) -> RegexPattern:
        return url(self.url, self.function)

def split_fixture_path(path: str) -> Tuple[str, str]:
    path, fixture_name = os.path.split(path)
    fixture_name, _ = os.path.splitext(fixture_name)
    integration_name = os.path.split(os.path.dirname(path))[-1]
    return integration_name, fixture_name

@dataclass
class ScreenshotConfig:
    fixture_name: str
    image_name: str = '001.png'
    image_dir: Optional[str] = None
    bot_name: Optional[str] = None
    payload_as_query_param: bool = False
    payload_param_name: str = 'payload'
    extra_params: Dict[str, str] = field(default_factory=dict)
    use_basic_auth: bool = False
    custom_headers: Dict[str, str] = field(default_factory=dict)

def get_fixture_and_image_paths(integration: WebhookIntegration,
                                screenshot_config: ScreenshotConfig) -> Tuple[str, str]:
    fixture_dir = os.path.join('zerver', 'webhooks', integration.name, 'fixtures')
    fixture_path = os.path.join(fixture_dir, screenshot_config.fixture_name)
    image_dir = screenshot_config.image_dir or integration.name
    image_name = screenshot_config.image_name
    image_path = os.path.join('static/images/integrations', image_dir, image_name)
    return fixture_path, image_path

class HubotIntegration(Integration):
    GIT_URL_TEMPLATE = "https://github.com/hubot-scripts/hubot-{}"

    def __init__(self, name: str, categories: List[str],
                 display_name: Optional[str]=None, logo: Optional[str]=None,
                 logo_alt: Optional[str]=None, git_url: Optional[str]=None,
                 legacy: bool=False) -> None:
        if logo_alt is None:
            logo_alt = f"{name.title()} logo"
        self.logo_alt = logo_alt

        if git_url is None:
            git_url = self.GIT_URL_TEMPLATE.format(name)
        self.hubot_docs_url = git_url

        super().__init__(
            name, name, categories,
            logo=logo, display_name=display_name,
            doc = 'zerver/integrations/hubot_common.md',
            legacy=legacy,
        )

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

EMBEDDED_BOTS: List[EmbeddedBotIntegration] = [
    EmbeddedBotIntegration('converter', []),
    EmbeddedBotIntegration('encrypt', []),
    EmbeddedBotIntegration('helloworld', []),
    EmbeddedBotIntegration('virtual_fs', []),
    EmbeddedBotIntegration('giphy', []),
    EmbeddedBotIntegration('followup', []),
]

WEBHOOK_INTEGRATIONS: List[WebhookIntegration] = [
    WebhookIntegration('airbrake', ['monitoring']),
    WebhookIntegration(
        'alertmanager',
        ['monitoring'],
        display_name='Prometheus Alertmanager',
        logo='images/integrations/logos/prometheus.svg',
    ),
    WebhookIntegration('ansibletower', ['deployment'], display_name='Ansible Tower'),
    WebhookIntegration('appfollow', ['customer-support'], display_name='AppFollow'),
    WebhookIntegration('appveyor', ['continuous-integration'], display_name='AppVeyor'),
    WebhookIntegration('beanstalk', ['version-control'], stream_name='commits'),
    WebhookIntegration('basecamp', ['project-management']),
    WebhookIntegration('beeminder', ['misc'], display_name='Beeminder'),
    WebhookIntegration(
        'bitbucket3',
        ['version-control'],
        logo='images/integrations/logos/bitbucket.svg',
        display_name='Bitbucket Server',
        stream_name='bitbucket',
    ),
    WebhookIntegration(
        'bitbucket2',
        ['version-control'],
        logo='images/integrations/logos/bitbucket.svg',
        display_name='Bitbucket',
        stream_name='bitbucket',
    ),
    WebhookIntegration(
        'bitbucket',
        ['version-control'],
        display_name='Bitbucket',
        secondary_line_text='(Enterprise)',
        stream_name='commits',
        legacy=True,
    ),
    WebhookIntegration('buildbot', ['continuous-integration'], display_name='Buildbot'),
    WebhookIntegration('canarytoken', ['monitoring'], display_name='Thinkst Canarytoken'),
    WebhookIntegration('circleci', ['continuous-integration'], display_name='CircleCI'),
    WebhookIntegration('clubhouse', ['project-management']),
    WebhookIntegration('codeship', ['continuous-integration', 'deployment']),
    WebhookIntegration('crashlytics', ['monitoring']),
    WebhookIntegration('dialogflow', ['customer-support'], display_name='Dialogflow'),
    WebhookIntegration('delighted', ['customer-support', 'marketing'], display_name='Delighted'),
    WebhookIntegration(
        'deskdotcom',
        ['customer-support'],
        logo='images/integrations/logos/deskcom.png',
        display_name='Desk.com',
        stream_name='desk',
    ),
    WebhookIntegration('dropbox', ['productivity'], display_name='Dropbox'),
    WebhookIntegration('errbit', ['monitoring'], display_name='Errbit'),
    WebhookIntegration('flock', ['customer-support'], display_name='Flock'),
    WebhookIntegration('freshdesk', ['customer-support']),
    WebhookIntegration('front', ['customer-support'], display_name='Front'),
    WebhookIntegration('gitea', ['version-control'], stream_name='commits'),
    WebhookIntegration(
        'github',
        ['version-control'],
        display_name='GitHub',
        logo='images/integrations/logos/github.svg',
        function='zerver.webhooks.github.view.api_github_webhook',
        stream_name='github',
    ),
    WebhookIntegration('gitlab', ['version-control'], display_name='GitLab'),
    WebhookIntegration('gocd', ['continuous-integration'], display_name='GoCD'),
    WebhookIntegration('gogs', ['version-control'], stream_name='commits'),
    WebhookIntegration('gosquared', ['marketing'], display_name='GoSquared'),
    WebhookIntegration('grafana', ['monitoring'], display_name='Grafana'),
    WebhookIntegration('greenhouse', ['hr'], display_name='Greenhouse'),
    WebhookIntegration('groove', ['customer-support'], display_name='Groove'),
    WebhookIntegration('harbor', ['deployment', 'productivity'], display_name='Harbor'),
    WebhookIntegration('hellosign', ['productivity', 'hr'], display_name='HelloSign'),
    WebhookIntegration('helloworld', ['misc'], display_name='Hello World'),
    WebhookIntegration('heroku', ['deployment'], display_name='Heroku'),
    WebhookIntegration('homeassistant', ['misc'], display_name='Home Assistant'),
    WebhookIntegration(
        'ifttt',
        ['meta-integration'],
        function='zerver.webhooks.ifttt.view.api_iftt_app_webhook',
        display_name='IFTTT',
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
        function='zerver.webhooks.opbeat.view.api_opbeat_webhook',
    ),
    WebhookIntegration('opsgenie', ['meta-integration', 'monitoring']),
    WebhookIntegration('pagerduty', ['monitoring'], display_name='PagerDuty'),
    WebhookIntegration('papertrail', ['monitoring']),
    WebhookIntegration('pingdom', ['monitoring']),
    WebhookIntegration('pivotal', ['project-management'], display_name='Pivotal Tracker'),
    WebhookIntegration('raygun', ['monitoring'], display_name="Raygun"),
    WebhookIntegration('reviewboard', ['version-control'], display_name="ReviewBoard"),
    WebhookIntegration('semaphore', ['continuous-integration', 'deployment']),
    WebhookIntegration('sentry', ['monitoring']),
    WebhookIntegration(
        'slack_incoming',
        ['communication', 'meta-integration'],
        display_name="Slack-compatible webhook",
        logo='images/integrations/logos/slack.svg',
    ),
    WebhookIntegration('slack', ['communication']),
    WebhookIntegration('solano', ['continuous-integration'], display_name='Solano Labs'),
    WebhookIntegration('splunk', ['monitoring'], display_name='Splunk'),
    WebhookIntegration('statuspage', ['customer-support'], display_name='Statuspage'),
    WebhookIntegration('stripe', ['financial'], display_name='Stripe'),
    WebhookIntegration('taiga', ['project-management']),
    WebhookIntegration('teamcity', ['continuous-integration']),
    WebhookIntegration('thinkst', ['monitoring']),
    WebhookIntegration('transifex', ['misc']),
    WebhookIntegration('travis', ['continuous-integration'], display_name='Travis CI'),
    WebhookIntegration('trello', ['project-management']),
    WebhookIntegration('updown', ['monitoring']),
    WebhookIntegration(
        'yo',
        ['communication'],
        function='zerver.webhooks.yo.view.api_yo_app_webhook',
        display_name='Yo App',
    ),
    WebhookIntegration('wordpress', ['marketing'], display_name='WordPress'),
    WebhookIntegration('zapier', ['meta-integration']),
    WebhookIntegration('zendesk', ['customer-support']),
    WebhookIntegration('zabbix', ['monitoring'], display_name='Zabbix'),
    WebhookIntegration('gci', ['misc'], display_name='Google Code-in',
                       stream_name='gci'),
]

INTEGRATIONS: Dict[str, Integration] = {
    'asana': Integration('asana', 'asana', ['project-management'], doc='zerver/integrations/asana.md'),
    'capistrano': Integration(
        'capistrano',
        'capistrano',
        ['deployment'],
        display_name='Capistrano',
        doc='zerver/integrations/capistrano.md',
    ),
    'codebase': Integration('codebase', 'codebase', ['version-control'],
                            doc='zerver/integrations/codebase.md'),
    'discourse': Integration('discourse', 'discourse', ['communication'],
                             doc='zerver/integrations/discourse.md'),
    'email': Integration('email', 'email', ['communication'],
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
        doc='zerver/integrations/google-calendar.md',
    ),
    'hubot': Integration('hubot', 'hubot', ['meta-integration', 'bots'], doc='zerver/integrations/hubot.md'),
    'irc': Integration('irc', 'irc', ['communication'], display_name='IRC',
                       doc='zerver/integrations/irc.md'),
    'jenkins': Integration(
        'jenkins',
        'jenkins',
        ['continuous-integration'],
        secondary_line_text='(or Hudson)',
        doc='zerver/integrations/jenkins.md',
    ),
    'jira-plugin': Integration(
        'jira-plugin',
        'jira-plugin',
        ['project-management'],
        logo='images/integrations/logos/jira.svg',
        secondary_line_text='(locally installed)',
        display_name='JIRA',
        doc='zerver/integrations/jira-plugin.md',
        stream_name='jira',
        legacy=True,
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
        logo='images/integrations/logos/trello.svg',
        secondary_line_text='(legacy)',
        display_name='Trello',
        doc='zerver/integrations/trello-plugin.md',
        stream_name='trello',
        legacy=True,
    ),
    'twitter': Integration('twitter', 'twitter', ['customer-support', 'marketing'],
                           # _ needed to get around adblock plus
                           logo='images/integrations/logos/twitte_r.svg',
                           doc='zerver/integrations/twitter.md'),
}

BOT_INTEGRATIONS: List[BotIntegration] = [
    BotIntegration('github_detail', ['version-control', 'bots'],
                   display_name='GitHub Detail'),
    BotIntegration('xkcd', ['bots', 'misc'], display_name='xkcd',
                   logo='images/integrations/logos/xkcd.png'),
]

HUBOT_INTEGRATIONS: List[HubotIntegration] = [
    HubotIntegration('assembla', ['version-control', 'project-management'],
                     display_name='Assembla', logo_alt='Assembla'),
    HubotIntegration('bonusly', ['hr']),
    HubotIntegration('chartbeat', ['marketing'], display_name='Chartbeat'),
    HubotIntegration('darksky', ['misc'], display_name='Dark Sky',
                     logo_alt='Dark Sky logo'),
    HubotIntegration('instagram', ['misc'], display_name='Instagram',
                     # _ needed to get around adblock plus
                     logo='images/integrations/logos/instagra_m.svg'),
    HubotIntegration('mailchimp', ['communication', 'marketing'],
                     display_name='MailChimp'),
    HubotIntegration('google-translate', ['misc'],
                     display_name="Google Translate", logo_alt='Google Translate logo'),
    HubotIntegration('youtube', ['misc'], display_name='YouTube',
                     # _ needed to get around adblock plus
                     logo='images/integrations/logos/youtub_e.svg'),
]

for hubot_integration in HUBOT_INTEGRATIONS:
    INTEGRATIONS[hubot_integration.name] = hubot_integration

for webhook_integration in WEBHOOK_INTEGRATIONS:
    INTEGRATIONS[webhook_integration.name] = webhook_integration

for bot_integration in BOT_INTEGRATIONS:
    INTEGRATIONS[bot_integration.name] = bot_integration

# Add integrations that don't have automated screenshots here
NO_SCREENSHOT_WEBHOOKS = {
    'beeminder',  # FIXME: fixture's goal.losedate needs to be modified dynamically
    'ifttt',   # Docs don't have a screenshot
    'slack_incoming',   # Docs don't have a screenshot
    'zapier',   # Docs don't have a screenshot
}


DOC_SCREENSHOT_CONFIG: Dict[str, List[ScreenshotConfig]] = {
    'airbrake': [ScreenshotConfig('error_message.json')],
    'alertmanager': [ScreenshotConfig('alert.json', extra_params={'name': 'topic', 'desc': 'description'})],
    'ansibletower': [ScreenshotConfig('job_successful_multiple_hosts.json')],
    'appfollow': [ScreenshotConfig('review.json')],
    'appveyor': [ScreenshotConfig('appveyor_build_success.json')],
    'basecamp': [ScreenshotConfig('doc_active.json')],
    'beanstalk': [ScreenshotConfig('git_multiple.json', use_basic_auth=True, payload_as_query_param=True)],
    # 'beeminder': [ScreenshotConfig('derail_worried.json')],
    'bitbucket': [
        ScreenshotConfig('push.json', '002.png', use_basic_auth=True,
                         payload_as_query_param=True)],
    'bitbucket2': [
        ScreenshotConfig('issue_created.json', '003.png', 'bitbucket',
                         bot_name='Bitbucket Bot')],
    'bitbucket3': [
        ScreenshotConfig('repo_push_update_single_branch.json', '004.png', 'bitbucket',
                         bot_name='Bitbucket Server Bot')],
    'buildbot': [ScreenshotConfig('started.json')],
    'canarytoken': [ScreenshotConfig('canarytoken_real.json')],
    'circleci': [ScreenshotConfig('github_bionic_production_build_success_multiple_parties.json', image_name='001.png'),
                 ScreenshotConfig('bitbucket_private_repo_pull_request_failure.json', image_name='002.png')],
    'clubhouse': [ScreenshotConfig('story_create.json')],
    'codeship': [ScreenshotConfig('error_build.json')],
    'crashlytics': [ScreenshotConfig('issue_message.json')],
    'delighted': [ScreenshotConfig('survey_response_updated_promoter.json')],
    'deskdotcom': [ScreenshotConfig('static_text.txt', '009.png', 'desk', use_basic_auth=True)],
    'dialogflow': [ScreenshotConfig('weather_app.json', extra_params={'email': 'iago@zulip.com'})],
    'dropbox': [ScreenshotConfig('file_updated.json')],
    'errbit': [ScreenshotConfig('error_message.json')],
    'flock': [ScreenshotConfig('messages.json')],
    'freshdesk': [ScreenshotConfig('ticket_created.json', image_name='004.png', use_basic_auth=True)],
    'front': [ScreenshotConfig('inbound_message.json')],
    'gci': [ScreenshotConfig('task_abandoned_by_student.json')],
    'gitea': [ScreenshotConfig('pull_request__merged.json')],
    'github': [ScreenshotConfig('push__1_commit.json')],
    'gitlab': [ScreenshotConfig('push_hook__push_local_branch_without_commits.json')],
    'gocd': [ScreenshotConfig('pipeline.json')],
    'gogs': [ScreenshotConfig('pull_request__opened.json')],
    'gosquared': [ScreenshotConfig('traffic_spike.json', image_name='000.png')],
    'grafana': [ScreenshotConfig('alert.json')],
    'greenhouse': [ScreenshotConfig('candidate_stage_change.json', image_name='000.png')],
    'groove': [ScreenshotConfig('ticket_started.json')],
    'harbor': [ScreenshotConfig('scanning_completed.json')],
    'hellosign': [ScreenshotConfig('signatures_signed_by_one_signatory.json',
                                   payload_as_query_param=True, payload_param_name='json')],
    'helloworld': [ScreenshotConfig('hello.json')],
    'heroku': [ScreenshotConfig('deploy.txt')],
    'homeassistant': [ScreenshotConfig('reqwithtitle.json', image_name='003.png')],
    'insping': [ScreenshotConfig('website_state_available.json')],
    'intercom': [ScreenshotConfig('conversation_admin_replied.json')],
    'jira': [ScreenshotConfig('created_v1.json')],
    'librato': [ScreenshotConfig('three_conditions_alert.json', payload_as_query_param=True)],
    'mention': [ScreenshotConfig('webfeeds.json')],
    'netlify': [ScreenshotConfig('deploy_building.json')],
    'newrelic': [ScreenshotConfig('alert.txt', '002.png')],
    'opbeat': [ScreenshotConfig('error_reopen.json')],
    'opsgenie': [ScreenshotConfig('addrecipient.json', image_name='000.png')],
    'pagerduty': [ScreenshotConfig('trigger_v2.json')],
    'papertrail': [ScreenshotConfig('short_post.json', payload_as_query_param=True)],
    'pingdom': [ScreenshotConfig('http_up_to_down.json', image_name='002.png')],
    'pivotal': [ScreenshotConfig('v5_type_changed.json')],
    'raygun': [ScreenshotConfig('new_error.json')],
    'reviewboard': [ScreenshotConfig('review_request_published.json')],
    'semaphore': [ScreenshotConfig('pull_request.json')],
    'sentry': [ScreenshotConfig('event_for_exception_python.json'),
               ScreenshotConfig('issue_assigned_to_team.json', '002.png')],
    'slack': [ScreenshotConfig('message_info.txt')],
    'solano': [ScreenshotConfig('build_001.json')],
    'splunk': [ScreenshotConfig('search_one_result.json')],
    'statuspage': [ScreenshotConfig('incident_created.json')],
    'stripe': [ScreenshotConfig('charge_succeeded__card.json')],
    'taiga': [ScreenshotConfig('userstory_changed_status.json')],
    'teamcity': [ScreenshotConfig('success.json'), ScreenshotConfig('personal.json', '002.png')],
    'thinkst': [ScreenshotConfig('canary_consolidated_port_scan.json')],
    'transifex': [ScreenshotConfig('', extra_params={'project': 'Zulip Mobile',
                                                     'language': 'en',
                                                     'resource': 'file',
                                                     'reviewed': '100'})],
    'travis': [ScreenshotConfig('build.json', payload_as_query_param=True)],
    'trello': [ScreenshotConfig('adding_comment_to_card.json')],
    'updown': [ScreenshotConfig('check_multiple_events.json')],
    'wordpress': [ScreenshotConfig('publish_post.txt', 'wordpress_post_created.png')],
    'yo': [ScreenshotConfig('', '002.png', 'yo-app', extra_params={'email': 'iago@zulip.com',
                                                                   'username': 'Cordelia'})],
    'zabbix': [ScreenshotConfig('zabbix_alert.json')],
    'zendesk': [ScreenshotConfig('', '007.png', use_basic_auth=True,
                                 extra_params={'ticket_title': 'Test ticket',
                                               'ticket_id': '4',
                                               'message': 'Test Message'})],
}
