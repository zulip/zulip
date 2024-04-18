"use strict";

const {strict: assert} = require("assert");

const {mock_banners} = require("./lib/compose_banner");
const {mock_esm, set_global, with_overrides, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const $ = require("./lib/zjquery");
const {current_user, realm, user_settings} = require("./lib/zpage_params");

let autosize_called;

const bootstrap_typeahead = mock_esm("../src/bootstrap_typeahead");
const compose_ui = mock_esm("../src/compose_ui", {
    autosize_textarea() {
        autosize_called = true;
    },
    cursor_inside_code_block: () => false,
    set_code_formatting_button_triggered: noop,
});
const compose_validate = mock_esm("../src/compose_validate", {
    validate_message_length: () => true,
    warn_if_topic_resolved: noop,
    stream_wildcard_mention_allowed: () => true,
});
const input_pill = mock_esm("../src/input_pill");
const message_user_ids = mock_esm("../src/message_user_ids", {
    user_ids: () => [],
});
const stream_topic_history_util = mock_esm("../src/stream_topic_history_util");

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
const stream_data = zrequire("stream_data");
const stream_list_sort = zrequire("stream_list_sort");
const compose_pm_pill = zrequire("compose_pm_pill");
const compose_recipient = zrequire("compose_recipient");
const composebox_typeahead = zrequire("composebox_typeahead");
const settings_config = zrequire("settings_config");
const pygments_data = zrequire("pygments_data");

const ct = composebox_typeahead;

// Use a slightly larger value than what's user-facing
// to facilitate testing different combinations of
// broadcast-mentions/persons/groups.
ct.__Rewire__("max_num_items", 15);

function user_or_mention_item(item) {
    return {
        ...item,
        type: "user_or_mention",
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

    assert.equal(mention_all.special_item_text, "all (translated: Notify channel)");
    assert.equal(mention_everyone.special_item_text, "everyone (translated: Notify channel)");
    assert.equal(mention_stream.special_item_text, "stream (translated: Notify channel)");
    assert.equal(mention_channel.special_item_text, "channel (translated: Notify channel)");
    assert.equal(mention_topic.special_item_text, "topic (translated: Notify topic)");

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

    assert.equal(mention_all.special_item_text, "all (translated: Notify recipients)");
    assert.equal(mention_everyone.special_item_text, "everyone (translated: Notify recipients)");
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

const me_slash = {
    name: "me",
    aliases: "",
    text: "translated: /me (Action message)",
    placeholder: "translated: is …",
};

const my_slash = {
    name: "my",
    aliases: "",
    text: "translated: /my (Test)",
};

const dark_slash = {
    name: "dark",
    aliases: "night",
    text: "translated: /dark (Switch to the dark theme)",
};

const light_slash = {
    name: "light",
    aliases: "day",
    text: "translated: /light (Switch to light theme)",
};

const sweden_stream = {
    name: "Sweden",
    description: "Cold, mountains and home decor.",
    stream_id: 1,
    subscribed: true,
};
const denmark_stream = {
    name: "Denmark",
    description: "Vikings and boats, in a serene and cold weather.",
    stream_id: 2,
    subscribed: true,
};
const netherland_stream = {
    name: "The Netherlands",
    description: "The Netherlands, city of dream.",
    stream_id: 3,
    subscribed: false,
};
const mobile_stream = {
    name: "Mobile",
    description: "Mobile development",
    stream_id: 4,
    subscribed: false,
};
const mobile_team_stream = {
    name: "Mobile team",
    description: "Mobile development team",
    stream_id: 5,
    subscribed: true,
};

stream_data.add_sub(sweden_stream);
stream_data.add_sub(denmark_stream);
stream_data.add_sub(netherland_stream);
stream_data.add_sub(mobile_stream);
stream_data.add_sub(mobile_team_stream);

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
const emoji_list = composebox_typeahead.emoji_collection;

const ali = {
    email: "ali@zulip.com",
    user_id: 98,
    full_name: "Ali",
    is_moderator: false,
};
const ali_item = user_or_mention_item(ali);

const alice = {
    email: "alice@zulip.com",
    user_id: 99,
    full_name: "Alice",
    is_moderator: false,
};
const alice_item = user_or_mention_item(alice);

const hamlet = {
    email: "hamlet@zulip.com",
    user_id: 100,
    full_name: "King Hamlet",
    is_moderator: false,
};
const hamlet_item = user_or_mention_item(hamlet);

const othello = {
    email: "othello@zulip.com",
    user_id: 101,
    full_name: "Othello, the Moor of Venice",
    is_moderator: false,
    delivery_email: null,
};
const othello_item = user_or_mention_item(othello);

const cordelia = {
    email: "cordelia@zulip.com",
    user_id: 102,
    full_name: "Cordelia, Lear's daughter",
    is_moderator: false,
};
const cordelia_item = user_or_mention_item(cordelia);

const deactivated_user = {
    email: "other@zulip.com",
    user_id: 103,
    full_name: "Deactivated User",
    is_moderator: false,
};
const deactivated_user_item = user_or_mention_item(deactivated_user);

const lear = {
    email: "lear@zulip.com",
    user_id: 104,
    full_name: "King Lear",
    is_moderator: false,
};
const lear_item = user_or_mention_item(lear);

const twin1 = {
    full_name: "Mark Twin",
    is_moderator: false,
    user_id: 105,
    email: "twin1@zulip.com",
};
const twin1_item = user_or_mention_item(twin1);

const twin2 = {
    full_name: "Mark Twin",
    is_moderator: false,
    user_id: 106,
    email: "twin2@zulip.com",
};
const twin2_item = user_or_mention_item(twin2);

const gael = {
    full_name: "Gaël Twin",
    is_moderator: false,
    user_id: 107,
    email: "twin3@zulip.com",
};
const gael_item = user_or_mention_item(gael);

const hal = {
    full_name: "Earl Hal",
    is_moderator: false,
    user_id: 108,
    email: "hal@zulip.com",
};
const hal_item = user_or_mention_item(hal);

const harry = {
    full_name: "Harry",
    is_moderator: false,
    user_id: 109,
    email: "harry@zulip.com",
};
const harry_item = user_or_mention_item(harry);

const hamletcharacters = {
    name: "hamletcharacters",
    id: 1,
    description: "Characters of Hamlet",
    members: new Set([100, 104]),
    is_system_group: false,
    direct_subgroup_ids: new Set([]),
    can_mention_group: 2,
};

const backend = {
    name: "Backend",
    id: 2,
    description: "Backend team",
    members: new Set([101]),
    is_system_group: false,
    direct_subgroup_ids: new Set([1]),
    can_mention_group: 1,
};

const call_center = {
    name: "Call Center",
    id: 3,
    description: "folks working in support",
    members: new Set([102]),
    is_system_group: false,
    direct_subgroup_ids: new Set([]),
    can_mention_group: 2,
};

const make_emoji = (emoji_dict) => ({
    emoji_name: emoji_dict.name,
    emoji_code: emoji_dict.emoji_code,
    reaction_type: "unicode_emoji",
});

function test(label, f) {
    run_test(label, (helpers) => {
        people.init();
        user_groups.init();

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
        people.deactivate(deactivated_user);
        people.initialize_current_user(hamlet.user_id);

        user_groups.add(hamletcharacters);
        user_groups.add(backend);
        user_groups.add(call_center);

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
    actual_value = ct.content_typeahead_selected(twin1, query, input_element);
    expected_value = "@**Mark Twin|105** ";
    assert.equal(actual_value, expected_value);

    let warned_for_mention = false;
    override(compose_validate, "warn_if_mentioning_unsubscribed_user", (mentioned) => {
        assert.equal(mentioned, othello);
        warned_for_mention = true;
    });

    query = "@oth";
    ct.get_or_set_token_for_testing("oth");
    actual_value = ct.content_typeahead_selected(othello, query, input_element);
    expected_value = "@**Othello, the Moor of Venice** ";
    assert.equal(actual_value, expected_value);
    assert.ok(warned_for_mention);

    query = "Hello @oth";
    ct.get_or_set_token_for_testing("oth");
    actual_value = ct.content_typeahead_selected(othello, query, input_element);
    expected_value = "Hello @**Othello, the Moor of Venice** ";
    assert.equal(actual_value, expected_value);

    query = "@**oth";
    ct.get_or_set_token_for_testing("oth");
    actual_value = ct.content_typeahead_selected(othello, query, input_element);
    expected_value = "@**Othello, the Moor of Venice** ";
    assert.equal(actual_value, expected_value);

    query = "@*oth";
    ct.get_or_set_token_for_testing("oth");
    actual_value = ct.content_typeahead_selected(othello, query, input_element);
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
    query = "@_kin";
    ct.get_or_set_token_for_testing("kin");
    with_overrides(({disallow}) => {
        disallow(compose_validate, "warn_if_mentioning_unsubscribed_user");
        actual_value = ct.content_typeahead_selected(hamlet, query, input_element);
    });

    expected_value = "@_**King Hamlet** ";
    assert.equal(actual_value, expected_value);

    query = "Hello @_kin";
    ct.get_or_set_token_for_testing("kin");
    actual_value = ct.content_typeahead_selected(hamlet, query, input_element);
    expected_value = "Hello @_**King Hamlet** ";
    assert.equal(actual_value, expected_value);

    query = "@_*kin";
    ct.get_or_set_token_for_testing("kin");
    actual_value = ct.content_typeahead_selected(hamlet, query, input_element);
    expected_value = "@_**King Hamlet** ";
    assert.equal(actual_value, expected_value);

    query = "@_**kin";
    ct.get_or_set_token_for_testing("kin");
    actual_value = ct.content_typeahead_selected(hamlet, query, input_element);
    expected_value = "@_**King Hamlet** ";
    assert.equal(actual_value, expected_value);

    query = "@_back";
    ct.get_or_set_token_for_testing("back");
    with_overrides(({disallow}) => {
        disallow(compose_validate, "warn_if_mentioning_unsubscribed_user");
        actual_value = ct.content_typeahead_selected(backend, query, input_element);
    });
    expected_value = "@_*Backend* ";
    assert.equal(actual_value, expected_value);

    query = "@_*back";
    ct.get_or_set_token_for_testing("back");
    actual_value = ct.content_typeahead_selected(backend, query, input_element);
    expected_value = "@_*Backend* ";
    assert.equal(actual_value, expected_value);

    query = "/m";
    ct.get_or_set_completing_for_tests("slash");
    actual_value = ct.content_typeahead_selected(me_slash, query, input_element);
    expected_value = "/me translated: is …";
    assert.equal(actual_value, expected_value);

    query = "/da";
    ct.get_or_set_completing_for_tests("slash");
    actual_value = ct.content_typeahead_selected(dark_slash, query, input_element);
    expected_value = "/dark ";
    assert.equal(actual_value, expected_value);

    query = "/ni";
    ct.get_or_set_completing_for_tests("slash");
    actual_value = ct.content_typeahead_selected(dark_slash, query, input_element);
    expected_value = "/dark ";
    assert.equal(actual_value, expected_value);

    query = "/li";
    ct.get_or_set_completing_for_tests("slash");
    actual_value = ct.content_typeahead_selected(light_slash, query, input_element);
    expected_value = "/light ";
    assert.equal(actual_value, expected_value);

    query = "/da";
    ct.get_or_set_completing_for_tests("slash");
    actual_value = ct.content_typeahead_selected(light_slash, query, input_element);
    expected_value = "/light ";
    assert.equal(actual_value, expected_value);

    // stream
    ct.get_or_set_completing_for_tests("stream");
    let warned_for_stream_link = false;
    override(compose_validate, "warn_if_private_stream_is_linked", (linked_stream) => {
        assert.equal(linked_stream, sweden_stream);
        warned_for_stream_link = true;
    });

    query = "#swed";
    ct.get_or_set_token_for_testing("swed");
    actual_value = ct.content_typeahead_selected(sweden_stream, query, input_element);
    expected_value = "#**Sweden** ";
    assert.equal(actual_value, expected_value);

    query = "Hello #swed";
    ct.get_or_set_token_for_testing("swed");
    actual_value = ct.content_typeahead_selected(sweden_stream, query, input_element);
    expected_value = "Hello #**Sweden** ";
    assert.equal(actual_value, expected_value);

    query = "#**swed";
    ct.get_or_set_token_for_testing("swed");
    actual_value = ct.content_typeahead_selected(sweden_stream, query, input_element);
    expected_value = "#**Sweden** ";
    assert.equal(actual_value, expected_value);

    // topic_list
    ct.get_or_set_completing_for_tests("topic_list");

    query = "Hello #**Sweden>test";
    ct.get_or_set_token_for_testing("test");
    actual_value = ct.content_typeahead_selected("testing", query, input_element);
    expected_value = "Hello #**Sweden>testing** ";
    assert.equal(actual_value, expected_value);

    query = "Hello #**Sweden>";
    ct.get_or_set_token_for_testing("");
    actual_value = ct.content_typeahead_selected("testing", query, input_element);
    expected_value = "Hello #**Sweden>testing** ";
    assert.equal(actual_value, expected_value);

    // syntax
    ct.get_or_set_completing_for_tests("syntax");

    query = "~~~p";
    ct.get_or_set_token_for_testing("p");
    actual_value = ct.content_typeahead_selected("python", query, input_element);
    expected_value = "~~~python\n\n~~~";
    assert.equal(actual_value, expected_value);

    query = "Hello ~~~p";
    ct.get_or_set_token_for_testing("p");
    actual_value = ct.content_typeahead_selected("python", query, input_element);
    expected_value = "Hello ~~~python\n\n~~~";
    assert.equal(actual_value, expected_value);

    query = "```p";
    ct.get_or_set_token_for_testing("p");
    actual_value = ct.content_typeahead_selected("python", query, input_element);
    expected_value = "```python\n\n```";
    assert.equal(actual_value, expected_value);

    query = "```spo";
    ct.get_or_set_token_for_testing("spo");
    actual_value = ct.content_typeahead_selected("spoiler", query, input_element);
    expected_value = "```spoiler translated: Header\n\n```";
    assert.equal(actual_value, expected_value);

    // Test special case to not close code blocks if there is text afterward
    query = "```p\nsome existing code";
    ct.get_or_set_token_for_testing("p");
    input_element.$element.caret = () => 4; // Put cursor right after ```p
    actual_value = ct.content_typeahead_selected("python", query, input_element);
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

const sweden_topics_to_show = ["<&>", "even more ice", "furniture", "ice", "kronor", "more ice"];

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
            appended_names.push(item.display_value);
        },
    }));
    compose_pm_pill.initialize({
        on_pill_create_or_remove: compose_recipient.update_placeholder_text,
    });

    let expected_value;
    realm.custom_profile_field_types = {
        PRONOUNS: {id: 8, name: "Pronouns"},
    };

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

                // options.highlighter_html()
                options.query = "Kro";
                actual_value = options.highlighter_html("kronor");
                expected_value = "<strong>kronor</strong>";
                assert.equal(actual_value, expected_value);

                // Highlighted content should be escaped.
                options.query = "<";
                actual_value = options.highlighter_html("<&>");
                expected_value = "<strong>&lt;&amp;&gt;</strong>";
                assert.equal(actual_value, expected_value);

                options.query = "even m";
                actual_value = options.highlighter_html("even more ice");
                expected_value = "<strong>even more ice</strong>";
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
                    user_or_mention_item(ali),
                    user_or_mention_item(alice),
                    user_or_mention_item(cordelia),
                    user_or_mention_item(hal),
                    user_or_mention_item(gael),
                    user_or_mention_item(harry),
                    user_or_mention_item(hamlet),
                    user_or_mention_item(lear),
                    user_or_mention_item(twin1),
                    user_or_mention_item(twin2),
                    user_or_mention_item(othello),
                    hamletcharacters,
                    backend,
                    call_center,
                ];
                actual_value.sort((a, b) => a.user_id - b.user_id);
                expected_value.sort((a, b) => a.user_id - b.user_id);
                assert.deepEqual(actual_value, expected_value);

                function matcher(query, person) {
                    query = typeahead.clean_query_lowercase(query);
                    return typeahead_helper.query_matches_person(query, person);
                }

                let query;
                query = "el"; // Matches both "othELlo" and "cordELia"
                assert.equal(matcher(query, othello), true);
                assert.equal(matcher(query, cordelia), true);

                query = "bender"; // Doesn't exist
                assert.equal(matcher(query, othello), false);
                assert.equal(matcher(query, cordelia), false);

                query = "gael";
                assert.equal(matcher(query, gael), true);

                query = "Gaël";
                assert.equal(matcher(query, gael), true);

                query = "gaël";
                assert.equal(matcher(query, gael), true);

                // Don't make suggestions if the last name only has whitespaces
                // (we're between typing names).
                query = "othello@zulip.com,     ";
                assert.equal(matcher(query, othello), false);
                assert.equal(matcher(query, cordelia), false);

                // query = 'othello@zulip.com,, , cord';
                query = "cord";
                assert.equal(matcher(query, othello), false);
                assert.equal(matcher(query, cordelia), true);

                // If the user is already in the list, typeahead doesn't include it
                // again.
                query = "cordelia@zulip.com, cord";
                assert.equal(matcher(query, othello), false);
                assert.equal(matcher(query, cordelia), false);

                query = "oth";
                deactivated_user.delivery_email = null;
                assert.equal(matcher(query, deactivated_user), false);

                deactivated_user.delivery_email = "other@zulip.com";
                assert.equal(matcher(query, deactivated_user), true);

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
                actual_value.sort((a, b) => a.user_id - b.user_id);
                expected_value.sort((a, b) => a.user_id - b.user_id);
                assert.deepEqual(actual_value, expected_value);

                query = "non-existing-user";
                actual_value = sorter(query, []);
                expected_value = [];
                assert.deepEqual(actual_value, expected_value);

                // Adds a `no break-space` at the end. This should fail
                // if there wasn't any logic replacing `no break-space`
                // with normal space.
                query = "cordelia, lear's\u00A0";
                assert.equal(matcher(query, cordelia), true);
                assert.equal(matcher(query, othello), false);

                const event = {
                    target: "#doesnotmatter",
                };

                // options.updater()
                options.query = "othello";
                appended_names = [];
                options.updater(othello, event);
                assert.deepEqual(appended_names, ["Othello, the Moor of Venice"]);

                options.query = "othello@zulip.com, cor";
                appended_names = [];
                actual_value = options.updater(cordelia, event);
                assert.deepEqual(appended_names, ["Cordelia, Lear's daughter"]);

                const click_event = {type: "click", target: "#doesnotmatter"};
                options.query = "othello";
                // Focus lost (caused by the click event in the typeahead list)
                $("#private_message_recipient").trigger("blur");
                appended_names = [];
                actual_value = options.updater(othello, click_event);
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
                input_element.$element.closest = () => [];
                let actual_value = options.source("test #s", input_element);
                assert.deepEqual(sorted_names_from(actual_value), ["Sweden", "The Netherlands"]);
                assert.ok(caret_called);

                othello.delivery_email = "othello@zulip.com";
                // options.highlighter_html()
                //
                // Again, here we only verify that the highlighter has been set to
                // content_highlighter_html.
                ct.get_or_set_completing_for_tests("mention");
                ct.get_or_set_token_for_testing("othello");
                actual_value = options.highlighter_html(othello);
                expected_value =
                    `    <span class="user_circle_empty user_circle"></span>\n` +
                    `    <img class="typeahead-image" src="http://zulip.zulipdev.com/avatar/${othello.user_id}?s&#x3D;50" />\n` +
                    `<strong>Othello, the Moor of Venice</strong>&nbsp;&nbsp;\n` +
                    `<small class="autocomplete_secondary">othello@zulip.com</small>\n`;
                assert.equal(actual_value, expected_value);
                // Reset the email such that this does not affect further tests.
                othello.delivery_email = null;

                ct.get_or_set_completing_for_tests("mention");
                ct.get_or_set_token_for_testing("hamletcharacters");
                actual_value = options.highlighter_html(hamletcharacters);
                expected_value =
                    '    <i class="typeahead-image zulip-icon zulip-icon-triple-users no-presence-circle" aria-hidden="true"></i>\n<strong>hamletcharacters</strong>&nbsp;&nbsp;\n<small class="autocomplete_secondary">Characters of Hamlet</small>\n';
                assert.equal(actual_value, expected_value);

                // matching

                function match(item) {
                    const token = ct.get_or_set_token_for_testing();
                    const completing = ct.get_or_set_completing_for_tests();

                    return ct.compose_content_matcher(completing, token)(item);
                }

                ct.get_or_set_completing_for_tests("emoji");
                ct.get_or_set_token_for_testing("ta");
                assert.equal(match(make_emoji(emoji_tada)), true);
                assert.equal(match(make_emoji(emoji_moneybag)), false);

                ct.get_or_set_completing_for_tests("stream");
                ct.get_or_set_token_for_testing("swed");
                assert.equal(match(sweden_stream), true);
                assert.equal(match(denmark_stream), false);

                ct.get_or_set_completing_for_tests("syntax");
                ct.get_or_set_token_for_testing("py");
                assert.equal(match("python"), true);
                assert.equal(match("javascript"), false);

                ct.get_or_set_completing_for_tests("non-existing-completion");
                assert.equal(match(), undefined);

                function sort_items(item) {
                    const token = ct.get_or_set_token_for_testing();
                    const completing = ct.get_or_set_completing_for_tests();

                    return ct.sort_results(completing, item, token);
                }

                // options.sorter()
                ct.get_or_set_completing_for_tests("emoji");
                ct.get_or_set_token_for_testing("ta");
                actual_value = sort_items([make_emoji(emoji_stadium), make_emoji(emoji_tada)]);
                expected_value = [make_emoji(emoji_tada), make_emoji(emoji_stadium)];
                assert.deepEqual(actual_value, expected_value);

                ct.get_or_set_completing_for_tests("emoji");
                ct.get_or_set_token_for_testing("th");
                actual_value = sort_items([
                    make_emoji(emoji_thermometer),
                    make_emoji(emoji_thumbs_up),
                ]);
                expected_value = [make_emoji(emoji_thumbs_up), make_emoji(emoji_thermometer)];
                assert.deepEqual(actual_value, expected_value);

                ct.get_or_set_completing_for_tests("emoji");
                ct.get_or_set_token_for_testing("he");
                actual_value = sort_items([make_emoji(emoji_headphones), make_emoji(emoji_heart)]);
                expected_value = [make_emoji(emoji_heart), make_emoji(emoji_headphones)];
                assert.deepEqual(actual_value, expected_value);

                ct.get_or_set_completing_for_tests("slash");
                ct.get_or_set_token_for_testing("m");
                actual_value = sort_items([my_slash, me_slash]);
                expected_value = [me_slash, my_slash];
                assert.deepEqual(actual_value, expected_value);

                ct.get_or_set_completing_for_tests("slash");
                ct.get_or_set_token_for_testing("da");
                actual_value = sort_items([dark_slash, light_slash]);
                expected_value = [dark_slash, light_slash];
                assert.deepEqual(actual_value, expected_value);

                ct.get_or_set_completing_for_tests("stream");
                ct.get_or_set_token_for_testing("de");
                actual_value = sort_items([sweden_stream, denmark_stream]);
                expected_value = [denmark_stream, sweden_stream];
                assert.deepEqual(actual_value, expected_value);

                // Matches in the descriptions affect the order as well.
                // Testing "co" for "cold", in both streams' description. It's at the
                // beginning of Sweden's description, so that one should go first.
                ct.get_or_set_completing_for_tests("stream");
                ct.get_or_set_token_for_testing("co");
                actual_value = sort_items([denmark_stream, sweden_stream]);
                expected_value = [sweden_stream, denmark_stream];
                assert.deepEqual(actual_value, expected_value);

                ct.get_or_set_completing_for_tests("syntax");
                ct.get_or_set_token_for_testing("ap");
                actual_value = sort_items(["abap", "applescript"]);
                expected_value = ["applescript", "abap"];
                assert.deepEqual(actual_value, expected_value);

                const serbia_stream = {
                    name: "Serbia",
                    description: "Snow and cold",
                    stream_id: 3,
                    subscribed: false,
                };
                // Subscribed stream is active
                override(
                    user_settings,
                    "demote_inactive_streams",
                    settings_config.demote_inactive_streams_values.never.code,
                );

                stream_list_sort.set_filter_out_inactives();
                ct.get_or_set_completing_for_tests("stream");
                ct.get_or_set_token_for_testing("s");
                actual_value = sort_items([sweden_stream, serbia_stream]);
                expected_value = [sweden_stream, serbia_stream];
                assert.deepEqual(actual_value, expected_value);
                // Subscribed stream is inactive
                override(
                    user_settings,
                    "demote_inactive_streams",
                    settings_config.demote_inactive_streams_values.always.code,
                );

                stream_list_sort.set_filter_out_inactives();
                actual_value = sort_items([sweden_stream, serbia_stream]);
                expected_value = [sweden_stream, serbia_stream];
                assert.deepEqual(actual_value, expected_value);

                ct.get_or_set_completing_for_tests("stream");
                ct.get_or_set_token_for_testing("ser");
                actual_value = sort_items([denmark_stream, serbia_stream]);
                expected_value = [serbia_stream, denmark_stream];
                assert.deepEqual(actual_value, expected_value);

                ct.get_or_set_completing_for_tests("non-existing-completion");
                assert.equal(sort_items(), undefined);

                compose_textarea_typeahead_called = true;

                break;
            }
            // No default
        }
    });

    user_settings.enter_sends = false;
    let compose_finish_called = false;
    function finish() {
        compose_finish_called = true;
    }

    ct.initialize({
        on_enter_send: finish,
    });

    $("#private_message_recipient").val("othello@zulip.com, ");
    $("#private_message_recipient").trigger("blur");
    assert.equal($("#private_message_recipient").val(), "othello@zulip.com");

    // the UI of selecting a stream is tested in puppeteer tests.
    compose_state.set_stream_id(sweden_stream.stream_id);

    let event = {
        type: "keydown",
        key: "Tab",
        shiftKey: false,
        target: {
            id: "stream_message_recipient_topic",
        },
        preventDefault: noop,
        stopPropagation: noop,
    };
    $("form#send_message_form").trigger(event);
    event.target.id = "compose-textarea";
    $("form#send_message_form").trigger(event);
    event.target.id = "some_non_existing_id";
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
    event.target.id = "stream_message_recipient_topic";
    $("form#send_message_form").trigger(event);
    event.target.id = "compose-textarea";
    user_settings.enter_sends = false;
    event.metaKey = true;

    $("form#send_message_form").trigger(event);
    assert.ok(compose_finish_called);
    event.metaKey = false;
    event.ctrlKey = true;
    $("form#send_message_form").trigger(event);
    user_settings.enter_sends = true;
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
    event.target.id = "private_message_recipient";
    $("form#send_message_form").trigger(event);

    event.key = "a";
    $("form#send_message_form").trigger(event);

    // the UI of selecting a stream is tested in puppeteer tests.
    compose_state.set_stream_id(sweden_stream.stream_id);
    // handle_keyup()
    event = {
        type: "keydown",
        key: "Enter",
        target: {
            id: "stream_message_recipient_topic",
        },
        preventDefault: noop,
    };
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
    $("#send_later").css = noop;
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
        $element: {},
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

    const people_only = {is_silent: true};
    const all_mentions = {is_silent: false};
    const lang_list = Object.keys(pygments_data.langs);

    assert_typeahead_equals("test", false);
    assert_typeahead_equals("test one two", false);
    assert_typeahead_equals("*", false);
    assert_typeahead_equals("* ", false);
    assert_typeahead_equals(" *", false);
    assert_typeahead_equals("test *", false);

    // Make sure that the last token is the one we read.
    assert_typeahead_equals("~~~ @zulip", all_mentions);
    assert_typeahead_equals("@zulip :ta", emoji_list);
    assert_typeahead_equals("#foo\n~~~py", lang_list);
    assert_typeahead_equals(":tada: <time:", ["translated: Mention a time-zone-aware time"]);

    assert_typeahead_equals("@", all_mentions);
    assert_typeahead_equals("@_", people_only);
    assert_typeahead_equals(" @", all_mentions);
    assert_typeahead_equals(" @_", people_only);
    assert_typeahead_equals("@*", all_mentions);
    assert_typeahead_equals("@_*", people_only);
    assert_typeahead_equals("@**", all_mentions);
    assert_typeahead_equals("@_**", people_only);
    assert_typeahead_equals("test @**o", all_mentions);
    assert_typeahead_equals("test @_**o", people_only);
    assert_typeahead_equals("test @*o", all_mentions);
    assert_typeahead_equals("test @_*k", people_only);
    assert_typeahead_equals("test @*h", all_mentions);
    assert_typeahead_equals("test @_*h", people_only);
    assert_typeahead_equals("test @", all_mentions);
    assert_typeahead_equals("test @_", people_only);
    assert_typeahead_equals("test no@o", false);
    assert_typeahead_equals("test no@_k", false);
    assert_typeahead_equals("@ ", false);
    assert_typeahead_equals("@_ ", false);
    assert_typeahead_equals("@* ", false);
    assert_typeahead_equals("@_* ", false);
    assert_typeahead_equals("@** ", false);
    assert_typeahead_equals("@_** ", false);
    assert_typeahead_equals("test\n@i", all_mentions);
    assert_typeahead_equals("test\n@_i", people_only);
    assert_typeahead_equals("test\n @l", all_mentions);
    assert_typeahead_equals("test\n @_l", people_only);
    assert_typeahead_equals("@zuli", all_mentions);
    assert_typeahead_equals("@_zuli", people_only);
    assert_typeahead_equals("@ zuli", false);
    assert_typeahead_equals("@_ zuli", false);
    assert_typeahead_equals(" @zuli", all_mentions);
    assert_typeahead_equals(" @_zuli", people_only);
    assert_typeahead_equals("test @o", all_mentions);
    assert_typeahead_equals("test @_o", people_only);
    assert_typeahead_equals("test @z", all_mentions);
    assert_typeahead_equals("test @_z", people_only);

    assert_typeahead_equals(":", false);
    assert_typeahead_equals(": ", false);
    assert_typeahead_equals(" :", false);
    assert_typeahead_equals(":)", false);
    assert_typeahead_equals(":4", false);
    assert_typeahead_equals(": la", false);
    assert_typeahead_equals("test :-P", false);
    assert_typeahead_equals("hi emoji :", false);
    assert_typeahead_equals("hi emoj:i", false);
    assert_typeahead_equals("hi emoji :D", false);
    assert_typeahead_equals("hi emoji : t", false);
    assert_typeahead_equals("hi emoji :t", emoji_list);
    assert_typeahead_equals("hi emoji :ta", emoji_list);
    assert_typeahead_equals("hi emoji :da", emoji_list);
    assert_typeahead_equals("hi emoji :da_", emoji_list);
    assert_typeahead_equals("hi emoji :da ", emoji_list);
    assert_typeahead_equals("hi emoji\n:da", emoji_list);
    assert_typeahead_equals("hi emoji\n :ra", emoji_list);
    assert_typeahead_equals(":+", emoji_list);
    assert_typeahead_equals(":la", emoji_list);
    assert_typeahead_equals(" :lee", emoji_list);
    assert_typeahead_equals("hi :see no", emoji_list);
    assert_typeahead_equals("hi :japanese post of", emoji_list);

    assert_typeahead_equals("#", false);
    assert_typeahead_equals("# ", false);
    assert_typeahead_equals(" #", false);
    assert_typeahead_equals("# s", false);
    assert_typeahead_equals("test #", false);
    assert_typeahead_equals("test # a", false);
    assert_typeahead_equals("test no#o", false);

    assert_typeahead_equals("/", composebox_typeahead.slash_commands);
    assert_typeahead_equals("/m", composebox_typeahead.slash_commands);
    assert_typeahead_equals(" /m", false);
    assert_typeahead_equals("abc/me", false);
    assert_typeahead_equals("hello /me", false);
    assert_typeahead_equals("\n/m", false);
    assert_typeahead_equals("/poll", composebox_typeahead.slash_commands);
    assert_typeahead_equals(" /pol", false);
    assert_typeahead_equals("abc/po", false);
    assert_typeahead_equals("hello /poll", false);
    assert_typeahead_equals("\n/pol", false);
    assert_typeahead_equals("/todo", composebox_typeahead.slash_commands);
    assert_typeahead_equals("my /todo", false);
    assert_typeahead_equals("\n/to", false);
    assert_typeahead_equals(" /tod", false);

    assert_typeahead_equals("x/", false);
    assert_typeahead_equals("```", false);
    assert_typeahead_equals("``` ", false);
    assert_typeahead_equals(" ```", false);
    assert_typeahead_equals("test ```", false);
    assert_typeahead_equals("test ``` py", false);
    assert_typeahead_equals("test ```a", false);
    assert_typeahead_equals("test\n```", false);
    assert_typeahead_equals("``c", false);
    assert_typeahead_equals("```b", lang_list);
    assert_typeahead_equals("``` d", lang_list);
    assert_typeahead_equals("test\n``` p", lang_list);
    assert_typeahead_equals("test\n```  p", lang_list);
    assert_typeahead_equals("~~~", false);
    assert_typeahead_equals("~~~ ", false);
    assert_typeahead_equals(" ~~~", false);
    assert_typeahead_equals(" ~~~ g", false);
    assert_typeahead_equals("test ~~~", false);
    assert_typeahead_equals("test ~~~p", false);
    assert_typeahead_equals("test\n~~~", false);
    assert_typeahead_equals("~~~e", lang_list);
    assert_typeahead_equals("~~~ f", lang_list);
    assert_typeahead_equals("test\n~~~ p", lang_list);
    assert_typeahead_equals("test\n~~~  p", lang_list);

    // topic_jump
    assert_typeahead_equals("@**a person**>", false);
    assert_typeahead_equals("@**a person** >", false);
    assert_typeahead_equals("#**stream**>", [""]); // this is deliberately a blank choice.
    assert_typeahead_equals("#**stream** >", [""]);
    assert_typeahead_equals("#**Sweden>some topic** >", false); // Already completed a topic.

    // topic_list
    // includes "more ice"
    assert_typeahead_equals("#**Sweden>more ice", sweden_topics_to_show);
    sweden_topics_to_show.push("totally new topic");
    assert_typeahead_equals("#**Sweden>totally new topic", sweden_topics_to_show);

    // time_jump
    assert_typeahead_equals("<tim", false);
    assert_typeahead_equals("<timerandom", false);
    assert_typeahead_equals("<time", ["translated: Mention a time-zone-aware time"]);
    assert_typeahead_equals("<time:", ["translated: Mention a time-zone-aware time"]);
    assert_typeahead_equals("<time:something", ["translated: Mention a time-zone-aware time"]);
    assert_typeahead_equals("<time:something", "> ", [
        "translated: Mention a time-zone-aware time",
    ]);
    assert_typeahead_equals("<time:something>", ["translated: Mention a time-zone-aware time"]);
    assert_typeahead_equals("<time:something> ", false); // Already completed the mention

    // Following tests place the cursor before the second string
    assert_typeahead_equals("#test", "ing", false);
    assert_typeahead_equals("@test", "ing", false);
    assert_typeahead_equals(":test", "ing", false);
    assert_typeahead_equals("```test", "ing", false);
    assert_typeahead_equals("~~~test", "ing", false);
    const terminal_symbols = ",.;?!()[]> \"'\n\t";
    for (const symbol of terminal_symbols.split()) {
        assert_typeahead_equals("@test", symbol, all_mentions);
        assert_typeahead_equals(":test", symbol, emoji_list);
        assert_typeahead_equals("```test", symbol, lang_list);
        assert_typeahead_equals("~~~test", symbol, lang_list);
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
    assert.equal(ct.tokenize_compose_str("foo @toomanycharactersisridiculoustocomplete"), "");
    assert.equal(ct.tokenize_compose_str("foo #bar@foo"), "#bar@foo");
});

