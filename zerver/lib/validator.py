'''
This module sets up a scheme for validating that arbitrary Python
objects are correctly typed.  It is totally decoupled from Django,
composable, easily wrapped, and easily extended.

A validator takes two parameters--var_name and val--and returns an
error if val is not the correct type.  The var_name parameter is used
to format error messages.  Validators return None when there are no errors.

Example primitive validators are check_string, check_int, and check_bool.

Compound validators are created by check_list and check_dict.  Note that
those functions aren't directly called for validation; instead, those
functions are called to return other functions that adhere to the validator
contract.  This is similar to how Python decorators are often parameterized.

The contract for check_list and check_dict is that they get passed in other
validators to apply to their items.  This allows you to build up validators
for arbitrarily complex validators.  See ValidatorTestCase for example usage.

A simple example of composition is this:

   check_list(check_string)('my_list', ['a', 'b', 'c']) is None

To extend this concept, it's simply a matter of writing your own validator
for any particular type of object.
'''
import re
import ujson
from django.utils.translation import ugettext as _
from django.core.exceptions import ValidationError
from django.core.validators import validate_email, URLValidator
from typing import Iterable, Optional, Tuple, cast

from datetime import datetime
from zerver.lib.request import JsonableError
from zerver.lib.types import Validator, ProfileFieldData

def check_string(var_name: str, val: object) -> Optional[str]:
    if not isinstance(val, str):
        return _('%s is not a string') % (var_name,)
    return None

def check_required_string(var_name: str, val: object) -> Optional[str]:
    error = check_string(var_name, val)
    if error:
        return error

    val = cast(str, val)
    if not val.strip():
        return _("{item} cannot be blank.").format(item=var_name)

    return None

def check_short_string(var_name: str, val: object) -> Optional[str]:
    return check_capped_string(50)(var_name, val)

def check_capped_string(max_length: int) -> Validator:
    def validator(var_name: str, val: object) -> Optional[str]:
        if not isinstance(val, str):
            return _('%s is not a string') % (var_name,)
        if len(val) > max_length:
            return _("{var_name} is too long (limit: {max_length} characters)".format(
                var_name=var_name, max_length=max_length))
        return None
    return validator

def check_string_fixed_length(length: int) -> Validator:
    def validator(var_name: str, val: object) -> Optional[str]:
        if not isinstance(val, str):
            return _('%s is not a string') % (var_name,)
        if len(val) != length:
            return _("{var_name} has incorrect length {length}; should be {target_length}".format(
                var_name=var_name, target_length=length, length=len(val)))
        return None
    return validator

def check_long_string(var_name: str, val: object) -> Optional[str]:
    return check_capped_string(500)(var_name, val)

def check_date(var_name: str, val: object) -> Optional[str]:
    if not isinstance(val, str):
        return _('%s is not a string') % (var_name,)
    try:
        datetime.strptime(val, '%Y-%m-%d')
    except ValueError:
        return _('%s is not a date') % (var_name,)
    return None

def check_int(var_name: str, val: object) -> Optional[str]:
    if not isinstance(val, int):
        return _('%s is not an integer') % (var_name,)
    return None

def check_float(var_name: str, val: object) -> Optional[str]:
    if not isinstance(val, float):
        return _('%s is not a float') % (var_name,)
    return None

def check_bool(var_name: str, val: object) -> Optional[str]:
    if not isinstance(val, bool):
        return _('%s is not a boolean') % (var_name,)
    return None

def check_color(var_name: str, val: object) -> Optional[str]:
    if not isinstance(val, str):
        return _('%s is not a string') % (var_name,)
    valid_color_pattern = re.compile(r'^#(?:[a-fA-F0-9]{6})$')
    matched_results = valid_color_pattern.match(val)
    if not matched_results:
        return _('%s is not a valid hex color code') % (var_name,)
    return None

def check_none_or(sub_validator: Validator) -> Validator:
    def f(var_name: str, val: object) -> Optional[str]:
        if val is None:
            return None
        else:
            return sub_validator(var_name, val)
    return f

def check_list(sub_validator: Optional[Validator], length: Optional[int]=None) -> Validator:
    def f(var_name: str, val: object) -> Optional[str]:
        if not isinstance(val, list):
            return _('%s is not a list') % (var_name,)

        if length is not None and length != len(val):
            return (_('%(container)s should have exactly %(length)s items') %
                    {'container': var_name, 'length': length})

        if sub_validator:
            for i, item in enumerate(val):
                vname = '%s[%d]' % (var_name, i)
                error = sub_validator(vname, item)
                if error:
                    return error

        return None
    return f

