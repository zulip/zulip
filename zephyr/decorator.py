from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from zephyr.models import UserProfile, UserActivity, get_client
from zephyr.lib.response import json_success, json_error
from django.utils.timezone import now
from django.db import transaction, IntegrityError
from django.conf import settings
import simplejson
from zephyr.lib.cache import cache_with_key
from zephyr.lib.queue import SimpleQueueClient
from zephyr.lib.timestamp import datetime_to_timestamp

from functools import wraps

class _RespondAsynchronously(object):
    pass

# Return RespondAsynchronously from an @asynchronous view if the
# response will be provided later by calling handler.finish(), or has
# already been provided this way. We use this for longpolling mode.
RespondAsynchronously = _RespondAsynchronously()

def asynchronous(method):
    @wraps(method)
    def wrapper(request, *args, **kwargs):
        return method(request, handler=request._tornado_handler, *args, **kwargs)
    if getattr(method, 'csrf_exempt', False):
        wrapper.csrf_exempt = True
    return wrapper

if settings.USING_RABBITMQ:
    # Don't try to publish messages to rabbitmq if we're not using
    # it.  UserActivity updates aren't really important for most
    # local development, so skipping publishing them here is
    # reasonable.
    #
    # update_active_status also pushes to rabbitmq, and we don't
    #  want to log it

    activity_queue = SimpleQueueClient()

    def update_user_activity(request, user_profile, client):
        if request.META["PATH_INFO"] == '/json/update_active_status':
            return
        event={'query': request.META["PATH_INFO"],
               'user_profile_id': user_profile.id,
               'time': datetime_to_timestamp(now()),
               'client': client.name}
        activity_queue.json_publish("user_activity", event)
else:
   update_user_activity = lambda request, user_profile, client: None


# I like the all-lowercase name better
require_post = require_POST

@cache_with_key(lambda user_profile_id: 'tornado_user_profile:%d' % (user_profile_id,))
def get_tornado_user_profile(user_id):
    return UserProfile.objects.select_related().get(user_id=user_id)

@cache_with_key(lambda email: 'tornado_user_profile_email:%s' % (email,))
def get_tornado_user_profile_by_email(email):
    return UserProfile.objects.select_related().get(user__email=email)

# authenticated_api_view will add the authenticated user's user_profile to
# the view function's arguments list, since we have to look it up
# anyway.
def authenticated_api_view(view_func):
    @csrf_exempt
    @require_post
    @has_request_variables
    @wraps(view_func)
    def _wrapped_view_func(request, email=POST, api_key=POST('api-key'),
                           client=POST(default=get_client("API"), converter=get_client),
                           *args, **kwargs):
        try:
            if settings.RUNNING_INSIDE_TORNADO:
                # Get the UserProfile from a cache because we aren't accessing
                # any mutable fields (just ids plus the realm.domain)
                user_profile = get_tornado_user_profile_by_email(email)
            else:
                user_profile = UserProfile.objects.select_related().get(user__email=email)
        except UserProfile.DoesNotExist:
            return json_error("Invalid user: %s" % (email,))
        if api_key != user_profile.api_key:
            return json_error("Invalid API key for user '%s'" % (email,))
        request._client = client
        request._email = email
        update_user_activity(request, user_profile, client)
        return view_func(request, user_profile, *args, **kwargs)
    return _wrapped_view_func

def authenticate_log_and_execute_json(request, client, view_func, *args, **kwargs):
    if not request.user.is_authenticated():
        return json_error("Not logged in", status=401)
    request._client = client
    if settings.RUNNING_INSIDE_TORNADO:
        # Get the UserProfile from a cache because we aren't accessing
        # any mutable fields (just ids plus the realm.domain)
        user_profile = get_tornado_user_profile(request.user.id)
    else:
        user_profile = UserProfile.objects.select_related().get(user=request.user)
    request._email = user_profile.user.email
    update_user_activity(request, user_profile, client)
    return view_func(request, user_profile, *args, **kwargs)

# Checks if the request is a POST request and that the user is logged
# in.  If not, return an error (the @login_required behavior of
# redirecting to a login page doesn't make sense for json views)
def authenticated_json_post_view(view_func):
    @require_post
    @has_request_variables
    @wraps(view_func)
    def _wrapped_view_func(request,
                           client=POST(default=get_client("website"), converter=get_client),
                           *args, **kwargs):
        return authenticate_log_and_execute_json(request, client, view_func, *args, **kwargs)
    return _wrapped_view_func

def authenticated_json_view(view_func):
    @wraps(view_func)
    def _wrapped_view_func(request,
                           client=get_client("website"),
                           *args, **kwargs):
        return authenticate_log_and_execute_json(request, client, view_func, *args, **kwargs)
    return _wrapped_view_func

# These views are used by the main Django server to notify the Tornado server
# of events.  We protect them from the outside world by checking a shared
# secret, and also the originating IP (for now).
def authenticate_notify(request):
    return (request.META['REMOTE_ADDR'] in ('127.0.0.1', '::1')
            and request.POST.get('secret') == settings.SHARED_SECRET)

def internal_notify_view(view_func):
    @csrf_exempt
    @require_post
    @wraps(view_func)
    def _wrapped_view_func(request, *args, **kwargs):
        if not authenticate_notify(request):
            return json_error('Access denied', status=403)
        if not hasattr(request, '_tornado_handler'):
            # We got called through the non-Tornado server somehow.
            # This is not a security check; it's an internal assertion
            # to help us find bugs.
            raise RuntimeError, 'notify view called with no Tornado handler'
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

class JsonableError(Exception):
    def __init__(self, error):
        self.error = error

    def __str__(self):
        return self.to_json_error_msg()

    def to_json_error_msg(self):
        return self.error

class RequestVariableMissingError(JsonableError):
    def __init__(self, var_name):
        self.var_name = var_name

    def to_json_error_msg(self):
        return "Missing '%s' argument" % (self.var_name,)

class RequestVariableConversionError(JsonableError):
    def __init__(self, var_name, bad_value):
        self.var_name = var_name
        self.bad_value = bad_value

    def to_json_error_msg(self):
        return "Bad value for '%s': %s" % (self.var_name, self.bad_value)

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
# This should generally be the innermost (syntactically bottommost)
# decorator applied to a view, since other decorators won't preserve
# the default parameter values used by has_request_variables.
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
            if param.func_var_name in kwargs:
                continue

            default_assigned = False
            try:
                val = request.POST[param.post_var_name]
            except KeyError:
                if param.default is POST.NotSpecified:
                    raise RequestVariableMissingError(param.post_var_name)
                val = param.default
                default_assigned = True

            if param.converter is not None and not default_assigned:
                try:
                    val = param.converter(val)
                except:
                    raise RequestVariableConversionError(param.post_var_name, val)
            kwargs[param.func_var_name] = val

        return view_func(request, *args, **kwargs)

    return _wrapped_view_func

# Converter functions for use with has_request_variables
def to_non_negative_int(x):
    x = int(x)
    if x < 0:
        raise ValueError("argument is negative")
    return x

def json_to_foo(json, type):
    data = simplejson.loads(json)
    if not isinstance(data, type):
        raise ValueError("argument is not a %s" % (type().__class__.__name__))
    return data

def json_to_dict(json):
    return json_to_foo(json, dict)

def json_to_list(json):
    return json_to_foo(json, list)

def json_to_bool(json):
    return json_to_foo(json, bool)
