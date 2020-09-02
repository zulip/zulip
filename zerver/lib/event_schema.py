"""
This is new module that we intend to GROW from test_events.py.

It will contain schemas (aka validators) for Zulip events.

Right now it's only intended to be used by test code.
"""
from typing import Callable, Dict, List, Sequence, Set, Tuple, Union

from zerver.lib.topic import ORIG_TOPIC, TOPIC_LINKS, TOPIC_NAME
from zerver.lib.validator import (
    Validator,
    check_bool,
    check_dict,
    check_dict_only,
    check_int,
    check_int_in,
    check_list,
    check_none_or,
    check_string,
    check_union,
    check_url,
    equals,
)
from zerver.models import Realm, Stream, Subscription, UserProfile

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
    ("date_created", check_int),
]

subscription_fields: Sequence[Tuple[str, Validator[object]]] = [
    *basic_stream_fields,
    ("audible_notifications", check_none_or(check_bool)),
    ("color", check_string),
    ("desktop_notifications", check_none_or(check_bool)),
    ("email_address", check_string),
    ("email_notifications", check_none_or(check_bool)),
    ("in_home_view", check_bool),
    ("is_muted", check_bool),
    ("role", check_int_in(Subscription.ROLE_TYPES)),
    ("pin_to_top", check_bool),
    ("push_notifications", check_none_or(check_bool)),
    ("stream_weekly_traffic", check_none_or(check_int)),
    ("wildcard_mentions_notify", check_none_or(check_bool)),
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
        required_keys=[*required_keys, ("id", check_int)],
        optional_keys=optional_keys,
    )


