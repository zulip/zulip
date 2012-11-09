from django.views.decorators.csrf import csrf_exempt
from zephyr.models import UserProfile, UserActivity, get_client
from zephyr.lib.response import json_success, json_error
from django.utils.timezone import now

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

def parse_client(request, default):
    client_name = default
    if 'client' in request.POST:
        client_name = request.POST['client']
    return get_client(client_name)

def update_user_activity(request, user_profile, client):
    current_time = now()
    (activity, created) = UserActivity.objects.get_or_create(
        user_profile = user_profile,
        client = client,
        query = request.META["PATH_INFO"],
        defaults={'last_visit': current_time, 'count': 0})
    activity.count += 1
    activity.last_visit = current_time
    activity.save()

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
        update_user_activity(request, user_profile,
                             parse_client(request, "API"))
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
        update_user_activity(request, request.user.userprofile,
                             parse_client(request, "website"))
        return view_func(request, request.user.userprofile, *args, **kwargs)
    return _wrapped_view_func

# Used in conjunction with @has_request_variables, below
class POST(object):
    # NotSpecified is a sentinel value for determining whether a
    # default value was specified for a request variable.  We can't
    # use None because that could be a valid, user-specified default
    class _NotSpecified(object):
        pass
    NotSpecified = _NotSpecified()

    def __init__(self, whence=None, converter=None, default=NotSpecified):
        """
        whence: the name of the request variable that should be used
        for this parameter.  Defaults to a request variable of the
        same name as the parameter.

        converter: a function that takes a string and returns a new
        value.  If specified, this will be called on the request
        variable value before passing to the function

        default: a value to be used for the argument if the parameter
        is missing in the request
        """

        self.post_var_name = whence
        self.func_var_name = None
        self.converter = converter
        self.default = default

# Extracts variables from the request object and passes them as
# named function arguments.  The request object must be the first
# argument to the function.
#
# To use, assign a function parameter a default value that is an
# instance of the POST class.  That paramter will then be
# automatically populated from the HTTP request.  The request object
# must be the first argument to the decorated function.
#
# Note that this can't be used in helper functions which are not
# expected to call json_error or json_success, as it uses json_error
# internally when it encounters an error
def has_request_variables(view_func):
    num_params = view_func.func_code.co_argcount
    if view_func.func_defaults is None:
        num_default_params = 0
    else:
        num_default_params = len(view_func.func_defaults)
    default_param_names = view_func.func_code.co_varnames[num_params - num_default_params:]
    default_param_values = view_func.func_defaults

    post_params = []

    for (name, value) in zip(default_param_names, default_param_values):
        if isinstance(value, POST):
            value.func_var_name = name
            if value.post_var_name is None:
                value.post_var_name = name
            post_params.append(value)
        elif value == POST:
            # If the function definition does not actually
            # instantiate a POST object but instead uses the POST
            # class itself as a value, we instantiate it as a
            # convenience
            post_var = POST(name)
            post_var.func_var_name = name
            post_params.append(post_var)

    @wraps(view_func)
    def _wrapped_view_func(request, *args, **kwargs):
        for param in post_params:
            default_assigned = False
            try:
                val = request.POST[param.post_var_name]
            except KeyError:
                if param.default is POST.NotSpecified:
                    return json_error("Missing '%s' argument" % (param.post_var_name,))
                val = param.default
                default_assigned = True

            if param.converter is not None and not default_assigned:
                try:
                    val = param.converter(val)
                except:
                    return json_error("Bad value for '%s'" % (param.post_var_name,))
            kwargs[param.func_var_name] = val

        return view_func(request, *args, **kwargs)

    return _wrapped_view_func
