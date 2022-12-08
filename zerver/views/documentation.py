import os
import random
import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.template import loader
from django.views.generic import TemplateView

from zerver.context_processors import zulip_default_context
from zerver.decorator import add_google_analytics_context
from zerver.lib.integrations import (
    CATEGORIES,
    INTEGRATIONS,
    META_CATEGORY,
    HubotIntegration,
    WebhookIntegration,
)
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.subdomains import get_subdomain
from zerver.lib.templates import render_markdown_path
from zerver.models import Realm
from zerver.openapi.openapi import get_endpoint_from_operationid, get_openapi_summary


@dataclass
class DocumentationArticle:
    article_path: str
    article_http_status: int
    endpoint_path: Optional[str]
    endpoint_method: Optional[str]


def add_api_uri_context(context: Dict[str, Any], request: HttpRequest) -> None:
    context.update(zulip_default_context(request))

    subdomain = get_subdomain(request)
    if subdomain != Realm.SUBDOMAIN_FOR_ROOT_DOMAIN or not settings.ROOT_DOMAIN_LANDING_PAGE:
        display_subdomain = subdomain
        html_settings_links = True
    else:
        display_subdomain = "yourZulipDomain"
        html_settings_links = False

    display_host = Realm.host_for_subdomain(display_subdomain)
    api_url_scheme_relative = display_host + "/api"
    api_url = settings.EXTERNAL_URI_SCHEME + api_url_scheme_relative
    zulip_url = settings.EXTERNAL_URI_SCHEME + display_host

    context["external_uri_scheme"] = settings.EXTERNAL_URI_SCHEME
    context["api_url"] = api_url
    context["api_url_scheme_relative"] = api_url_scheme_relative
    context["zulip_url"] = zulip_url

    context["html_settings_links"] = html_settings_links


class ApiURLView(TemplateView):
    def get_context_data(self, **kwargs: Any) -> Dict[str, str]:
        context = super().get_context_data(**kwargs)
        add_api_uri_context(context, self.request)
        return context


