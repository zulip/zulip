from typing import List, Optional

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.translation import gettext as _
from pydantic_core import PydanticCustomError

# The Pydantic.StringConstraints does not have validation for the string to be
# of the specified length. So, we need to create a custom validator for that.


def check_string_fixed_length(string: str, length: int) -> Optional[str]:
    if len(string) != length:
        raise PydanticCustomError(
            "string_fixed_length",
            "",
            {
                "length": length,
            },
        )
    return string


def check_int_in(val: int, possible_values: List[int]) -> int:
    if val not in possible_values:
        raise ValueError(_("Not in the list of possible values"))
    return val


def check_url(val: str) -> str:
    validate = URLValidator()
    try:
        validate(val)
        return val
    except ValidationError:
        raise ValueError(_("Not a URL"))
