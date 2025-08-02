import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, TypeAlias

from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import HttpRequest, HttpResponseBase
from django.urls import URLPattern, path
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy
from django.views.decorators.csrf import csrf_exempt
from django_stubs_ext import StrPromise

from zerver.lib.storage import static_path
from zerver.lib.validator import check_bool, check_string
from zerver.lib.webhooks.common import WebhookConfigOption, WebhookUrlOption

"""This module declares all of the (documented) integrations available
in the Zulip server.  The Integration class is used as part of
generating the documentation on the /integrations/ page, while the
WebhookIntegration class is also used to generate the URLs in
`zproject/urls.py` for webhook integrations.

To add a new non-webhook integration, add code to the INTEGRATIONS
dictionary below.

To add a new webhook integration, declare a WebhookIntegration in the
WEBHOOK_INTEGRATIONS list below (it will be automatically added to
INTEGRATIONS).

To add a new integration category, add to either the CATEGORIES or
META_CATEGORY dicts below. The META_CATEGORY dict is for categories
that do not describe types of tools (e.g., bots or frameworks).

Over time, we expect this registry to grow additional convenience
features for writing and configuring integrations efficiently.
"""

OptionValidator: TypeAlias = Callable[[str, str], str | bool | None]

META_CATEGORY: dict[str, StrPromise] = {
    "meta-integration": gettext_lazy("Integration frameworks"),
    "bots": gettext_lazy("Interactive bots"),
}

CATEGORIES: dict[str, StrPromise] = {
    **META_CATEGORY,
    "continuous-integration": gettext_lazy("Continuous integration"),
    "customer-support": gettext_lazy("Customer support"),
    "deployment": gettext_lazy("Deployment"),
    "entertainment": gettext_lazy("Entertainment"),
    "communication": gettext_lazy("Communication"),
    "financial": gettext_lazy("Financial"),
    "hr": gettext_lazy("Human resources"),
    "marketing": gettext_lazy("Marketing"),
    "misc": gettext_lazy("Miscellaneous"),
    "monitoring": gettext_lazy("Monitoring"),
    "project-management": gettext_lazy("Project management"),
    "productivity": gettext_lazy("Productivity"),
    "version-control": gettext_lazy("Version control"),
}


class Integration:
    DEFAULT_LOGO_STATIC_PATH_PNG = "images/integrations/logos/{name}.png"
    DEFAULT_LOGO_STATIC_PATH_SVG = "images/integrations/logos/{name}.svg"
    DEFAULT_BOT_AVATAR_PATH = "images/integrations/bot_avatars/{name}.png"
    DEFAULT_DOC_PATH = "zerver/integrations/{name}.md"

    def __init__(
        self,
        name: str,
        categories: list[str],
        client_name: str | None = None,
        logo: str | None = None,
        secondary_line_text: str | None = None,
        display_name: str | None = None,
        doc: str | None = None,
        stream_name: str | None = None,
        legacy: bool = False,
        config_options: Sequence[WebhookConfigOption] = [],
        url_options: Sequence[WebhookUrlOption] = [],
    ) -> None:
        self.name = name
        self.client_name = client_name if client_name is not None else name
        self.secondary_line_text = secondary_line_text
        self.legacy = legacy
        self.doc = doc
        self.url_options = url_options

        # Note: Currently only incoming webhook type bots use this list for
        # defining how the bot's BotConfigData should be. Embedded bots follow
        # a different approach.
        self.config_options = config_options

        for category in categories:
            if category not in CATEGORIES:
                raise KeyError(  # nocoverage
                    "INTEGRATIONS: "
                    + name
                    + " - category '"
                    + category
                    + "' is not a key in CATEGORIES.",
                )
        self.categories = [CATEGORIES[c] for c in categories]

        self.logo_path = logo if logo is not None else self.get_logo_path()
        # TODO: Enforce that all integrations have logo_url with an assertion.
        self.logo_url = self.get_logo_url()

        if display_name is None:
            display_name = name.title()
        self.display_name = display_name

        if doc is None:
            doc = self.DEFAULT_DOC_PATH.format(name=self.name)
        self.doc = doc

        if stream_name is None:
            stream_name = self.name
        self.stream_name = stream_name

    def is_enabled(self) -> bool:
        return True

    def get_logo_path(self) -> str | None:
        logo_file_path_svg = self.DEFAULT_LOGO_STATIC_PATH_SVG.format(name=self.name)
        logo_file_path_png = self.DEFAULT_LOGO_STATIC_PATH_PNG.format(name=self.name)
        if os.path.isfile(static_path(logo_file_path_svg)):
            return logo_file_path_svg
        elif os.path.isfile(static_path(logo_file_path_png)):
            return logo_file_path_png

        return None

    def get_bot_avatar_path(self) -> str | None:
        if self.logo_path is not None:
            name = os.path.splitext(os.path.basename(self.logo_path))[0]
            return self.DEFAULT_BOT_AVATAR_PATH.format(name=name)

        return None

    def get_logo_url(self) -> str | None:
        if self.logo_path is not None:
            return staticfiles_storage.url(self.logo_path)

        return None

    def get_translated_categories(self) -> list[str]:
        return [str(category) for category in self.categories]


