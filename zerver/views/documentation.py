import os
import random
import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.template import loader
from django.template.response import TemplateResponse
from django.views.generic import TemplateView
from lxml import html
from lxml.etree import Element, SubElement, XPath, _Element
from markupsafe import Markup
from typing_extensions import override

from zerver.context_processors import zulip_default_context
from zerver.decorator import add_google_analytics_context
from zerver.lib.html_to_text import get_content_description
from zerver.lib.integrations import (
    CATEGORIES,
    INTEGRATIONS,
    META_CATEGORY,
    HubotIntegration,
    WebhookIntegration,
    get_all_event_types_for_integration,
)
from zerver.lib.request import REQ, has_request_variables
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


def add_api_url_context(context: Dict[str, Any], request: HttpRequest) -> None:
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

    context["external_url_scheme"] = settings.EXTERNAL_URI_SCHEME
    context["api_url"] = api_url
    context["api_url_scheme_relative"] = api_url_scheme_relative
    context["zulip_url"] = zulip_url

    context["html_settings_links"] = html_settings_links


class ApiURLView(TemplateView):
    @override
    def get_context_data(self, **kwargs: Any) -> Dict[str, str]:
        context = super().get_context_data(**kwargs)
        add_api_url_context(context, self.request)
        return context


sidebar_headings = XPath("//*[self::h1 or self::h2 or self::h3 or self::h4]")
sidebar_links = XPath("//a[@href=$url]")


