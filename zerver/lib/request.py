from __future__ import absolute_import
from functools import wraps
import ujson
from six.moves import zip

from django.utils.translation import ugettext as _

class JsonableError(Exception):
    def __init__(self, error, status_code=400):
        self.error = error
        self.status_code = status_code

    def __str__(self):
        return self.to_json_error_msg()

    def to_json_error_msg(self):
        return self.error

class RequestVariableMissingError(JsonableError):
    def __init__(self, var_name, status_code=400):
        self.var_name = var_name
        self.status_code = status_code

    def to_json_error_msg(self):
        return _("Missing '%s' argument") % (self.var_name,)

class RequestVariableConversionError(JsonableError):
    def __init__(self, var_name, bad_value, status_code=400):
        self.var_name = var_name
        self.bad_value = bad_value
        self.status_code = status_code

    def to_json_error_msg(self):
        return (_("Bad value for '%(var_name)s': %(value)s") %
                {'var_name': self.var_name, 'value': self.bad_value})

# Used in conjunction with @has_request_variables, below
class REQ(object):
    # NotSpecified is a sentinel value for determining whether a
    # default value was specified for a request variable.  We can't
    # use None because that could be a valid, user-specified default
    class _NotSpecified(object):
        pass
    NotSpecified = _NotSpecified()

    def __init__(self, whence=None, converter=None, default=NotSpecified,
                 validator=None, argument_type=None):
        """whence: the name of the request variable that should be used
        for this parameter.  Defaults to a request variable of the
        same name as the parameter.

        converter: a function that takes a string and returns a new
        value.  If specified, this will be called on the request
        variable value before passing to the function

        default: a value to be used for the argument if the parameter
        is missing in the request

        validator: similar to converter, but takes an already parsed JSON
        data structure.  If specified, we will parse the JSON request
        variable value before passing to the function

        argument_type: pass 'body' to extract the parsed JSON
        corresponding to the request body
        """

        self.post_var_name = whence
        self.func_var_name = None # type: str
        self.converter = converter
        self.validator = validator
        self.default = default
        self.argument_type = argument_type

        if converter and validator:
            raise Exception(_('converter and validator are mutually exclusive'))

# Extracts variables from the request object and passes them as
# named function arguments.  The request object must be the first
# argument to the function.
#
# To use, assign a function parameter a default value that is an
# instance of the REQ class.  That paramter will then be automatically
# populated from the HTTP request.  The request object must be the
# first argument to the decorated function.
#
# This should generally be the innermost (syntactically bottommost)
# decorator applied to a view, since other decorators won't preserve
# the default parameter values used by has_request_variables.
#
# Note that this can't be used in helper functions which are not
# expected to call json_error or json_success, as it uses json_error
# internally when it encounters an error
def has_request_variables(view_func):
    num_params = view_func.__code__.co_argcount
    if view_func.__defaults__ is None:
        num_default_params = 0
    else:
        num_default_params = len(view_func.__defaults__)
    default_param_names = view_func.__code__.co_varnames[num_params - num_default_params:]
    default_param_values = view_func.__defaults__
    if default_param_values is None:
        default_param_values = []

    post_params = []

    for (name, value) in zip(default_param_names, default_param_values):
        if isinstance(value, REQ):
            value.func_var_name = name
            if value.post_var_name is None:
                value.post_var_name = name
            post_params.append(value)

    @wraps(view_func)
    def _wrapped_view_func(request, *args, **kwargs):
        for param in post_params:
            if param.func_var_name in kwargs:
                continue

            if param.argument_type == 'body':
                try:
                    val = ujson.loads(request.body)
                except ValueError:
                    raise JsonableError(_('Malformed JSON'))
                kwargs[param.func_var_name] = val
                continue
            elif param.argument_type is not None:
                # This is a view bug, not a user error, and thus should throw a 500.
                raise Exception(_("Invalid argument type"))

            default_assigned = False
            try:
                val = request.REQUEST[param.post_var_name]
            except KeyError:
                if param.default is REQ.NotSpecified:
                    raise RequestVariableMissingError(param.post_var_name)
                val = param.default
                default_assigned = True

            if param.converter is not None and not default_assigned:
                try:
                    val = param.converter(val)
                except JsonableError:
                    raise
                except:
                    raise RequestVariableConversionError(param.post_var_name, val)

            # Validators are like converters, but they don't handle JSON parsing; we do.
            if param.validator is not None and not default_assigned:
                try:
                    val = ujson.loads(val)
                except:
                    raise JsonableError(_('argument "%s" is not valid json.') % (param.post_var_name,))

                error = param.validator(param.post_var_name, val)
                if error:
                    raise JsonableError(error)

            kwargs[param.func_var_name] = val

        return view_func(request, *args, **kwargs)

    return _wrapped_view_func