class BotIntegration(Integration):
    DEFAULT_LOGO_STATIC_PATH_PNG = "generated/bots/{name}/logo.png"
    DEFAULT_LOGO_STATIC_PATH_SVG = "generated/bots/{name}/logo.svg"
    ZULIP_LOGO_STATIC_PATH_PNG = "images/logo/zulip-icon-128x128.png"
    DEFAULT_DOC_PATH = "{name}/doc.md"

    def __init__(
        self,
        name: str,
        categories: list[str],
        logo: str | None = None,
        secondary_line_text: str | None = None,
        display_name: str | None = None,
        doc: str | None = None,
    ) -> None:
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


class PythonAPIIntegration(Integration):
    DEFAULT_DOC_PATH = "{directory_name}/doc.md"

    def __init__(
        self,
        name: str,
        categories: list[str],
        client_name: str | None = None,
        logo: str | None = None,
        secondary_line_text: str | None = None,
        display_name: str | None = None,
        directory_name: str | None = None,
        doc: str | None = None,
        stream_name: str | None = None,
        legacy: bool = False,
    ) -> None:
        if directory_name is None:
            directory_name = name
        self.directory_name = directory_name

        # Assign before super(), to use self.directory_name instead of self.name
        if doc is None:
            doc = self.DEFAULT_DOC_PATH.format(directory_name=self.directory_name)
        self.doc = doc

        super().__init__(
            name,
            categories,
            client_name=client_name,
            logo=logo,
            secondary_line_text=secondary_line_text,
            display_name=display_name,
            doc=doc,
            stream_name=stream_name,
            legacy=legacy,
        )


class WebhookIntegration(Integration):
    DEFAULT_FUNCTION_PATH = "zerver.webhooks.{name}.view.api_{name}_webhook"
    DEFAULT_URL = "api/v1/external/{name}"
    DEFAULT_CLIENT_NAME = "Zulip{name}Webhook"
    DEFAULT_DOC_PATH = "{name}/doc.md"

    def __init__(
        self,
        name: str,
        categories: list[str],
        client_name: str | None = None,
        logo: str | None = None,
        secondary_line_text: str | None = None,
        function: str | None = None,
        url: str | None = None,
        display_name: str | None = None,
        doc: str | None = None,
        stream_name: str | None = None,
        legacy: bool = False,
        config_options: Sequence[WebhookConfigOption] = [],
        url_options: Sequence[WebhookUrlOption] = [],
        dir_name: str | None = None,
    ) -> None:
        if client_name is None:
            client_name = self.DEFAULT_CLIENT_NAME.format(name=name.title())
        super().__init__(
            name,
            categories,
            client_name=client_name,
            logo=logo,
            secondary_line_text=secondary_line_text,
            display_name=display_name,
            stream_name=stream_name,
            legacy=legacy,
            config_options=config_options,
            url_options=url_options,
        )

        if function is None:
            function = self.DEFAULT_FUNCTION_PATH.format(name=name)
        self.function_name = function

        if url is None:
            url = self.DEFAULT_URL.format(name=name)
        self.url = url

        if doc is None:
            doc = self.DEFAULT_DOC_PATH.format(name=name)
        self.doc = doc

        if dir_name is None:
            dir_name = self.name
        self.dir_name = dir_name

    def get_function(self) -> Callable[[HttpRequest], HttpResponseBase]:
        return import_string(self.function_name)

    @csrf_exempt
    def view(self, request: HttpRequest) -> HttpResponseBase:
        # Lazily load the real view function to improve startup performance.
        function = self.get_function()
        assert function.csrf_exempt  # type: ignore[attr-defined] # ensure the above @csrf_exempt is justified
        return function(request)

    @property
    def url_object(self) -> URLPattern:
        return path(self.url, self.view)


