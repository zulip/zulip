"""
This module sets up type classes like DictType and
ListType that define types for arbitrary objects, but
our first use case is to specify the types of Zulip
events that come from send_event calls.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


@dataclass
class DictType:
    def __init__(
        self,
        required_keys: Sequence[Tuple[str, Any]],
        optional_keys: Sequence[Tuple[str, Any]] = [],
    ) -> None:
        self.required_keys = required_keys
        self.optional_keys = optional_keys

    def check_data(self, var_name: str, val: Dict[str, Any]) -> None:
        if not isinstance(val, dict):
            raise AssertionError(f"{var_name} is not a dict")

        for k in val:
            if not isinstance(k, str):
                raise AssertionError(f"{var_name} has non-string key {k}")

        for k, data_type in self.required_keys:
            if k not in val:
                raise AssertionError(f"{k} key is missing from {var_name}")
            vname = f"{var_name}['{k}']"
            check_data(data_type, vname, val[k])

        for k, data_type in self.optional_keys:
            if k in val:
                vname = f"{var_name}['{k}']"
                check_data(data_type, vname, val[k])

        rkeys = {tup[0] for tup in self.required_keys}
        okeys = {tup[0] for tup in self.optional_keys}
        keys = rkeys | okeys
        for k in val:
            if k not in keys:
                raise AssertionError(f"Unknown key {k} in {var_name}")


@dataclass
class EnumType:
    valid_vals: Sequence[Any]

    def check_data(self, var_name: str, val: Dict[str, Any]) -> None:
        if val not in self.valid_vals:
            raise AssertionError(f"{var_name} is not in {self.valid_vals}")


class Equals:
    def __init__(self, expected_value: Any) -> None:
        self.expected_value = expected_value

    def check_data(self, var_name: str, val: Dict[str, Any]) -> None:
        if val != self.expected_value:
            raise AssertionError(f"{var_name} should be equal to {self.expected_value}")


class ListType:
    def __init__(self, sub_type: Any, length: Optional[int] = None) -> None:
        self.sub_type = sub_type
        self.length = length

    def check_data(self, var_name: str, val: List[Any]) -> None:
        if not isinstance(val, list):
            raise AssertionError(f"{var_name} is not a list")

        for i, sub_val in enumerate(val):
            vname = f"{var_name}[{i}]"
            check_data(self.sub_type, vname, sub_val)


@dataclass
class OptionalType:
    sub_type: Any

    def check_data(self, var_name: str, val: Optional[Any]) -> None:
        if val is None:
            return
        check_data(self.sub_type, var_name, val)


@dataclass
class UnionType:
    sub_types: Sequence[Any]

    def check_data(self, var_name: str, val: Any) -> None:
        for sub_type in self.sub_types:
            try:
                check_data(sub_type, var_name, val)
            except AssertionError:
                pass

            # We matched on one of our sub_types, so return
            return

        raise AssertionError(f"{var_name} does not pass the union type check")

class UrlType:
    def check_data(self, var_name: str, val: Any) -> None:
        try:
            URLValidator()(val)
        except ValidationError:
            raise AssertionError(f"{var_name} is not a URL")

def event_dict_type(
    required_keys: Sequence[Tuple[str, Any]],
    optional_keys: Sequence[Tuple[str, Any]] = [],
) -> DictType:
    """
    This is just a tiny wrapper on DictType, but it provides
    some minor benefits:

        - mark clearly that the schema is for a Zulip event
        - make sure there's a type field
        - add id field automatically
        - sanity check that we have no duplicate keys

    """
    rkeys = [key[0] for key in required_keys]
    okeys = [key[0] for key in optional_keys]
    keys = rkeys + okeys
    assert len(keys) == len(set(keys))
    assert "type" in rkeys
    assert "id" not in keys
    return DictType(
        required_keys=list(required_keys) + [("id", int)], optional_keys=optional_keys,
    )


def make_checker(data_type: DictType,) -> Callable[[str, Dict[str, object]], None]:
    def f(var_name: str, event: Dict[str, Any]) -> None:
        check_data(data_type, var_name, event)

    return f


def check_data(
    # Check that data conforms to our data_type
    data_type: Any,
    var_name: str,
    val: Any,
) -> None:
    if hasattr(data_type, "check_data"):
        data_type.check_data(var_name, val)
        return
    if not isinstance(val, data_type):
        raise AssertionError(f"{var_name} is not type {data_type}")
