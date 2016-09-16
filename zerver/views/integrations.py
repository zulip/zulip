from __future__ import absolute_import
from typing import Optional, Any, Dict
from collections import OrderedDict
from django.views.generic import TemplateView
from django.conf import settings
from django.http import HttpRequest, HttpResponse

import ujson

from zerver.lib import bugdown
from zerver.lib.integrations import INTEGRATIONS
from zproject.jinja2 import render_to_response

def add_api_uri_context(context, request):
    # type: (Dict[str, Any], HttpRequest) -> None
    external_api_path_subdomain = settings.EXTERNAL_API_PATH
    external_api_uri_subdomain = settings.EXTERNAL_API_URI

    context['external_api_path_subdomain'] = external_api_path_subdomain
    context['external_api_uri_subdomain'] = external_api_uri_subdomain

class ApiURLView(TemplateView):
    def get_context_data(self, **kwargs):
        # type: (Optional[Dict[str, Any]]) -> Dict[str, str]
        context = super(ApiURLView, self).get_context_data(**kwargs)
        add_api_uri_context(context, self.request)
        return context


class APIView(ApiURLView):
    template_name = 'zerver/api.html'


class IntegrationView(ApiURLView):
    template_name = 'zerver/integrations.html'

    def get_context_data(self, **kwargs):
        # type: (Optional[Dict[str, Any]]) -> Dict[str, Any]
        context = super(IntegrationView, self).get_context_data(**kwargs)  # type: Dict[str, Any]
        alphabetical_sorted_integration = OrderedDict(sorted(INTEGRATIONS.items()))
        context['integrations_dict'] = alphabetical_sorted_integration

        settings_html = '<a href="../#settings">Zulip settings page</a>'
        subscriptions_html = '<a target="_blank" href="../#subscriptions">subscriptions page</a>'

        context['settings_html'] = settings_html
        context['subscriptions_html'] = subscriptions_html

        return context


def api_endpoint_docs(request):
    # type: (HttpRequest) -> HttpResponse
    context = {} # type: Dict[str, Any]
    add_api_uri_context(context, request)

    raw_calls = open('templates/zerver/api_content.json', 'r').read()
    calls = ujson.loads(raw_calls)
    langs = set()
    for call in calls:
        call["endpoint"] = "%s/v1/%s" % (context["external_api_uri_subdomain"],
                                         call["endpoint"])
        call["example_request"]["curl"] = call["example_request"]["curl"].replace("https://api.zulip.com",
                                                                                  context["external_api_uri_subdomain"])
        response = call['example_response']
        if '\n' not in response:
            # For 1-line responses, pretty-print them
            extended_response = response.replace(", ", ",\n ")
        else:
            extended_response = response
        call['rendered_response'] = bugdown.convert("~~~ .py\n" + extended_response + "\n~~~\n", "default")
        for example_type in ('request', 'response'):
            for lang in call.get('example_' + example_type, []):
                langs.add(lang)
    return render_to_response(
            'zerver/api_endpoints.html', {
                'content': calls,
                'langs': langs,
                },
        request=request)
