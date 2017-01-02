from __future__ import absolute_import
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .github_webhook import api_github_webhook
from .github import api_github_landing

# Since this dispatcher is an API-style endpoint, it needs to be
# explicitly marked as CSRF-exempt
@csrf_exempt
def api_github_webhook_dispatch(request):
    # type: (HttpRequest) -> HttpResponse
    if request.META.get('HTTP_X_GITHUB_EVENT'):
        return api_github_webhook(request)
    else:
        return api_github_landing(request)