test("content_highlighter_html", ({override_rewire}) => {
    ct.get_or_set_completing_for_tests("emoji");
    const emoji = {emoji_name: "person shrugging", emoji_url: "¯\\_(ツ)_/¯"};
    let th_render_typeahead_item_called = false;
    override_rewire(typeahead_helper, "render_emoji", (item) => {
        assert.deepEqual(item, emoji);
        th_render_typeahead_item_called = true;
    });
    ct.content_highlighter_html(emoji);

    ct.get_or_set_completing_for_tests("mention");
    let th_render_person_called = false;
    override_rewire(typeahead_helper, "render_person", (person) => {
        assert.deepEqual(person, othello);
        th_render_person_called = true;
    });
    ct.content_highlighter_html(othello);

    let th_render_user_group_called = false;
    override_rewire(typeahead_helper, "render_user_group", (user_group) => {
        assert.deepEqual(user_group, backend);
        th_render_user_group_called = true;
    });
    ct.content_highlighter_html(backend);

    // We don't have any fancy rendering for slash commands yet.
    ct.get_or_set_completing_for_tests("slash");
    let th_render_slash_command_called = false;
    const me_slash = {
        text: "/me (Action message)",
    };
    override_rewire(typeahead_helper, "render_typeahead_item", (item) => {
        assert.deepEqual(item, {
            primary: "/me (Action message)",
        });
        th_render_slash_command_called = true;
    });
    ct.content_highlighter_html(me_slash);

    ct.get_or_set_completing_for_tests("stream");
    let th_render_stream_called = false;
    override_rewire(typeahead_helper, "render_stream", (stream) => {
        assert.deepEqual(stream, denmark_stream);
        th_render_stream_called = true;
    });
    ct.content_highlighter_html(denmark_stream);

    ct.get_or_set_completing_for_tests("syntax");
    th_render_typeahead_item_called = false;
    override_rewire(typeahead_helper, "render_typeahead_item", (item) => {
        assert.deepEqual(item, {primary: "py"});
        th_render_typeahead_item_called = true;
    });
    ct.content_highlighter_html("py");

    ct.get_or_set_completing_for_tests("something-else");
    assert.ok(!ct.content_highlighter_html());

    // Verify that all stub functions have been called.
    assert.ok(th_render_typeahead_item_called);
    assert.ok(th_render_person_called);
    assert.ok(th_render_user_group_called);
    assert.ok(th_render_stream_called);
    assert.ok(th_render_typeahead_item_called);
    assert.ok(th_render_slash_command_called);
});

