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


def indent(s: str) -> str:
    padding = "    "
    parts = s.split("\n")
    return "\n".join(padding + part for part in parts)


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

    def schema(self, var_name: str) -> str:
        # Our current schema is lossy, since our openapi configs
        # aren't rigorous about "required" fields yet.
        keys = sorted(list(self.required_keys) + list(self.optional_keys))

        sub_schema = "\n".join(schema(name, data_type) for name, data_type in keys)
        return f"{var_name} (dict):\n{indent(sub_schema)}"


@dataclass
class EnumType:
    valid_vals: Sequence[Any]

    def check_data(self, var_name: str, val: Dict[str, Any]) -> None:
        if val not in self.valid_vals:
            raise AssertionError(f"{var_name} is not in {self.valid_vals}")

    def schema(self, var_name: str) -> str:
        return f"{var_name} in {sorted(self.valid_vals)}"


class Equals:
    def __init__(self, expected_value: Any) -> None:
        self.expected_value = expected_value

        # super hack for openapi workaround
        if self.expected_value is None:
            self.equalsNone = True

    def check_data(self, var_name: str, val: Dict[str, Any]) -> None:
        if val != self.expected_value:
            raise AssertionError(f"{var_name} should be equal to {self.expected_value}")

    def schema(self, var_name: str) -> str:
        # Treat Equals as the degenerate case of EnumType, which
        # matches how we do things with openapi.
        return f"{var_name} in {repr([self.expected_value])}"


class NumberType:
    def check_data(self, var_name: str, val: Optional[Any]) -> None:
        if isinstance(val, int) or isinstance(val, float):
            return
        raise AssertionError(f"{var_name} is not a number")

    def schema(self, var_name: str) -> str:
        return f"{var_name}: number"


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

    def schema(self, var_name: str) -> str:
        sub_schema = schema("type", self.sub_type)
        return f"{var_name} (list):\n{indent(sub_schema)}"


@dataclass
class StringDictType:
    def check_data(self, var_name: str, val: Dict[Any, Any]) -> None:
        if not isinstance(val, dict):
            raise AssertionError(f"{var_name} is not a dictionary")

        for key, value in val.items():
            if isinstance(key, str) and isinstance(value, str):
                continue
            raise AssertionError(f"{var_name} is not a string:string dictionary")

    def schema(self, var_name: str) -> str:
        return f"{var_name}: string_dict"


@dataclass
class OptionalType:
    sub_type: Any

    def check_data(self, var_name: str, val: Optional[Any]) -> None:
        if val is None:
            return
        check_data(self.sub_type, var_name, val)

    def schema(self, var_name: str) -> str:
        # our openapi spec doesn't support optional types very well yet,
        # so we just return the schema for our subtype
        return schema(var_name, self.sub_type)


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

    def schema(self, var_name: str) -> str:
        # We hack around our openapi specs not accounting for None.
        sub_schemas = "\n".join(
            sorted(
                schema("type", sub_type)
                for sub_type in self.sub_types
                if not hasattr(sub_type, "equalsNone")
            )
        )
        return f"{var_name} (union):\n{indent(sub_schemas)}"


class UrlType:
    def check_data(self, var_name: str, val: Any) -> None:
        try:
            URLValidator()(val)
        except ValidationError:  # nocoverage
            raise AssertionError(f"{var_name} is not a URL")

    def schema(self, var_name: str) -> str:
        # just report str to match openapi
        return f"{var_name}: str"


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


def schema(
    # return a YAML-like string for our data type
    var_name: str,
    data_type: Any,
) -> str:
    """
    schema is a glorified repr of a data type, but it
    also includes a var_name you pass in, plus we dumb
    things down a bit to match our current openapi spec
    """
    if hasattr(data_type, "schema"):
        return data_type.schema(var_name)
    if data_type in [bool, dict, int, float, list, str]:
        return f"{var_name}: {data_type.__name__}"
    raise AssertionError(f"unknown type {data_type}")


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
