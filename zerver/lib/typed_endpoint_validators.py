from typing import Optional

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
