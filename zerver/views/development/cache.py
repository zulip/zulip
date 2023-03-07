import os

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from zerver.decorator import require_post
from zerver.lib.cache import get_cache_backend
from zerver.lib.response import json_success
from zerver.models import clear_client_cache, flush_per_request_caches

ZULIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../")


# This is used only by the Puppeteer tests to clear all the cache after each run.
@csrf_exempt
@require_post
def remove_caches(request: HttpRequest) -> HttpResponse:
    cache = get_cache_backend(None)
    cache.clear()
    clear_client_cache()
    flush_per_request_caches()
    return json_success(request)