def split_fixture_path(path: str) -> tuple[str, str]:
    path, fixture_name = os.path.split(path)
    fixture_name, _ = os.path.splitext(fixture_name)
    integration_name = os.path.split(os.path.dirname(path))[-1]
    return integration_name, fixture_name


@dataclass
class WebhookScreenshotConfig:
    fixture_name: str
    image_name: str = "001.png"
    image_dir: str | None = None
    bot_name: str | None = None
    payload_as_query_param: bool = False
    payload_param_name: str = "payload"
    extra_params: dict[str, str] = field(default_factory=dict)
    use_basic_auth: bool = False
    custom_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class FixturelessScreenshotConfig:
    message: str
    topic: str
    channel: str | None = None
    image_name: str = "001.png"
    image_dir: str | None = None
    bot_name: str | None = None


def get_fixture_path(
    integration: WebhookIntegration, screenshot_config: WebhookScreenshotConfig
) -> str:
    fixture_dir = os.path.join("zerver", "webhooks", integration.dir_name, "fixtures")
    fixture_path = os.path.join(fixture_dir, screenshot_config.fixture_name)
    return fixture_path


def get_image_path(
    integration: Integration,
    screenshot_config: WebhookScreenshotConfig | FixturelessScreenshotConfig,
) -> str:
    image_dir = screenshot_config.image_dir or integration.name
    image_name = screenshot_config.image_name
    image_path = os.path.join("static/images/integrations", image_dir, image_name)
    return image_path


class HubotIntegration(Integration):
    GIT_URL_TEMPLATE = "https://github.com/hubot-archive/hubot-{}"
    SECONDARY_LINE_TEXT = "(Hubot script)"
    DOC_PATH = "zerver/integrations/hubot_common.md"

    def __init__(
        self,
        name: str,
        categories: list[str],
        display_name: str | None = None,
        logo: str | None = None,
        git_url: str | None = None,
        legacy: bool = False,
    ) -> None:
        if git_url is None:
            git_url = self.GIT_URL_TEMPLATE.format(name)
        self.hubot_docs_url = git_url

        super().__init__(
            name,
            categories,
            logo=logo,
            secondary_line_text=self.SECONDARY_LINE_TEXT,
            display_name=display_name,
            doc=self.DOC_PATH,
            legacy=legacy,
        )


class EmbeddedBotIntegration(Integration):
    """
    This class acts as a registry for bots verified as safe
    and valid such that these are capable of being deployed on the server.
    """

    DEFAULT_CLIENT_NAME = "Zulip{name}EmbeddedBot"

    def __init__(self, name: str, *args: Any, **kwargs: Any) -> None:
        assert kwargs.get("client_name") is None
        kwargs["client_name"] = self.DEFAULT_CLIENT_NAME.format(name=name.title())
        super().__init__(name, *args, **kwargs)


EMBEDDED_BOTS: list[EmbeddedBotIntegration] = [
    EmbeddedBotIntegration("converter", []),
    EmbeddedBotIntegration("encrypt", []),
    EmbeddedBotIntegration("helloworld", []),
    EmbeddedBotIntegration("virtual_fs", []),
    EmbeddedBotIntegration("giphy", []),
    EmbeddedBotIntegration("followup", []),
]

