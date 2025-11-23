import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from itertools import chain, zip_longest
from typing import Any, TypeAlias

from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import HttpRequest, HttpResponseBase
from django.urls import URLPattern, path
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy
from django.views.decorators.csrf import csrf_exempt
from django_stubs_ext import StrPromise

from zerver.lib.storage import static_path
from zerver.lib.validator import check_bool
from zerver.lib.webhooks.common import PresetUrlOption, WebhookConfigOption, WebhookUrlOption
from zerver.webhooks import fixtureless_integrations

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
    "video-calling": gettext_lazy("Video calling"),
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

# Can also be computed from INTEGRATIONS by removing entries from
# WEBHOOK_INTEGRATIONS and NO_SCREENSHOT_CONFIG, but defined explicitly to
# avoid circular dependency
FIXTURELESS_INTEGRATIONS_WITH_SCREENSHOTS: list[str] = [
    "asana",
    "capistrano",
    "codebase",
    "discourse",
    "git",
    "github-actions",
    "google-calendar",
    "jenkins",
    "jira-plugin",
    "mastodon",
    "mercurial",
    "nagios",
    "notion",
    "openshift",
    "perforce",
    "puppet",
    "redmine",
    "rss",
    "svn",
    "trac",
]
FIXTURELESS_SCREENSHOT_CONTENT: dict[str, list[fixtureless_integrations.ScreenshotContent]] = {
    key: [getattr(fixtureless_integrations, key.upper().replace("-", "_"))]
    for key in FIXTURELESS_INTEGRATIONS_WITH_SCREENSHOTS
}


@dataclass
class WebhookScreenshotConfig:
    fixture_name: str
    image_name: str = "001.png"
    image_dir: str | None = None
    bot_name: str | None = None
    channel: str | None = None
    payload_as_query_param: bool = False
    payload_param_name: str = "payload"
    extra_params: dict[str, str] = field(default_factory=dict)
    use_basic_auth: bool = False
    custom_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class FixturelessScreenshotConfigOptions:
    # These configured values for individual integrations are written
    # over an object with defaults for content and topic to construct
    # a FixturelessScreenshotConfig.
    channel: str | None = None
    image_name: str = "001.png"
    image_dir: str | None = None
    bot_name: str | None = None


@dataclass
class FixturelessScreenshotConfig:
    message: str
    topic: str
    channel: str | None = None
    image_name: str = "001.png"
    image_dir: str | None = None
    bot_name: str | None = None


def get_screenshot_configs(
    integration_name: str,
    screenshot_config_options: list[FixturelessScreenshotConfigOptions] | None,
) -> list[FixturelessScreenshotConfig] | None:
    screenshot_contents = FIXTURELESS_SCREENSHOT_CONTENT.get(integration_name, [])
    if not screenshot_contents:
        return None  # nocoverage
    return [
        FixturelessScreenshotConfig(
            screenshot_content["content"],
            screenshot_content["topic"],
            **vars(screenshot_config_option) if screenshot_config_option else {},
        )
        for screenshot_content, screenshot_config_option in zip_longest(
            screenshot_contents, screenshot_config_options or []
        )
    ]


class Integration:
    DEFAULT_LOGO_STATIC_PATH_PNG = "images/integrations/logos/{name}.png"
    DEFAULT_LOGO_STATIC_PATH_SVG = "images/integrations/logos/{name}.svg"
    DEFAULT_BOT_AVATAR_PATH = "images/integrations/bot_avatars/{name}.png"
    DEFAULT_DOC_PATH = "zerver/integrations/{name}.md"

    def __init__(
        self,
        name: str,
        categories: list[str],
        fixtureless_screenshot_config_options: list[FixturelessScreenshotConfigOptions]
        | None = None,
        webhook_screenshot_configs: list[WebhookScreenshotConfig] | None = None,
        client_name: str | None = None,
        logo: str | None = None,
        secondary_line_text: str | None = None,
        display_name: str | None = None,
        doc: str | None = None,
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

        self.screenshot_configs: (
            list[WebhookScreenshotConfig] | list[FixturelessScreenshotConfig] | None
        ) = None
        if webhook_screenshot_configs is not None:
            self.screenshot_configs = webhook_screenshot_configs
        elif self.name in FIXTURELESS_INTEGRATIONS_WITH_SCREENSHOTS:
            self.screenshot_configs = get_screenshot_configs(
                name, fixtureless_screenshot_config_options
            )

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
        fixtureless_screenshot_config_options: list[FixturelessScreenshotConfigOptions]
        | None = None,
        logo: str | None = None,
        secondary_line_text: str | None = None,
        display_name: str | None = None,
        doc: str | None = None,
    ) -> None:
        super().__init__(
            name,
            client_name=name,
            categories=categories,
            fixtureless_screenshot_config_options=fixtureless_screenshot_config_options,
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
        fixtureless_screenshot_config_options: list[FixturelessScreenshotConfigOptions]
        | None = None,
        client_name: str | None = None,
        logo: str | None = None,
        secondary_line_text: str | None = None,
        display_name: str | None = None,
        directory_name: str | None = None,
        doc: str | None = None,
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
            fixtureless_screenshot_config_options=fixtureless_screenshot_config_options,
            client_name=client_name,
            logo=logo,
            secondary_line_text=secondary_line_text,
            display_name=display_name,
            doc=doc,
            legacy=legacy,
        )


