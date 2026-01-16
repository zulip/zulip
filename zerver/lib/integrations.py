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
from typing_extensions import override

from zerver.lib.storage import static_path
from zerver.lib.validator import check_bool, check_string
from zerver.lib.webhooks.common import PresetUrlOption, WebhookConfigOption, WebhookUrlOption
from zerver.webhooks import fixtureless_integrations

"""This module declares all of the (documented) integrations available
in the Zulip server.

The Integration class is used as part of generating the
documentation on the /integrations/ page, while the
IncomingWebhookIntegration class is also used to generate the URLs in
`zproject/urls.py` for incoming webhook integrations.

To add a new integration, register it in the appropriate *_INTEGRATIONS
list. For example, to add a new incoming webhook integration, declare a
IncomingWebhookIntegration in the INCOMING_WEBHOOK_INTEGRATIONS list. All
*_INTEGRATIONS lists are automatically aggregated into the INTEGRATIONS dict.

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
# INCOMING_WEBHOOK_INTEGRATIONS and NO_SCREENSHOT_CONFIG, but defined explicitly to
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
    "mastodon",
    "mercurial",
    "nagios",
    "notion",
    "openshift",
    "perforce",
    "puppet",
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
        fallback_logo_path: str | None = None,
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

        self.logo_path = logo if logo is not None else self.get_logo_path(fallback_logo_path)
        self.logo_url = staticfiles_storage.url(self.logo_path)

        if display_name is None:
            display_name = name.title()
        self.display_name = display_name

        if doc is None:
            doc = self.DEFAULT_DOC_PATH.format(name=self.name)
        self.doc = doc

    def is_enabled_in_catalog(self) -> bool:
        return True

    def get_logo_path(self, fallback_logo_path: str | None = None) -> str:
        paths_to_check = [
            self.DEFAULT_LOGO_STATIC_PATH_SVG.format(name=self.name),
            self.DEFAULT_LOGO_STATIC_PATH_PNG.format(name=self.name),
        ]
        if fallback_logo_path is not None:
            paths_to_check.append(fallback_logo_path)

        for potential_path in paths_to_check:
            if os.path.isfile(static_path(potential_path)):
                return potential_path

        raise AssertionError(
            f"Could not find a logo for integration {self.name}. Paths checked: {', '.join(paths_to_check)}"
        )

    def get_bot_avatar_path(self) -> str:
        name = os.path.splitext(os.path.basename(self.logo_path))[0]
        return self.DEFAULT_BOT_AVATAR_PATH.format(name=name)

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
            logo=logo,
            fallback_logo_path=self.ZULIP_LOGO_STATIC_PATH_PNG,
        )

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


class IncomingWebhookIntegration(Integration):
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
    integration: IncomingWebhookIntegration, screenshot_config: WebhookScreenshotConfig
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
    ZULIP_LOGO_STATIC_PATH_PNG = "images/logo/zulip-icon-128x128.png"

    def __init__(self, name: str, *args: Any, **kwargs: Any) -> None:
        assert kwargs.get("client_name") is None
        kwargs["client_name"] = self.DEFAULT_CLIENT_NAME.format(name=name.title())
        kwargs["fallback_logo_path"] = self.ZULIP_LOGO_STATIC_PATH_PNG
        super().__init__(name, *args, **kwargs)

    @override
    def is_enabled_in_catalog(self) -> bool:
        # Only integrations with docs can be part of the catalog
        # Embedded bots do not have docs
        return False


EMBEDDED_BOTS: list[EmbeddedBotIntegration] = [
    EmbeddedBotIntegration("converter", []),
    EmbeddedBotIntegration("encrypt", []),
    EmbeddedBotIntegration("helloworld", []),
    EmbeddedBotIntegration("virtual_fs", []),
    EmbeddedBotIntegration("giphy", []),
    EmbeddedBotIntegration("followup", []),
]

INCOMING_WEBHOOK_INTEGRATIONS: list[IncomingWebhookIntegration] = [
    IncomingWebhookIntegration(
        "airbrake", ["monitoring"], [WebhookScreenshotConfig("error_message.json")]
    ),
    IncomingWebhookIntegration(
        "airbyte", ["deployment"], [WebhookScreenshotConfig("airbyte_job_payload_success.json")]
    ),
    IncomingWebhookIntegration(
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
    IncomingWebhookIntegration(
        "ansibletower",
        ["deployment"],
        [WebhookScreenshotConfig("job_successful_multiple_hosts.json")],
        display_name="Ansible Tower",
    ),
    IncomingWebhookIntegration(
        "appfollow",
        ["marketing", "customer-support"],
        [WebhookScreenshotConfig("review.json")],
        display_name="AppFollow",
    ),
    IncomingWebhookIntegration(
        "appveyor",
        ["continuous-integration"],
        [WebhookScreenshotConfig("appveyor_build_success.json")],
        display_name="AppVeyor",
    ),
    IncomingWebhookIntegration(
        "azuredevops",
        ["continuous-integration"],
        [WebhookScreenshotConfig("code_push.json")],
        display_name="AzureDevOps",
        url_options=[WebhookUrlOption.build_preset_config(PresetUrlOption.BRANCHES)],
    ),
    IncomingWebhookIntegration(
        "basecamp", ["project-management"], [WebhookScreenshotConfig("doc_active.json")]
    ),
    IncomingWebhookIntegration(
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
    IncomingWebhookIntegration(
        "beeminder",
        ["productivity"],
        # The fixture's goal.losedate needs to be modified dynamically
        # before uncommenting the screenshot config below.
        # [WebhookScreenshotConfig("derail_worried.json")],
        display_name="Beeminder",
    ),
    IncomingWebhookIntegration(
        "bitbucket2",
        ["version-control"],
        [
            WebhookScreenshotConfig(
                "push.json",
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
    IncomingWebhookIntegration(
        "buildbot", ["continuous-integration"], [WebhookScreenshotConfig("started.json")]
    ),
    IncomingWebhookIntegration(
        "canarytoken",
        ["monitoring"],
        [WebhookScreenshotConfig("canarytoken_real.json")],
        display_name="Thinkst Canarytokens",
    ),
    IncomingWebhookIntegration(
        "circleci",
        ["continuous-integration"],
        [WebhookScreenshotConfig("github_job_completed.json")],
        display_name="CircleCI",
    ),
    IncomingWebhookIntegration(
        "clubhouse", ["project-management"], [WebhookScreenshotConfig("story_create.json")]
    ),
    IncomingWebhookIntegration(
        "codeship",
        ["continuous-integration", "deployment"],
        [WebhookScreenshotConfig("error_build.json")],
    ),
    IncomingWebhookIntegration(
        "crashlytics", ["monitoring"], [WebhookScreenshotConfig("issue_message.json")]
    ),
    IncomingWebhookIntegration(
        "dbt",
        ["deployment"],
        [WebhookScreenshotConfig("job_run_completed_errored.json")],
        display_name="DBT",
        url_options=[
            WebhookUrlOption(name="access_url", label="DBT Access URL", validator=check_string)
        ],
    ),
    IncomingWebhookIntegration(
        "delighted",
        ["customer-support", "marketing"],
        [WebhookScreenshotConfig("survey_response_updated_promoter.json")],
    ),
    IncomingWebhookIntegration(
        "dialogflow",
        ["customer-support"],
        [WebhookScreenshotConfig("weather_app.json", extra_params={"email": "iago@zulip.com"})],
    ),
    IncomingWebhookIntegration(
        "dropbox", ["productivity"], [WebhookScreenshotConfig("file_updated.json")]
    ),
    IncomingWebhookIntegration(
        "errbit", ["monitoring"], [WebhookScreenshotConfig("error_message.json")]
    ),
    IncomingWebhookIntegration(
        "flock", ["communication"], [WebhookScreenshotConfig("messages.json")]
    ),
    IncomingWebhookIntegration(
        "freshdesk",
        ["customer-support"],
        [WebhookScreenshotConfig("ticket_created.json", image_name="004.png", use_basic_auth=True)],
    ),
    IncomingWebhookIntegration(
        "freshping", ["monitoring"], [WebhookScreenshotConfig("freshping_check_unreachable.json")]
    ),
    IncomingWebhookIntegration(
        "freshstatus",
        ["monitoring", "customer-support"],
        [WebhookScreenshotConfig("freshstatus_incident_open.json")],
    ),
    IncomingWebhookIntegration(
        "front",
        ["customer-support", "communication"],
        [WebhookScreenshotConfig("inbound_message.json")],
    ),
    IncomingWebhookIntegration(
        "gitea",
        ["version-control"],
        [WebhookScreenshotConfig("pull_request__merged.json", channel="commits")],
        url_options=[WebhookUrlOption.build_preset_config(PresetUrlOption.BRANCHES)],
    ),
    IncomingWebhookIntegration(
        "github",
        ["version-control", "continuous-integration", "project-management"],
        [WebhookScreenshotConfig("push__1_commit.json", channel="commits")],
        display_name="GitHub",
        url_options=[
            WebhookUrlOption.build_preset_config(PresetUrlOption.BRANCHES),
            WebhookUrlOption.build_preset_config(PresetUrlOption.IGNORE_PRIVATE_REPOSITORIES),
            WebhookUrlOption(
                name="include_repository_name",
                label="Include repository name in the notifications",
                validator=check_bool,
            ),
        ],
    ),
    IncomingWebhookIntegration(
        "githubsponsors",
        ["financial"],
        [WebhookScreenshotConfig("created.json", channel="github")],
        display_name="GitHub Sponsors",
        logo="images/integrations/logos/github.svg",
        dir_name="github",
        doc="github/githubsponsors.md",
    ),
    IncomingWebhookIntegration(
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
    IncomingWebhookIntegration(
        "gocd",
        ["continuous-integration"],
        [WebhookScreenshotConfig("pipeline_with_mixed_job_result.json")],
        display_name="GoCD",
    ),
    IncomingWebhookIntegration(
        "gogs",
        ["version-control"],
        [WebhookScreenshotConfig("pull_request__opened.json", channel="commits")],
        url_options=[WebhookUrlOption.build_preset_config(PresetUrlOption.BRANCHES)],
    ),
    IncomingWebhookIntegration(
        "gosquared",
        ["marketing"],
        [WebhookScreenshotConfig("traffic_spike.json")],
        display_name="GoSquared",
    ),
    IncomingWebhookIntegration(
        "grafana", ["monitoring"], [WebhookScreenshotConfig("alert_values_v11.json")]
    ),
    IncomingWebhookIntegration(
        "greenhouse", ["hr"], [WebhookScreenshotConfig("candidate_stage_change.json")]
    ),
    IncomingWebhookIntegration(
        "groove", ["customer-support"], [WebhookScreenshotConfig("ticket_started.json")]
    ),
    IncomingWebhookIntegration(
        "harbor",
        ["deployment"],
        [WebhookScreenshotConfig("scanning_completed.json")],
    ),
    IncomingWebhookIntegration(
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
    IncomingWebhookIntegration(
        "helloworld", ["misc"], [WebhookScreenshotConfig("hello.json")], display_name="Hello World"
    ),
    IncomingWebhookIntegration("heroku", ["deployment"], [WebhookScreenshotConfig("deploy.txt")]),
    IncomingWebhookIntegration(
        "homeassistant",
        ["misc"],
        [WebhookScreenshotConfig("reqwithtitle.json")],
        display_name="Home Assistant",
    ),
    IncomingWebhookIntegration("ifttt", ["meta-integration"], display_name="IFTTT"),
    IncomingWebhookIntegration(
        "insping", ["monitoring"], [WebhookScreenshotConfig("website_state_available.json")]
    ),
    IncomingWebhookIntegration(
        "intercom",
        ["customer-support"],
        [WebhookScreenshotConfig("conversation_admin_replied.json")],
    ),
    IncomingWebhookIntegration(
        "jira",
        ["project-management"],
        [WebhookScreenshotConfig("created_v1.json")],
    ),
    IncomingWebhookIntegration(
        "jotform", ["productivity"], [WebhookScreenshotConfig("screenshot_response.multipart")]
    ),
    IncomingWebhookIntegration(
        "json",
        ["misc"],
        [WebhookScreenshotConfig("json_github_push__1_commit.json")],
        display_name="JSON formatter",
    ),
    IncomingWebhookIntegration(
        "librato",
        ["monitoring"],
        [WebhookScreenshotConfig("three_conditions_alert.json", payload_as_query_param=True)],
    ),
    IncomingWebhookIntegration(
        "lidarr", ["entertainment"], [WebhookScreenshotConfig("lidarr_album_grabbed.json")]
    ),
    IncomingWebhookIntegration(
        "linear", ["project-management"], [WebhookScreenshotConfig("issue_create_complex.json")]
    ),
    IncomingWebhookIntegration(
        "mention", ["marketing"], [WebhookScreenshotConfig("webfeeds.json")]
    ),
    IncomingWebhookIntegration(
        "netlify",
        ["deployment", "continuous-integration"],
        [WebhookScreenshotConfig("deploy_building.json")],
    ),
    IncomingWebhookIntegration(
        "newrelic",
        ["monitoring"],
        [WebhookScreenshotConfig("incident_activated_new_default_payload.json")],
        display_name="New Relic",
    ),
    IncomingWebhookIntegration(
        "opencollective",
        ["financial"],
        [WebhookScreenshotConfig("one_time_donation.json")],
        display_name="Open Collective",
    ),
    IncomingWebhookIntegration(
        "openproject",
        ["project-management"],
        [WebhookScreenshotConfig("project_created__without_parent.json")],
        display_name="OpenProject",
    ),
    IncomingWebhookIntegration(
        "opensearch",
        ["monitoring"],
        [WebhookScreenshotConfig("example_template.txt")],
        display_name="OpenSearch",
    ),
    IncomingWebhookIntegration(
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
    IncomingWebhookIntegration(
        "pagerduty",
        ["monitoring"],
        [WebhookScreenshotConfig("trigger_v2.json")],
        display_name="PagerDuty",
    ),
    IncomingWebhookIntegration(
        "papertrail",
        ["monitoring"],
        [WebhookScreenshotConfig("short_post.json", payload_as_query_param=True)],
    ),
    IncomingWebhookIntegration(
        "patreon", ["financial"], [WebhookScreenshotConfig("members_pledge_create.json")]
    ),
    IncomingWebhookIntegration(
        "pingdom", ["monitoring"], [WebhookScreenshotConfig("http_up_to_down.json")]
    ),
    IncomingWebhookIntegration(
        "pivotal",
        ["project-management"],
        [WebhookScreenshotConfig("v5_type_changed.json")],
        display_name="Pivotal Tracker",
    ),
    IncomingWebhookIntegration(
        "radarr", ["entertainment"], [WebhookScreenshotConfig("radarr_movie_grabbed.json")]
    ),
    IncomingWebhookIntegration(
        "raygun", ["monitoring"], [WebhookScreenshotConfig("new_error.json")]
    ),
    IncomingWebhookIntegration(
        "redmine", ["project-management"], [WebhookScreenshotConfig("issue_opened.json")]
    ),
    IncomingWebhookIntegration(
        "reviewboard",
        ["productivity"],
        [WebhookScreenshotConfig("review_request_published.json")],
        display_name="Review Board",
    ),
    IncomingWebhookIntegration(
        "rhodecode",
        ["version-control"],
        [WebhookScreenshotConfig("push.json", channel="commits")],
        display_name="RhodeCode",
        url_options=[WebhookUrlOption.build_preset_config(PresetUrlOption.BRANCHES)],
    ),
    IncomingWebhookIntegration("rundeck", ["deployment"], [WebhookScreenshotConfig("start.json")]),
    IncomingWebhookIntegration(
        "semaphore",
        ["continuous-integration", "deployment"],
        [WebhookScreenshotConfig("pull_request.json")],
    ),
    IncomingWebhookIntegration(
        "sentry", ["monitoring"], [WebhookScreenshotConfig("event_for_exception_python.json")]
    ),
    IncomingWebhookIntegration(
        "slack",
        ["communication"],
        url_options=[
            WebhookUrlOption.build_preset_config(PresetUrlOption.CHANNEL_MAPPING),
        ],
    ),
    IncomingWebhookIntegration(
        "slack_incoming",
        ["communication", "meta-integration"],
        display_name="Slack-compatible webhook",
        logo="images/integrations/logos/slack.svg",
    ),
    IncomingWebhookIntegration(
        "sonarqube",
        ["continuous-integration", "monitoring"],
        [WebhookScreenshotConfig("error.json")],
        display_name="SonarQube",
    ),
    IncomingWebhookIntegration(
        "sonarr", ["entertainment"], [WebhookScreenshotConfig("sonarr_episode_grabbed.json")]
    ),
    IncomingWebhookIntegration(
        "splunk", ["monitoring"], [WebhookScreenshotConfig("search_one_result.json")]
    ),
    IncomingWebhookIntegration(
        "statuspage",
        ["customer-support", "monitoring"],
        [WebhookScreenshotConfig("incident_created.json")],
    ),
    IncomingWebhookIntegration(
        "stripe", ["financial"], [WebhookScreenshotConfig("charge_succeeded__card.json")]
    ),
    IncomingWebhookIntegration(
        "taiga", ["project-management"], [WebhookScreenshotConfig("userstory_changed_status.json")]
    ),
    IncomingWebhookIntegration(
        "teamcity", ["continuous-integration"], [WebhookScreenshotConfig("success.json")]
    ),
    IncomingWebhookIntegration(
        "thinkst", ["monitoring"], [WebhookScreenshotConfig("canary_consolidated_port_scan.json")]
    ),
    IncomingWebhookIntegration(
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
    IncomingWebhookIntegration(
        "travis",
        ["continuous-integration"],
        [WebhookScreenshotConfig("build.json", payload_as_query_param=True)],
        display_name="Travis CI",
    ),
    IncomingWebhookIntegration(
        "trello", ["project-management"], [WebhookScreenshotConfig("adding_comment_to_card.json")]
    ),
    IncomingWebhookIntegration(
        "updown", ["monitoring"], [WebhookScreenshotConfig("check_multiple_events.json")]
    ),
    IncomingWebhookIntegration(
        "uptimerobot",
        ["monitoring"],
        [WebhookScreenshotConfig("uptimerobot_monitor_up.json")],
        display_name="UptimeRobot",
    ),
    IncomingWebhookIntegration(
        "wekan",
        ["productivity", "project-management"],
        [WebhookScreenshotConfig("add_comment.json")],
    ),
    IncomingWebhookIntegration(
        "wordpress",
        ["marketing"],
        [WebhookScreenshotConfig("publish_post.txt", "wordpress_post_created.png")],
        display_name="WordPress",
    ),
    IncomingWebhookIntegration(
        "zabbix", ["monitoring"], [WebhookScreenshotConfig("zabbix_alert.json")]
    ),
    IncomingWebhookIntegration("zapier", ["meta-integration"]),
    IncomingWebhookIntegration(
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
    Integration("tenor", ["misc"], display_name="Tenor"),
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
    PythonAPIIntegration(
        "codebase",
        ["version-control", "project-management"],
        [FixturelessScreenshotConfigOptions(channel="commits")],
    ),
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
    PythonAPIIntegration(
        "perforce", ["version-control"], [FixturelessScreenshotConfigOptions(channel="commits")]
    ),
    PythonAPIIntegration("rss", ["communication"], display_name="RSS"),
    PythonAPIIntegration(
        "svn",
        ["version-control"],
        [FixturelessScreenshotConfigOptions(channel="commits")],
        display_name="Subversion",
    ),
    PythonAPIIntegration("trac", ["project-management"]),
]

BOT_INTEGRATIONS: list[BotIntegration] = [
    BotIntegration("github_detail", ["version-control", "bots"], display_name="GitHub Detail"),
    BotIntegration("xkcd", ["bots", "entertainment"], display_name="xkcd"),
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
    (
        # To avoid namespace collisions, use a prefix for embedded bots
        f"embedded_bot_{integration.name}"
        if isinstance(integration, EmbeddedBotIntegration)
        else integration.name
    ): integration
    for integration in chain(
        INCOMING_WEBHOOK_INTEGRATIONS,
        PYTHON_API_INTEGRATIONS,
        BOT_INTEGRATIONS,
        HUBOT_INTEGRATIONS,
        EMBEDDED_BOTS,
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
        # these integrations do not send messages
        "giphy",
        "tenor",
        # the integration is planned to be removed
        "twitter",
    }
)

NO_SCREENSHOT_CONFIG = INTEGRATIONS_MISSING_SCREENSHOT_CONFIG | INTEGRATIONS_WITHOUT_SCREENSHOTS


def get_all_event_types_for_integration(integration: Integration) -> list[str] | None:
    integration = INTEGRATIONS[integration.name]
    if isinstance(integration, IncomingWebhookIntegration):
        if integration.name == "githubsponsors":
            return import_string("zerver.webhooks.github.view.SPONSORS_EVENT_TYPES")
        function = integration.get_function()
        if hasattr(function, "_all_event_types"):
            return function._all_event_types
    return None