class MarkdownDirectoryView(ApiURLView):
    path_template = ""
    policies_view = False
    help_view = False
    api_doc_view = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._post_render_callbacks: List[Callable[[HttpResponse], Optional[HttpResponse]]] = []

    def add_post_render_callback(
        self, callback: Callable[[HttpResponse], Optional[HttpResponse]]
    ) -> None:
        self._post_render_callbacks.append(callback)

    def get_path(self, article: str) -> DocumentationArticle:
        http_status = 200
        if article == "":
            article = "index"
        elif article == "include/sidebar_index":
            pass
        elif article == "api-doc-template":
            # This markdown template shouldn't be accessed directly.
            article = "missing"
            http_status = 404
        elif "/" in article:
            article = "missing"
            http_status = 404
        elif len(article) > 100 or not re.match(r"^[0-9a-zA-Z_-]+$", article):
            article = "missing"
            http_status = 404

        path = self.path_template % (article,)
        endpoint_name = None
        endpoint_method = None

        if not self.path_template.startswith("/"):
            # Relative paths only used for policies documentation
            # when it is not configured or in the dev environment
            assert self.policies_view

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

        if not os.path.exists(path):
            if self.api_doc_view:
                try:
                    # API endpoints documented in zerver/openapi/zulip.yaml
                    endpoint_name, endpoint_method = get_endpoint_from_operationid(article)
                    path = self.path_template % ("api-doc-template",)
                except AssertionError:
                    return DocumentationArticle(
                        article_path=self.path_template % ("missing",),
                        article_http_status=404,
                        endpoint_path=None,
                        endpoint_method=None,
                    )
            elif self.help_view or self.policies_view:
                article = "missing"
                http_status = 404
                path = self.path_template % (article,)
            else:
                raise AssertionError("Invalid documentation view type")

        return DocumentationArticle(
            article_path=path,
            article_http_status=http_status,
            endpoint_path=endpoint_name,
            endpoint_method=endpoint_method,
        )

    @override
    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        article = kwargs["article"]
        context: Dict[str, Any] = super().get_context_data()

        documentation_article = self.get_path(article)
        context["article"] = documentation_article.article_path
        not_index_page = not context["article"].endswith("/index.md")

        if documentation_article.article_path.startswith("/") and os.path.exists(
            documentation_article.article_path
        ):
            # Absolute path case
            article_absolute_path = documentation_article.article_path
        else:
            # Relative path case
            article_absolute_path = os.path.join(
                settings.DEPLOY_ROOT, "templates", documentation_article.article_path
            )

        if self.help_view:
            context["page_is_help_center"] = True
            context["doc_root"] = "/help/"
            context["doc_root_title"] = "Help center"
            sidebar_article = self.get_path("include/sidebar_index")
            sidebar_index = sidebar_article.article_path
            title_base = "Zulip help center"
        elif self.policies_view:
            context["page_is_policy_center"] = True
            context["doc_root"] = "/policies/"
            context["doc_root_title"] = "Terms and policies"
            sidebar_article = self.get_path("sidebar_index")
            if sidebar_article.article_http_status == 200:
                sidebar_index = sidebar_article.article_path
            else:
                sidebar_index = None
            title_base = "Zulip terms and policies"
        elif self.api_doc_view:
            context["page_is_api_center"] = True
            context["doc_root"] = "/api/"
            context["doc_root_title"] = "API documentation"
            sidebar_article = self.get_path("sidebar_index")
            sidebar_index = sidebar_article.article_path
            title_base = "Zulip API documentation"
        else:
            raise AssertionError("Invalid documentation view type")

        # The following is a somewhat hacky approach to extract titles from articles.
        endpoint_name = None
        endpoint_method = None
        if os.path.exists(article_absolute_path):
            with open(article_absolute_path) as article_file:
                first_line = article_file.readlines()[0]
            if self.api_doc_view and context["article"].endswith("api-doc-template.md"):
                endpoint_name, endpoint_method = (
                    documentation_article.endpoint_path,
                    documentation_article.endpoint_method,
                )
                assert endpoint_name is not None
                assert endpoint_method is not None
                article_title = get_openapi_summary(endpoint_name, endpoint_method)
            elif self.api_doc_view and "{generate_api_header(" in first_line:
                api_operation = context["PAGE_METADATA_URL"].split("/api/")[1]
                endpoint_name, endpoint_method = get_endpoint_from_operationid(api_operation)
                article_title = get_openapi_summary(endpoint_name, endpoint_method)
            else:
                # Strip the header and then use the first line to get the article title
                article_title = first_line.lstrip("#").strip()
                endpoint_name = endpoint_method = None
            if not_index_page:
                context["PAGE_TITLE"] = f"{article_title} | {title_base}"
            else:
                context["PAGE_TITLE"] = title_base
            placeholder_open_graph_description = (
                f"REPLACEMENT_PAGE_DESCRIPTION_{int(2**24 * random.random())}"
            )
            context["PAGE_DESCRIPTION"] = placeholder_open_graph_description

            def update_description(response: HttpResponse) -> None:
                if placeholder_open_graph_description.encode() in response.content:
                    first_paragraph_text = get_content_description(
                        response.content, context["PAGE_METADATA_URL"]
                    )
                    response.content = response.content.replace(
                        placeholder_open_graph_description.encode(),
                        first_paragraph_text.encode(),
                    )

            self.add_post_render_callback(update_description)

        # An "article" might require the api_url_context to be rendered
        api_url_context: Dict[str, Any] = {}
        add_api_url_context(api_url_context, self.request)
        api_url_context["run_content_validators"] = True
        context["api_url_context"] = api_url_context
        if endpoint_name and endpoint_method:
            context["api_url_context"]["API_ENDPOINT_NAME"] = endpoint_name + ":" + endpoint_method

        if sidebar_index is not None:
            sidebar_html = render_markdown_path(sidebar_index)
        else:
            sidebar_html = ""
        tree = html.fragment_fromstring(sidebar_html, create_parent=True)
        if not context.get("page_is_policy_center", False):
            home_h1 = Element("h1")
            home_link = SubElement(home_h1, "a")
            home_link.attrib["class"] = "no-underline"
            home_link.attrib["href"] = context["doc_root"]
            home_link.text = context["doc_root_title"] + " home"
            tree.insert(0, home_h1)
        url = context["doc_root"] + article
        # Remove ID attributes from sidebar headings so they don't conflict with index page headings
        headings = sidebar_headings(tree)
        assert isinstance(headings, list)
        for h in headings:
            assert isinstance(h, _Element)
            h.attrib.pop("id", "")
        # Highlight current article link
        links = sidebar_links(tree, url=url)
        assert isinstance(links, list)
        for a in links:
            assert isinstance(a, _Element)
            old_class = a.attrib.get("class", "")
            assert isinstance(old_class, str)
            a.attrib["class"] = old_class + " highlighted"
        sidebar_html = "".join(html.tostring(child, encoding="unicode") for child in tree)
        context["sidebar_html"] = Markup(sidebar_html)

        add_google_analytics_context(context)
        return context

    @override
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
        assert isinstance(result, TemplateResponse)
        for callback in self._post_render_callbacks:
            result.add_post_render_callback(callback)
        if http_status != 200:
            result.status_code = http_status
        return result


def add_integrations_context(context: Dict[str, Any]) -> None:
    alphabetical_sorted_categories = OrderedDict(sorted(CATEGORIES.items()))
    alphabetical_sorted_integration = OrderedDict(sorted(INTEGRATIONS.items()))
    enabled_integrations_count = sum(v.is_enabled() for v in INTEGRATIONS.values())
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

    @override
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
    add_api_url_context(context, request)

    context["integration_name"] = integration.name
    context["integration_display_name"] = integration.display_name
    context["recommended_channel_name"] = integration.stream_name
    if isinstance(integration, WebhookIntegration):
        context["integration_url"] = integration.url[3:]
        all_event_types = get_all_event_types_for_integration(integration)
        if all_event_types is not None:
            context["all_event_types"] = all_event_types
    if isinstance(integration, HubotIntegration):
        context["hubot_docs_url"] = integration.hubot_docs_url

    doc_html_str = render_markdown_path(integration.doc, context, integration_doc=True)

    return HttpResponse(doc_html_str)
