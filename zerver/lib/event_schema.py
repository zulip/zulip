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
    check_string,
    check_union,
    equals,
)


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
