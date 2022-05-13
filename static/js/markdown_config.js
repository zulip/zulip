import * as emoji from "./emoji";
import * as hash_util from "./hash_util";
import * as linkifiers from "./linkifiers";
import * as people from "./people";
import * as stream_data from "./stream_data";
import * as user_groups from "./user_groups";
import {user_settings} from "./user_settings";

/*
    This config is in a separate file for partly
    tactical reasons.  We want the web app to
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

function abstract_map(map) {
    return {
        keys: () => map.keys(),
        entries: () => map.entries(),
        get: (k) => map.get(k),
    };
}

function stream(obj) {
    if (obj === undefined) {
        return undefined;
    }

    return {
        stream_id: obj.stream_id,
        name: obj.name,
    };
}

function user_group(obj) {
    if (obj === undefined) {
        return undefined;
    }

    return {
        id: obj.id,
        name: obj.name,
    };
}

export const get_helpers = () => ({
    // user stuff
    get_actual_name_from_user_id: people.get_actual_name_from_user_id,
    get_user_id_from_name: people.get_user_id_from_name,
    is_valid_full_name_and_user_id: people.is_valid_full_name_and_user_id,
    my_user_id: people.my_current_user_id,
    is_valid_user_id: people.is_known_user_id,

    // user groups
    get_user_group_from_name: (name) => user_group(user_groups.get_user_group_from_name(name)),
    is_member_of_user_group: user_groups.is_direct_member_of,

    // stream hashes
    get_stream_by_name: (name) => stream(stream_data.get_sub(name)),
    stream_hash: hash_util.by_stream_url,
    stream_topic_hash: hash_util.by_stream_topic_url,

    // settings
    should_translate_emoticons: () => user_settings.translate_emoticons,

    // emojis
    get_emoji_name: emoji.get_emoji_name,
    get_emoji_codepoint: emoji.get_emoji_codepoint,
    get_emoticon_translations: emoji.get_emoticon_translations,
    get_realm_emoji_url: emoji.get_realm_emoji_url,

    // linkifiers
    get_linkifier_map: () => abstract_map(linkifiers.get_linkifier_map()),
});