WEBHOOK_INTEGRATIONS: list[WebhookIntegration] = [
    WebhookIntegration("airbrake", ["monitoring"]),
    WebhookIntegration("airbyte", ["monitoring"]),
    WebhookIntegration(
        "alertmanager",
        ["monitoring"],
        display_name="Prometheus Alertmanager",
        logo="images/integrations/logos/prometheus.svg",
    ),
    WebhookIntegration("ansibletower", ["deployment"], display_name="Ansible Tower"),
    WebhookIntegration("appfollow", ["customer-support"], display_name="AppFollow"),
    WebhookIntegration("appveyor", ["continuous-integration"], display_name="AppVeyor"),
    WebhookIntegration(
        "azuredevops",
        ["version-control"],
        display_name="AzureDevOps",
        url_options=[WebhookUrlOption(name="branches", label="", validator=check_string)],
    ),
    WebhookIntegration("beanstalk", ["version-control"], stream_name="commits"),
    WebhookIntegration("basecamp", ["project-management"]),
    WebhookIntegration("beeminder", ["misc"], display_name="Beeminder"),
    WebhookIntegration(
        "bitbucket3",
        ["version-control"],
        logo="images/integrations/logos/bitbucket.svg",
        display_name="Bitbucket Server",
        stream_name="bitbucket",
        url_options=[WebhookUrlOption(name="branches", label="", validator=check_string)],
    ),
    WebhookIntegration(
        "bitbucket2",
        ["version-control"],
        logo="images/integrations/logos/bitbucket.svg",
        display_name="Bitbucket",
        stream_name="bitbucket",
        url_options=[WebhookUrlOption(name="branches", label="", validator=check_string)],
    ),
    WebhookIntegration(
        "bitbucket",
        ["version-control"],
        display_name="Bitbucket",
        secondary_line_text="(Enterprise)",
        stream_name="commits",
        legacy=True,
    ),
    WebhookIntegration("buildbot", ["continuous-integration"]),
    WebhookIntegration("canarytoken", ["monitoring"], display_name="Thinkst Canarytokens"),
    WebhookIntegration("circleci", ["continuous-integration"], display_name="CircleCI"),
    WebhookIntegration("clubhouse", ["project-management"]),
    WebhookIntegration("codeship", ["continuous-integration", "deployment"]),
    WebhookIntegration("crashlytics", ["monitoring"]),
    WebhookIntegration("dialogflow", ["customer-support"]),
    WebhookIntegration("delighted", ["customer-support", "marketing"]),
    WebhookIntegration("dropbox", ["productivity"]),
    WebhookIntegration("errbit", ["monitoring"]),
    WebhookIntegration("flock", ["customer-support"]),
    WebhookIntegration("freshdesk", ["customer-support"]),
    WebhookIntegration("freshping", ["monitoring"]),
    WebhookIntegration("freshstatus", ["monitoring", "customer-support"]),
    WebhookIntegration("front", ["customer-support"]),
    WebhookIntegration(
        "gitea",
        ["version-control"],
        stream_name="commits",
        url_options=[WebhookUrlOption(name="branches", label="", validator=check_string)],
    ),
    WebhookIntegration(
        "github",
        ["version-control"],
        display_name="GitHub",
        function="zerver.webhooks.github.view.api_github_webhook",
        stream_name="github",
        url_options=[
            WebhookUrlOption(name="branches", label="", validator=check_string),
            WebhookUrlOption(
                name="ignore_private_repositories",
                label="Exclude notifications from private repositories",
                validator=check_bool,
            ),
        ],
    ),
    WebhookIntegration(
        "githubsponsors",
        ["financial"],
        display_name="GitHub Sponsors",
        logo="images/integrations/logos/github.svg",
        dir_name="github",
        function="zerver.webhooks.github.view.api_github_webhook",
        doc="github/githubsponsors.md",
        stream_name="github",
    ),
    WebhookIntegration(
        "gitlab",
        ["version-control"],
        display_name="GitLab",
        url_options=[WebhookUrlOption(name="branches", label="", validator=check_string)],
    ),
    WebhookIntegration("gocd", ["continuous-integration"], display_name="GoCD"),
    WebhookIntegration(
        "gogs",
        ["version-control"],
        stream_name="commits",
        url_options=[WebhookUrlOption(name="branches", label="", validator=check_string)],
    ),
    WebhookIntegration("gosquared", ["marketing"], display_name="GoSquared"),
    WebhookIntegration("grafana", ["monitoring"]),
    WebhookIntegration("greenhouse", ["hr"]),
    WebhookIntegration("groove", ["customer-support"]),
    WebhookIntegration("harbor", ["deployment", "productivity"]),
    WebhookIntegration("hellosign", ["productivity", "hr"], display_name="HelloSign"),
    WebhookIntegration("helloworld", ["misc"], display_name="Hello World"),
    WebhookIntegration("heroku", ["deployment"]),
    WebhookIntegration("homeassistant", ["misc"], display_name="Home Assistant"),
    WebhookIntegration(
        "ifttt",
        ["meta-integration"],
        function="zerver.webhooks.ifttt.view.api_iftt_app_webhook",
        display_name="IFTTT",
    ),
    WebhookIntegration("insping", ["monitoring"]),
    WebhookIntegration("intercom", ["customer-support"]),
    # Avoid collision with jira-plugin's doc "jira/doc.md".
    WebhookIntegration("jira", ["project-management"], doc="jira/jira-doc.md"),
    WebhookIntegration("jotform", ["misc"]),
    WebhookIntegration("json", ["misc"], display_name="JSON formatter"),
    WebhookIntegration("librato", ["monitoring"]),
    WebhookIntegration("lidarr", ["entertainment"]),
    WebhookIntegration("linear", ["project-management"]),
    WebhookIntegration("mention", ["marketing"]),
    WebhookIntegration("netlify", ["continuous-integration", "deployment"]),
    WebhookIntegration("newrelic", ["monitoring"], display_name="New Relic"),
    WebhookIntegration("opencollective", ["financial"], display_name="Open Collective"),
    WebhookIntegration("openproject", ["project-management"], display_name="OpenProject"),
    WebhookIntegration("opensearch", ["monitoring"], display_name="OpenSearch"),
    WebhookIntegration(
        "opsgenie",
        ["meta-integration", "monitoring"],
        url_options=[
            WebhookUrlOption(
                name="eu_region",
                label="Use Opsgenie's European service region",
                validator=check_bool,
            )
        ],
    ),
    WebhookIntegration("pagerduty", ["monitoring"], display_name="PagerDuty"),
    WebhookIntegration("papertrail", ["monitoring"]),
    WebhookIntegration("patreon", ["financial"]),
    WebhookIntegration("pingdom", ["monitoring"]),
    WebhookIntegration("pivotal", ["project-management"], display_name="Pivotal Tracker"),
    WebhookIntegration("radarr", ["entertainment"]),
    WebhookIntegration("raygun", ["monitoring"]),
    WebhookIntegration("reviewboard", ["version-control"], display_name="Review Board"),
    WebhookIntegration(
        "rhodecode",
        ["version-control"],
        display_name="RhodeCode",
        url_options=[WebhookUrlOption(name="branches", label="", validator=check_string)],
    ),
    WebhookIntegration("rundeck", ["deployment"]),
    WebhookIntegration("semaphore", ["continuous-integration", "deployment"]),
    WebhookIntegration("sentry", ["monitoring"]),
    WebhookIntegration(
        "slack_incoming",
        ["communication", "meta-integration"],
        display_name="Slack-compatible webhook",
        logo="images/integrations/logos/slack.svg",
    ),
    WebhookIntegration("slack", ["communication"]),
    WebhookIntegration("sonarqube", ["continuous-integration"], display_name="SonarQube"),
    WebhookIntegration("sonarr", ["entertainment"]),
    WebhookIntegration("splunk", ["monitoring"]),
    WebhookIntegration("statuspage", ["customer-support"]),
    WebhookIntegration("stripe", ["financial"]),
    WebhookIntegration("taiga", ["project-management"]),
    WebhookIntegration("teamcity", ["continuous-integration"]),
    WebhookIntegration("thinkst", ["monitoring"]),
    WebhookIntegration("transifex", ["misc"]),
    WebhookIntegration("travis", ["continuous-integration"], display_name="Travis CI"),
    WebhookIntegration("trello", ["project-management"]),
    WebhookIntegration("updown", ["monitoring"]),
    WebhookIntegration("uptimerobot", ["monitoring"], display_name="UptimeRobot"),
    WebhookIntegration("wekan", ["productivity"]),
    WebhookIntegration("wordpress", ["marketing"], display_name="WordPress"),
    WebhookIntegration("zapier", ["meta-integration"]),
    WebhookIntegration("zendesk", ["customer-support"]),
    WebhookIntegration("zabbix", ["monitoring"]),
]

