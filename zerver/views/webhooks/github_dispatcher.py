from __future__ import absolute_import
from django.http import HttpRequest, HttpResponse
from .github_webhook import api_github_webhook
from .github import api_github_landing


def api_github_webhook_dispatch(request):
    # type: (HttpRequest) -> HttpResponse
    if request.META.get('HTTP_X_GITHUB_EVENT'):
        return api_github_webhook(request)
    else:
        return api_github_landing(request)