def check_dict(required_keys: Iterable[Tuple[str, Validator]]=[],
               optional_keys: Iterable[Tuple[str, Validator]]=[],
               value_validator: Optional[Validator]=None,
               _allow_only_listed_keys: bool=False) -> Validator:
    def f(var_name: str, val: object) -> Optional[str]:
        if not isinstance(val, dict):
            return _('%s is not a dict') % (var_name,)

        for k, sub_validator in required_keys:
            if k not in val:
                return (_('%(key_name)s key is missing from %(var_name)s') %
                        {'key_name': k, 'var_name': var_name})
            vname = '%s["%s"]' % (var_name, k)
            error = sub_validator(vname, val[k])
            if error:
                return error

        for k, sub_validator in optional_keys:
            if k in val:
                vname = '%s["%s"]' % (var_name, k)
                error = sub_validator(vname, val[k])
                if error:
                    return error

        if value_validator:
            for key in val:
                vname = '%s contains a value that' % (var_name,)
                error = value_validator(vname, val[key])
                if error:
                    return error

        if _allow_only_listed_keys:
            required_keys_set = set(x[0] for x in required_keys)
            optional_keys_set = set(x[0] for x in optional_keys)
            delta_keys = set(val.keys()) - required_keys_set - optional_keys_set
            if len(delta_keys) != 0:
                return _("Unexpected arguments: %s" % (", ".join(list(delta_keys))))

        return None

    return f

def check_dict_only(required_keys: Iterable[Tuple[str, Validator]],
                    optional_keys: Iterable[Tuple[str, Validator]]=[]) -> Validator:
    return check_dict(required_keys, optional_keys, _allow_only_listed_keys=True)

def check_variable_type(allowed_type_funcs: Iterable[Validator]) -> Validator:
    """
    Use this validator if an argument is of a variable type (e.g. processing
    properties that might be strings or booleans).

    `allowed_type_funcs`: the check_* validator functions for the possible data
    types for this variable.
    """
    def enumerated_type_check(var_name: str, val: object) -> Optional[str]:
        for func in allowed_type_funcs:
            if not func(var_name, val):
                return None
        return _('%s is not an allowed_type') % (var_name,)
    return enumerated_type_check

def equals(expected_val: object) -> Validator:
    def f(var_name: str, val: object) -> Optional[str]:
        if val != expected_val:
            return (_('%(variable)s != %(expected_value)s (%(value)s is wrong)') %
                    {'variable': var_name,
                     'expected_value': expected_val,
                     'value': val})
        return None
    return f

def validate_login_email(email: str) -> None:
    try:
        validate_email(email)
    except ValidationError as err:
        raise JsonableError(str(err.message))

def check_url(var_name: str, val: object) -> Optional[str]:
    # First, ensure val is a string
    string_msg = check_string(var_name, val)
    if string_msg is not None:
        return string_msg
    # Now, validate as URL
    validate = URLValidator()
    try:
        validate(val)
        return None
    except ValidationError:
        return _('%s is not a URL') % (var_name,)

def validate_field_data(field_data: ProfileFieldData) -> Optional[str]:
    """
    This function is used to validate the data sent to the server while
    creating/editing choices of the choice field in Organization settings.
    """
    validator = check_dict_only([
        ('text', check_required_string),
        ('order', check_required_string),
    ])

    for key, value in field_data.items():
        if not key.strip():
            return _("'{item}' cannot be blank.").format(item='value')

        error = validator('field_data', value)
        if error:
            return error

    return None

def validate_choice_field(var_name: str, field_data: str, value: object) -> Optional[str]:
    """
    This function is used to validate the value selected by the user against a
    choice field. This is not used to validate admin data.
    """
    field_data_dict = ujson.loads(field_data)
    if value not in field_data_dict:
        msg = _("'{value}' is not a valid choice for '{field_name}'.")
        return msg.format(value=value, field_name=var_name)
    return None

def check_widget_content(widget_content: object) -> Optional[str]:
    if not isinstance(widget_content, dict):
        return 'widget_content is not a dict'

    if 'widget_type' not in widget_content:
        return 'widget_type is not in widget_content'

    if 'extra_data' not in widget_content:
        return 'extra_data is not in widget_content'

    widget_type = widget_content['widget_type']
    extra_data = widget_content['extra_data']

    if not isinstance(extra_data, dict):
        return 'extra_data is not a dict'

    if widget_type == 'zform':

        if 'type' not in extra_data:
            return 'zform is missing type field'

        if extra_data['type'] == 'choices':
            check_choices = check_list(
                check_dict([
                    ('short_name', check_string),
                    ('long_name', check_string),
                    ('reply', check_string),
                ]),
            )

            checker = check_dict([
                ('heading', check_string),
                ('choices', check_choices),
            ])

            msg = checker('extra_data', extra_data)
            if msg:
                return msg

            return None

        return 'unknown zform type: ' + extra_data['type']

    return 'unknown widget type: ' + widget_type


# Converter functions for use with has_request_variables
def to_non_negative_int(s: str, max_int_size: int=2**32-1) -> int:
    x = int(s)
    if x < 0:
        raise ValueError("argument is negative")
    if x > max_int_size:
        raise ValueError('%s is too large (max %s)' % (x, max_int_size))
    return x