class WebhookIntegration(Integration):
    DEFAULT_FUNCTION_PATH = "zerver.webhooks.{dir_name}.view.api_{dir_name}_webhook"
    DEFAULT_URL = "api/v1/external/{name}"
    DEFAULT_CLIENT_NAME = "Zulip{name}Webhook"
    DEFAULT_DOC_PATH = "{name}/doc.md"

    def __init__(
        self,
        name: str,
        categories: list[str],
        webhook_screenshot_configs: list[WebhookScreenshotConfig] | None = None,
        client_name: str | None = None,
        logo: str | None = None,
        secondary_line_text: str | None = None,
        function: str | None = None,
        url: str | None = None,
        display_name: str | None = None,
        doc: str | None = None,
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
            webhook_screenshot_configs=webhook_screenshot_configs,
            client_name=client_name,
            logo=logo,
            secondary_line_text=secondary_line_text,
            display_name=display_name,
            legacy=legacy,
            config_options=config_options,
            url_options=url_options,
        )

        if dir_name is None:
            dir_name = self.name
        self.dir_name = dir_name

        if function is None:
            function = self.DEFAULT_FUNCTION_PATH.format(dir_name=dir_name)
        self.function_name = function

        if url is None:
            url = self.DEFAULT_URL.format(name=name)
        self.url = url

        if doc is None:
            doc = self.DEFAULT_DOC_PATH.format(name=name)
        self.doc = doc

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
        fixtureless_screenshot_config_options: list[FixturelessScreenshotConfigOptions]
        | None = None,
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
            fixtureless_screenshot_config_options=fixtureless_screenshot_config_options,
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
    WebhookIntegration("airbrake", ["monitoring"], [WebhookScreenshotConfig("error_message.json")]),
    WebhookIntegration(
        "airbyte", ["deployment"], [WebhookScreenshotConfig("airbyte_job_payload_success.json")]
    ),
    WebhookIntegration(
        "alertmanager",
        ["monitoring"],
        [
            WebhookScreenshotConfig(
                "alert.json", extra_params={"name": "topic", "desc": "description"}
            )
        ],
        display_name="Prometheus Alertmanager",
        logo="images/integrations/logos/prometheus.svg",
    ),
    WebhookIntegration(
        "ansibletower",
        ["deployment"],
        [WebhookScreenshotConfig("job_successful_multiple_hosts.json")],
        display_name="Ansible Tower",
    ),
    WebhookIntegration(
        "appfollow",
        ["marketing", "customer-support"],
        [WebhookScreenshotConfig("review.json")],
        display_name="AppFollow",
    ),
    WebhookIntegration(
        "appveyor",
        ["continuous-integration"],
        [WebhookScreenshotConfig("appveyor_build_success.json")],
        display_name="AppVeyor",
    ),
    WebhookIntegration(
        "azuredevops",
        ["continuous-integration"],
        [WebhookScreenshotConfig("code_push.json")],
        display_name="AzureDevOps",
        url_options=[WebhookUrlOption.build_preset_config(PresetUrlOption.BRANCHES)],
    ),
    WebhookIntegration(
        "basecamp", ["project-management"], [WebhookScreenshotConfig("doc_active.json")]
    ),
    WebhookIntegration(
        "beanstalk",
        ["version-control"],
        [
            WebhookScreenshotConfig(
                "git_multiple.json",
                channel="commits",
                use_basic_auth=True,
                payload_as_query_param=True,
            )
        ],
    ),
    WebhookIntegration(
        "beeminder",
        ["productivity"],
        # The fixture's goal.losedate needs to be modified dynamically
        # before uncommenting the screenshot config below.
        # [WebhookScreenshotConfig("derail_worried.json")],
        display_name="Beeminder",
    ),
    WebhookIntegration(
        "bitbucket",
        ["version-control"],
        [
            WebhookScreenshotConfig(
                "push.json",
                "002.png",
                channel="commits",
                use_basic_auth=True,
                payload_as_query_param=True,
            )
        ],
        display_name="Bitbucket",
        secondary_line_text="(Enterprise)",
        legacy=True,
    ),
    WebhookIntegration(
        "bitbucket2",
        ["version-control"],
        [
            WebhookScreenshotConfig(
                "issue_created.json",
                "003.png",
                "bitbucket",
                bot_name="Bitbucket Bot",
                channel="commits",
            )
        ],
        logo="images/integrations/logos/bitbucket.svg",
        display_name="Bitbucket",
        url_options=[WebhookUrlOption.build_preset_config(PresetUrlOption.BRANCHES)],
    ),
    WebhookIntegration(
        "bitbucket3",
        ["version-control"],
        [
            WebhookScreenshotConfig(
                "repo_push_update_single_branch.json",
                "004.png",
                "bitbucket",
                bot_name="Bitbucket Server Bot",
                channel="commits",
            )
        ],
        logo="images/integrations/logos/bitbucket.svg",
        display_name="Bitbucket Server",
        url_options=[WebhookUrlOption.build_preset_config(PresetUrlOption.BRANCHES)],
    ),
    WebhookIntegration(
        "buildbot", ["continuous-integration"], [WebhookScreenshotConfig("started.json")]
    ),
    WebhookIntegration(
        "canarytoken",
        ["monitoring"],
        [WebhookScreenshotConfig("canarytoken_real.json")],
        display_name="Thinkst Canarytokens",
    ),
    WebhookIntegration(
        "circleci",
        ["continuous-integration"],
        [WebhookScreenshotConfig("github_job_completed.json")],
        display_name="CircleCI",
    ),
    WebhookIntegration(
        "clubhouse", ["project-management"], [WebhookScreenshotConfig("story_create.json")]
    ),
    WebhookIntegration(
        "codeship",
        ["continuous-integration", "deployment"],
        [WebhookScreenshotConfig("error_build.json")],
    ),
    WebhookIntegration(
        "crashlytics", ["monitoring"], [WebhookScreenshotConfig("issue_message.json")]
    ),
    WebhookIntegration(
        "delighted",
        ["customer-support", "marketing"],
        [WebhookScreenshotConfig("survey_response_updated_promoter.json")],
    ),
    WebhookIntegration(
        "dialogflow",
        ["customer-support"],
        [WebhookScreenshotConfig("weather_app.json", extra_params={"email": "iago@zulip.com"})],
    ),
    WebhookIntegration("dropbox", ["productivity"], [WebhookScreenshotConfig("file_updated.json")]),
    WebhookIntegration("errbit", ["monitoring"], [WebhookScreenshotConfig("error_message.json")]),
    WebhookIntegration("flock", ["communication"], [WebhookScreenshotConfig("messages.json")]),
    WebhookIntegration(
        "freshdesk",
        ["customer-support"],
        [WebhookScreenshotConfig("ticket_created.json", image_name="004.png", use_basic_auth=True)],
    ),
    WebhookIntegration(
        "freshping", ["monitoring"], [WebhookScreenshotConfig("freshping_check_unreachable.json")]
    ),
    WebhookIntegration(
        "freshstatus",
        ["monitoring", "customer-support"],
        [WebhookScreenshotConfig("freshstatus_incident_open.json")],
    ),
    WebhookIntegration(
        "front",
        ["customer-support", "communication"],
        [WebhookScreenshotConfig("inbound_message.json")],
    ),
    WebhookIntegration(
        "gitea",
        ["version-control"],
        [WebhookScreenshotConfig("pull_request__merged.json", channel="commits")],
        url_options=[WebhookUrlOption.build_preset_config(PresetUrlOption.BRANCHES)],
    ),
    WebhookIntegration(
        "github",
        ["version-control", "continuous-integration", "project-management"],
        [WebhookScreenshotConfig("push__1_commit.json", channel="commits")],
        display_name="GitHub",
        url_options=[
            WebhookUrlOption.build_preset_config(PresetUrlOption.BRANCHES),
            WebhookUrlOption.build_preset_config(PresetUrlOption.IGNORE_PRIVATE_REPOSITORIES),
        ],
    ),
    WebhookIntegration(
        "githubsponsors",
        ["financial"],
        [WebhookScreenshotConfig("created.json", channel="github")],
        display_name="GitHub Sponsors",
        logo="images/integrations/logos/github.svg",
        dir_name="github",
        doc="github/githubsponsors.md",
    ),
    WebhookIntegration(
        "gitlab",
        ["version-control"],
        [
            WebhookScreenshotConfig(
                "push_hook__push_local_branch_without_commits.json", channel="commits"
            )
        ],
        display_name="GitLab",
        url_options=[WebhookUrlOption.build_preset_config(PresetUrlOption.BRANCHES)],
    ),
    WebhookIntegration(
        "gocd",
        ["continuous-integration"],
        [WebhookScreenshotConfig("pipeline_with_mixed_job_result.json")],
        display_name="GoCD",
    ),
    WebhookIntegration(
        "gogs",
        ["version-control"],
        [WebhookScreenshotConfig("pull_request__opened.json", channel="commits")],
        url_options=[WebhookUrlOption.build_preset_config(PresetUrlOption.BRANCHES)],
    ),
    WebhookIntegration(
        "gosquared",
        ["marketing"],
        [WebhookScreenshotConfig("traffic_spike.json")],
        display_name="GoSquared",
    ),
    WebhookIntegration(
        "grafana", ["monitoring"], [WebhookScreenshotConfig("alert_values_v11.json")]
    ),
    WebhookIntegration(
        "greenhouse", ["hr"], [WebhookScreenshotConfig("candidate_stage_change.json")]
    ),
    WebhookIntegration(
        "groove", ["customer-support"], [WebhookScreenshotConfig("ticket_started.json")]
    ),
    WebhookIntegration(
        "harbor",
        ["deployment"],
        [WebhookScreenshotConfig("scanning_completed.json")],
    ),
    WebhookIntegration(
        "hellosign",
        ["productivity", "hr"],
        [
            WebhookScreenshotConfig(
                "signatures_signed_by_one_signatory.json",
                payload_as_query_param=True,
                payload_param_name="json",
            )
        ],
        display_name="HelloSign",
    ),
    WebhookIntegration(
        "helloworld", ["misc"], [WebhookScreenshotConfig("hello.json")], display_name="Hello World"
    ),
    WebhookIntegration("heroku", ["deployment"], [WebhookScreenshotConfig("deploy.txt")]),
    WebhookIntegration(
        "homeassistant",
        ["misc"],
        [WebhookScreenshotConfig("reqwithtitle.json")],
        display_name="Home Assistant",
    ),
    WebhookIntegration("ifttt", ["meta-integration"], display_name="IFTTT"),
    WebhookIntegration(
        "insping", ["monitoring"], [WebhookScreenshotConfig("website_state_available.json")]
    ),
    WebhookIntegration(
        "intercom",
        ["customer-support"],
        [WebhookScreenshotConfig("conversation_admin_replied.json")],
    ),
    # Avoid collision with jira-plugin's doc "jira/doc.md".
    WebhookIntegration(
        "jira",
        ["project-management"],
        [WebhookScreenshotConfig("created_v1.json")],
        doc="jira/jira-doc.md",
    ),
    WebhookIntegration(
        "jotform", ["productivity"], [WebhookScreenshotConfig("screenshot_response.multipart")]
    ),
    WebhookIntegration(
        "json",
        ["misc"],
        [WebhookScreenshotConfig("json_github_push__1_commit.json")],
        display_name="JSON formatter",
    ),
    WebhookIntegration(
        "librato",
        ["monitoring"],
        [WebhookScreenshotConfig("three_conditions_alert.json", payload_as_query_param=True)],
    ),
    WebhookIntegration(
        "lidarr", ["entertainment"], [WebhookScreenshotConfig("lidarr_album_grabbed.json")]
    ),
    WebhookIntegration(
        "linear", ["project-management"], [WebhookScreenshotConfig("issue_create_complex.json")]
    ),
    WebhookIntegration("mention", ["marketing"], [WebhookScreenshotConfig("webfeeds.json")]),
    WebhookIntegration(
        "netlify",
        ["deployment", "continuous-integration"],
        [WebhookScreenshotConfig("deploy_building.json")],
    ),
    WebhookIntegration(
        "newrelic",
        ["monitoring"],
        [WebhookScreenshotConfig("incident_activated_new_default_payload.json")],
        display_name="New Relic",
    ),
    WebhookIntegration(
        "opencollective",
        ["financial"],
        [WebhookScreenshotConfig("one_time_donation.json")],
        display_name="Open Collective",
    ),
    WebhookIntegration(
        "openproject",
        ["project-management"],
        [WebhookScreenshotConfig("project_created__without_parent.json")],
        display_name="OpenProject",
    ),
    WebhookIntegration(
        "opensearch",
        ["monitoring"],
        [WebhookScreenshotConfig("example_template.txt")],
        display_name="OpenSearch",
    ),
    WebhookIntegration(
        "opsgenie",
        ["monitoring"],
        [WebhookScreenshotConfig("addrecipient.json")],
        url_options=[
            WebhookUrlOption(
                name="eu_region",
                label="Use Opsgenie's European service region",
                validator=check_bool,
            )
        ],
    ),
    WebhookIntegration(
        "pagerduty",
        ["monitoring"],
        [WebhookScreenshotConfig("trigger_v2.json")],
        display_name="PagerDuty",
    ),
    WebhookIntegration(
        "papertrail",
        ["monitoring"],
        [WebhookScreenshotConfig("short_post.json", payload_as_query_param=True)],
    ),
    WebhookIntegration(
        "patreon", ["financial"], [WebhookScreenshotConfig("members_pledge_create.json")]
    ),
    WebhookIntegration(
        "pingdom", ["monitoring"], [WebhookScreenshotConfig("http_up_to_down.json")]
    ),
    WebhookIntegration(
        "pivotal",
        ["project-management"],
        [WebhookScreenshotConfig("v5_type_changed.json")],
        display_name="Pivotal Tracker",
    ),
    WebhookIntegration(
        "radarr", ["entertainment"], [WebhookScreenshotConfig("radarr_movie_grabbed.json")]
    ),
    WebhookIntegration("raygun", ["monitoring"], [WebhookScreenshotConfig("new_error.json")]),
    WebhookIntegration(
        "reviewboard",
        ["productivity"],
        [WebhookScreenshotConfig("review_request_published.json")],
        display_name="Review Board",
    ),
    WebhookIntegration(
        "rhodecode",
        ["version-control"],
        [WebhookScreenshotConfig("push.json", channel="commits")],
        display_name="RhodeCode",
        url_options=[WebhookUrlOption.build_preset_config(PresetUrlOption.BRANCHES)],
    ),
    WebhookIntegration("rundeck", ["deployment"], [WebhookScreenshotConfig("start.json")]),
    WebhookIntegration(
        "semaphore",
        ["continuous-integration", "deployment"],
        [WebhookScreenshotConfig("pull_request.json")],
    ),
    WebhookIntegration(
        "sentry", ["monitoring"], [WebhookScreenshotConfig("event_for_exception_python.json")]
    ),
    WebhookIntegration("slack", ["communication"]),
    WebhookIntegration(
        "slack_incoming",
        ["communication", "meta-integration"],
        display_name="Slack-compatible webhook",
        logo="images/integrations/logos/slack.svg",
    ),
    WebhookIntegration(
        "sonarqube",
        ["continuous-integration", "monitoring"],
        [WebhookScreenshotConfig("error.json")],
        display_name="SonarQube",
    ),
    WebhookIntegration(
        "sonarr", ["entertainment"], [WebhookScreenshotConfig("sonarr_episode_grabbed.json")]
    ),
    WebhookIntegration(
        "splunk", ["monitoring"], [WebhookScreenshotConfig("search_one_result.json")]
    ),
    WebhookIntegration(
        "statuspage",
        ["customer-support", "monitoring"],
        [WebhookScreenshotConfig("incident_created.json")],
    ),
    WebhookIntegration(
        "stripe", ["financial"], [WebhookScreenshotConfig("charge_succeeded__card.json")]
    ),
    WebhookIntegration(
        "taiga", ["project-management"], [WebhookScreenshotConfig("userstory_changed_status.json")]
    ),
    WebhookIntegration(
        "teamcity", ["continuous-integration"], [WebhookScreenshotConfig("success.json")]
    ),
    WebhookIntegration(
        "thinkst", ["monitoring"], [WebhookScreenshotConfig("canary_consolidated_port_scan.json")]
    ),
    WebhookIntegration(
        "transifex",
        ["misc"],
        [
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
    ),
    WebhookIntegration(
        "travis",
        ["continuous-integration"],
        [WebhookScreenshotConfig("build.json", payload_as_query_param=True)],
        display_name="Travis CI",
    ),
    WebhookIntegration(
        "trello", ["project-management"], [WebhookScreenshotConfig("adding_comment_to_card.json")]
    ),
    WebhookIntegration(
        "updown", ["monitoring"], [WebhookScreenshotConfig("check_multiple_events.json")]
    ),
    WebhookIntegration(
        "uptimerobot",
        ["monitoring"],
        [WebhookScreenshotConfig("uptimerobot_monitor_up.json")],
        display_name="UptimeRobot",
    ),
    WebhookIntegration(
        "wekan",
        ["productivity", "project-management"],
        [WebhookScreenshotConfig("add_comment.json")],
    ),
    WebhookIntegration(
        "wordpress",
        ["marketing"],
        [WebhookScreenshotConfig("publish_post.txt", "wordpress_post_created.png")],
        display_name="WordPress",
    ),
    WebhookIntegration("zabbix", ["monitoring"], [WebhookScreenshotConfig("zabbix_alert.json")]),
    WebhookIntegration("zapier", ["meta-integration"]),
    WebhookIntegration(
        "zendesk",
        ["customer-support"],
        [
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
    ),
]

VIDEO_CALL_INTEGRATIONS: list[Integration] = [
    Integration(
        "big-blue-button", ["video-calling", "communication"], display_name="BigBlueButton"
    ),
    Integration("jitsi", ["video-calling", "communication"], display_name="Jitsi Meet"),
    Integration("zoom", ["video-calling", "communication"]),
]

EMBEDDED_INTEGRATIONS: list[Integration] = [
    Integration("email", ["communication"]),
    Integration("giphy", ["misc"], display_name="GIPHY"),
]

ZAPIER_INTEGRATIONS: list[Integration] = [
    Integration("asana", ["project-management"]),
    # Can be used with RSS integration too
    Integration("mastodon", ["communication"]),
    Integration("notion", ["productivity", "project-management"]),
]

PLUGIN_INTEGRATIONS: list[Integration] = [
    Integration("discourse", ["communication"]),
    Integration(
        "jenkins",
        ["continuous-integration"],
        [FixturelessScreenshotConfigOptions(image_name="004.png")],
    ),
    Integration("onyx", ["productivity"], logo="images/integrations/logos/onyx.png"),
]

# Each of these integrations have their own Zulip repository in GitHub.
STANDALONE_REPO_INTEGRATIONS: list[Integration] = [
    Integration("errbot", ["meta-integration", "bots"]),
    Integration(
        "github-actions",
        ["continuous-integration"],
        [FixturelessScreenshotConfigOptions(channel="github-actions updates")],
        display_name="GitHub Actions",
    ),
    Integration("hubot", ["meta-integration", "bots"]),
    Integration("puppet", ["deployment"]),
    Integration("redmine", ["project-management"]),
]

ZULIP_SEND_INTEGRATIONS: list[Integration] = [
    Integration("capistrano", ["deployment"]),
]

OTHER_INTEGRATIONS = [
    *VIDEO_CALL_INTEGRATIONS,
    *EMBEDDED_INTEGRATIONS,
    *ZAPIER_INTEGRATIONS,
    *PLUGIN_INTEGRATIONS,
    *STANDALONE_REPO_INTEGRATIONS,
    *ZULIP_SEND_INTEGRATIONS,
]

PYTHON_API_INTEGRATIONS: list[PythonAPIIntegration] = [
    PythonAPIIntegration("codebase", ["version-control", "project-management"]),
    PythonAPIIntegration(
        "git", ["version-control"], [FixturelessScreenshotConfigOptions(channel="commits")]
    ),
    PythonAPIIntegration(
        "google-calendar",
        ["productivity"],
        [FixturelessScreenshotConfigOptions(image_name="003.png", image_dir="google/calendar")],
        display_name="Google Calendar",
        directory_name="google",
    ),
    PythonAPIIntegration(
        "irc", ["communication"], display_name="IRC", directory_name="bridge_with_irc"
    ),
    PythonAPIIntegration(
        "jira-plugin",
        ["project-management"],
        [FixturelessScreenshotConfigOptions(channel="jira")],
        logo="images/integrations/logos/jira.svg",
        secondary_line_text="(locally installed)",
        display_name="Jira",
        directory_name="jira",
        legacy=True,
    ),
    PythonAPIIntegration("matrix", ["communication"], directory_name="bridge_with_matrix"),
    PythonAPIIntegration(
        "mercurial",
        ["version-control"],
        [FixturelessScreenshotConfigOptions(channel="commits", image_dir="hg")],
        display_name="Mercurial (hg)",
        directory_name="hg",
    ),
    PythonAPIIntegration("nagios", ["monitoring"]),
    PythonAPIIntegration(
        "openshift",
        ["deployment"],
        [FixturelessScreenshotConfigOptions(channel="deployments")],
        display_name="OpenShift",
    ),
    PythonAPIIntegration("perforce", ["version-control"]),
    PythonAPIIntegration("rss", ["communication"], display_name="RSS"),
    PythonAPIIntegration("svn", ["version-control"], display_name="Subversion"),
    PythonAPIIntegration("trac", ["project-management"]),
]

BOT_INTEGRATIONS: list[BotIntegration] = [
    BotIntegration("github_detail", ["version-control", "bots"], display_name="GitHub Detail"),
    BotIntegration(
        "xkcd",
        ["bots", "entertainment"],
        display_name="xkcd",
        logo="images/integrations/logos/xkcd.png",
    ),
]

HUBOT_INTEGRATIONS: list[HubotIntegration] = [
    HubotIntegration("assembla", ["version-control", "project-management"]),
    HubotIntegration("bonusly", ["hr"]),
    HubotIntegration("chartbeat", ["marketing"]),
    HubotIntegration("darksky", ["misc"], display_name="Dark Sky"),
    HubotIntegration("google-translate", ["misc"], display_name="Google Translate"),
    HubotIntegration(
        "instagram",
        ["entertainment", "marketing"],
        # _ needed to get around adblock plus
        logo="images/integrations/logos/instagra_m.svg",
    ),
    HubotIntegration("mailchimp", ["marketing", "communication"]),
    HubotIntegration(
        "youtube",
        ["entertainment", "marketing"],
        display_name="YouTube",
        # _ needed to get around adblock plus
        logo="images/integrations/logos/youtub_e.svg",
    ),
]


INTEGRATIONS: dict[str, Integration] = {
    integration.name: integration
    for integration in chain(
        WEBHOOK_INTEGRATIONS,
        PYTHON_API_INTEGRATIONS,
        BOT_INTEGRATIONS,
        HUBOT_INTEGRATIONS,
        OTHER_INTEGRATIONS,
    )
}

hubot_integration_names = {integration.name for integration in HUBOT_INTEGRATIONS}

# Add integrations whose example screenshots are not yet automated here
INTEGRATIONS_MISSING_SCREENSHOT_CONFIG = (
    # The fixture's goal.losedate needs to be modified dynamically,
    # so the screenshot config is commented out.
    {"beeminder"}
    # Integrations that call external API endpoints.
    | {"slack"}
    # Integrations that require screenshots of message threads - support is yet to be added
    | {
        "errbot",
        "github_detail",
        "hubot",
        "irc",
        # Also requires a screenshot on the Matrix side of the bridge
        "matrix",
        "xkcd",
    }
    | hubot_integration_names
)

# Add integrations that are not meant to have example screenshots here
INTEGRATIONS_WITHOUT_SCREENSHOTS = (
    # Integration frameworks
    {"ifttt", "slack_incoming", "zapier"}
    # Outgoing integrations
    | {"email", "onyx"}
    # Video call integrations
    | {"big-blue-button", "jitsi", "zoom"}
    | {
        # the integration does not send messages
        "giphy",
        # the integration is planned to be removed
        "twitter",
    }
)

NO_SCREENSHOT_CONFIG = INTEGRATIONS_MISSING_SCREENSHOT_CONFIG | INTEGRATIONS_WITHOUT_SCREENSHOTS


def get_all_event_types_for_integration(integration: Integration) -> list[str] | None:
    integration = INTEGRATIONS[integration.name]
    if isinstance(integration, WebhookIntegration):
        if integration.name == "githubsponsors":
            return import_string("zerver.webhooks.github.view.SPONSORS_EVENT_TYPES")
        function = integration.get_function()
        if hasattr(function, "_all_event_types"):
            return function._all_event_types
    return None