check_add_or_remove = check_union(
    [
        # force vertical
        equals("add"),
        equals("remove"),
    ]
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

check_alert_words = check_events_dict(
    required_keys=[
        # force vertical formatting
        ("type", equals("alert_words")),
        ("alert_words", check_list(check_string)),
    ]
)

_check_custom_profile_field = check_dict_only(
    required_keys=[
        ("id", check_int),
        ("type", check_int),
        ("name", check_string),
        ("hint", check_string),
        ("field_data", check_string),
        ("order", check_int),
    ]
)

check_custom_profile_fields = check_events_dict(
    required_keys=[
        ("type", equals("custom_profile_fields")),
        ("op", equals("add")),
        ("fields", check_list(_check_custom_profile_field)),
    ]
)

_check_stream_group = check_dict_only(
    required_keys=[
        ("name", check_string),
        ("id", check_int),
        ("description", check_string),
        ("streams", check_list(check_dict_only(basic_stream_fields))),
    ]
)

check_default_stream_groups = check_events_dict(
    required_keys=[
        # force vertical
        ("type", equals("default_stream_groups")),
        ("default_stream_groups", check_list(_check_stream_group)),
    ]
)

check_default_streams = check_events_dict(
    required_keys=[
        ("type", equals("default_streams")),
        ("default_streams", check_list(check_dict_only(basic_stream_fields))),
    ]
)

check_invites_changed = check_events_dict(
    required_keys=[
        # the most boring event...no metadata
        ("type", equals("invites_changed")),
    ]
)

message_fields = [
    ("avatar_url", check_none_or(check_string)),
    ("client", check_string),
    ("content", check_string),
    ("content_type", equals("text/html")),
    ("display_recipient", check_string),
    ("id", check_int),
    ("is_me_message", check_bool),
    ("reactions", check_list(check_dict([]))),
    ("recipient_id", check_int),
    ("sender_realm_str", check_string),
    ("sender_email", check_string),
    ("sender_full_name", check_string),
    ("sender_id", check_int),
    ("stream_id", check_int),
    (TOPIC_NAME, check_string),
    (TOPIC_LINKS, check_list(check_string)),
    ("submessages", check_list(check_dict([]))),
    ("timestamp", check_int),
    ("type", check_string),
]

check_message = check_events_dict(
    required_keys=[
        ("type", equals("message")),
        ("flags", check_list(check_string)),
        ("message", check_dict_only(message_fields)),
    ]
)

# We will eventually just send user_ids.
_check_reaction_user = check_dict_only(
    required_keys=[
        # force vertical
        ("email", check_string),
        ("full_name", check_string),
        ("user_id", check_int),
    ]
)

_check_reaction = check_events_dict(
    required_keys=[
        ("type", equals("reaction")),
        ("op", check_add_or_remove),
        ("message_id", check_int),
        ("emoji_name", check_string),
        ("emoji_code", check_string),
        ("reaction_type", check_string),
        ("user_id", check_int),
        ("user", _check_reaction_user),
    ]
)


def check_reaction(var_name: str, event: Dict[str, object], op: str) -> None:
    _check_reaction(var_name, event)
    assert event["op"] == op


_check_bot_services_outgoing = check_dict_only(
    required_keys=[
        # force vertical
        ("base_url", check_url),
        ("interface", check_int),
        ("token", check_string),
    ]
)

# We use a strict check here, because our tests
# don't specifically focus on seeing how
# flexible we can make the types be for config_data.
_ad_hoc_config_data_schema = equals(dict(foo="bar"))

_check_bot_services_embedded = check_dict_only(
    required_keys=[
        # force vertical
        ("service_name", check_string),
        ("config_data", _ad_hoc_config_data_schema),
    ]
)

# Note that regular bots just get an empty list of services,
# so the sub_validator for check_list won't matter for them.
_check_bot_services = check_list(
    check_union(
        [
            # force vertical
            _check_bot_services_outgoing,
            _check_bot_services_embedded,
        ]
    ),
)

_check_bot = check_dict_only(
    required_keys=[
        ("user_id", check_int),
        ("api_key", check_string),
        ("avatar_url", check_string),
        ("bot_type", check_int),
        ("default_all_public_streams", check_bool),
        ("default_events_register_stream", check_none_or(check_string)),
        ("default_sending_stream", check_none_or(check_string)),
        ("email", check_string),
        ("full_name", check_string),
        ("is_active", check_bool),
        ("owner_id", check_int),
        ("services", _check_bot_services),
    ]
)

_check_realm_bot_add = check_events_dict(
    required_keys=[
        # force vertical
        ("type", equals("realm_bot")),
        ("op", equals("add")),
        ("bot", _check_bot),
    ]
)


def check_realm_bot_add(var_name: str, event: Dict[str, object],) -> None:
    _check_realm_bot_add(var_name, event)

    assert isinstance(event["bot"], dict)
    bot_type = event["bot"]["bot_type"]

    services_field = f"{var_name}['bot']['services']"
    services = event["bot"]["services"]

    if bot_type == UserProfile.DEFAULT_BOT:
        equals([])(services_field, services)
    elif bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
        check_list(_check_bot_services_outgoing, length=1)(services_field, services)
    elif bot_type == UserProfile.EMBEDDED_BOT:
        check_list(_check_bot_services_embedded, length=1)(services_field, services)
    else:
        raise AssertionError(f"Unknown bot_type: {bot_type}")


_check_bot_for_delete = check_dict_only(
    required_keys=[
        # for legacy reasons we have a dict here
        # with only one key
        ("user_id", check_int),
    ]
)

check_realm_bot_delete = check_events_dict(
    required_keys=[
        ("type", equals("realm_bot")),
        ("op", equals("delete")),
        ("bot", _check_bot_for_delete),
    ]
)

_check_bot_for_remove = check_dict_only(
    required_keys=[
        # Why does remove have full_name but delete doesn't?
        # Why do we have both a remove and a delete event
        # for bots?  I don't know the answer as I write this.
        ("full_name", check_string),
        ("user_id", check_int),
    ]
)

check_realm_bot_remove = check_events_dict(
    required_keys=[
        ("type", equals("realm_bot")),
        ("op", equals("remove")),
        ("bot", _check_bot_for_remove),
    ]
)

_check_bot_for_update = check_dict_only(
    required_keys=[
        # force vertical
        ("user_id", check_int),
    ],
    optional_keys=[
        ("api_key", check_string),
        ("avatar_url", check_string),
        ("default_all_public_streams", check_bool),
        ("default_events_register_stream", check_none_or(check_string)),
        ("default_sending_stream", check_none_or(check_string)),
        ("full_name", check_string),
        ("owner_id", check_int),
        ("services", _check_bot_services),
    ],
)

_check_realm_bot_update = check_events_dict(
    required_keys=[
        ("type", equals("realm_bot")),
        ("op", equals("update")),
        ("bot", _check_bot_for_update),
    ]
)


def check_realm_bot_update(
    # Check schema plus the field.
    var_name: str,
    event: Dict[str, object],
    field: str,
) -> None:
    # Check the overall schema first.
    _check_realm_bot_update(var_name, event)

    assert isinstance(event["bot"], dict)
    assert {"user_id", field} == set(event["bot"].keys())


_check_plan_type_extra_data = check_dict_only(
    required_keys=[
        # force vertical
        ("upload_quota", check_int),
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
    ],
    optional_keys=[
        # force vertical
        ("extra_data", _check_plan_type_extra_data),
    ],
)


def check_realm_update(var_name: str, event: Dict[str, object], prop: str,) -> None:
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

    assert prop == event["property"]
    value = event["value"]

    if prop == "plan_type":
        assert isinstance(value, int)
        assert "extra_data" in event.keys()
        return

    assert "extra_data" not in event.keys()

    if prop in ["notifications_stream_id", "signup_notifications_stream_id"]:
        assert isinstance(value, int)
        return

    property_type = Realm.property_types[prop]

    if property_type in (bool, int, str):
        assert isinstance(value, property_type)
    elif property_type == (int, type(None)):
        assert isinstance(value, int)
    elif property_type == (str, type(None)):
        assert isinstance(value, str)
    else:
        raise AssertionError(f"Unexpected property type {property_type}")


avatar_fields = {
    "avatar_source",
    "avatar_url",
    "avatar_url_medium",
    "avatar_version",
}

_check_custom_profile_field = check_dict_only(
    required_keys=[
        # vertical formatting
        ("id", check_int),
        ("value", check_string),
    ],
    optional_keys=[
        # vertical formatting
        ("rendered_value", check_string),
    ],
)

_check_realm_user_person = check_dict_only(
    required_keys=[
        # vertical formatting
        ("user_id", check_int),
    ],
    optional_keys=[
        ("avatar_source", check_string),
        ("avatar_url", check_none_or(check_string)),
        ("avatar_url_medium", check_none_or(check_string)),
        ("avatar_version", check_int),
        ("bot_owner_id", check_int),
        ("custom_profile_field", _check_custom_profile_field),
        ("delivery_email", check_string),
        ("full_name", check_string),
        ("role", check_int_in(UserProfile.ROLE_TYPES)),
        ("email", check_string),
        ("user_id", check_int),
        ("timezone", check_string),
    ],
)

_check_realm_user_update = check_events_dict(
    required_keys=[
        ("type", equals("realm_user")),
        ("op", equals("update")),
        ("person", _check_realm_user_person),
    ]
)


def check_realm_user_update(
    var_name: str, event: Dict[str, object], optional_fields: Set[str],
) -> None:
    _check_realm_user_update(var_name, event)

    assert isinstance(event["person"], dict)
    keys = set(event["person"].keys()) - {"user_id"}
    assert optional_fields == keys


check_stream_create = check_events_dict(
    required_keys=[
        ("type", equals("stream")),
        ("op", equals("create")),
        ("streams", check_list(check_dict_only(basic_stream_fields))),
    ]
)

check_stream_delete = check_events_dict(
    required_keys=[
        ("type", equals("stream")),
        ("op", equals("delete")),
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


def check_stream_update(var_name: str, event: Dict[str, object],) -> None:
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


check_submessage = check_events_dict(
    required_keys=[
        ("type", equals("submessage")),
        ("message_id", check_int),
        ("submessage_id", check_int),
        ("sender_id", check_int),
        ("msg_type", check_string),
        ("content", check_string),
    ]
)

_check_single_subscription = check_dict_only(
    required_keys=subscription_fields,
    optional_keys=[
        # force vertical
        ("subscribers", check_list(check_int)),
    ],
)

_check_subscription_add = check_events_dict(
    required_keys=[
        ("type", equals("subscription")),
        ("op", equals("add")),
        ("subscriptions", check_list(_check_single_subscription)),
    ],
)


def check_subscription_add(
    var_name: str, event: Dict[str, object], include_subscribers: bool,
) -> None:
    _check_subscription_add(var_name, event)

    assert isinstance(event["subscriptions"], list)
    for sub in event["subscriptions"]:
        if include_subscribers:
            assert "subscribers" in sub.keys()
        else:
            assert "subscribers" not in sub.keys()


check_subscription_peer_add = check_events_dict(
    required_keys=[
        ("type", equals("subscription")),
        ("op", equals("peer_add")),
        ("user_id", check_int),
        ("stream_id", check_int),
    ]
)

check_subscription_peer_remove = check_events_dict(
    required_keys=[
        ("type", equals("subscription")),
        ("op", equals("peer_remove")),
        ("user_id", check_int),
        ("stream_id", check_int),
    ]
)

_check_remove_sub = check_dict_only(
    required_keys=[
        # We should eventually just return stream_id here.
        ("name", check_string),
        ("stream_id", check_int),
    ]
)

check_subscription_remove = check_events_dict(
    required_keys=[
        ("type", equals("subscription")),
        ("op", equals("remove")),
        ("subscriptions", check_list(_check_remove_sub)),
    ]
)

_check_typing_person = check_dict_only(
    required_keys=[
        # we should eventually just send user_id
        ("email", check_string),
        ("user_id", check_int),
    ]
)

check_typing_start = check_events_dict(
    required_keys=[
        ("type", equals("typing")),
        ("op", equals("start")),
        ("sender", _check_typing_person),
        ("recipients", check_list(_check_typing_person)),
    ]
)

check_typing_stop = check_events_dict(
    required_keys=[
        ("type", equals("typing")),
        ("op", equals("stop")),
        ("sender", _check_typing_person),
        ("recipients", check_list(_check_typing_person)),
    ]
)

_check_update_display_settings = check_events_dict(
    required_keys=[
        ("type", equals("update_display_settings")),
        ("setting_name", check_string),
        ("setting", check_value),
        ("user", check_string),
    ],
    optional_keys=[
        # force vertical
        ("language_name", check_string),
    ],
)


def check_update_display_settings(var_name: str, event: Dict[str, object],) -> None:
    """
    Display setting events have a "setting" field that
    is more specifically typed according to the
    UserProfile.property_types dictionary.
    """
    _check_update_display_settings(var_name, event)
    setting_name = event["setting_name"]
    setting = event["setting"]

    assert isinstance(setting_name, str)
    setting_type = UserProfile.property_types[setting_name]
    assert isinstance(setting, setting_type)

    if setting_name == "default_language":
        assert "language_name" in event.keys()
    else:
        assert "language_name" not in event.keys()


_check_update_global_notifications = check_events_dict(
    required_keys=[
        ("type", equals("update_global_notifications")),
        ("notification_name", check_string),
        ("setting", check_value),
        ("user", check_string),
    ]
)


def check_update_global_notifications(
    var_name: str, event: Dict[str, object], desired_val: Union[bool, int, str],
) -> None:
    """
    See UserProfile.notification_setting_types for
    more details.
    """
    _check_update_global_notifications(var_name, event)
    setting_name = event["notification_name"]
    setting = event["setting"]
    assert setting == desired_val

    assert isinstance(setting_name, str)
    setting_type = UserProfile.notification_setting_types[setting_name]
    assert isinstance(setting, setting_type)


update_message_required_fields = [
    ("type", equals("update_message")),
    ("user_id", check_int),
    ("edit_timestamp", check_int),
    ("message_id", check_int),
]

update_message_content_fields: List[Tuple[str, Callable[[str, object], object]]] = [
    ("content", check_string),
    ("is_me_message", check_bool),
    ("orig_content", check_string),
    ("orig_rendered_content", check_string),
    ("prev_rendered_content_version", check_int),
    ("rendered_content", check_string),
]

update_message_topic_fields = [
    ("flags", check_list(check_string)),
    ("message_ids", check_list(check_int)),
    ("new_stream_id", check_int),
    (ORIG_TOPIC, check_string),
    ("propagate_mode", check_string),
    ("stream_id", check_int),
    ("stream_name", check_string),
    (TOPIC_LINKS, check_list(check_string)),
    (TOPIC_NAME, check_string),
]

update_message_optional_fields = (
    update_message_content_fields + update_message_topic_fields
)

# The schema here does not include the "embedded"
# variant of update_message; it is for message
# and topic editing.
_check_update_message = check_events_dict(
    required_keys=update_message_required_fields,
    optional_keys=update_message_optional_fields,
)


def check_update_message(
    var_name: str,
    event: Dict[str, object],
    has_content: bool,
    has_topic: bool,
    has_new_stream_id: bool,
) -> None:
    # Always check the basic schema first.
    _check_update_message(var_name, event)

    actual_keys = set(event.keys())
    expected_keys = {"id"}
    expected_keys.update(tup[0] for tup in update_message_required_fields)

    if has_content:
        expected_keys.update(tup[0] for tup in update_message_content_fields)

    if has_topic:
        expected_keys.update(tup[0] for tup in update_message_topic_fields)

    if not has_new_stream_id:
        expected_keys.discard("new_stream_id")

    assert expected_keys == actual_keys


check_update_message_embedded = check_events_dict(
    required_keys=[
        ("type", equals("update_message")),
        ("flags", check_list(check_string)),
        ("content", check_string),
        ("message_id", check_int),
        ("message_ids", check_list(check_int)),
        ("rendered_content", check_string),
    ]
)

_check_update_message_flags = check_events_dict(
    required_keys=[
        ("type", equals("update_message_flags")),
        ("op", check_add_or_remove),
        ("operation", check_add_or_remove),
        ("flag", check_string),
        ("messages", check_list(check_int)),
        ("all", check_bool),
    ]
)


def check_update_message_flags(
    var_name: str, event: Dict[str, object], operation: str
) -> None:
    _check_update_message_flags(var_name, event)
    assert event["operation"] == operation and event['op'] == operation


_check_group = check_dict_only(
    required_keys=[
        ("id", check_int),
        ("name", check_string),
        ("members", check_list(check_int)),
        ("description", check_string),
    ]
)

check_user_group_add = check_events_dict(
    required_keys=[
        ("type", equals("user_group")),
        ("op", equals("add")),
        ("group", _check_group),
    ]
)

check_user_status = check_events_dict(
    required_keys=[
        ("type", equals("user_status")),
        ("user_id", check_int),
        ("away", check_bool),
        ("status_text", check_string),
    ]
)
