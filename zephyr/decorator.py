from django.views.decorators.csrf import csrf_exempt
from zephyr.models import UserProfile
from zephyr.lib.response import json_success, json_error

from functools import wraps

import types

class TornadoAsyncException(Exception): pass

class _DefGen_Return(BaseException):
    def __init__(self, value):
        self.value = value

def returnResponse(value):
    raise _DefGen_Return(value)

def asynchronous(method):
    @wraps(method)
    def wrapper(request, *args, **kwargs):
        try:
            v = method(request, request._tornado_handler, *args, **kwargs)
            if v == None or type(v) == types.GeneratorType:
                raise TornadoAsyncException
        except _DefGen_Return, e:
            request._tornado_handler.finish(e.value.content)
        return v
    if getattr(method, 'csrf_exempt', False):
        wrapper.csrf_exempt = True
    return wrapper

def require_post(view_func):
    @wraps(view_func)
    def _wrapped_view_func(request, *args, **kwargs):
        if request.method != "POST":
            return json_error('This form can only be submitted by POST.')
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

# authenticated_api_view will add the authenticated user's user_profile to
# the view function's arguments list, since we have to look it up
# anyway.
def authenticated_api_view(view_func):
    @csrf_exempt
    @require_post
    @wraps(view_func)
    def _wrapped_view_func(request, *args, **kwargs):
        try:
            user_profile = UserProfile.objects.get(user__email=request.POST.get("email"))
        except UserProfile.DoesNotExist:
            return json_error("Invalid user")
        if user_profile is None or request.POST.get("api-key") != user_profile.api_key:
            return json_error('Invalid API user/key pair.')
        return view_func(request, user_profile, *args, **kwargs)
    return _wrapped_view_func

# Checks if the request is a POST request and that the user is logged
# in.  If not, return an error (the @login_required behavior of
# redirecting to a login page doesn't make sense for json views)
def authenticated_json_view(view_func):
    @require_post
    @wraps(view_func)
    def _wrapped_view_func(request, *args, **kwargs):
        if not request.user.is_authenticated():
            return json_error("Not logged in")
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func
