from collections.abc import Collection

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.translation import gettext as _
from pydantic import AfterValidator
from pydantic_core import PydanticCustomError

# The Pydantic.StringConstraints does not have validation for the string to be
# of the specified length. So, we need to create a custom validator for that.


def check_string_fixed_length(string: str, length: int) -> str | None:
    if len(string) != length:
        raise PydanticCustomError(
            "string_fixed_length",
            "",
            {
                "length": length,
            },
        )
    return string


def check_string_in(val: str, possible_values: Collection[str]) -> str:
    if val not in possible_values:
        raise ValueError(_("Not in the list of possible values"))
    return val


def check_int_in(val: int, possible_values: Collection[int]) -> int:
    if val not in possible_values:
        raise ValueError(_("Not in the list of possible values"))
    return val


def check_int_in_validator(possible_values: Collection[int]) -> AfterValidator:
    return AfterValidator(lambda val: check_int_in(val, possible_values))


def check_string_in_validator(possible_values: Collection[str]) -> AfterValidator:
    return AfterValidator(lambda val: check_string_in(val, possible_values))


def check_url(val: str) -> str:
    validate = URLValidator()
    try:
        validate(val)
        return val
    except ValidationError:
        raise ValueError(_("Not a URL"))
