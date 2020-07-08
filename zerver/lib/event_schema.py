"""
This is new module that we intend to GROW from test_events.py.

It will contain schemas (aka validators) for Zulip events.

Right now it's only intended to be used by test code.
"""
from typing import Any, Dict, Sequence, Tuple

from zerver.lib.validator import (
    Validator,
    check_bool,
    check_dict_only,
    check_int,
    check_string,
    check_union,
    equals,
)
from zerver.models import Realm


def check_events_dict(
    required_keys: Sequence[Tuple[str, Validator[object]]],
    optional_keys: Sequence[Tuple[str, Validator[object]]] = [],
) -> Validator[Dict[str, object]]:
    """
    This is just a tiny wrapper on check_dict, but it provides
    some minor benefits:

        - mark clearly that the schema is for a Zulip event
        - make sure there's a type field
        - add id field automatically
        - sanity check that we have no duplicate keys (we
          should just make check_dict do that, eventually)

    """
    rkeys = [key[0] for key in required_keys]
    okeys = [key[0] for key in optional_keys]
    keys = rkeys + okeys
    assert len(keys) == len(set(keys))
    assert "type" in rkeys
    assert "id" not in keys
    return check_dict_only(
        required_keys=list(required_keys) + [("id", check_int)],
        optional_keys=optional_keys,
    )


check_value = check_union(
    [
        # force vertical formatting
        check_bool,
        check_int,
        check_string,
    ]
)


"""
realm/update events are flexible for values;
we will use a more strict checker to check
types in a context-specific manner
"""
_check_realm_update = check_events_dict(
    required_keys=[
        ("type", equals("realm")),
        ("op", equals("update")),
        ("property", check_string),
        ("value", check_value),
    ]
)


def check_realm_update(var_name: str, event: Dict[str, Any],) -> None:
    """
    Realm updates have these two fields:

        property
        value

    We check not only the basic schema, but also that
    the value people actually matches the type from
    Realm.property_types that we have configured
    for the property.
    """
    _check_realm_update(var_name, event)
    prop = event["property"]
    value = event["value"]

    property_type = Realm.property_types[prop]
    if property_type in (bool, int, str):
        assert isinstance(value, property_type)
    elif property_type == (int, type(None)):
        assert isinstance(value, int)
    elif property_type == (str, type(None)):
        assert isinstance(value, str)
    else:
        raise AssertionError(f"Unexpected property type {property_type}")
