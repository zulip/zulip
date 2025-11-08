import re
import zoneinfo
from collections.abc import Collection
from enum import Enum
from typing import TypeVar

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.translation import gettext as _
from pydantic import AfterValidator, BeforeValidator, NonNegativeInt
from pydantic_core import PydanticCustomError

from zerver.lib.exceptions import JsonableError
from zerver.lib.timezone import canonicalize_timezone

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


def to_timezone_or_empty(s: str) -> str:
    try:
        s = canonicalize_timezone(s)
        zoneinfo.ZoneInfo(s)
    except (ValueError, zoneinfo.ZoneInfoNotFoundError):
        return ""
    else:
        return s


def timezone_or_empty_validator() -> AfterValidator:
    return AfterValidator(lambda s: to_timezone_or_empty(s))


def check_timezone(s: str) -> str:
    try:
        zoneinfo.ZoneInfo(canonicalize_timezone(s))
    except (ValueError, zoneinfo.ZoneInfoNotFoundError):
        raise ValueError(_("Not a recognized time zone"))
    return s


def timezone_validator() -> AfterValidator:
    return AfterValidator(lambda s: check_timezone(s))


def to_non_negative_int_or_none(s: str) -> NonNegativeInt | None:
    try:
        i = int(s)
        if i < 0:
            return None
        return i
    except ValueError:
        return None


# We use BeforeValidator, not AfterValidator, here, because the int
# type conversion will raise a ValueError if the string is not a valid
# integer, and we want to return None in that case.
def non_negative_int_or_none_validator() -> BeforeValidator:
    return BeforeValidator(lambda s: to_non_negative_int_or_none(s))


def check_color(var_name: str, val: object) -> str:
    s = str(val)
    valid_color_pattern = re.compile(r"^#([a-fA-F0-9]{3,6})$")
    matched_results = valid_color_pattern.match(s)
    if not matched_results:
        raise ValueError(_("{var_name} is not a valid hex color code").format(var_name=var_name))
    return s


EnumT = TypeVar("EnumT", bound=Enum)


def parse_enum_from_string_value(
    val: str,
    setting_name: str,
    enum: type[EnumT],
) -> EnumT:
    try:
        return enum[val]
    except KeyError:
        raise JsonableError(_("Invalid {setting_name}").format(setting_name=setting_name))
