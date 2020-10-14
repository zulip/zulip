"use strict";

const people = require("./people");

/*
    This config is in a separate file for partly
    tactical reasons.  We want the webapp to
    configure this one way, but we don't want to
    share this code with mobile.

    I also wanted to make some diffs clear before
    doing any major file moves.

    Also, I want the unit tests for Markdown to
    be able to reuse this code easily (and therefore
    didn't just put this in ui_init.js).

    Once the first steps of making Markdown be a
    shared library are complete, we may tweak
    the file organization a bit.

    Most functions here that are looking up data
    follow the convention of returning `undefined`
    when the lookups fail.
*/

exports.get_helpers = () => ({
    // user stuff
    get_actual_name_from_user_id: people.get_actual_name_from_user_id,
    get_user_id_from_name: people.get_user_id_from_name,
    is_valid_full_name_and_user_id: people.is_valid_full_name_and_user_id,
    my_user_id: people.my_current_user_id,

    // user groups
    get_user_group_from_name: user_groups.get_user_group_from_name,
    is_member_of_user_group: user_groups.is_member_of,

    // stream hashes
    get_stream_by_name: stream_data.get_sub,
    stream_hash: hash_util.by_stream_uri,
    stream_topic_hash: hash_util.by_stream_topic_uri,

    // settings
    should_translate_emoticons: () => page_params.translate_emoticons,
});