INTEGRATIONS: dict[str, Integration] = {
    "asana": Integration("asana", ["project-management"]),
    "big-blue-button": Integration(
        "big-blue-button", ["communication"], display_name="BigBlueButton"
    ),
    "capistrano": Integration("capistrano", ["deployment"], display_name="Capistrano"),
    "discourse": Integration("discourse", ["communication"]),
    "email": Integration("email", ["communication"]),
    "errbot": Integration("errbot", ["meta-integration", "bots"]),
    "giphy": Integration("giphy", ["misc"], display_name="GIPHY"),
    "github-actions": Integration(
        "github-actions", ["continuous-integration"], display_name="GitHub Actions"
    ),
    "hubot": Integration("hubot", ["meta-integration", "bots"]),
    "jenkins": Integration("jenkins", ["continuous-integration"]),
    "jitsi": Integration("jitsi", ["communication"], display_name="Jitsi Meet"),
    "mastodon": Integration("mastodon", ["communication"]),
    "notion": Integration("notion", ["productivity"]),
    "onyx": Integration("onyx", ["productivity"], logo="images/integrations/logos/onyx.png"),
    "puppet": Integration("puppet", ["deployment"]),
    "redmine": Integration("redmine", ["project-management"]),
    "zoom": Integration("zoom", ["communication"]),
}