test("filter_and_sort_mentions (normal)", () => {
    compose_state.set_message_type("stream");
    const is_silent = false;
    current_user.user_id = 101;
    let suggestions = ct.filter_and_sort_mentions(is_silent, "al");

    const mention_all = ct.broadcast_mentions()[0];
    const mention_all_item = user_or_mention_item(mention_all);
    assert.deepEqual(suggestions, [mention_all_item, ali_item, alice_item, hal_item, call_center]);

    // call_center group is shown in typeahead even when user is member of
    // one of the subgroups of can_mention_group.
    current_user.user_id = 104;
    suggestions = ct.filter_and_sort_mentions(is_silent, "al");
    assert.deepEqual(suggestions, [mention_all_item, ali_item, alice_item, hal_item, call_center]);

    // call_center group is not shown in typeahead when user is neither
    // a direct member of can_mention_group nor a member of any of its
    // recursive subgroups.
    current_user.user_id = 102;
    suggestions = ct.filter_and_sort_mentions(is_silent, "al");
    assert.deepEqual(suggestions, [mention_all_item, ali_item, alice_item, hal_item]);
});

test("filter_and_sort_mentions (silent)", () => {
    const is_silent = true;

    let suggestions = ct.filter_and_sort_mentions(is_silent, "al");

    assert.deepEqual(suggestions, [ali_item, alice_item, hal_item, call_center]);

    // call_center group is shown in typeahead irrespective of whether
    // user is member of can_mention_group or its subgroups for a
    // silent mention.
    current_user.user_id = 102;
    suggestions = ct.filter_and_sort_mentions(is_silent, "al");
    assert.deepEqual(suggestions, [ali_item, alice_item, hal_item, call_center]);
});