class MarkdownDirectoryView(ApiURLView):
    path_template = ""
    policies_view = False

    def get_path(self, article: str) -> DocumentationArticle:
        http_status = 200
        if article == "":
            article = "index"
        elif article == "include/sidebar_index":
            pass
        elif "/" in article:
            article = "missing"
            http_status = 404
        elif len(article) > 100 or not re.match("^[0-9a-zA-Z_-]+$", article):
            article = "missing"
            http_status = 404

        path = self.path_template % (article,)
        endpoint_name = None
        endpoint_method = None

        if self.policies_view and self.path_template.startswith("/"):
            # This block is required because neither the Django
            # template loader nor the article_path logic below support
            # settings.POLICIES_DIRECTORY being an absolute path.
            if not os.path.exists(path):
                article = "missing"
                http_status = 404
                path = self.path_template % (article,)

            return DocumentationArticle(
                article_path=path,
                article_http_status=http_status,
                endpoint_path=None,
                endpoint_method=None,
            )

        if path == "/zerver/api/api-doc-template.md":
            # This template shouldn't be accessed directly.
            return DocumentationArticle(
                article_path=self.path_template % ("missing",),
                article_http_status=404,
                endpoint_path=None,
                endpoint_method=None,
            )

        # The following is a somewhat hacky approach to extract titles from articles.
        # Hack: `context["article"] has a leading `/`, so we use + to add directories.
        article_path = os.path.join(settings.DEPLOY_ROOT, "templates") + path
        if (not os.path.exists(article_path)) and self.path_template == "/zerver/api/%s.md":
            try:
                endpoint_name, endpoint_method = get_endpoint_from_operationid(article)
                path = "/zerver/api/api-doc-template.md"
            except AssertionError:
                return DocumentationArticle(
                    article_path=self.path_template % ("missing",),
                    article_http_status=404,
                    endpoint_path=None,
                    endpoint_method=None,
                )

        try:
            loader.get_template(path)
            return DocumentationArticle(
                article_path=path,
                article_http_status=http_status,
                endpoint_path=endpoint_name,
                endpoint_method=endpoint_method,
            )
        except loader.TemplateDoesNotExist:
            return DocumentationArticle(
                article_path=self.path_template % ("missing",),
                article_http_status=404,
                endpoint_path=None,
                endpoint_method=None,
            )

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        article = kwargs["article"]
        context: Dict[str, Any] = super().get_context_data()

        documentation_article = self.get_path(article)
        context["article"] = documentation_article.article_path
        if documentation_article.article_path.startswith("/") and os.path.exists(
            documentation_article.article_path
        ):
            # Absolute path case
            article_path = documentation_article.article_path
        elif documentation_article.article_path.startswith("/"):
            # Hack: `context["article"] has a leading `/`, so we use + to add directories.
            article_path = (
                os.path.join(settings.DEPLOY_ROOT, "templates") + documentation_article.article_path
            )
        else:
            article_path = os.path.join(
                settings.DEPLOY_ROOT, "templates", documentation_article.article_path
            )

        # For disabling the "Back to home" on the homepage
        context["not_index_page"] = not context["article"].endswith("/index.md")
        if self.path_template == "/zerver/help/%s.md":
            context["page_is_help_center"] = True
            context["doc_root"] = "/help/"
            context["doc_root_title"] = "Help center"
            sidebar_article = self.get_path("include/sidebar_index")
            sidebar_index = sidebar_article.article_path
            title_base = "Zulip help center"
        elif self.path_template == f"{settings.POLICIES_DIRECTORY}/%s.md":
            context["page_is_policy_center"] = True
            context["doc_root"] = "/policies/"
            context["doc_root_title"] = "Terms and policies"
            sidebar_article = self.get_path("sidebar_index")
            sidebar_index = sidebar_article.article_path
            title_base = "Zulip terms and policies"
        else:
            context["page_is_api_center"] = True
            context["doc_root"] = "/api/"
            context["doc_root_title"] = "API documentation"
            sidebar_article = self.get_path("sidebar_index")
            sidebar_index = sidebar_article.article_path
            title_base = "Zulip API documentation"

        # The following is a somewhat hacky approach to extract titles from articles.
        endpoint_name = None
        endpoint_method = None
        if os.path.exists(article_path):
            with open(article_path) as article_file:
                first_line = article_file.readlines()[0]
            # Strip the header and then use the first line to get the article title
            if context["article"] == "/zerver/api/api-doc-template.md":
                endpoint_name, endpoint_method = (
                    documentation_article.endpoint_path,
                    documentation_article.endpoint_method,
                )
                assert endpoint_name is not None
                assert endpoint_method is not None
                article_title = get_openapi_summary(endpoint_name, endpoint_method)
            elif (
                self.path_template == "/zerver/api/%s.md" and "{generate_api_header(" in first_line
            ):
                api_operation = context["PAGE_METADATA_URL"].split("/api/")[1]
                endpoint_name, endpoint_method = get_endpoint_from_operationid(api_operation)
                article_title = get_openapi_summary(endpoint_name, endpoint_method)
            else:
                article_title = first_line.lstrip("#").strip()
                endpoint_name = endpoint_method = None
            if context["not_index_page"]:
                context["PAGE_TITLE"] = f"{article_title} | {title_base}"
            else:
                context["PAGE_TITLE"] = title_base
            request_notes = RequestNotes.get_notes(self.request)
            request_notes.placeholder_open_graph_description = (
                f"REPLACEMENT_PAGE_DESCRIPTION_{int(2**24 * random.random())}"
            )
            context["PAGE_DESCRIPTION"] = request_notes.placeholder_open_graph_description

        context["sidebar_index"] = sidebar_index
        # An "article" might require the api_uri_context to be rendered
        api_uri_context: Dict[str, Any] = {}
        add_api_uri_context(api_uri_context, self.request)
        api_uri_context["run_content_validators"] = True
        context["api_uri_context"] = api_uri_context
        if endpoint_name and endpoint_method:
            context["api_uri_context"]["API_ENDPOINT_NAME"] = endpoint_name + ":" + endpoint_method
        add_google_analytics_context(context)
        return context

    def get(
        self, request: HttpRequest, *args: object, article: str = "", **kwargs: object
    ) -> HttpResponse:
        # Hack: It's hard to reinitialize urls.py from tests, and so
        # we want to defer the use of settings.POLICIES_DIRECTORY to
        # runtime.
        if self.policies_view:
            self.path_template = f"{settings.POLICIES_DIRECTORY}/%s.md"

        documentation_article = self.get_path(article)
        http_status = documentation_article.article_http_status
        result = super().get(request, article=article)
        if http_status != 200:
            result.status_code = http_status
        return result