PYTHON_API_INTEGRATIONS: list[PythonAPIIntegration] = [
    PythonAPIIntegration("codebase", ["version-control"]),
    PythonAPIIntegration("git", ["version-control"], stream_name="commits"),
    PythonAPIIntegration(
        "google-calendar", ["productivity"], display_name="Google Calendar", directory_name="google"
    ),
    PythonAPIIntegration(
        "irc", ["communication"], display_name="IRC", directory_name="bridge_with_irc"
    ),
    PythonAPIIntegration(
        "jira-plugin",
        ["project-management"],
        logo="images/integrations/logos/jira.svg",
        secondary_line_text="(locally installed)",
        display_name="Jira",
        directory_name="jira",
        stream_name="jira",
        legacy=True,
    ),
    PythonAPIIntegration("matrix", ["communication"], directory_name="bridge_with_matrix"),
    PythonAPIIntegration(
        "mercurial",
        ["version-control"],
        display_name="Mercurial (hg)",
        stream_name="commits",
        directory_name="hg",
    ),
    PythonAPIIntegration("nagios", ["monitoring"]),
    PythonAPIIntegration(
        "openshift", ["deployment"], display_name="OpenShift", stream_name="deployments"
    ),
    PythonAPIIntegration("perforce", ["version-control"]),
    PythonAPIIntegration("rss", ["communication"], display_name="RSS"),
    PythonAPIIntegration("svn", ["version-control"], display_name="Subversion"),
    PythonAPIIntegration("trac", ["project-management"]),
    PythonAPIIntegration(
        "twitter",
        ["customer-support", "marketing"],
        # _ needed to get around adblock plus
        logo="images/integrations/logos/twitte_r.svg",
    ),
]

BOT_INTEGRATIONS: list[BotIntegration] = [
    BotIntegration("github_detail", ["version-control", "bots"], display_name="GitHub Detail"),
    BotIntegration(
        "xkcd", ["bots", "misc"], display_name="xkcd", logo="images/integrations/logos/xkcd.png"
    ),
]

HUBOT_INTEGRATIONS: list[HubotIntegration] = [
    HubotIntegration("assembla", ["version-control", "project-management"]),
    HubotIntegration("bonusly", ["hr"]),
    HubotIntegration("chartbeat", ["marketing"]),
    HubotIntegration("darksky", ["misc"], display_name="Dark Sky"),
    HubotIntegration(
        "instagram",
        ["misc"],
        # _ needed to get around adblock plus
        logo="images/integrations/logos/instagra_m.svg",
    ),
    HubotIntegration("mailchimp", ["communication", "marketing"]),
    HubotIntegration("google-translate", ["misc"], display_name="Google Translate"),
    HubotIntegration(
        "youtube",
        ["misc"],
        display_name="YouTube",
        # _ needed to get around adblock plus
        logo="images/integrations/logos/youtub_e.svg",
    ),
]

for python_api_integration in PYTHON_API_INTEGRATIONS:
    INTEGRATIONS[python_api_integration.name] = python_api_integration

for hubot_integration in HUBOT_INTEGRATIONS:
    INTEGRATIONS[hubot_integration.name] = hubot_integration

for webhook_integration in WEBHOOK_INTEGRATIONS:
    INTEGRATIONS[webhook_integration.name] = webhook_integration

for bot_integration in BOT_INTEGRATIONS:
    INTEGRATIONS[bot_integration.name] = bot_integration

# Add integrations that don't have automated screenshots here
NO_SCREENSHOT_WEBHOOKS = {
    "beeminder",  # FIXME: fixture's goal.losedate needs to be modified dynamically
    "ifttt",  # Docs don't have a screenshot
    "slack_incoming",  # Docs don't have a screenshot
    "zapier",  # Docs don't have a screenshot
}


