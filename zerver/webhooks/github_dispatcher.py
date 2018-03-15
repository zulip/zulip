from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .github.view import api_github_landing
from .github_webhook.view import api_github_webhook

# Since this dispatcher is an API-style endpoint, it needs to be
# explicitly marked as CSRF-exempt
@csrf_exempt
def api_github_webhook_dispatch(request: HttpRequest) -> HttpResponse:
    if request.META.get('HTTP_X_GITHUB_EVENT'):
        return api_github_webhook(request)  # type: ignore # mypy doesn't seem to apply the decorator
    else:
        return api_github_landing(request)  # type: ignore # mypy doesn't seem to apply the decorator
