import zerver.lib.cache_manager as cache_manager

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

# Service worker needs to served in the directory
# the cache files are in our case `static` directory
# and we need to add cache version on it handle it using
# views.
def zulip_sw(request: HttpRequest) -> HttpResponse:
    # update version in case file is changed
    # every time a request is made
    cache_manager.check()

    return render(request, 'zerver/service_worker/zulip_sw.js', {
        'version': 'v' + str(cache_manager.CACHE_VERSION),
        'files': cache_manager.get_cache_files_array()
    }, content_type='application/javascript')
