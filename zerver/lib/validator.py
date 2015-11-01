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

   check_list(check_string)('my_list', ['a', 'b', 'c']) == None

To extend this concept, it's simply a matter of writing your own validator
for any particular type of object.
'''
from __future__ import absolute_import
import six

def check_string(var_name, val):
    if not isinstance(val, six.string_types):
        return '%s is not a string' % (var_name,)
    return None

def check_int(var_name, val):
    if not isinstance(val, int):
        return '%s is not an integer' % (var_name,)
    return None

def check_bool(var_name, val):
    if not isinstance(val, bool):
        return '%s is not a boolean' % (var_name,)
    return None

def check_none_or(sub_validator):
    def f(var_name, val):
        if val is None:
            return
        else:
            return sub_validator(var_name, val)
    return f

def check_list(sub_validator, length=None):
    def f(var_name, val):
        if not isinstance(val, list):
            return '%s is not a list' % (var_name,)

        if length is not None and length != len(val):
            return '%s should have exactly %d items' % (var_name, length)

        if sub_validator:
            for i, item in enumerate(val):
                vname = '%s[%d]' % (var_name, i)
                error = sub_validator(vname, item)
                if error:
                    return error

        return None
    return f

def check_dict(required_keys):
    # required_keys is a list of tuples of
    # key_name/validator

    def f(var_name, val):
        if not isinstance(val, dict):
            return '%s is not a dict' % (var_name,)

        for k, sub_validator in required_keys:
            if k not in val:
                return '%s key is missing from %s' % (k, var_name)
            vname = '%s["%s"]' % (var_name, k)
            error = sub_validator(vname, val[k])
            if error:
                return error

        return None

    return f

def check_variable_type(allowed_type_funcs):
    """
    Use this validator if an argument is of a variable type (e.g. processing
    properties that might be strings or booleans).

    `allowed_type_funcs`: the check_* validator functions for the possible data
    types for this variable.
    """
    def enumerated_type_check(var_name, val):
        for func in allowed_type_funcs:
            if not func(var_name, val):
                return None
        return '%s is not an allowed_type' % (var_name,)
    return enumerated_type_check

def equals(expected_val):
    def f(var_name, val):
        if val != expected_val:
            return '%s != %r (%r is wrong)' % (var_name, expected_val, val)
        return None
    return f
