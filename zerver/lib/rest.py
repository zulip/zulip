from __future__ import absolute_import

from django.views.decorators.csrf import csrf_exempt, csrf_protect

from zerver.decorator import authenticated_json_view, authenticated_rest_api_view, \
        process_as_post, JsonableError
from zerver.lib.response import json_method_not_allowed, json_unauthorized, json_unhandled_exception
from django.http import HttpResponse, HttpResponseRedirect
from django.conf import settings

import logging


METHODS = ('GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH')

@csrf_exempt
def rest_dispatch(request, globals_list, **kwargs):
    """Dispatch to a REST API endpoint.

    This calls the function named in kwargs[request.method], if that request
    method is supported, and after wrapping that function to:

        * protect against CSRF (if the user is already authenticated through
          a Django session)
        * authenticate via an API key (otherwise)
        * coerce PUT/PATCH/DELETE into having POST-like semantics for
          retrieving variables

    Any keyword args that are *not* HTTP methods are passed through to the
    target function.

    Note that we search views.py globals for the function to call, so never
    make a urls.py pattern put user input into a variable called GET, POST,
    etc.
    """
    supported_methods = {}
    # duplicate kwargs so we can mutate the original as we go
    for arg in list(kwargs):
        if arg in METHODS:
            supported_methods[arg] = kwargs[arg]
            del kwargs[arg]

    if request.method == 'OPTIONS':
        response = HttpResponse(status=204) # No content
        response['Allow'] = ', '.join(supported_methods.keys())
        response['Content-Length'] = "0"
        return response

    # Override requested method if magic method=??? parameter exists
    method_to_use = request.method
    if request.POST and 'method' in request.POST:
        method_to_use = request.POST['method']
    if method_to_use == "SOCKET" and "zulip.emulated_method" in request.META:
        method_to_use = request.META["zulip.emulated_method"]

    if method_to_use in supported_methods:
        target_function = globals_list[supported_methods[method_to_use]]

        # Set request._query for update_activity_user(), which is called
        # by some of the later wrappers.
        request._query = target_function.__name__

        # We want to support authentication by both cookies (web client)
        # and API keys (API clients). In the former case, we want to
        # do a check to ensure that CSRF etc is honored, but in the latter
        # we can skip all of that.
        #
        # Security implications of this portion of the code are minimal,
        # as we should worst-case fail closed if we miscategorise a request.
        if not request.path.startswith("/api") and request.user.is_authenticated():
            # Authenticated via sessions framework, only CSRF check needed
            target_function = csrf_protect(authenticated_json_view(target_function))
        elif request.META.get('HTTP_AUTHORIZATION', None):
            # Wrap function with decorator to authenticate the user before
            # proceeding
            target_function = authenticated_rest_api_view(target_function)
        else:
            if 'text/html' in request.META.get('HTTP_ACCEPT', ''):
                # If this looks like a request from a top-level page in a
                # browser, send the user to the login page
                return HttpResponseRedirect('%s/?next=%s' % (settings.HOME_NOT_LOGGED_IN, request.path))
            else:
                return json_unauthorized("Not logged in: API authentication or user session required")

        if request.method not in ["GET", "POST"]:
            # process_as_post needs to be the outer decorator, because
            # otherwise we might access and thus cache a value for
            # request.REQUEST.
            target_function = process_as_post(target_function)

        return target_function(request, **kwargs)

    return json_method_not_allowed(list(supported_methods.keys()))


