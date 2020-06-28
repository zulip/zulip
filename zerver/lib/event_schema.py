'''
This is new module that we intend to GROW from test_events.py.

It will contain schemas (aka validators) for Zulip events.

Right now it's only intended to be used by test code.
'''
from typing import Dict, Sequence, Tuple

from zerver.lib.validator import (
    Validator,
    check_bool,
    check_dict_only,
    check_int,
    check_int_in,
    check_list,
    check_none_or,
    check_string,
    check_union,
    equals,
)
from zerver.models import Stream


def check_events_dict(
    required_keys: Sequence[Tuple[str, Validator[object]]],
    optional_keys: Sequence[Tuple[str, Validator[object]]]=[]
) -> Validator[Dict[str, object]]:
    '''
    This is just a tiny wrapper on check_dict, but it provides
    some minor benefits:

        - mark clearly that the schema is for a Zulip event
        - make sure there's a type field
        - add id field automatically
        - sanity check that we have no duplicate keys (we
          should just make check_dict do that, eventually)

    '''
    rkeys = [key[0] for key in required_keys]
    okeys = [key[0] for key in optional_keys]
    keys = rkeys + okeys
    assert len(keys) == len(set(keys))
    assert 'type' in rkeys
    assert 'id' not in keys
    return check_dict_only(
        required_keys=list(required_keys) + [('id', check_int)],
        optional_keys=optional_keys,
    )

# These fields are used for "stream" events, and are included in the
# larger "subscription" events that also contain personal settings.
basic_stream_fields = [
    ('description', check_string),
    ('first_message_id', check_none_or(check_int)),
    ('history_public_to_subscribers', check_bool),
    ('invite_only', check_bool),
    ('is_announcement_only', check_bool),
    ('is_web_public', check_bool),
    ('message_retention_days', equals(None)),
    ('name', check_string),
    ('rendered_description', check_string),
    ('stream_id', check_int),
    ('stream_post_policy', check_int),
]

subscription_fields = basic_stream_fields + [
    ('audible_notifications', check_none_or(check_bool)),
    ('color', check_string),
    ('desktop_notifications', check_none_or(check_bool)),
    ('email_address', check_string),
    ('email_notifications', check_none_or(check_bool)),
    ('in_home_view', check_bool),
    ('is_muted', check_bool),
    ('pin_to_top', check_bool),
    ('push_notifications', check_none_or(check_bool)),
    ('stream_weekly_traffic', check_none_or(check_int)),
    ('wildcard_mentions_notify', check_none_or(check_bool)),
]

realm_update_schema = check_events_dict([
    ('type', equals('realm')),
    ('op', equals('update')),
    ('property', check_string),
    ('value', check_union([
        check_bool,
        check_int,
        check_string,
    ])),
])

stream_create_schema = check_events_dict([
    ('type', equals('stream')),
    ('op', equals('create')),
    ('streams', check_list(check_dict_only(basic_stream_fields))),
])

stream_update_description_schema = check_events_dict([
    ('type', equals('stream')),
    ('op', equals('update')),
    ('property', equals('description')),
    ('value', check_string),
    ('rendered_description', check_string),
    ('stream_id', check_int),
    ('name', check_string),
])

stream_update_invite_only_schema = check_events_dict([
    ('type', equals('stream')),
    ('op', equals('update')),
    ('property', equals('invite_only')),
    ('stream_id', check_int),
    ('name', check_string),
    ('value', check_bool),
    ('history_public_to_subscribers', check_bool),
])

stream_update_stream_post_policy_schema = check_events_dict([
    ('type', equals('stream')),
    ('op', equals('update')),
    ('property', equals('stream_post_policy')),
    ('stream_id', check_int),
    ('name', check_string),
    ('value', check_int_in(Stream.STREAM_POST_POLICY_TYPES)),
])

stream_update_message_retention_days_schema = check_events_dict([
    ('type', equals('stream')),
    ('op', equals('update')),
    ('property', equals('message_retention_days')),
    ('stream_id', check_int),
    ('name', check_string),
    ('value', check_none_or(check_int))
])

subscription_add_schema = check_events_dict([
    ('type', equals('subscription')),
    ('op', equals('add')),
    ('subscriptions', check_list(
        check_dict_only(
            required_keys=subscription_fields,
            optional_keys=[
                ('subscribers', check_list(check_int)),
            ],
        ),
    )),
])

subscription_peer_add_schema = check_events_dict([
    ('type', equals('subscription')),
    ('op', equals('peer_add')),
    ('user_id', check_int),
    ('stream_id', check_int),
])

subscription_peer_remove_schema = check_events_dict([
    ('type', equals('subscription')),
    ('op', equals('peer_remove')),
    ('user_id', check_int),
    ('stream_id', check_int),
])

subscription_remove_schema = check_events_dict([
    ('type', equals('subscription')),
    ('op', equals('remove')),
    ('subscriptions', check_list(
        check_dict_only([
            ('name', equals('test_stream')),
            ('stream_id', check_int),
        ]),
    )),
])

update_display_settings_schema = check_events_dict(
    required_keys=[
        ('type', equals('update_display_settings')),
        ('setting_name', check_string),
        ('user', check_string),
        ('setting', check_union([
            check_bool,
            check_int,
            check_string,
        ])),
    ],
    optional_keys=[
        ('language_name', check_string),
    ],
)
