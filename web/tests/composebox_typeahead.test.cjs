"use strict";

const assert = require("node:assert/strict");

const {get_final_topic_display_name} = require("../src/util.ts");

const {mock_banners} = require("./lib/compose_banner.cjs");
const example_settings = require("./lib/example_settings.cjs");
const {mock_esm, set_global, with_overrides, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

let autosize_called;
const REALM_EMPTY_TOPIC_DISPLAY_NAME = "general chat";

const bootstrap_typeahead = mock_esm("../src/bootstrap_typeahead");
const compose_ui = mock_esm("../src/compose_ui", {
    autosize_textarea() {
        autosize_called = true;
    },
    cursor_inside_code_block: () => false,
    set_code_formatting_button_triggered: noop,
    set_compose_textarea_typeahead: noop,
});
const compose_validate = mock_esm("../src/compose_validate", {
    validate_message_length: () => true,
    warn_if_topic_resolved: noop,
    stream_wildcard_mention_allowed: () => true,
    warn_if_mentioning_unsubscribed_group: noop,
    initialize: noop,
});
const input_pill = mock_esm("../src/input_pill");
const message_user_ids = mock_esm("../src/message_user_ids", {
    user_ids: () => [],
});
const stream_topic_history_util = mock_esm("../src/stream_topic_history_util");
mock_esm("../src/channel", {
    get: () => ({subscribers: []}),
});

let set_timeout_called;
set_global("setTimeout", (f, time) => {
    f();
    assert.equal(time, 0);
    set_timeout_called = true;
});
set_global("document", "document-stub");

const typeahead = zrequire("../shared/src/typeahead");
const stream_topic_history = zrequire("stream_topic_history");
const compose_state = zrequire("compose_state");
const emoji = zrequire("emoji");
const emoji_picker = zrequire("emoji_picker");
const typeahead_helper = zrequire("typeahead_helper");
const muted_users = zrequire("muted_users");
const people = zrequire("people");
const user_groups = zrequire("user_groups");
const user_pill = zrequire("user_pill");
const stream_data = zrequire("stream_data");
const stream_list_sort = zrequire("stream_list_sort");
const compose_pm_pill = zrequire("compose_pm_pill");
const compose_recipient = zrequire("compose_recipient");
const composebox_typeahead = zrequire("composebox_typeahead");
const settings_config = zrequire("settings_config");
const {set_current_user, set_realm} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");
const current_user = {};
set_current_user(current_user);
const realm = {
    realm_empty_topic_display_name: REALM_EMPTY_TOPIC_DISPLAY_NAME,
    realm_topics_policy: "allow_empty_topic",
};
set_realm(realm);
const user_settings = {
    web_channel_default_view: settings_config.web_channel_default_view_values.channel_feed.code,
};
initialize_user_settings({user_settings});

const ct = composebox_typeahead;

function user_item(user) {
    return {type: "user", user};
}

function broadcast_item(user) {
    return {type: "broadcast", user};
}

function slash_item(slash) {
    return {
        ...slash,
        type: "slash",
    };
}

function stream_item(stream) {
    return {
        ...stream,
        type: "stream",
    };
}

function user_group_item(item) {
    return {
        ...item,
        type: "user_group",
    };
}

function language_item(language) {
    return {
        language,
        type: "syntax",
    };
}

run_test("verify wildcard mentions typeahead for stream message", () => {
    compose_state.set_message_type("stream");
    const mention_all = ct.broadcast_mentions()[0];
    const mention_everyone = ct.broadcast_mentions()[1];
    const mention_stream = ct.broadcast_mentions()[2];
    const mention_channel = ct.broadcast_mentions()[3];
    const mention_topic = ct.broadcast_mentions()[4];
    assert.equal(mention_all.email, "all");
    assert.equal(mention_all.full_name, "all");
    assert.equal(mention_everyone.email, "everyone");
    assert.equal(mention_everyone.full_name, "everyone");
    assert.equal(mention_stream.email, "stream");
    assert.equal(mention_stream.full_name, "stream");
    assert.equal(mention_channel.email, "channel");
    assert.equal(mention_channel.full_name, "channel");
    assert.equal(mention_topic.email, "topic");
    assert.equal(mention_topic.full_name, "topic");

    assert.equal(mention_all.special_item_text, "all");
    assert.equal(mention_all.secondary_text, "translated: Notify channel");
    assert.equal(mention_everyone.special_item_text, "everyone");
    assert.equal(mention_everyone.secondary_text, "translated: Notify channel");
    assert.equal(mention_stream.special_item_text, "stream");
    assert.equal(mention_stream.secondary_text, "translated: Notify channel");
    assert.equal(mention_channel.special_item_text, "channel");
    assert.equal(mention_channel.secondary_text, "translated: Notify channel");
    assert.equal(mention_topic.special_item_text, "topic");
    assert.equal(mention_topic.secondary_text, "translated: Notify topic");

    compose_validate.stream_wildcard_mention_allowed = () => false;
    compose_validate.topic_wildcard_mention_allowed = () => true;
    const mention_topic_only = ct.broadcast_mentions()[0];
    assert.equal(mention_topic_only.full_name, "topic");

    compose_validate.stream_wildcard_mention_allowed = () => false;
    compose_validate.topic_wildcard_mention_allowed = () => false;
    const mentionNobody = ct.broadcast_mentions();
    assert.equal(mentionNobody.length, 0);
    compose_validate.stream_wildcard_mention_allowed = () => true;
});

run_test("verify wildcard mentions typeahead for direct message", () => {
    compose_state.set_message_type("private");
    assert.equal(ct.broadcast_mentions().length, 2);
    const mention_all = ct.broadcast_mentions()[0];
    const mention_everyone = ct.broadcast_mentions()[1];
    assert.equal(mention_all.email, "all");
    assert.equal(mention_all.full_name, "all");
    assert.equal(mention_everyone.email, "everyone");
    assert.equal(mention_everyone.full_name, "everyone");

    assert.equal(mention_all.special_item_text, "all");
    assert.equal(mention_all.secondary_text, "translated: Notify recipients");
    assert.equal(mention_everyone.special_item_text, "everyone");
    assert.equal(mention_all.secondary_text, "translated: Notify recipients");
});

const emoji_stadium = {
    name: "stadium",
    aliases: ["stadium"],
    emoji_url: "TBD",
    emoji_code: "1f3df",
};
const emoji_tada = {
    name: "tada",
    aliases: ["tada"],
    emoji_url: "TBD",
    emoji_code: "1f389",
};
const emoji_moneybag = {
    name: "moneybag",
    aliases: ["moneybag"],
    emoji_url: "TBD",
    emoji_code: "1f4b0",
};
const emoji_japanese_post_office = {
    name: "japanese_post_office",
    aliases: ["japanese_post_office"],
    emoji_url: "TBD",
    emoji_code: "1f3e3",
};
const emoji_panda_face = {
    name: "panda_face",
    aliases: ["panda_face"],
    emoji_url: "TBD",
    emoji_code: "1f43c",
};
const emoji_see_no_evil = {
    name: "see_no_evil",
    aliases: ["see_no_evil"],
    emoji_url: "TBD",
    emoji_code: "1f648",
};
const emoji_thumbs_up = {
    name: "thumbs_up",
    aliases: ["thumbs_up"],
    emoji_url: "TBD",
    emoji_code: "1f44d",
};
const emoji_thermometer = {
    name: "thermometer",
    aliases: ["thermometer"],
    emoji_url: "TBD",
    emoji_code: "1f321",
};
const emoji_heart = {
    name: "heart",
    aliases: ["heart"],
    emoji_url: "TBD",
    emoji_code: "2764",
};
const emoji_headphones = {
    name: "headphones",
    aliases: ["headphones"],
    emoji_url: "TBD",
    emoji_code: "1f3a7",
};

const emojis_by_name = new Map(
    Object.entries({
        tada: emoji_tada,
        moneybag: emoji_moneybag,
        stadium: emoji_stadium,
        japanese_post_office: emoji_japanese_post_office,
        panda_face: emoji_panda_face,
        see_no_evil: emoji_see_no_evil,
        thumbs_up: emoji_thumbs_up,
        thermometer: emoji_thermometer,
        heart: emoji_heart,
        headphones: emoji_headphones,
    }),
);

const me_command = {
    name: "me",
    aliases: "",
    text: "translated: /me",
    placeholder: "translated: is …",
    info: "translated: Action message",
};
const me_command_item = slash_item(me_command);

const my_command_item = slash_item({
    name: "my",
    aliases: "",
    text: "translated: /my (Test)",
});

const dark_command = {
    name: "dark",
    aliases: "night",
    text: "translated: /dark",
    info: "translated: Switch to the dark theme",
};
const dark_command_item = slash_item(dark_command);

const light_command = {
    name: "light",
    aliases: "day",
    text: "translated: /light",
    info: "translated: Switch to light theme",
};
const light_command_item = slash_item(light_command);

const name_to_codepoint = {};
for (const [key, val] of emojis_by_name.entries()) {
    name_to_codepoint[key] = val.emoji_code;
}

const codepoint_to_name = {};
for (const [key, val] of emojis_by_name.entries()) {
    codepoint_to_name[val.emoji_code] = key;
}

const emoji_codes = {
    name_to_codepoint,
    names: [...emojis_by_name.keys()],
    emoji_catalog: {},
    emoticon_conversions: {},
    codepoint_to_name,
};

emoji.initialize({
    realm_emoji: {},
    emoji_codes,
});
emoji.active_realm_emojis.clear();
emoji.emojis_by_name.clear();
for (const [key, val] of emojis_by_name.entries()) {
    emoji.emojis_by_name.set(key, val);
}
emoji_picker.rebuild_catalog();
const emoji_list = composebox_typeahead.emoji_collection.map((emoji) => ({
    ...emoji,
    type: "emoji",
}));
const emoji_list_by_name = new Map(emoji_list.map((emoji) => [emoji.emoji_name, emoji]));
function emoji_objects(emoji_names) {
    return emoji_names.map((emoji_name) => emoji_list_by_name.get(emoji_name));
}

const ali = {
    email: "ali@zulip.com",
    user_id: 98,
    full_name: "Ali",
    is_moderator: false,
    is_bot: false,
};
const ali_item = user_item(ali);

const alice = {
    email: "alice@zulip.com",
    user_id: 99,
    full_name: "Alice",
    is_moderator: false,
    is_bot: false,
};
const alice_item = user_item(alice);

const hamlet = {
    email: "hamlet@zulip.com",
    user_id: 100,
    full_name: "King Hamlet",
    is_moderator: false,
    is_bot: false,
};
const hamlet_item = user_item(hamlet);

const othello = {
    email: "othello@zulip.com",
    user_id: 101,
    full_name: "Othello, the Moor of Venice",
    is_moderator: false,
    delivery_email: null,
    is_bot: false,
};
const othello_item = user_item(othello);

const cordelia = {
    email: "cordelia@zulip.com",
    user_id: 102,
    full_name: "Cordelia, Lear's daughter",
    is_moderator: false,
    is_bot: false,
};
const cordelia_item = user_item(cordelia);

const deactivated_user = {
    email: "other@zulip.com",
    user_id: 103,
    full_name: "Deactivated User",
    is_moderator: false,
    is_bot: false,
};
const deactivated_user_item = user_item(deactivated_user);

const lear = {
    email: "lear@zulip.com",
    user_id: 104,
    full_name: "King Lear",
    is_moderator: false,
    is_bot: false,
};
const lear_item = user_item(lear);

const twin1 = {
    full_name: "Mark Twin",
    is_moderator: false,
    user_id: 105,
    email: "twin1@zulip.com",
    is_bot: false,
};
const twin1_item = user_item(twin1);

const twin2 = {
    full_name: "Mark Twin",
    is_moderator: false,
    user_id: 106,
    email: "twin2@zulip.com",
    is_bot: false,
};
const twin2_item = user_item(twin2);

const gael = {
    full_name: "Gaël Twin",
    is_moderator: false,
    user_id: 107,
    email: "twin3@zulip.com",
    is_bot: false,
};
const gael_item = user_item(gael);

const hal = {
    full_name: "Earl Hal",
    is_moderator: false,
    user_id: 108,
    email: "hal@zulip.com",
    is_bot: false,
};
const hal_item = user_item(hal);

const harry = {
    full_name: "Harry",
    is_moderator: false,
    user_id: 109,
    email: "harry@zulip.com",
    is_bot: false,
};
const harry_item = user_item(harry);

const welcome_bot = {
    full_name: "Welcome Bot",
    is_bot: true,
    is_system_bot: true,
    user_id: 110,
    email: "welcome-bot@zulip.com",
};

const welcome_bot_item = user_item(welcome_bot);

const notification_bot = {
    full_name: "Notification Bot",
    is_bot: true,
    is_system_bot: true,
    user_id: 111,
    email: "notification-bot@zulip.com",
};

const notification_bot_item = user_item(notification_bot);

const hamletcharacters = user_group_item({
    name: "hamletcharacters",
    id: 1,
    creator_id: null,
    date_created: 1596710000,
    description: "Characters of Hamlet",
    members: new Set([100, 104]),
    is_system_group: false,
    direct_subgroup_ids: new Set([]),
    can_add_members_group: 2,
    can_join_group: 2,
    can_leave_group: 2,
    can_manage_group: 2,
    can_mention_group: 2,
    can_remove_members_group: 2,
    deactivated: false,
});

const backend = user_group_item({
    name: "Backend",
    id: 2,
    creator_id: null,
    date_created: 1596710000,
    description: "Backend team",
    members: new Set([101]),
    is_system_group: false,
    direct_subgroup_ids: new Set([1]),
    can_add_members_group: 1,
    can_join_group: 1,
    can_leave_group: 2,
    can_manage_group: 1,
    can_mention_group: 1,
    can_remove_members_group: 2,
    deactivated: false,
});

const call_center = user_group_item({
    name: "Call Center",
    id: 3,
    creator_id: null,
    date_created: 1596710000,
    description: "folks working in support",
    members: new Set([102]),
    is_system_group: false,
    direct_subgroup_ids: new Set([]),
    can_add_members_group: 2,
    can_join_group: 2,
    can_leave_group: 2,
    can_manage_group: 2,
    can_mention_group: 2,
    can_remove_members_group: 2,
    deactivated: false,
});

const support = user_group_item({
    name: "support",
    id: 4,
    creator_id: null,
    date_created: 1596710000,
    description: "Support team",
    members: new Set([]),
    is_system_group: false,
    direct_subgroup_ids: new Set([]),
    can_add_members_group: 2,
    can_join_group: 2,
    can_leave_group: 2,
    can_manage_group: 2,
    can_mention_group: 2,
    deactivated: false,
});

const admins = user_group_item({
    name: "Administrators",
    id: 5,
    creator_id: null,
    date_created: 1596710000,
    description: "Administrators",
    members: new Set([102, 103]),
    is_system_group: true,
    direct_subgroup_ids: new Set([]),
    can_add_members_group: 2,
    can_join_group: 2,
    can_leave_group: 2,
    can_manage_group: 2,
    can_mention_group: 2,
    can_remove_members_group: 2,
    deactivated: false,
});

const members = user_group_item({
    name: "role:members",
    id: 6,
    creator_id: null,
    date_created: 1596710000,
    description: "Members",
    members: new Set([100, 101, 104]),
    is_system_group: true,
    direct_subgroup_ids: new Set([5]),
    can_add_members_group: 2,
    can_join_group: 2,
    can_leave_group: 2,
    can_manage_group: 2,
    can_mention_group: 2,
    can_remove_members_group: 2,
    deactivated: false,
});

const sweden_stream = stream_item({
    name: "Sweden",
    description: "Cold, mountains and home decor.",
    stream_id: 1,
    subscribed: true,
    can_administer_channel_group: support.id,
    can_add_subscribers_group: support.id,
    can_subscribe_group: support.id,
});
const denmark_stream = stream_item({
    name: "Denmark",
    description: "Vikings and boats, in a serene and cold weather.",
    stream_id: 2,
    subscribed: true,
    can_administer_channel_group: support.id,
    can_add_subscribers_group: support.id,
    can_subscribe_group: support.id,
});
const netherland_stream = stream_item({
    name: "The Netherlands",
    description: "The Netherlands, city of dream.",
    stream_id: 3,
    subscribed: false,
    can_administer_channel_group: support.id,
    can_add_subscribers_group: support.id,
    can_subscribe_group: support.id,
});
const mobile_stream = stream_item({
    name: "Mobile",
    description: "Mobile development",
    stream_id: 4,
    subscribed: false,
    can_administer_channel_group: support.id,
    can_add_subscribers_group: support.id,
    can_subscribe_group: support.id,
});
const mobile_team_stream = stream_item({
    name: "Mobile team",
    description: "Mobile development team",
    stream_id: 5,
    subscribed: true,
    can_administer_channel_group: support.id,
    can_add_subscribers_group: support.id,
    can_subscribe_group: support.id,
});
const broken_link_stream = stream_item({
    name: "A* Algorithm",
    description: "A `*` in the stream name produces a broken #**stream>topic** link",
    stream_id: 6,
    subscribed: true,
    can_administer_channel_group: support.id,
    can_add_subscribers_group: support.id,
});

stream_data.add_sub(sweden_stream);
stream_data.add_sub(denmark_stream);
stream_data.add_sub(netherland_stream);
stream_data.add_sub(mobile_stream);
stream_data.add_sub(mobile_team_stream);
stream_data.add_sub(broken_link_stream);

const make_emoji = (emoji_dict) => ({
    emoji_name: emoji_dict.name,
    emoji_code: emoji_dict.emoji_code,
    reaction_type: "unicode_emoji",
    is_realm_emoji: false,
    type: "emoji",
});

// Sorted by name
const sorted_user_list = [
    ali_item,
    alice_item,
    cordelia_item,
    hal_item, // Early Hal
    gael_item,
    harry_item,
    hamlet_item, // King Hamlet
    lear_item,
    twin1_item, // Mark Twin
    twin2_item,
    othello_item,
];

function test(label, f) {
    run_test(label, (helpers) => {
        people.init();
        user_groups.init();
        helpers.override(
            realm,
            "server_supported_permission_settings",
            example_settings.server_supported_permission_settings,
        );
        helpers.override(realm, "realm_can_access_all_users_group", members.id);

        people.add_active_user(ali);
        people.add_active_user(alice);
        people.add_active_user(hamlet);
        people.add_active_user(othello);
        people.add_active_user(cordelia);
        people.add_active_user(lear);
        people.add_active_user(twin1);
        people.add_active_user(twin2);
        people.add_active_user(gael);
        people.add_active_user(hal);
        people.add_active_user(harry);
        people.add_active_user(deactivated_user);
        people.add_cross_realm_user(welcome_bot);
        people.add_cross_realm_user(notification_bot);
        people.deactivate(deactivated_user);
        people.initialize_current_user(hamlet.user_id);

        user_groups.add(hamletcharacters);
        user_groups.add(backend);
        user_groups.add(call_center);
        user_groups.add(support);
        user_groups.add(admins);
        user_groups.add(members);

        muted_users.set_muted_users([]);

        f(helpers);
    });
}

test("topics_seen_for", ({override, override_rewire}) => {
    override_rewire(stream_topic_history, "get_recent_topic_names", (stream_id) => {
        assert.equal(stream_id, denmark_stream.stream_id);
        return ["With Twisted Metal", "acceptance", "civil fears"];
    });

    override(stream_topic_history_util, "get_server_history", (stream_id) => {
        assert.equal(stream_id, denmark_stream.stream_id);
    });

    assert.deepEqual(ct.topics_seen_for(denmark_stream.stream_id), [
        "With Twisted Metal",
        "acceptance",
        "civil fears",
    ]);

    // Test when the stream doesn't exist (there are no topics)
    assert.deepEqual(ct.topics_seen_for(""), []);
});

test("content_typeahead_selected", ({override}) => {
    const input_element = {
        $element: {},
        type: "textarea",
    };
    let caret_called1 = false;
    let caret_called2 = false;
    let query;
    input_element.$element.caret = function (...args) {
        if (args.length === 0) {
            // .caret() used in split_at_cursor
            caret_called1 = true;
            return query.length;
        }
        caret_called2 = true;
        return this;
    };
    let range_called = false;
    input_element.$element.range = function (...args) {
        const [arg1, arg2] = args;
        // .range() used in setTimeout
        assert.ok(arg2 > arg1);
        range_called = true;
        return this;
    };
    autosize_called = false;
    set_timeout_called = false;

    // emoji
    ct.get_or_set_completing_for_tests("emoji");
    query = ":octo";
    ct.get_or_set_token_for_testing("octo");
    const item = {
        emoji_name: "octopus",
        type: "emoji",
    };

    let actual_value = ct.content_typeahead_selected(item, query, input_element);
    let expected_value = ":octopus: ";
    assert.equal(actual_value, expected_value);

    query = " :octo";
    ct.get_or_set_token_for_testing("octo");
    actual_value = ct.content_typeahead_selected(item, query, input_element);
    expected_value = " :octopus: ";
    assert.equal(actual_value, expected_value);

    query = "{:octo";
    ct.get_or_set_token_for_testing("octo");
    actual_value = ct.content_typeahead_selected(item, query, input_element);
    expected_value = "{ :octopus: ";
    assert.equal(actual_value, expected_value);

    // mention
    ct.get_or_set_completing_for_tests("mention");

    override(compose_validate, "warn_if_mentioning_unsubscribed_user", noop);
    override(
        compose_validate,
        "convert_mentions_to_silent_in_direct_messages",
        (mention_text) => mention_text,
    );

    query = "@**Mark Tw";
    ct.get_or_set_token_for_testing("Mark Tw");
    actual_value = ct.content_typeahead_selected(twin1_item, query, input_element);
    expected_value = "@**Mark Twin|105** ";
    assert.equal(actual_value, expected_value);

    let warned_for_mention = false;
    override(compose_validate, "warn_if_mentioning_unsubscribed_user", (mentioned) => {
        assert.equal(mentioned, othello_item);
        warned_for_mention = true;
    });

    query = "@oth";
    ct.get_or_set_token_for_testing("oth");
    actual_value = ct.content_typeahead_selected(othello_item, query, input_element);
    expected_value = "@**Othello, the Moor of Venice** ";
    assert.equal(actual_value, expected_value);
    assert.ok(warned_for_mention);

    query = "Hello @oth";
    ct.get_or_set_token_for_testing("oth");
    actual_value = ct.content_typeahead_selected(othello_item, query, input_element);
    expected_value = "Hello @**Othello, the Moor of Venice** ";
    assert.equal(actual_value, expected_value);

    query = "@**oth";
    ct.get_or_set_token_for_testing("oth");
    actual_value = ct.content_typeahead_selected(othello_item, query, input_element);
    expected_value = "@**Othello, the Moor of Venice** ";
    assert.equal(actual_value, expected_value);

    query = "@*oth";
    ct.get_or_set_token_for_testing("oth");
    actual_value = ct.content_typeahead_selected(othello_item, query, input_element);
    expected_value = "@**Othello, the Moor of Venice** ";
    assert.equal(actual_value, expected_value);

    query = "@back";
    ct.get_or_set_token_for_testing("back");
    with_overrides(({disallow}) => {
        disallow(compose_validate, "warn_if_mentioning_unsubscribed_user");
        actual_value = ct.content_typeahead_selected(backend, query, input_element);
    });
    expected_value = "@*Backend* ";
    assert.equal(actual_value, expected_value);

    query = "@*back";
    ct.get_or_set_token_for_testing("back");
    actual_value = ct.content_typeahead_selected(backend, query, input_element);
    expected_value = "@*Backend* ";
    assert.equal(actual_value, expected_value);

    // silent mention
    ct.get_or_set_completing_for_tests("silent_mention");
    const silent_hamlet = {
        ...hamlet_item,
        is_silent: true,
    };
    query = "@_kin";
    ct.get_or_set_token_for_testing("kin");
    with_overrides(({disallow}) => {
        disallow(compose_validate, "warn_if_mentioning_unsubscribed_user");
        actual_value = ct.content_typeahead_selected(silent_hamlet, query, input_element);
    });

    expected_value = "@_**King Hamlet** ";
    assert.equal(actual_value, expected_value);

    query = "Hello @_kin";
    ct.get_or_set_token_for_testing("kin");
    actual_value = ct.content_typeahead_selected(silent_hamlet, query, input_element);
    expected_value = "Hello @_**King Hamlet** ";
    assert.equal(actual_value, expected_value);

    query = "@_*kin";
    ct.get_or_set_token_for_testing("kin");
    actual_value = ct.content_typeahead_selected(silent_hamlet, query, input_element);
    expected_value = "@_**King Hamlet** ";
    assert.equal(actual_value, expected_value);

    query = "@_**kin";
    ct.get_or_set_token_for_testing("kin");
    actual_value = ct.content_typeahead_selected(silent_hamlet, query, input_element);
    expected_value = "@_**King Hamlet** ";
    assert.equal(actual_value, expected_value);

    query = "@_back";
    ct.get_or_set_token_for_testing("back");
    const silent_backend = {
        ...backend,
        is_silent: true,
    };
    with_overrides(({disallow}) => {
        disallow(compose_validate, "warn_if_mentioning_unsubscribed_user");
        actual_value = ct.content_typeahead_selected(silent_backend, query, input_element);
    });
    expected_value = "@_*Backend* ";
    assert.equal(actual_value, expected_value);

    query = "@_*back";
    ct.get_or_set_token_for_testing("back");
    actual_value = ct.content_typeahead_selected(silent_backend, query, input_element);
    expected_value = "@_*Backend* ";
    assert.equal(actual_value, expected_value);

    query = "/m";
    ct.get_or_set_completing_for_tests("slash");
    actual_value = ct.content_typeahead_selected(me_command_item, query, input_element);
    expected_value = "/me translated: is …";
    assert.equal(actual_value, expected_value);

    query = "/da";
    ct.get_or_set_completing_for_tests("slash");
    actual_value = ct.content_typeahead_selected(dark_command_item, query, input_element);
    expected_value = "/dark ";
    assert.equal(actual_value, expected_value);

    query = "/ni";
    ct.get_or_set_completing_for_tests("slash");
    actual_value = ct.content_typeahead_selected(dark_command_item, query, input_element);
    expected_value = "/dark ";
    assert.equal(actual_value, expected_value);

    query = "/li";
    ct.get_or_set_completing_for_tests("slash");
    actual_value = ct.content_typeahead_selected(light_command_item, query, input_element);
    expected_value = "/light ";
    assert.equal(actual_value, expected_value);

    query = "/da";
    ct.get_or_set_completing_for_tests("slash");
    actual_value = ct.content_typeahead_selected(light_command_item, query, input_element);
    expected_value = "/light ";
    assert.equal(actual_value, expected_value);

    // stream
    ct.get_or_set_completing_for_tests("stream");
    let warned_for_stream_link = false;
    override(compose_validate, "warn_if_private_stream_is_linked", (linked_stream) => {
        assert.ok(linked_stream === sweden_stream || linked_stream === broken_link_stream);
        warned_for_stream_link = true;
    });

    query = "#swed";
    ct.get_or_set_token_for_testing("swed");
    actual_value = ct.content_typeahead_selected(sweden_stream, query, input_element);
    expected_value = "#**Sweden>";
    assert.equal(actual_value, expected_value);

    query = "Hello #swed";
    ct.get_or_set_token_for_testing("swed");
    actual_value = ct.content_typeahead_selected(sweden_stream, query, input_element);
    expected_value = "Hello #**Sweden>";
    assert.equal(actual_value, expected_value);

    query = "#**swed";
    ct.get_or_set_token_for_testing("swed");
    actual_value = ct.content_typeahead_selected(sweden_stream, query, input_element);
    expected_value = "#**Sweden>";
    assert.equal(actual_value, expected_value);

    query = "#**A* al";
    ct.get_or_set_token_for_testing("A* al");
    actual_value = ct.content_typeahead_selected(broken_link_stream, query, input_element);
    expected_value = "[#A&#42; Algorithm](#narrow/channel/6-A*-Algorithm)>";
    assert.equal(actual_value, expected_value);

    query = "#>";
    ct.get_or_set_token_for_testing("#");
    actual_value = ct.content_typeahead_selected(broken_link_stream, query, input_element);
    expected_value = "[#A&#42; Algorithm](#narrow/channel/6-A*-Algorithm)>";
    assert.equal(actual_value, expected_value);

    // topic_list
    ct.get_or_set_completing_for_tests("topic_list");

    query = "Hello #**Sweden>test";
    ct.get_or_set_token_for_testing("test");
    actual_value = ct.content_typeahead_selected(
        {
            topic: "testing",
            topic_display_name: "testing",
            type: "topic_list",
            used_syntax_prefix: "#**",
            stream_data: {
                name: "Sweden",
            },
        },
        query,
        input_element,
    );
    expected_value = "Hello #**Sweden>testing** ";
    assert.equal(actual_value, expected_value);

    query = "Hello #**Sweden>";
    ct.get_or_set_token_for_testing("");
    actual_value = ct.content_typeahead_selected(
        {
            topic: "testing",
            topic_display_name: "testing",
            type: "topic_list",
            used_syntax_prefix: "#**",
            stream_data: {
                name: "Sweden",
            },
        },
        query,
        input_element,
    );
    expected_value = "Hello #**Sweden>testing** ";
    assert.equal(actual_value, expected_value);

    // shortcut syntax for topic_list
    compose_state.set_stream_id(sweden_stream.stream_id);
    query = "Hello #>";
    ct.get_or_set_token_for_testing("");
    actual_value = ct.content_typeahead_selected(
        {
            topic: "testing",
            type: "topic_list",
            used_syntax_prefix: "#>",
            stream_data: {
                name: "Sweden",
            },
        },
        query,
        input_element,
    );
    expected_value = "Hello #**Sweden>testing** ";
    assert.equal(actual_value, expected_value);

    query = "Hello #**Sweden>";
    ct.get_or_set_token_for_testing("");
    actual_value = ct.content_typeahead_selected(
        {
            topic: "Sweden",
            topic_display_name: "Sweden",
            type: "topic_list",
            used_syntax_prefix: "#**",
            is_channel_link: false,
            stream_data: {
                name: "Sweden",
            },
        },
        query,
        input_element,
    );
    expected_value = "Hello #**Sweden>Sweden** ";
    assert.equal(actual_value, expected_value);

    query = "Hello #**Sweden>general";
    ct.get_or_set_token_for_testing("");
    actual_value = ct.content_typeahead_selected(
        {
            topic: "",
            topic_display_name: get_final_topic_display_name(""),
            type: "topic_list",
            used_syntax_prefix: "#**",
            is_channel_link: false,
            stream_data: {
                name: "Sweden",
            },
        },
        query,
        input_element,
    );
    expected_value = `Hello #**Sweden>** `;
    assert.equal(actual_value, expected_value);

    ct.get_or_set_token_for_testing("");
    actual_value = ct.content_typeahead_selected(
        {
            topic: "Sweden",
            topic_display_name: "Sweden",
            type: "topic_list",
            used_syntax_prefix: "#**",
            is_channel_link: true,
            stream_data: {
                name: "Sweden",
            },
        },
        query,
        input_element,
    );
    expected_value = "Hello #**Sweden** ";
    assert.equal(actual_value, expected_value);

    compose_state.set_stream_id(broken_link_stream.stream_id);
    query = "Hello #>";
    ct.get_or_set_token_for_testing("");
    actual_value = ct.content_typeahead_selected(
        {
            topic: "",
            type: "topic_list",
            used_syntax_prefix: "#>",
            is_channel_link: true,
            stream_data: {
                name: "A* Algorithm",
            },
        },
        query,
        input_element,
    );
    expected_value = "Hello [#A&#42; Algorithm](#narrow/channel/6-A*-Algorithm) ";
    assert.equal(actual_value, expected_value);

    query = "Hello #**A* Algorithm>";
    ct.get_or_set_token_for_testing("");
    actual_value = ct.content_typeahead_selected(
        {
            topic: "fast",
            topic_display_name: "fast",
            type: "topic_list",
            used_syntax_prefix: "#**",
            is_channel_link: false,
            stream_data: {
                name: "A* Algorithm",
            },
        },
        query,
        input_element,
    );
    expected_value = "Hello [#A&#42; Algorithm > fast](#narrow/channel/6-A*-Algorithm/topic/fast) ";
    assert.equal(actual_value, expected_value);

    // syntax
    ct.get_or_set_completing_for_tests("syntax");

    query = "~~~p";
    ct.get_or_set_token_for_testing("p");
    actual_value = ct.content_typeahead_selected(language_item("python"), query, input_element);
    expected_value = "~~~python\n\n~~~";
    assert.equal(actual_value, expected_value);

    query = "Hello ~~~p";
    ct.get_or_set_token_for_testing("p");
    actual_value = ct.content_typeahead_selected(language_item("python"), query, input_element);
    expected_value = "Hello ~~~python\n\n~~~";
    assert.equal(actual_value, expected_value);

    query = "```p";
    ct.get_or_set_token_for_testing("p");
    actual_value = ct.content_typeahead_selected(language_item("python"), query, input_element);
    expected_value = "```python\n\n```";
    assert.equal(actual_value, expected_value);

    query = "```spo";
    ct.get_or_set_token_for_testing("spo");
    actual_value = ct.content_typeahead_selected(language_item("spoiler"), query, input_element);
    expected_value = "```spoiler translated: Header\n\n```";
    assert.equal(actual_value, expected_value);

    // Test special case to not close code blocks if there is text afterward
    query = "```p\nsome existing code";
    ct.get_or_set_token_for_testing("p");
    input_element.$element.caret = () => 4; // Put cursor right after ```p
    actual_value = ct.content_typeahead_selected(language_item("python"), query, input_element);
    expected_value = "```python\nsome existing code";
    assert.equal(actual_value, expected_value);

    ct.get_or_set_completing_for_tests("something-else");

    query = "foo";
    actual_value = ct.content_typeahead_selected({}, query, input_element);
    expected_value = query;
    assert.equal(actual_value, expected_value);

    assert.ok(caret_called1);
    assert.ok(caret_called2);
    assert.ok(range_called);
    assert.ok(autosize_called);
    assert.ok(set_timeout_called);
    assert.ok(warned_for_stream_link);
});

function sorted_names_from(subs) {
    return subs.map((sub) => sub.name).sort();
}

const sweden_topics_to_show = [
    "<&>",
    "even more ice",
    "furniture",
    "ice",
    "kronor",
    "more ice",
    "",
];

test("initialize", ({override, override_rewire, mock_template}) => {
    mock_banners();

    let pill_items = [];
    let cleared = false;
    let appended_names = [];
    override(input_pill, "create", () => ({
        clear_text() {
            cleared = true;
        },
        items: () => pill_items,
        onPillCreate() {},
        onPillRemove() {},
        appendValidatedData(item) {
            appended_names.push(user_pill.get_display_value_from_item(item));
        },
    }));
    compose_pm_pill.initialize({
        on_pill_create_or_remove: compose_recipient.update_compose_area_placeholder_text,
    });

    let expected_value;
    override(realm, "custom_profile_field_types", {
        PRONOUNS: {id: 8, name: "Pronouns"},
    });

    mock_template("typeahead_list_item.hbs", true, (data, html) => {
        assert.equal(typeof data.primary, "string");
        if (data.has_secondary) {
            assert.equal(typeof data.secondary, "string");
        } else {
            assert.equal(data.has_secondary, false);
        }
        assert.equal(typeof data.has_image, "boolean");
        return html;
    });
    override(stream_topic_history_util, "get_server_history", noop);

    let topic_typeahead_called = false;
    let pm_recipient_typeahead_called = false;
    let compose_textarea_typeahead_called = false;
    override(bootstrap_typeahead, "Typeahead", (input_element, options) => {
        switch (input_element.$element) {
            case $("input#stream_message_recipient_topic"): {
                override_rewire(stream_topic_history, "get_recent_topic_names", (stream_id) => {
                    assert.equal(stream_id, sweden_stream.stream_id);
                    return sweden_topics_to_show;
                });

                compose_state.set_stream_id(sweden_stream.stream_id);
                let actual_value = options.source();
                // Topics should be sorted alphabetically, not by addition order.
                let expected_value = sweden_topics_to_show;
                assert.deepEqual(actual_value, expected_value);

                // options.item_html()
                options.query = "Kro";
                actual_value = options.item_html("kronor");
                expected_value =
                    '<div class="typeahead-text-container">\n' +
                    '    <strong class="typeahead-strong-section">kronor</strong></div>\n';
                assert.equal(actual_value, expected_value);

                // Highlighted content should be escaped.
                options.query = "<";
                actual_value = options.item_html("<&>");
                expected_value =
                    '<div class="typeahead-text-container">\n' +
                    '    <strong class="typeahead-strong-section">&lt;&amp;&gt;</strong></div>\n';
                assert.equal(actual_value, expected_value);

                options.query = "even m";
                actual_value = options.item_html("even more ice");
                expected_value =
                    '<div class="typeahead-text-container">\n' +
                    '    <strong class="typeahead-strong-section">even more ice</strong></div>\n';
                assert.equal(actual_value, expected_value);

                // options.sorter()
                //
                // Notice that alphabetical sorting isn't managed by this sorter,
                // it is a result of the topics already being sorted after adding
                // them with add_topic().
                let query = "furniture";
                actual_value = options.sorter(["furniture"], query);
                expected_value = ["furniture"];
                assert.deepEqual(actual_value, expected_value);

                // A literal match at the beginning of an element puts it at the top.
                query = "ice";
                actual_value = options.sorter(["even more ice", "ice", "more ice"], query);
                expected_value = ["ice", "even more ice", "more ice"];
                assert.deepEqual(actual_value, expected_value);

                // The sorter should return the query as the first element if there
                // isn't a topic with such name.
                // This only happens if typeahead is providing other suggestions.
                query = "e"; // Letter present in "furniture" and "ice"
                actual_value = options.sorter(["furniture", "ice"], query);
                expected_value = ["e", "furniture", "ice"];
                assert.deepEqual(actual_value, expected_value);

                // Suggest the query if this query doesn't match any existing topic.
                query = "non-existing-topic";
                actual_value = options.sorter([], query);
                expected_value = [];
                assert.deepEqual(actual_value, expected_value);

                topic_typeahead_called = true;

                // Unset the stream.
                compose_state.set_stream_id("");

                break;
            }
            case $("#private_message_recipient"): {
                pill_items = [];

                // This should match the users added at the beginning of this test file.
                let actual_value = options.source("");
                let expected_value = [
                    ali_item,
                    alice_item,
                    cordelia_item,
                    hal_item,
                    gael_item,
                    harry_item,
                    hamlet_item,
                    lear_item,
                    twin1_item,
                    twin2_item,
                    othello_item,
                    hamletcharacters,
                    backend,
                    call_center,
                    admins,
                    members,
                    welcome_bot_item,
                ];
                assert.deepEqual(actual_value, expected_value);

                function matcher(query, person) {
                    query = typeahead.clean_query_lowercase(query);
                    return typeahead_helper.query_matches_person(query, person);
                }

                let query;
                query = "el"; // Matches both "othELlo" and "cordELia"
                assert.equal(matcher(query, othello_item), true);
                assert.equal(matcher(query, cordelia_item), true);

                query = "bender"; // Doesn't exist
                assert.equal(matcher(query, othello_item), false);
                assert.equal(matcher(query, cordelia_item), false);

                query = "gael";
                assert.equal(matcher(query, gael_item), true);

                query = "Gaël";
                assert.equal(matcher(query, gael_item), true);

                query = "gaël";
                assert.equal(matcher(query, gael_item), true);

                // Don't make suggestions if the last name only has whitespaces
                // (we're between typing names).
                query = "othello@zulip.com,     ";
                assert.equal(matcher(query, othello_item), false);
                assert.equal(matcher(query, cordelia_item), false);

                // query = 'othello@zulip.com,, , cord';
                query = "cord";
                assert.equal(matcher(query, othello_item), false);
                assert.equal(matcher(query, cordelia_item), true);

                // If the user is already in the list, typeahead doesn't include it
                // again.
                query = "cordelia@zulip.com, cord";
                assert.equal(matcher(query, othello_item), false);
                assert.equal(matcher(query, cordelia_item), false);

                // Matching by email
                query = "oth";
                deactivated_user.delivery_email = null;
                assert.equal(matcher(query, deactivated_user_item), false);

                deactivated_user.delivery_email = "other@zulip.com";
                assert.equal(matcher(query, deactivated_user_item), true);

                function sorter(query, people) {
                    return typeahead_helper.sort_recipients({
                        users: people,
                        query,
                        current_stream_id: compose_state.stream_id(),
                        current_topic: compose_state.topic(),
                    });
                }

                // The sorter's output has the items that match the query from the
                // beginning first, and then the rest of them in REVERSE order of
                // the input.
                query = "othello";
                actual_value = sorter(query, [othello_item]);
                expected_value = [othello_item];
                assert.deepEqual(actual_value, expected_value);

                query = "Ali";
                actual_value = sorter(query, [alice_item, ali_item]);
                expected_value = [ali_item, alice_item];
                assert.deepEqual(actual_value, expected_value);

                // A literal match at the beginning of an element puts it at the top.
                query = "co"; // Matches everything ("x@zulip.COm")
                actual_value = sorter(query, [othello_item, deactivated_user_item, cordelia_item]);
                expected_value = [cordelia_item, deactivated_user_item, othello_item];
                actual_value.sort((a, b) => a.user.user_id - b.user.user_id);
                expected_value.sort((a, b) => a.user.user_id - b.user.user_id);
                assert.deepEqual(actual_value, expected_value);

                query = "non-existing-user";
                actual_value = sorter(query, []);
                expected_value = [];
                assert.deepEqual(actual_value, expected_value);

                // Adds a `no break-space` at the end. This should fail
                // if there wasn't any logic replacing `no break-space`
                // with normal space.
                query = "cordelia, lear's\u00A0";
                assert.equal(matcher(query, cordelia_item), true);
                assert.equal(matcher(query, othello_item), false);

                const event = {
                    target: "#doesnotmatter",
                };

                // options.updater()
                options.query = "othello";
                appended_names = [];
                options.updater(othello_item, event);
                assert.deepEqual(appended_names, ["Othello, the Moor of Venice"]);

                options.query = "othello@zulip.com, cor";
                appended_names = [];
                actual_value = options.updater(cordelia_item, event);
                assert.deepEqual(appended_names, ["Cordelia, Lear's daughter"]);

                const click_event = {type: "click", target: "#doesnotmatter"};
                options.query = "othello";
                // Focus lost (caused by the click event in the typeahead list)
                $("#private_message_recipient").trigger("blur");
                appended_names = [];
                actual_value = options.updater(othello_item, click_event);
                assert.deepEqual(appended_names, ["Othello, the Moor of Venice"]);

                cleared = false;
                options.query = "hamletchar";
                appended_names = [];
                options.updater(hamletcharacters, event);
                assert.deepEqual(appended_names, ["King Lear"]);
                assert.ok(cleared);

                pill_items = [{user_id: lear.user_id, type: "user"}];
                appended_names = [];
                cleared = false;
                options.updater(hamletcharacters, event);
                assert.deepEqual(appended_names, []);
                assert.ok(cleared);

                pm_recipient_typeahead_called = true;

                break;
            }
            case $("textarea#compose-textarea"): {
                // options.source()
                //
                // For now we only test that get_sorted_filtered_items has been
                // properly set as the .source(). All its features are tested later on
                // in test_begins_typeahead().
                const input_element = {
                    $element: {},
                    type: "input",
                };
                let caret_called = false;
                input_element.$element.caret = () => {
                    caret_called = true;
                    return 7;
                };
                let actual_value = options.source("test #s", input_element);
                assert.deepEqual(sorted_names_from(actual_value), ["Sweden", "The Netherlands"]);
                assert.ok(caret_called);

                othello.delivery_email = "othello@zulip.com";
                // options.item_html()
                //
                // Again, here we only verify that the item_html has been set to
                // content_item_html.
                ct.get_or_set_completing_for_tests("mention");
                ct.get_or_set_token_for_testing("othello");
                actual_value = options.item_html(othello_item);
                expected_value =
                    `    <span class="zulip-icon zulip-icon-user-circle-offline user-circle-offline user-circle"></span>\n` +
                    `    <img class="typeahead-image" src="/avatar/${othello.user_id}" />\n` +
                    '<div class="typeahead-text-container">\n' +
                    '    <strong class="typeahead-strong-section">Othello, the Moor of Venice</strong>    <span class="autocomplete_secondary">othello@zulip.com</span>' +
                    "</div>\n";
                assert.equal(actual_value, expected_value);
                // Reset the email such that this does not affect further tests.
                othello.delivery_email = null;

                ct.get_or_set_completing_for_tests("mention");
                ct.get_or_set_token_for_testing("hamletcharacters");
                actual_value = options.item_html(hamletcharacters);
                expected_value =
                    '    <i class="typeahead-image zulip-icon zulip-icon-user-group no-presence-circle" aria-hidden="true"></i>\n' +
                    '<div class="typeahead-text-container">\n' +
                    '    <strong class="typeahead-strong-section">hamletcharacters</strong>    <span class="autocomplete_secondary">Characters of Hamlet</span>' +
                    "</div>\n";
                assert.equal(actual_value, expected_value);

                // matching
                let matcher = typeahead.get_emoji_matcher("ta");
                assert.equal(matcher(make_emoji(emoji_tada)), true);
                assert.equal(matcher(make_emoji(emoji_moneybag)), false);

                matcher = ct.get_stream_matcher("swed");
                assert.equal(matcher(sweden_stream), true);
                assert.equal(matcher(denmark_stream), false);

                matcher = ct.get_language_matcher("py");
                assert.equal(matcher("python"), true);
                assert.equal(matcher("javascript"), false);

                // options.sorter()
                actual_value = typeahead.sort_emojis(
                    [make_emoji(emoji_stadium), make_emoji(emoji_tada)],
                    "ta",
                );
                expected_value = [make_emoji(emoji_tada), make_emoji(emoji_stadium)];
                assert.deepEqual(actual_value, expected_value);

                actual_value = typeahead.sort_emojis(
                    [make_emoji(emoji_thermometer), make_emoji(emoji_thumbs_up)],
                    "th",
                );
                expected_value = [make_emoji(emoji_thumbs_up), make_emoji(emoji_thermometer)];
                assert.deepEqual(actual_value, expected_value);

                actual_value = typeahead.sort_emojis(
                    [make_emoji(emoji_headphones), make_emoji(emoji_heart)],
                    "he",
                );
                expected_value = [make_emoji(emoji_heart), make_emoji(emoji_headphones)];
                assert.deepEqual(actual_value, expected_value);

                actual_value = typeahead_helper.sort_slash_commands(
                    [my_command_item, me_command_item],
                    "m",
                );
                expected_value = [me_command_item, my_command_item];
                assert.deepEqual(actual_value, expected_value);

                actual_value = typeahead_helper.sort_slash_commands(
                    [dark_command_item, light_command_item],
                    "da",
                );
                expected_value = [dark_command_item, light_command_item];
                assert.deepEqual(actual_value, expected_value);

                actual_value = typeahead_helper.sort_streams([sweden_stream, denmark_stream], "de");
                expected_value = [denmark_stream, sweden_stream];
                assert.deepEqual(actual_value, expected_value);

                // Matches in the descriptions affect the order as well.
                // Testing "co" for "cold", in both streams' description. It's at the
                // beginning of Sweden's description, so that one should go first.
                actual_value = typeahead_helper.sort_streams([denmark_stream, sweden_stream], "co");
                expected_value = [sweden_stream, denmark_stream];
                assert.deepEqual(actual_value, expected_value);

                actual_value = typeahead_helper.sort_languages(
                    [language_item("abap"), language_item("applescript")],
                    "ap",
                );
                expected_value = [language_item("applescript"), language_item("abap")];
                assert.deepEqual(actual_value, expected_value);

                const serbia_stream = {
                    name: "Serbia",
                    description: "Snow and cold",
                    stream_id: 3,
                    subscribed: false,
                    type: "stream",
                };
                // Subscribed stream is active
                override(
                    user_settings,
                    "demote_inactive_streams",
                    settings_config.demote_inactive_streams_values.never.code,
                );

                stream_list_sort.set_filter_out_inactives();
                actual_value = typeahead_helper.sort_streams([sweden_stream, serbia_stream], "s");
                expected_value = [sweden_stream, serbia_stream];
                assert.deepEqual(actual_value, expected_value);
                // Subscribed stream is inactive
                override(
                    user_settings,
                    "demote_inactive_streams",
                    settings_config.demote_inactive_streams_values.always.code,
                );

                stream_list_sort.set_filter_out_inactives();
                actual_value = typeahead_helper.sort_streams([sweden_stream, serbia_stream], "s");
                expected_value = [sweden_stream, serbia_stream];
                assert.deepEqual(actual_value, expected_value);

                actual_value = typeahead_helper.sort_streams(
                    [denmark_stream, serbia_stream],
                    "ser",
                );
                expected_value = [serbia_stream, denmark_stream];
                assert.deepEqual(actual_value, expected_value);

                compose_textarea_typeahead_called = true;

                break;
            }
            // No default
        }
    });

    override(user_settings, "enter_sends", false);
    let compose_finish_called = false;
    function finish() {
        compose_finish_called = true;
    }

    ct.initialize({
        on_enter_send: finish,
    });

    // the UI of selecting a stream is tested in puppeteer tests.
    compose_state.set_stream_id(sweden_stream.stream_id);

    const $stub_target = $.create("<stub-target>");
    let event = {
        type: "keydown",
        key: "Tab",
        shiftKey: false,
        target: "<stub-target>",
        preventDefault: noop,
        stopPropagation: noop,
    };
    $stub_target.attr("id", "stream_message_recipient_topic");
    $("form#send_message_form").trigger(event);
    $stub_target.attr("id", "compose-textarea");
    $("form#send_message_form").trigger(event);
    $stub_target.attr("id", "some_non_existing_id");
    $("form#send_message_form").trigger(event);

    $("textarea#compose-textarea")[0] = {
        selectionStart: 0,
        selectionEnd: 0,
    };
    override(compose_ui, "insert_and_scroll_into_view", (content, _textarea) => {
        assert.equal(content, "\n");
    });
    $("textarea#compose-textarea").caret = () => $("textarea#compose-textarea")[0].selectionStart;

    event.key = "Enter";
    $stub_target.attr("id", "stream_message_recipient_topic");
    $("form#send_message_form").trigger(event);
    $stub_target.attr("id", "compose-textarea");
    override(user_settings, "enter_sends", false);
    event.metaKey = true;

    $("form#send_message_form").trigger(event);
    assert.ok(compose_finish_called);
    event.metaKey = false;
    event.ctrlKey = true;
    $("form#send_message_form").trigger(event);
    override(user_settings, "enter_sends", true);
    event.ctrlKey = false;
    event.altKey = true;
    $("form#send_message_form").trigger(event);

    // Cover cases where there's at least one character there.

    // Test automatic bulleting.
    $("textarea#compose-textarea").val("- List item 1\n- List item 2");
    $("textarea#compose-textarea")[0].selectionStart = 27;
    $("textarea#compose-textarea")[0].selectionEnd = 27;
    override(compose_ui, "insert_and_scroll_into_view", (content, _textarea) => {
        assert.equal(content, "\n- ");
    });
    $("form#send_message_form").trigger(event);

    // Test removal of bullet.
    $("textarea#compose-textarea").val("- List item 1\n- List item 2\n- ");
    $("textarea#compose-textarea")[0].selectionStart = 30;
    $("textarea#compose-textarea")[0].selectionEnd = 30;
    $("textarea#compose-textarea")[0].setSelectionRange = (start, end) => {
        assert.equal(start, 28);
        assert.equal(end, 30);
    };
    override(compose_ui, "insert_and_scroll_into_view", (content, _textarea) => {
        assert.equal(content, "");
    });
    $("form#send_message_form").trigger(event);

    // Test automatic numbering.
    $("textarea#compose-textarea").val("1. List item 1\n2. List item 2");
    $("textarea#compose-textarea")[0].selectionStart = 29;
    $("textarea#compose-textarea")[0].selectionEnd = 29;
    override(compose_ui, "insert_and_scroll_into_view", (content, _textarea) => {
        assert.equal(content, "\n3. ");
    });
    $("form#send_message_form").trigger(event);

    // Test removal of numbering.
    $("textarea#compose-textarea").val("1. List item 1\n2. List item 2\n3. ");
    $("textarea#compose-textarea")[0].selectionStart = 33;
    $("textarea#compose-textarea")[0].selectionEnd = 33;
    $("textarea#compose-textarea")[0].setSelectionRange = (start, end) => {
        assert.equal(start, 30);
        assert.equal(end, 33);
    };
    override(compose_ui, "insert_and_scroll_into_view", (content, _textarea) => {
        assert.equal(content, "");
    });
    $("form#send_message_form").trigger(event);

    $("textarea#compose-textarea").val("A");
    $("textarea#compose-textarea")[0].selectionStart = 4;
    $("textarea#compose-textarea")[0].selectionEnd = 4;
    override(compose_ui, "insert_and_scroll_into_view", (content, _textarea) => {
        assert.equal(content, "\n");
    });
    event.altKey = false;
    event.metaKey = true;
    $("form#send_message_form").trigger(event);
    $stub_target.attr("id", "private_message_recipient");
    $("form#send_message_form").trigger(event);

    event.key = "a";
    $("form#send_message_form").trigger(event);

    // the UI of selecting a stream is tested in puppeteer tests.
    compose_state.set_stream_id(sweden_stream.stream_id);
    // handle_keyup()
    event = {
        type: "keydown",
        key: "Enter",
        target: "<stub-target>",
        preventDefault: noop,
    };
    $stub_target.attr("id", "stream_message_recipient_topic");
    // We trigger keydown in order to make nextFocus !== false
    $("form#send_message_form").trigger(event);
    $("input#stream_message_recipient_topic").off("mouseup");
    event.type = "keyup";
    $("form#send_message_form").trigger(event);
    event.key = "Tab";
    event.shiftKey = false;
    $("form#send_message_form").trigger(event);
    event.key = "a";
    $("form#send_message_form").trigger(event);

    $("input#stream_message_recipient_topic").off("focus");
    $("#private_message_recipient").off("focus");
    $("form#send_message_form").off("keydown");
    $("form#send_message_form").off("keyup");
    $("#private_message_recipient").off("blur");
    ct.initialize({
        on_enter_send: finish,
    });

    // Now let's make sure that all the stub functions have been called
    // during the initialization.
    assert.ok(topic_typeahead_called);
    assert.ok(pm_recipient_typeahead_called);
    assert.ok(compose_textarea_typeahead_called);
});

test("begins_typeahead", ({override, override_rewire}) => {
    override_rewire(stream_topic_history, "get_recent_topic_names", (stream_id) => {
        assert.equal(stream_id, sweden_stream.stream_id);
        return sweden_topics_to_show;
    });
    override(stream_topic_history_util, "get_server_history", noop);

    const input_element = {
        $element: {
            closest: () => [],
        },
        type: "input",
    };

    function get_values(input, rest) {
        // Stub out split_at_cursor that uses $(':focus')
        override_rewire(ct, "split_at_cursor", () => [input, rest]);
        const values = ct.get_candidates(input, input_element);
        return values;
    }

    function assert_typeahead_equals(input, rest, reference) {
        // Usage:
        // assert_typeahead_equals('#some', reference); => '#some|'
        // assert_typeahead_equals('#some', 'thing', reference) => '#some|thing'
        // In the above examples, '|' serves as the cursor.
        if (reference === undefined) {
            reference = rest;
            rest = "";
        }
        const values = get_values(input, rest);
        assert.deepEqual(values, reference);
    }

    function assert_typeahead_starts_with(input, rest, reference) {
        if (reference === undefined) {
            reference = rest;
            rest = "";
        }
        const values = get_values(input, rest);
        assert.ok(reference.length > 0);
        assert.deepEqual(values.slice(0, reference.length), reference);
    }

    assert_typeahead_equals("test", []);
    assert_typeahead_equals("test one two", []);
    assert_typeahead_equals("*", []);
    assert_typeahead_equals("* ", []);
    assert_typeahead_equals(" *", []);
    assert_typeahead_equals("test *", []);

    // Make sure that the last token is the one we read.
    assert_typeahead_equals("~~~ @zulip", []); // zulip isn't set up as a user group
    assert_typeahead_equals("@zulip :ta", emoji_objects(["tada", "stadium"]));
    function language_objects(languages) {
        return languages.map((language) => language_item(language));
    }
    assert_typeahead_equals(
        "#foo\n~~~py",
        language_objects([
            "py",
            "py+ul4",
            "py2",
            "py2tb",
            "py3tb",
            "pycon",
            "pypy",
            "pyrex",
            "antlr-python",
            "bst-pybtex",
            "ipython",
            "ipython3",
            "ipythonconsole",
            "numpy",
        ]),
    );
    assert_typeahead_equals(":tada: <time:", [
        {
            type: "time_jump",
            message: "translated: Mention a time-zone-aware time",
        },
    ]);

    const mention_all = broadcast_item(ct.broadcast_mentions()[0]);
    const users_and_all_mention = [
        ...sorted_user_list,
        mention_all,
        notification_bot_item,
        welcome_bot_item,
    ];
    const users_and_user_groups = [
        ...sorted_user_list,
        // alphabetical
        hamletcharacters, // "Characters of Hamlet"
        backend,
        call_center, // "folks working in support",
        admins,
        members,
        notification_bot_item,
        welcome_bot_item,
    ];
    const mention_everyone = broadcast_item(ct.broadcast_mentions()[1]);
    function mentions_with_silent_marker(mentions, is_silent) {
        return mentions.map((item) => ({
            ...item,
            is_silent,
        }));
    }
    assert_typeahead_equals("@", mentions_with_silent_marker(users_and_all_mention, false));
    // The user we're testing for is only allowed to do silent mentions of groups
    assert_typeahead_equals("@_", mentions_with_silent_marker(users_and_user_groups, true));
    assert_typeahead_equals(" @", mentions_with_silent_marker(users_and_all_mention, false));
    assert_typeahead_equals(" @_", mentions_with_silent_marker(users_and_user_groups, true));
    assert_typeahead_equals("@*", mentions_with_silent_marker(users_and_all_mention, false));
    assert_typeahead_equals("@_*", mentions_with_silent_marker(users_and_user_groups, true));
    assert_typeahead_equals("@**", mentions_with_silent_marker(users_and_all_mention, false));
    assert_typeahead_equals("@_**", mentions_with_silent_marker(users_and_user_groups, true));
    assert_typeahead_equals(
        "test @**o",
        mentions_with_silent_marker(
            [
                othello_item,
                cordelia_item,
                mention_everyone,
                notification_bot_item,
                welcome_bot_item,
            ],
            false,
        ),
    );
    assert_typeahead_equals(
        "test @_**o",

        mentions_with_silent_marker(
            [othello_item, cordelia_item, admins, members, notification_bot_item, welcome_bot_item],
            true,
        ),
    );
    assert_typeahead_equals(
        "test @*o",
        mentions_with_silent_marker(
            [
                othello_item,
                cordelia_item,
                mention_everyone,
                notification_bot_item,
                welcome_bot_item,
            ],
            false,
        ),
    );
    assert_typeahead_equals(
        "test @_*k",
        mentions_with_silent_marker(
            [hamlet_item, lear_item, twin1_item, twin2_item, backend],
            true,
        ),
    );
    assert_typeahead_equals(
        "test @*h",
        mentions_with_silent_marker(
            [harry_item, hal_item, hamlet_item, cordelia_item, othello_item],
            false,
        ),
    );
    assert_typeahead_equals(
        "test @_*h",
        mentions_with_silent_marker(
            [harry_item, hal_item, hamlet_item, hamletcharacters, cordelia_item, othello_item],
            true,
        ),
    );
    assert_typeahead_equals("test @", mentions_with_silent_marker(users_and_all_mention, false));
    assert_typeahead_equals("test @_", mentions_with_silent_marker(users_and_user_groups, true));
    assert_typeahead_equals("test no@o", []);
    assert_typeahead_equals("test no@_k", []);
    assert_typeahead_equals("@ ", []);
    assert_typeahead_equals("@_ ", []);
    assert_typeahead_equals("@* ", []);
    assert_typeahead_equals("@_* ", []);
    assert_typeahead_equals("@** ", []);
    assert_typeahead_equals("@_** ", []);
    assert_typeahead_equals(
        "test\n@i",
        mentions_with_silent_marker(
            [
                ali_item,
                alice_item,
                cordelia_item,
                gael_item,
                hamlet_item,
                lear_item,
                twin1_item,
                twin2_item,
                othello_item,
                notification_bot_item,
            ],
            false,
        ),
    );
    assert_typeahead_equals(
        "test\n@_i",
        mentions_with_silent_marker(
            [
                ali_item,
                alice_item,
                cordelia_item,
                gael_item,
                hamlet_item,
                lear_item,
                twin1_item,
                twin2_item,
                othello_item,
                admins,
                notification_bot_item,
            ],
            true,
        ),
    );
    assert_typeahead_equals(
        "test\n @l",
        mentions_with_silent_marker(
            [
                cordelia_item,
                lear_item,
                ali_item,
                alice_item,
                hal_item,
                gael_item,
                hamlet_item,
                othello_item,
                mention_all,
                welcome_bot_item,
            ],
            false,
        ),
    );
    assert_typeahead_equals(
        "test\n @_l",
        mentions_with_silent_marker(
            [
                cordelia_item,
                lear_item,
                ali_item,
                alice_item,
                hal_item,
                gael_item,
                hamlet_item,
                othello_item,
                hamletcharacters,
                call_center,
                members,
                welcome_bot_item,
            ],
            true,
        ),
    );
    assert_typeahead_equals("@zuli", []);
    assert_typeahead_equals("@_zuli", []);
    assert_typeahead_equals("@ zuli", []);
    assert_typeahead_equals("@_ zuli", []);
    assert_typeahead_equals(" @zuli", []);
    assert_typeahead_equals(" @_zuli", []);
    assert_typeahead_equals(
        "test @o",
        mentions_with_silent_marker(
            [
                othello_item,
                cordelia_item,
                mention_everyone,
                notification_bot_item,
                welcome_bot_item,
            ],
            false,
        ),
    );
    assert_typeahead_equals(
        "test @_o",
        mentions_with_silent_marker(
            [othello_item, cordelia_item, admins, members, notification_bot_item, welcome_bot_item],
            true,
        ),
    );
    assert_typeahead_equals("test @z", []);
    assert_typeahead_equals("test @_z", []);

    assert_typeahead_equals(":", []);
    assert_typeahead_equals(": ", []);
    assert_typeahead_equals(" :", []);
    assert_typeahead_equals(":)", []);
    assert_typeahead_equals(":4", []);
    assert_typeahead_equals(": la", []);
    assert_typeahead_equals("test :-P", []);
    assert_typeahead_equals("hi emoji :", []);
    assert_typeahead_equals("hi emoj:i", []);
    assert_typeahead_equals("hi emoji :D", []);
    assert_typeahead_equals("hi emoji : t", []);
    assert_typeahead_equals(
        "hi emoji :t",
        emoji_objects([
            "thumbs_up",
            "tada",
            "thermometer",
            "heart",
            "stadium",
            "japanese_post_office",
        ]),
    );
    assert_typeahead_equals("hi emoji :ta", emoji_objects(["tada", "stadium"]));
    assert_typeahead_equals("hi emoji :da", emoji_objects(["panda_face", "tada"]));
    // We store the emoji panda_face with underscore, but that's not part of the emoji's name
    assert_typeahead_equals("hi emoji :da_", emoji_objects([]));
    assert_typeahead_equals("hi emoji :da ", emoji_objects([]));
    assert_typeahead_equals("hi emoji\n:da", emoji_objects(["panda_face", "tada"]));
    assert_typeahead_equals("hi emoji\n :ra", []);
    assert_typeahead_equals(":+", []);
    assert_typeahead_equals(":la", []);
    assert_typeahead_equals(" :lee", []);
    assert_typeahead_equals("hi :see no", emoji_objects(["see_no_evil"]));
    assert_typeahead_equals("hi :japanese post of", emoji_objects(["japanese_post_office"]));

    assert_typeahead_equals("#", []);
    assert_typeahead_equals("# ", []);
    assert_typeahead_equals(" #", []);
    assert_typeahead_equals("# s", []);
    assert_typeahead_equals("test #", []);
    assert_typeahead_equals("test # a", []);
    assert_typeahead_equals("test no#o", []);

    const poll_command = {
        text: "translated: /poll",
        name: "poll",
        info: "translated: Create a poll",
        aliases: "",
        placeholder: "translated: Question",
        type: "slash",
    };
    const todo_command = {
        text: "translated: /todo",
        name: "todo",
        info: "translated: Create a collaborative to-do list",
        aliases: "",
        placeholder: "translated: Task list",
        type: "slash",
    };

    assert_typeahead_equals("/", [me_command_item, poll_command, todo_command]);
    assert_typeahead_equals("/m", [me_command_item]);
    // Slash commands can only occur at the start of a message
    assert_typeahead_equals(" /m", []);
    assert_typeahead_equals("abc/me", []);
    assert_typeahead_equals("hello /me", []);
    assert_typeahead_equals("\n/m", []);
    assert_typeahead_equals("/poll", [poll_command]);
    assert_typeahead_equals(" /pol", []);
    assert_typeahead_equals("abc/po", []);
    assert_typeahead_equals("hello /poll", []);
    assert_typeahead_equals("\n/pol", []);
    assert_typeahead_equals("/todo", [todo_command]);
    assert_typeahead_equals("my /todo", []);
    assert_typeahead_equals("\n/to", []);
    assert_typeahead_equals(" /tod", []);

    assert_typeahead_equals("x/", []);
    // We don't open the typeahead until there's a letter after ```
    assert_typeahead_equals("```", []);
    assert_typeahead_equals("``` ", []);
    assert_typeahead_equals(" ```", []);
    assert_typeahead_equals("test ```", []);
    assert_typeahead_equals("test ``` py", []);
    assert_typeahead_equals("test ```a", []);
    assert_typeahead_equals("test\n```", []);
    assert_typeahead_equals("``c", []);
    // Languages filtered by a single letter is a very long list.
    // The typeahead displays languages sorted by popularity, so to
    // avoid typing out all of them here we'll just test that the
    // first several match up.
    assert_typeahead_starts_with(
        "```b",
        language_objects(["bash", "b3d", "bare", "basemake", "basic", "bat"]),
    );
    assert_typeahead_starts_with(
        "``` d",
        language_objects(["d", "dart", "d-objdump", "dasm16", "dax", "debcontrol"]),
    );
    const p_langs = language_objects(["python", "powershell", "php", "perl", "pacmanconf", "pan"]);
    assert_typeahead_starts_with("test\n``` p", p_langs);
    // Too many spaces between ``` and the p to
    // trigger the typeahead.
    assert_typeahead_equals("test\n```  p", []);
    assert_typeahead_equals("~~~", []);
    assert_typeahead_equals("~~~ ", []);
    assert_typeahead_equals(" ~~~", []);
    // Only valid when ``` or ~~~ is at the beginning of a line.
    assert_typeahead_equals(" ~~~ g", []);
    assert_typeahead_equals("test ~~~", []);
    assert_typeahead_equals("test ~~~p", []);
    assert_typeahead_equals("test\n~~~", []);
    assert_typeahead_starts_with(
        "~~~e",
        language_objects(["earl-grey", "easytrieve", "ebnf", "ec", "ecl", "eiffel"]),
    );
    assert_typeahead_starts_with(
        "~~~ f",
        language_objects(["f#", "f90", "factor", "fan", "fancy", "fc"]),
    );
    assert_typeahead_starts_with("test\n~~~ p", p_langs);
    // Too many spaces before the p
    assert_typeahead_equals("test\n~~~  p", []);

    // topic_jump
    assert_typeahead_equals("@**a person**>", []);
    assert_typeahead_equals("@**a person** >", []);
    const topic_jump = [
        {
            // this is deliberately a blank choice.
            message: "",
            type: "topic_jump",
        },
    ];
    assert_typeahead_equals("#**stream**>", topic_jump);
    assert_typeahead_equals("#**stream** >", topic_jump);
    assert_typeahead_equals("[#A&#42; Algorithm](#narrow/channel/6-A*-Algorithm) >", topic_jump);
    assert_typeahead_equals("#**Sweden>some topic** >", []); // Already completed a topic.

    // topic_list
    // includes "more ice"
    function typed_topics(stream, topics, is_new_topic = false) {
        const matches_list = topics.map((topic, index) => ({
            is_channel_link: topic === stream && index === 0,
            stream_data: {
                ...stream_data.get_sub_by_name("Sweden"),
                rendered_description: "",
            },
            topic,
            is_empty_string_topic: topic === "",
            topic_display_name: get_final_topic_display_name(topic),
            type: "topic_list",
            used_syntax_prefix: "#**",
            is_new_topic,
        }));
        return matches_list;
    }
    assert_typeahead_equals(
        "#**Sweden>more ice",
        typed_topics("Sweden", ["more ice", "even more ice"]),
    );
    assert_typeahead_equals(
        "#**Sweden>",
        typed_topics("Sweden", ["Sweden", ...sweden_topics_to_show]),
    );
    const is_new_topic = true;
    assert_typeahead_equals(
        "#**Sweden>totally new topic",
        typed_topics("Sweden", ["totally new topic"], is_new_topic),
    );
    assert_typeahead_equals("#**Sweden>\n\nmore ice", typed_topics("Sweden", []));

    // time_jump
    const time_jump = [
        {
            message: "translated: Mention a time-zone-aware time",
            type: "time_jump",
        },
    ];
    assert_typeahead_equals("<tim", []);
    assert_typeahead_equals("<timerandom", []);
    assert_typeahead_equals("<time", time_jump);
    assert_typeahead_equals("<time:", time_jump);
    assert_typeahead_equals("<time:something", time_jump);
    assert_typeahead_equals("<time:something", "> ", time_jump);
    assert_typeahead_equals("<time:something>", time_jump);
    assert_typeahead_equals("<time:something> ", []); // Already completed the mention

    // Following tests place the cursor before the second string
    assert_typeahead_equals("#test", "ing", []);
    assert_typeahead_equals("@test", "ing", []);
    assert_typeahead_equals(":test", "ing", []);
    assert_typeahead_equals("```test", "ing", []);
    assert_typeahead_equals("~~~test", "ing", []);
    const terminal_symbols = ",.;?!()[]> \u00A0\"'\n\t";
    for (const symbol of terminal_symbols.split()) {
        assert_typeahead_equals(
            "@othello",
            symbol,
            mentions_with_silent_marker([othello_item], false),
        );
        assert_typeahead_equals(":tada", symbol, emoji_objects(["tada"]));
        assert_typeahead_starts_with("```p", symbol, p_langs);
        assert_typeahead_starts_with("~~~p", symbol, p_langs);
    }
});

test("tokenizing", () => {
    assert.equal(ct.tokenize_compose_str("/m"), "/m");
    assert.equal(ct.tokenize_compose_str("1/3"), "");
    assert.equal(ct.tokenize_compose_str("foo bar"), "");
    assert.equal(ct.tokenize_compose_str("foo#@:bar"), "");
    assert.equal(ct.tokenize_compose_str("foo bar [#alic"), "#alic");
    assert.equal(ct.tokenize_compose_str("foo bar (#alic"), "#alic");
    assert.equal(ct.tokenize_compose_str("foo bar {#alic"), "#alic");
    assert.equal(ct.tokenize_compose_str("foo bar /#alic"), "#alic");
    assert.equal(ct.tokenize_compose_str("foo bar <#alic"), "#alic");
    assert.equal(ct.tokenize_compose_str("foo bar '#alic"), "#alic");
    assert.equal(ct.tokenize_compose_str('foo bar "#alic'), "#alic");
    assert.equal(ct.tokenize_compose_str("#foo @bar [#alic"), "#alic");
    assert.equal(ct.tokenize_compose_str("foo bar #alic"), "#alic");
    assert.equal(ct.tokenize_compose_str("foo bar @alic"), "@alic");
    assert.equal(ct.tokenize_compose_str("foo bar :smil"), ":smil");
    assert.equal(ct.tokenize_compose_str(":smil"), ":smil");
    assert.equal(ct.tokenize_compose_str("foo @alice sm"), "@alice sm");
    assert.equal(ct.tokenize_compose_str("foo ```p"), "");
    assert.equal(ct.tokenize_compose_str("``` py"), "``` py");
    assert.equal(ct.tokenize_compose_str("foo``bar ~~~ py"), "");
    assert.equal(ct.tokenize_compose_str("foo ~~~why = why_not\n~~~"), "~~~");

    // The following cases are kinda judgment calls...
    // max scanning limit is 40 characters until chars like @, # , / are found
    assert.equal(
        ct.tokenize_compose_str(
            "foo @toomanycharactersistooridiculoustoautocompletethatitexceedsalllimitsusingthewildessequenceofstringsforthispurpose",
        ),
        "",
    );
    assert.equal(ct.tokenize_compose_str("foo #bar@foo"), "#bar@foo");
});

test("content_item_html", ({override_rewire}) => {
    ct.get_or_set_completing_for_tests("emoji");
    const emoji = {emoji_name: "person shrugging", emoji_url: "¯\\_(ツ)_/¯", type: "emoji"};
    let th_render_typeahead_item_called = false;
    override_rewire(typeahead_helper, "render_emoji", (item) => {
        assert.deepEqual(item, emoji);
        th_render_typeahead_item_called = true;
    });
    ct.content_item_html(emoji);

    ct.get_or_set_completing_for_tests("mention");
    let th_render_person_called = false;
    override_rewire(typeahead_helper, "render_person", (person) => {
        assert.deepEqual(person, othello_item);
        th_render_person_called = true;
    });
    ct.content_item_html(othello_item);

    let th_render_user_group_called = false;
    override_rewire(typeahead_helper, "render_user_group", (user_group) => {
        assert.deepEqual(user_group, backend);
        th_render_user_group_called = true;
    });
    ct.content_item_html(backend);

    // We don't have any fancy rendering for slash commands yet.
    ct.get_or_set_completing_for_tests("slash");
    let th_render_slash_command_called = false;
    const me_slash = {
        text: "/me",
        type: "slash",
        info: "translated: Action message",
    };
    override_rewire(typeahead_helper, "render_typeahead_item", (item) => {
        assert.deepEqual(item, {
            primary: "/me",
            secondary: "translated: Action message",
        });
        th_render_slash_command_called = true;
    });
    ct.content_item_html(me_slash);

    ct.get_or_set_completing_for_tests("stream");
    let th_render_stream_called = false;
    override_rewire(typeahead_helper, "render_stream", (stream) => {
        assert.deepEqual(stream, denmark_stream);
        th_render_stream_called = true;
    });
    ct.content_item_html(denmark_stream);

    ct.get_or_set_completing_for_tests("syntax");
    th_render_typeahead_item_called = false;
    override_rewire(typeahead_helper, "render_typeahead_item", (item) => {
        assert.deepEqual(item, {
            is_default_language: false,
            primary: "py",
        });
        th_render_typeahead_item_called = true;
    });
    ct.content_item_html({type: "syntax", language: "py"});

    // Verify that all stub functions have been called.
    assert.ok(th_render_typeahead_item_called);
    assert.ok(th_render_person_called);
    assert.ok(th_render_user_group_called);
    assert.ok(th_render_stream_called);
    assert.ok(th_render_typeahead_item_called);
    assert.ok(th_render_slash_command_called);
});

function possibly_silent_list(list, is_silent) {
    return list.map((item) => ({
        ...item,
        is_silent,
    }));
}

test("filter_and_sort_mentions (normal)", ({override}) => {
    compose_state.set_message_type("stream");
    const is_silent = false;
    override(current_user, "user_id", 101);
    let suggestions = ct.filter_and_sort_mentions(is_silent, "al");

    const mention_all = broadcast_item(ct.broadcast_mentions()[0]);
    assert.deepEqual(
        suggestions,
        possibly_silent_list([mention_all, ali_item, alice_item, hal_item, call_center], is_silent),
    );

    // call_center group is shown in typeahead even when user is member of
    // one of the subgroups of can_mention_group.
    override(current_user, "user_id", 104);
    suggestions = ct.filter_and_sort_mentions(is_silent, "al");
    assert.deepEqual(
        suggestions,
        possibly_silent_list([mention_all, ali_item, alice_item, hal_item, call_center], is_silent),
    );

    // call_center group is not shown in typeahead when user is neither
    // a direct member of can_mention_group nor a member of any of its
    // recursive subgroups.
    override(current_user, "user_id", 102);
    suggestions = ct.filter_and_sort_mentions(is_silent, "al");
    assert.deepEqual(
        suggestions,
        possibly_silent_list([mention_all, ali_item, alice_item, hal_item], is_silent),
    );
});

test("filter_and_sort_mentions (silent)", ({override}) => {
    const is_silent = true;

    let suggestions = ct.filter_and_sort_mentions(is_silent, "al");

    assert.deepEqual(
        suggestions,
        possibly_silent_list([ali_item, alice_item, hal_item, call_center], is_silent),
    );

    // call_center group is shown in typeahead irrespective of whether
    // user is member of can_mention_group or its subgroups for a
    // silent mention.
    override(current_user, "user_id", 102);
    suggestions = ct.filter_and_sort_mentions(is_silent, "al");
    assert.deepEqual(
        suggestions,
        possibly_silent_list([ali_item, alice_item, hal_item, call_center], is_silent),
    );
});

test("typeahead_results", ({override}) => {
    const stream_list = [
        denmark_stream,
        sweden_stream,
        netherland_stream,
        mobile_team_stream,
        mobile_stream,
    ];

    function assert_emoji_matches(input, expected) {
        const matcher = typeahead.get_emoji_matcher(input);
        const returned = emoji_list.filter((item) => matcher(item));
        assert.deepEqual(returned, expected);
    }

    function assert_mentions_matches(input, expected) {
        const is_silent = false;
        const returned = ct.filter_and_sort_mentions(is_silent, input);
        assert.deepEqual(returned, expected);
    }
    function assert_stream_matches(input, expected) {
        const matcher = ct.get_stream_matcher(input);
        const returned = stream_list.filter((item) => matcher(item));
        assert.deepEqual(returned, expected);
    }

    function assert_slash_matches(input, expected) {
        const matcher = ct.get_slash_matcher(input);
        const returned = composebox_typeahead.all_slash_commands.filter((item) => matcher(item));
        assert.deepEqual(returned, expected);
    }
    assert_emoji_matches("da", [
        {
            emoji_name: "panda_face",
            emoji_code: "1f43c",
            reaction_type: "unicode_emoji",
            is_realm_emoji: false,
            type: "emoji",
        },
        {
            emoji_name: "tada",
            emoji_code: "1f389",
            reaction_type: "unicode_emoji",
            is_realm_emoji: false,
            type: "emoji",
        },
    ]);
    assert_emoji_matches("da_", []);
    assert_emoji_matches("da ", []);
    assert_emoji_matches("panda ", [
        {
            emoji_name: "panda_face",
            emoji_code: "1f43c",
            reaction_type: "unicode_emoji",
            is_realm_emoji: false,
            type: "emoji",
        },
    ]);
    assert_emoji_matches("panda_", [
        {
            emoji_name: "panda_face",
            emoji_code: "1f43c",
            reaction_type: "unicode_emoji",
            is_realm_emoji: false,
            type: "emoji",
        },
    ]);
    assert_emoji_matches("japanese_post_", [
        {
            emoji_name: "japanese_post_office",
            emoji_code: "1f3e3",
            reaction_type: "unicode_emoji",
            is_realm_emoji: false,
            type: "emoji",
        },
    ]);
    assert_emoji_matches("japanese post ", [
        {
            emoji_name: "japanese_post_office",
            emoji_code: "1f3e3",
            reaction_type: "unicode_emoji",
            is_realm_emoji: false,
            type: "emoji",
        },
    ]);
    assert_emoji_matches("notaemoji", []);

    // Autocomplete user mentions by user name.
    function not_silent(item) {
        return {
            ...item,
            is_silent: false,
        };
    }
    assert_mentions_matches("cordelia", [not_silent(cordelia_item)]);
    assert_mentions_matches("cordelia, le", [not_silent(cordelia_item)]);
    assert_mentions_matches("cordelia, le ", []);
    assert_mentions_matches("moor", [not_silent(othello_item)]);
    assert_mentions_matches("moor ", [not_silent(othello_item)]);
    assert_mentions_matches("moor of", [not_silent(othello_item)]);
    assert_mentions_matches("moor of ven", [not_silent(othello_item)]);
    assert_mentions_matches("oor", [not_silent(othello_item)]);
    assert_mentions_matches("oor ", []);
    assert_mentions_matches("oor o", []);
    assert_mentions_matches("oor of venice", []);
    assert_mentions_matches("King ", [not_silent(hamlet_item), not_silent(lear_item)]);
    assert_mentions_matches("King H", [not_silent(hamlet_item)]);
    assert_mentions_matches("King L", [not_silent(lear_item)]);
    assert_mentions_matches("delia lear", []);
    assert_mentions_matches("Mark Tw", [not_silent(twin1_item), not_silent(twin2_item)]);

    // Earlier user group and stream mentions were autocompleted by their
    // description too. This is now removed as it often led to unexpected
    // behaviour, and did not have any great discoverability advantage.
    override(current_user, "user_id", 101);
    // Autocomplete user group mentions by group name.
    assert_mentions_matches("hamletchar", [not_silent(hamletcharacters)]);

    // Verify we're not matching on a terms that only appear in the description.
    assert_mentions_matches("characters of", []);

    // Verify we suggest only the first matching stream wildcard mention,
    // irrespective of how many equivalent stream wildcard mentions match.
    const mention_everyone = not_silent(broadcast_item(ct.broadcast_mentions()[1]));
    // Here, we suggest only "everyone" instead of both the matching
    // "everyone" and "stream" wildcard mentions.
    assert_mentions_matches("e", [
        not_silent(mention_everyone),
        not_silent(hal_item),
        not_silent(alice_item),
        not_silent(cordelia_item),
        not_silent(gael_item),
        not_silent(hamlet_item),
        not_silent(lear_item),
        not_silent(othello_item),
        not_silent(hamletcharacters),
        not_silent(call_center),
        not_silent(welcome_bot_item),
    ]);

    // Verify we suggest both 'the first matching stream wildcard' and
    // 'topic wildcard' mentions. Not only one matching wildcard mention.
    const mention_topic = broadcast_item(ct.broadcast_mentions()[4]);
    // Here, we suggest both "everyone" and "topic".
    assert_mentions_matches("o", [
        not_silent(othello_item),
        not_silent(mention_everyone),
        not_silent(mention_topic),
        not_silent(cordelia_item),
        not_silent(notification_bot_item),
        not_silent(welcome_bot_item),
    ]);

    // Autocomplete by slash commands.
    assert_slash_matches("me", [me_command]);
    assert_slash_matches("dark", [dark_command]);
    assert_slash_matches("night", [dark_command]);
    assert_slash_matches("light", [light_command]);
    assert_slash_matches("day", [light_command]);

    // Autocomplete stream by stream name
    assert_stream_matches("den", [denmark_stream, sweden_stream]);
    assert_stream_matches("denmark", [denmark_stream]);
    assert_stream_matches("denmark ", []);
    assert_stream_matches("den ", []);
    assert_stream_matches("the ", [netherland_stream]);
    // Do not match stream descriptions
    assert_stream_matches("cold", []);
    assert_stream_matches("city", []);
    // Always prioritise exact matches, irrespective of activity
    assert_stream_matches("Mobile", [mobile_team_stream, mobile_stream]);
});

test("message people", ({override, override_rewire}) => {
    let results;

    /*
        We will initially simulate that we talk to Hal and Harry, while
        we don't talk to King Hamlet or Characters of Hamlet. This
        will knock these 2 out of consideration in the filtering pass.
    */

    let user_ids = [hal.user_id, harry.user_id];
    override(message_user_ids, "user_ids", () => user_ids);
    override_rewire(ct, "max_num_items", 2);

    const opts = {
        want_broadcast: false,
        want_groups: true,
        filter_pills: false,
    };

    results = ct.get_person_suggestions("Ha", opts);
    assert.deepEqual(results, [harry_item, hal_item]);

    // Now let's exclude Hal and include King Hamlet.
    user_ids = [hamlet.user_id, harry.user_id];

    results = ct.get_person_suggestions("Ha", opts);
    assert.deepEqual(results, [harry_item, hamlet_item]);

    // Reincluding Hal and deactivating harry
    user_ids = [hamlet.user_id, harry.user_id, hal.user_id];
    people.deactivate(harry);
    results = ct.get_person_suggestions("Ha", opts);
    // harry is excluded since it has been deactivated.
    assert.deepEqual(results, [hal_item, hamlet_item]);

    // Test that members group is not include in DM typeahead
    // as it has more than 20 members.
    opts.filter_groups_for_dm = true;
    override_rewire(ct, "max_group_size_for_dm", 4);
    results = ct.get_person_suggestions("rs", opts);
    assert.deepEqual(results, [hamletcharacters, admins]);
});

test("person suggestion for unique full name syntax", () => {
    let results = ct.get_person_suggestions(`${ali.full_name}|${ali.user_id}`, {});
    // Ali is not a valid user, so we should get no results.
    assert.deepEqual(results, []);

    // Add Ali as a valid user.
    people.add_valid_user_id(ali.user_id);
    results = ct.get_person_suggestions(`${ali.full_name}|${ali.user_id}`, {});
    assert.deepEqual(results, [ali_item]);
});

test("muted users excluded from results", () => {
    // This logic is common to direct message recipients as
    // well as mentions typeaheads, so we need only test once.
    let results;
    const opts = {
        want_broadcast: true,
    };

    // Nobody is muted
    results = ct.get_person_suggestions("corde", opts);
    assert.deepEqual(results, [cordelia_item]);

    // Mute Cordelia, and test that she's excluded from results.
    muted_users.add_muted_user(cordelia.user_id);
    results = ct.get_person_suggestions("corde", opts);
    assert.deepEqual(results, []);

    // Make sure our muting logic doesn't break wildcard mentions
    // or user group mentions.
    results = ct.get_person_suggestions("all", opts);
    const mention_all = broadcast_item(ct.broadcast_mentions()[0]);
    assert.deepEqual(results, [mention_all, call_center]);
});

test("direct message recipients sorted according to stream / topic being viewed", ({
    override_rewire,
}) => {
    // This tests that direct message recipient results are sorted with
    // subscribers of the stream / topic being viewed being given priority.
    // If no stream is being viewed, the sort is alphabetical (for testing,
    // since we do not simulate direct message history)
    let results;

    // Simulating just cordelia being subscribed to denmark.
    override_rewire(
        stream_data,
        "is_user_subscribed",
        (stream_id, user_id) =>
            stream_id === denmark_stream.stream_id && user_id === cordelia.user_id,
    );
    mock_banners();

    // When viewing no stream, sorting is alphabetical
    compose_state.set_stream_id("");
    results = ct.get_pm_people("li");
    // `get_pm_people` can't return mentions, so the items are all user items.
    assert.deepEqual(results, [ali_item, alice_item, cordelia_item]);

    // When viewing denmark stream, subscriber cordelia is placed higher
    compose_state.set_stream_id(denmark_stream.stream_id);
    results = ct.get_pm_people("li");
    assert.deepEqual(results, [cordelia_item, ali_item, alice_item]);

    // Simulating just alice being subscribed to denmark.
    override_rewire(
        stream_data,
        "is_user_subscribed",
        (stream_id, user_id) => stream_id === denmark_stream.stream_id && user_id === alice.user_id,
    );

    // When viewing denmark stream to which alice is subscribed, ali is not
    // 1st despite having an exact name match with the query.
    results = ct.get_pm_people("ali");
    assert.deepEqual(results, [alice_item, ali_item]);
});