test("typeahead_results", () => {
    const stream_list = [
        denmark_stream,
        sweden_stream,
        netherland_stream,
        mobile_team_stream,
        mobile_stream,
    ];

    function compose_typeahead_results(completing, items, token) {
        return ct.filter_and_sort_candidates(completing, items, token);
    }

    function assert_emoji_matches(input, expected) {
        const returned = compose_typeahead_results("emoji", emoji_list, input);
        assert.deepEqual(returned, expected);
    }
    function assert_mentions_matches(input, expected) {
        const is_silent = false;
        const returned = ct.filter_and_sort_mentions(is_silent, input);
        assert.deepEqual(returned, expected);
    }
    function assert_stream_matches(input, expected) {
        const returned = compose_typeahead_results("stream", stream_list, input);
        assert.deepEqual(returned, expected);
    }

    function assert_slash_matches(input, expected) {
        const returned = compose_typeahead_results(
            "slash",
            composebox_typeahead.all_slash_commands,
            input,
        );
        assert.deepEqual(returned, expected);
    }
    assert_emoji_matches("da", [
        {
            emoji_name: "panda_face",
            emoji_code: "1f43c",
            reaction_type: "unicode_emoji",
            is_realm_emoji: false,
        },
        {
            emoji_name: "tada",
            emoji_code: "1f389",
            reaction_type: "unicode_emoji",
            is_realm_emoji: false,
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
        },
    ]);
    assert_emoji_matches("panda_", [
        {
            emoji_name: "panda_face",
            emoji_code: "1f43c",
            reaction_type: "unicode_emoji",
            is_realm_emoji: false,
        },
    ]);
    assert_emoji_matches("japanese_post_", [
        {
            emoji_name: "japanese_post_office",
            emoji_code: "1f3e3",
            reaction_type: "unicode_emoji",
            is_realm_emoji: false,
        },
    ]);
    assert_emoji_matches("japanese post ", [
        {
            emoji_name: "japanese_post_office",
            emoji_code: "1f3e3",
            reaction_type: "unicode_emoji",
            is_realm_emoji: false,
        },
    ]);
    assert_emoji_matches("notaemoji", []);

    // Autocomplete user mentions by user name.
    assert_mentions_matches("cordelia", [cordelia_item]);
    assert_mentions_matches("cordelia, le", [cordelia_item]);
    assert_mentions_matches("cordelia, le ", []);
    assert_mentions_matches("moor", [othello_item]);
    assert_mentions_matches("moor ", [othello_item]);
    assert_mentions_matches("moor of", [othello_item]);
    assert_mentions_matches("moor of ven", [othello_item]);
    assert_mentions_matches("oor", [othello_item]);
    assert_mentions_matches("oor ", []);
    assert_mentions_matches("oor o", []);
    assert_mentions_matches("oor of venice", []);
    assert_mentions_matches("King ", [hamlet_item, lear_item]);
    assert_mentions_matches("King H", [hamlet_item]);
    assert_mentions_matches("King L", [lear_item]);
    assert_mentions_matches("delia lear", []);
    assert_mentions_matches("Mark Tw", [twin1_item, twin2_item]);

    // Earlier user group and stream mentions were autocompleted by their
    // description too. This is now removed as it often led to unexpected
    // behaviour, and did not have any great discoverability advantage.
    current_user.user_id = 101;
    // Autocomplete user group mentions by group name.
    assert_mentions_matches("hamletchar", [hamletcharacters]);

    // Verify we're not matching on a terms that only appear in the description.
    assert_mentions_matches("characters of", []);

    // Verify we suggest only the first matching stream wildcard mention,
    // irrespective of how many equivalent stream wildcard mentions match.
    const mention_everyone = ct.broadcast_mentions()[1];
    const mention_everyone_item = user_or_mention_item(mention_everyone);
    // Here, we suggest only "everyone" instead of both the matching
    // "everyone" and "stream" wildcard mentions.
    assert_mentions_matches("e", [
        mention_everyone_item,
        hal_item,
        alice_item,
        cordelia_item,
        gael_item,
        hamlet_item,
        lear_item,
        othello_item,
        hamletcharacters,
        call_center,
    ]);

    // Verify we suggest both 'the first matching stream wildcard' and
    // 'topic wildcard' mentions. Not only one matching wildcard mention.
    const mention_topic = ct.broadcast_mentions()[4];
    const mention_topic_item = user_or_mention_item(mention_topic);
    // Here, we suggest both "everyone" and "topic".
    assert_mentions_matches("o", [
        othello_item,
        mention_everyone_item,
        mention_topic_item,
        cordelia_item,
    ]);

    // Autocomplete by slash commands.
    assert_slash_matches("me", [me_slash]);
    assert_slash_matches("dark", [dark_slash]);
    assert_slash_matches("night", [dark_slash]);
    assert_slash_matches("light", [light_slash]);
    assert_slash_matches("day", [light_slash]);

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
    assert_stream_matches("Mobile", [mobile_stream, mobile_team_stream]);
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
    const mention_all = ct.broadcast_mentions()[0];
    const mention_all_item = user_or_mention_item(mention_all);
    assert.deepEqual(results, [mention_all_item, call_center]);
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
