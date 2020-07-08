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
    check_list,
    check_none_or,
    check_string,
    check_union,
    equals,
)
from zerver.models import Realm, Stream

# These fields are used for "stream" events, and are included in the
# larger "subscription" events that also contain personal settings.
basic_stream_fields = [
    ("description", check_string),
    ("first_message_id", check_none_or(check_int)),
    ("history_public_to_subscribers", check_bool),
    ("invite_only", check_bool),
    ("is_announcement_only", check_bool),
    ("is_web_public", check_bool),
    ("message_retention_days", equals(None)),
    ("name", check_string),
    ("rendered_description", check_string),
    ("stream_id", check_int),
    ("stream_post_policy", check_int),
]


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

check_optional_value = check_union(
    [
        # force vertical formatting
        check_bool,
        check_int,
        check_string,
        equals(None),
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


check_stream_create = check_events_dict(
    required_keys=[
        ("type", equals("stream")),
        ("op", equals("create")),
        ("streams", check_list(check_dict_only(basic_stream_fields))),
    ]
)

_check_stream_update = check_events_dict(
    required_keys=[
        ("type", equals("stream")),
        ("op", equals("update")),
        ("property", check_string),
        ("value", check_optional_value),
        ("name", check_string),
        ("stream_id", check_int),
    ],
    optional_keys=[
        ("rendered_description", check_string),
        ("history_public_to_subscribers", check_bool),
    ],
)


def check_stream_update(var_name: str, event: Dict[str, Any],) -> None:
    _check_stream_update(var_name, event)
    prop = event["property"]
    value = event["value"]

    extra_keys = set(event.keys()) - {
        "id",
        "type",
        "op",
        "property",
        "value",
        "name",
        "stream_id",
    }

    if prop == "description":
        assert extra_keys == {"rendered_description"}
        assert isinstance(value, str)
    elif prop == "email_address":
        assert extra_keys == set()
        assert isinstance(value, str)
    elif prop == "invite_only":
        assert extra_keys == {"history_public_to_subscribers"}
        assert isinstance(value, bool)
    elif prop == "message_retention_days":
        assert extra_keys == set()
        if value is not None:
            assert isinstance(value, int)
    elif prop == "name":
        assert extra_keys == set()
        assert isinstance(value, str)
    elif prop == "stream_post_policy":
        assert extra_keys == set()
        assert value in Stream.STREAM_POST_POLICY_TYPES
    else:
        raise AssertionError(f"Unknown property: {prop}")
