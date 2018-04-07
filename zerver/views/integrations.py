from typing import Optional, Any, Dict
from collections import OrderedDict
from django.views.generic import TemplateView
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.template import loader
from django.shortcuts import render

import os
import ujson

from zerver.lib import bugdown
from zerver.lib.integrations import CATEGORIES, INTEGRATIONS, HubotIntegration, \
    WebhookIntegration, EmailIntegration
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.subdomains import get_subdomain
from zerver.models import Realm
from zerver.templatetags.app_filters import render_markdown_path

def add_api_uri_context(context: Dict[str, Any], request: HttpRequest) -> None:
    subdomain = get_subdomain(request)
    if (subdomain != Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
            or not settings.ROOT_DOMAIN_LANDING_PAGE):
        display_subdomain = subdomain
        html_settings_links = True
    else:
        display_subdomain = 'yourZulipDomain'
        html_settings_links = False

    display_host = Realm.host_for_subdomain(display_subdomain)
    api_url_scheme_relative = display_host + "/api"
    api_url = settings.EXTERNAL_URI_SCHEME + api_url_scheme_relative

    context['external_uri_scheme'] = settings.EXTERNAL_URI_SCHEME
    context['api_url'] = api_url
    context['api_url_scheme_relative'] = api_url_scheme_relative

    context["html_settings_links"] = html_settings_links
    if html_settings_links:
        settings_html = '<a href="/#settings">Zulip settings page</a>'
        subscriptions_html = '<a target="_blank" href="/#streams">streams page</a>'
    else:
        settings_html = 'Zulip settings page'
        subscriptions_html = 'streams page'
    context['settings_html'] = settings_html
    context['subscriptions_html'] = subscriptions_html

class ApiURLView(TemplateView):
    def get_context_data(self, **kwargs: Any) -> Dict[str, str]:
        context = super().get_context_data(**kwargs)
        add_api_uri_context(context, self.request)
        return context

class APIView(ApiURLView):
    template_name = 'zerver/api.html'


class MarkdownDirectoryView(ApiURLView):
    path_template = ""

    def get_path(self, article: str) -> str:
        if article == "":
            article = "index"
        elif "/" in article:
            article = "missing"
        return self.path_template % (article,)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        article = kwargs["article"]
        context = super().get_context_data()  # type: Dict[str, Any]
        path = self.get_path(article)
        try:
            loader.get_template(path)
            context["article"] = path
        except loader.TemplateDoesNotExist:
            context["article"] = self.get_path("missing")

        # For disabling the "Back to home" on the homepage
        context["not_index_page"] = not path.endswith("/index.md")
        if self.template_name == "zerver/help/main.html":
            context["page_is_help_center"] = True
        else:
            context["page_is_api_center"] = True
        # An "article" might require the api_uri_context to be rendered
        api_uri_context = {}  # type: Dict[str, Any]
        add_api_uri_context(api_uri_context, self.request)
        context["api_uri_context"] = api_uri_context
        return context

    def get(self, request: HttpRequest, article: str="") -> HttpResponse:
        path = self.get_path(article)
        result = super().get(self, article=article)
        try:
            loader.get_template(path)
        except loader.TemplateDoesNotExist:
            # Ensure a 404 response code if no such document
            result.status_code = 404
        if "/" in article:
            result.status_code = 404
        return result


def add_integrations_context(context: Dict[str, Any]) -> None:
    alphabetical_sorted_categories = OrderedDict(sorted(CATEGORIES.items()))
    alphabetical_sorted_integration = OrderedDict(sorted(INTEGRATIONS.items()))
    enabled_integrations_count = len(list(filter(lambda v: v.is_enabled(), INTEGRATIONS.values())))
    # Subtract 1 so saying "Over X integrations" is correct. Then,
    # round down to the nearest multiple of 10.
    integrations_count_display = ((enabled_integrations_count - 1) // 10) * 10
    context['categories_dict'] = alphabetical_sorted_categories
    context['integrations_dict'] = alphabetical_sorted_integration
    context['integrations_count_display'] = integrations_count_display


class IntegrationView(ApiURLView):
    template_name = 'zerver/integrations/index.html'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)  # type: Dict[str, Any]
        add_integrations_context(context)
        return context


@has_request_variables
def integration_doc(request: HttpRequest, integration_name: str=REQ(default=None)) -> HttpResponse:
    try:
        integration = INTEGRATIONS[integration_name]
    except KeyError:
        return HttpResponseNotFound()

    context = {}  # type: Dict[str, Any]
    add_api_uri_context(context, request)

    context['integration_name'] = integration.name
    context['integration_display_name'] = integration.display_name
    if hasattr(integration, 'stream_name'):
        context['recommended_stream_name'] = integration.stream_name
    if isinstance(integration, WebhookIntegration):
        context['integration_url'] = integration.url[3:]
    if isinstance(integration, HubotIntegration):
        context['hubot_docs_url'] = integration.hubot_docs_url
    if isinstance(integration, EmailIntegration):
        context['email_gateway_example'] = settings.EMAIL_GATEWAY_EXAMPLE

    doc_html_str = render_markdown_path(integration.doc, context)

    return HttpResponse(doc_html_str)