WEBHOOK_SCREENSHOT_CONFIG: dict[str, list[WebhookScreenshotConfig]] = {
    "airbrake": [WebhookScreenshotConfig("error_message.json")],
    "airbyte": [WebhookScreenshotConfig("airbyte_job_payload_success.json")],
    "alertmanager": [
        WebhookScreenshotConfig("alert.json", extra_params={"name": "topic", "desc": "description"})
    ],
    "ansibletower": [WebhookScreenshotConfig("job_successful_multiple_hosts.json")],
    "appfollow": [WebhookScreenshotConfig("review.json")],
    "appveyor": [WebhookScreenshotConfig("appveyor_build_success.json")],
    "azuredevops": [WebhookScreenshotConfig("code_push.json")],
    "basecamp": [WebhookScreenshotConfig("doc_active.json")],
    "beanstalk": [
        WebhookScreenshotConfig(
            "git_multiple.json", use_basic_auth=True, payload_as_query_param=True
        )
    ],
    # 'beeminder': [WebhookScreenshotConfig('derail_worried.json')],
    "bitbucket": [
        WebhookScreenshotConfig(
            "push.json", "002.png", use_basic_auth=True, payload_as_query_param=True
        )
    ],
    "bitbucket2": [
        WebhookScreenshotConfig(
            "issue_created.json", "003.png", "bitbucket", bot_name="Bitbucket Bot"
        )
    ],
    "bitbucket3": [
        WebhookScreenshotConfig(
            "repo_push_update_single_branch.json",
            "004.png",
            "bitbucket",
            bot_name="Bitbucket Server Bot",
        )
    ],
    "buildbot": [WebhookScreenshotConfig("started.json")],
    "canarytoken": [WebhookScreenshotConfig("canarytoken_real.json")],
    "circleci": [WebhookScreenshotConfig("github_job_completed.json")],
    "clubhouse": [WebhookScreenshotConfig("story_create.json")],
    "codeship": [WebhookScreenshotConfig("error_build.json")],
    "crashlytics": [WebhookScreenshotConfig("issue_message.json")],
    "delighted": [WebhookScreenshotConfig("survey_response_updated_promoter.json")],
    "dialogflow": [
        WebhookScreenshotConfig("weather_app.json", extra_params={"email": "iago@zulip.com"})
    ],
    "dropbox": [WebhookScreenshotConfig("file_updated.json")],
    "errbit": [WebhookScreenshotConfig("error_message.json")],
    "flock": [WebhookScreenshotConfig("messages.json")],
    "freshdesk": [
        WebhookScreenshotConfig("ticket_created.json", image_name="004.png", use_basic_auth=True)
    ],
    "freshping": [WebhookScreenshotConfig("freshping_check_unreachable.json")],
    "freshstatus": [WebhookScreenshotConfig("freshstatus_incident_open.json")],
    "front": [WebhookScreenshotConfig("inbound_message.json")],
    "gitea": [WebhookScreenshotConfig("pull_request__merged.json")],
    "github": [WebhookScreenshotConfig("push__1_commit.json")],
    "githubsponsors": [WebhookScreenshotConfig("created.json")],
    "gitlab": [WebhookScreenshotConfig("push_hook__push_local_branch_without_commits.json")],
    "gocd": [WebhookScreenshotConfig("pipeline_with_mixed_job_result.json")],
    "gogs": [WebhookScreenshotConfig("pull_request__opened.json")],
    "gosquared": [WebhookScreenshotConfig("traffic_spike.json")],
    "grafana": [WebhookScreenshotConfig("alert_values_v11.json")],
    "greenhouse": [WebhookScreenshotConfig("candidate_stage_change.json")],
    "groove": [WebhookScreenshotConfig("ticket_started.json")],
    "harbor": [WebhookScreenshotConfig("scanning_completed.json")],
    "hellosign": [
        WebhookScreenshotConfig(
            "signatures_signed_by_one_signatory.json",
            payload_as_query_param=True,
            payload_param_name="json",
        )
    ],
    "helloworld": [WebhookScreenshotConfig("hello.json")],
    "heroku": [WebhookScreenshotConfig("deploy.txt")],
    "homeassistant": [WebhookScreenshotConfig("reqwithtitle.json")],
    "insping": [WebhookScreenshotConfig("website_state_available.json")],
    "intercom": [WebhookScreenshotConfig("conversation_admin_replied.json")],
    "jira": [WebhookScreenshotConfig("created_v1.json")],
    "jotform": [WebhookScreenshotConfig("screenshot_response.multipart")],
    "json": [WebhookScreenshotConfig("json_github_push__1_commit.json")],
    "librato": [
        WebhookScreenshotConfig("three_conditions_alert.json", payload_as_query_param=True)
    ],
    "lidarr": [WebhookScreenshotConfig("lidarr_album_grabbed.json")],
    "linear": [WebhookScreenshotConfig("issue_create_complex.json")],
    "mention": [WebhookScreenshotConfig("webfeeds.json")],
    "netlify": [WebhookScreenshotConfig("deploy_building.json")],
    "newrelic": [WebhookScreenshotConfig("incident_activated_new_default_payload.json")],
    "opencollective": [WebhookScreenshotConfig("one_time_donation.json")],
    "openproject": [WebhookScreenshotConfig("project_created__without_parent.json")],
    "opensearch": [WebhookScreenshotConfig("example_template.txt")],
    "opsgenie": [WebhookScreenshotConfig("addrecipient.json")],
    "pagerduty": [WebhookScreenshotConfig("trigger_v2.json")],
    "papertrail": [WebhookScreenshotConfig("short_post.json", payload_as_query_param=True)],
    "patreon": [WebhookScreenshotConfig("members_pledge_create.json")],
    "pingdom": [WebhookScreenshotConfig("http_up_to_down.json")],
    "pivotal": [WebhookScreenshotConfig("v5_type_changed.json")],
    "radarr": [WebhookScreenshotConfig("radarr_movie_grabbed.json")],
    "raygun": [WebhookScreenshotConfig("new_error.json")],
    "reviewboard": [WebhookScreenshotConfig("review_request_published.json")],
    "rhodecode": [WebhookScreenshotConfig("push.json")],
    "rundeck": [WebhookScreenshotConfig("start.json")],
    "semaphore": [WebhookScreenshotConfig("pull_request.json")],
    "sentry": [WebhookScreenshotConfig("event_for_exception_python.json")],
    "slack": [WebhookScreenshotConfig("message_with_normal_text.json")],
    "sonarqube": [WebhookScreenshotConfig("error.json")],
    "sonarr": [WebhookScreenshotConfig("sonarr_episode_grabbed.json")],
    "splunk": [WebhookScreenshotConfig("search_one_result.json")],
    "statuspage": [WebhookScreenshotConfig("incident_created.json")],
    "stripe": [WebhookScreenshotConfig("charge_succeeded__card.json")],
    "taiga": [WebhookScreenshotConfig("userstory_changed_status.json")],
    "teamcity": [WebhookScreenshotConfig("success.json")],
    "thinkst": [WebhookScreenshotConfig("canary_consolidated_port_scan.json")],
    "transifex": [
        WebhookScreenshotConfig(
            "",
            extra_params={
                "project": "Zulip Mobile",
                "language": "en",
                "resource": "file",
                "event": "review_completed",
                "reviewed": "100",
            },
        )
    ],
    "travis": [WebhookScreenshotConfig("build.json", payload_as_query_param=True)],
    "trello": [WebhookScreenshotConfig("adding_comment_to_card.json")],
    "updown": [WebhookScreenshotConfig("check_multiple_events.json")],
    "uptimerobot": [WebhookScreenshotConfig("uptimerobot_monitor_up.json")],
    "wekan": [WebhookScreenshotConfig("add_comment.json")],
    "wordpress": [WebhookScreenshotConfig("publish_post.txt", "wordpress_post_created.png")],
    "zabbix": [WebhookScreenshotConfig("zabbix_alert.json")],
    "zendesk": [
        WebhookScreenshotConfig(
            "",
            use_basic_auth=True,
            extra_params={
                "ticket_title": "Hardware Ecosystem Compatibility Inquiry",
                "ticket_id": "4837",
                "message": "Hi, I am planning to purchase the X5000 smartphone and want to ensure compatibility with my existing devices - WDX10 wireless earbuds and Z600 smartwatch. Are there any known issues?",
            },
        )
    ],
}

FIXTURELESS_SCREENSHOT_CONFIG: dict[str, list[FixturelessScreenshotConfig]] = {}

DOC_SCREENSHOT_CONFIG: dict[
    str, list[WebhookScreenshotConfig] | list[FixturelessScreenshotConfig]
] = {
    **WEBHOOK_SCREENSHOT_CONFIG,
    **FIXTURELESS_SCREENSHOT_CONFIG,
}


def get_all_event_types_for_integration(integration: Integration) -> list[str] | None:
    integration = INTEGRATIONS[integration.name]
    if isinstance(integration, WebhookIntegration):
        if integration.name == "githubsponsors":
            return import_string("zerver.webhooks.github.view.SPONSORS_EVENT_TYPES")
        function = integration.get_function()
        if hasattr(function, "_all_event_types"):
            return function._all_event_types
    return None