def add_integrations_context(context: Dict[str, Any]) -> None:
    alphabetical_sorted_categories = OrderedDict(sorted(CATEGORIES.items()))
    alphabetical_sorted_integration = OrderedDict(sorted(INTEGRATIONS.items()))
    enabled_integrations_count = len(list(filter(lambda v: v.is_enabled(), INTEGRATIONS.values())))
    # Subtract 1 so saying "Over X integrations" is correct. Then,
    # round down to the nearest multiple of 10.
    integrations_count_display = ((enabled_integrations_count - 1) // 10) * 10
    context["categories_dict"] = alphabetical_sorted_categories
    context["integrations_dict"] = alphabetical_sorted_integration
    context["integrations_count_display"] = integrations_count_display


def add_integrations_open_graph_context(context: Dict[str, Any], request: HttpRequest) -> None:
    path_name = request.path.rstrip("/").split("/")[-1]
    description = (
        "Zulip comes with over a hundred native integrations out of the box, "
        "and integrates with Zapier and IFTTT to provide hundreds more. "
        "Connect the apps you use every day to Zulip."
    )

    if path_name in INTEGRATIONS:
        integration = INTEGRATIONS[path_name]
        context["PAGE_TITLE"] = f"{integration.display_name} | Zulip integrations"
        context["PAGE_DESCRIPTION"] = description

    elif path_name in CATEGORIES:
        category = CATEGORIES[path_name]
        if path_name in META_CATEGORY:
            context["PAGE_TITLE"] = f"{category} | Zulip integrations"
        else:
            context["PAGE_TITLE"] = f"{category} tools | Zulip integrations"
        context["PAGE_DESCRIPTION"] = description

    elif path_name == "integrations":
        context["PAGE_TITLE"] = "Zulip integrations"
        context["PAGE_DESCRIPTION"] = description


class IntegrationView(ApiURLView):
    template_name = "zerver/integrations/index.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context: Dict[str, Any] = super().get_context_data(**kwargs)
        add_integrations_context(context)
        add_integrations_open_graph_context(context, self.request)
        add_google_analytics_context(context)
        return context


@has_request_variables
def integration_doc(request: HttpRequest, integration_name: str = REQ()) -> HttpResponse:
    # FIXME: This check is jQuery-specific.
    if request.headers.get("x-requested-with") != "XMLHttpRequest":
        return HttpResponseNotFound()

    try:
        integration = INTEGRATIONS[integration_name]
    except KeyError:
        return HttpResponseNotFound()

    context: Dict[str, Any] = {}
    add_api_uri_context(context, request)

    context["integration_name"] = integration.name
    context["integration_display_name"] = integration.display_name
    context["recommended_stream_name"] = integration.stream_name
    if isinstance(integration, WebhookIntegration):
        context["integration_url"] = integration.url[3:]
        if (
            hasattr(integration.function, "_all_event_types")
            and integration.function._all_event_types is not None
        ):
            context["all_event_types"] = integration.function._all_event_types
    if isinstance(integration, HubotIntegration):
        context["hubot_docs_url"] = integration.hubot_docs_url

    doc_html_str = render_markdown_path(integration.doc, context, integration_doc=True)

    return HttpResponse(doc_html_str)
