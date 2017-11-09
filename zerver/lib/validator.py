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
from django.utils.translation import ugettext as _
from django.core.exceptions import ValidationError
from django.core.validators import validate_email, URLValidator
from typing import Callable, Iterable, Optional, Tuple, TypeVar, Text, Type, Sequence, Mapping, Any, Sized, List, Dict

from zerver.lib.request import JsonableError

Validator = Callable[[str, object], Optional[str]]

Constraint = Callable[[object], Optional[str]]

KeyT = TypeVar('KeyT')

def check(T: Type,
          sub_validator: Optional[Validator]=None,
          keyed_sub_validator: Optional[Iterable[Tuple[KeyT, Validator]]]=None,
          constraints: Optional[List[Constraint]]=None) -> Validator:
    def checker(var_name: str, val: object) -> Optional[str]:
        if sub_validator is not None and keyed_sub_validator is not None:
            return _('check(T) called incorrectly with both validator types')
        if not isinstance(val, T):
            return _('%s is not a %s') % (val, str(T))

        constraint_list = []  # type: List[Constraint]
        if constraints is not None:
            constraint_list = constraints
        if isinstance(val, Mapping) and keyed_sub_validator:  # excludes empty list
            keys, validators = zip(*keyed_sub_validator)
            constraint_list.append(has_keys(keys))  # Ensure dict has expected keys
        for c in constraint_list:
            error = c(val)
            if error is not None:
                return "%s%s" % (var_name, error)

        if sub_validator is not None:
            if isinstance(val, Sequence):  # from check_list
                for i, item in enumerate(val):  # type: (int, Any)
                    vname = '%s[%d]' % (var_name, i)
                    error = sub_validator(vname, item)
                    if error:
                        return error
        elif keyed_sub_validator is not None:
            if isinstance(val, Mapping):  # from check_dict
                for key, validator in keyed_sub_validator:
                    vname = '%s["%s"]' % (var_name, key)
                    error = validator(vname, val[key])
                    if error:
                        return error
        return None
    return checker

def max_length(length: int=200) -> Constraint:  # NOTE: from previous check_short_string
    def checker(val: object) -> Optional[str]:
        if not isinstance(val, Sized):
            return " is not a container with a length"
        if len(val) >= length:
            return _(" is longer than %s.") % (length,)
        return None
    return checker

def exact_length(length: int) -> Constraint: # NOTE: from previous check_list option
    def checker(val: object) -> Optional[str]:
        if not isinstance(val, Sized):
            return " is not a container with a length"
        if length != len(val):
            return _(" does not have exactly %s items") % (length,)
        return None
    return checker

def has_keys(keys: Iterable[str], _only_listed_keys: bool=False) -> Constraint: # NOTE: from previous check_dict
    def checker(val: object) -> Optional[str]:
        if not isinstance(val, Mapping):
            return " is not a mapping"
        for key in keys:
            if key not in val:
                return _(' does not contain key %s') % (key,)
        if _only_listed_keys:
            delta_keys = set(val.keys()) - set(keys)
            if len(delta_keys) != 0:
                return _(" has unexpected arguments: %s" % (", ".join(list(delta_keys))))
        return None
    return checker

def only_keys(keys: Iterable[str]) -> Constraint: # NOTE: from previous check_dict_only
    return has_keys(keys, _only_listed_keys=True)


def check_string(var_name: str, val: object) -> Optional[str]:
    return check(str)(var_name, val)

def check_short_string(var_name: str, val: object) -> Optional[str]:
    return check(str, constraints=[max_length()])(var_name, val)

def check_int(var_name: str, val: object) -> Optional[str]:
    return check(int)(var_name, val)

def check_float(var_name: str, val: object) -> Optional[str]:
    return check(float)(var_name, val)

def check_bool(var_name: str, val: object) -> Optional[str]:
    return check(bool)(var_name, val)

def check_none_or(sub_validator: Validator) -> Validator:
    def f(var_name: str, val: object) -> Optional[str]:
        if val is None:
            return None
        else:
            return sub_validator(var_name, val)
    return f

def check_list(sub_validator: Optional[Validator], length: Optional[int]=None) -> Validator:
    if length is not None:
        return check(List[Any], sub_validator=sub_validator, constraints=[exact_length(length)])
    else:
        return check(List[Any], sub_validator=sub_validator)

def check_dict(required_keys: Iterable[Tuple[str, Validator]],
               _allow_only_listed_keys: bool=False) -> Validator:
    if len(required_keys) == 0:
        keys = None
        cons = None
    else:
        keys, _ = zip(*required_keys)
        if _allow_only_listed_keys:
            cons = [only_keys(keys)]
        else:
            cons = [has_keys(keys)]
    return check(Dict[Any, Any], keyed_sub_validator=required_keys, constraints=cons)

def check_dict_only(required_keys: Iterable[Tuple[str, Validator]]) -> Validator:
    return check_dict(required_keys, _allow_only_listed_keys=True)

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

def validate_login_email(email: Text) -> None:
    try:
        validate_email(email)
    except ValidationError as err:
        raise JsonableError(str(err.message))

def check_url(var_name: str, val: Text) -> None:
    validate = URLValidator()
    try:
        validate(val)
    except ValidationError as err:
        raise JsonableError(str(err.message))
