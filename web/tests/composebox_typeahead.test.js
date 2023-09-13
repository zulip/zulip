"use strict";

const {strict: assert} = require("assert");

const {mock_stream_header_colorblock} = require("./lib/compose");
const {mock_banners} = require("./lib/compose_banner");
const {mock_esm, set_global, with_overrides, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {page_params, user_settings} = require("./lib/zpage_params");

const noop = () => {};

let autosize_called;

mock_esm("../src/compose_ui", {
    autosize_textarea() {
        autosize_called = true;
    },
});
const compose_validate = mock_esm("../src/compose_validate", {
    validate_message_length: () => true,
    warn_if_topic_resolved: noop,
    wildcard_mention_allowed: () => true,
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
const typeahead_helper = zrequire("typeahead_helper");
const muted_users = zrequire("muted_users");
const people = zrequire("people");
const user_groups = zrequire("user_groups");
const stream_data = zrequire("stream_data");
const stream_list_sort = zrequire("stream_list_sort");
const compose = zrequire("compose");
const compose_pm_pill = zrequire("compose_pm_pill");
const compose_recipient = zrequire("compose_recipient");
const composebox_typeahead = zrequire("composebox_typeahead");
const settings_config = zrequire("settings_config");
const pygments_data = zrequire("../generated/pygments_data.json");

const ct = composebox_typeahead;

// Use a slightly larger value than what's user-facing
// to facilitate testing different combinations of
// broadcast-mentions/persons/groups.
ct.__Rewire__("max_num_items", 15);

run_test("verify wildcard mentions typeahead for stream message", () => {
    const mention_all = ct.broadcast_mentions()[0];
    const mention_everyone = ct.broadcast_mentions()[1];
    const mention_stream = ct.broadcast_mentions()[2];
    assert.equal(mention_all.email, "all");
    assert.equal(mention_all.full_name, "all");
    assert.equal(mention_everyone.email, "everyone");
    assert.equal(mention_everyone.full_name, "everyone");
    assert.equal(mention_stream.email, "stream");
    assert.equal(mention_stream.full_name, "stream");

    assert.equal(mention_all.special_item_text, "all (translated: Notify stream)");
    assert.equal(mention_everyone.special_item_text, "everyone (translated: Notify stream)");
    assert.equal(mention_stream.special_item_text, "stream (translated: Notify stream)");

    compose_validate.wildcard_mention_allowed = () => false;
    const mentionNobody = ct.broadcast_mentions();
    assert.equal(mentionNobody.length, 0);
    compose_validate.wildcard_mention_allowed = () => true;
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
const emoji_list = [...emojis_by_name.values()].map((emoji_dict) => ({
    emoji_name: emoji_dict.name,
    emoji_code: emoji_dict.emoji_code,
    reaction_type: "unicode_emoji",
    is_realm_emoji: false,
}));

const me_slash = {
    name: "me",
    aliases: "",
    text: "translated: /me is excited (Display action text)",
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

const emoji_codes = {
    name_to_codepoint,
    names: [...emojis_by_name.keys()],
    emoji_catalog: {},
    emoticon_conversions: {},
    codepoint_to_name: {},
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

const ali = {
    email: "ali@zulip.com",
    user_id: 98,
    full_name: "Ali",
};

const alice = {
    email: "alice@zulip.com",
    user_id: 99,
    full_name: "Alice",
};

const hamlet = {
    email: "hamlet@zulip.com",
    user_id: 100,
    full_name: "King Hamlet",
};

const othello = {
    email: "othello@zulip.com",
    user_id: 101,
    full_name: "Othello, the Moor of Venice",
};
const cordelia = {
    email: "cordelia@zulip.com",
    user_id: 102,
    full_name: "Cordelia, Lear's daughter",
};
const deactivated_user = {
    email: "other@zulip.com",
    user_id: 103,
    full_name: "Deactivated User",
};
const lear = {
    email: "lear@zulip.com",
    user_id: 104,
    full_name: "King Lear",
};

const twin1 = {
    full_name: "Mark Twin",
    user_id: 105,
    email: "twin1@zulip.com",
};

const twin2 = {
    full_name: "Mark Twin",
    user_id: 106,
    email: "twin2@zulip.com",
};

const gael = {
    full_name: "Gaël Twin",
    user_id: 107,
    email: "twin3@zulip.com",
};

const hal = {
    full_name: "Earl Hal",
    user_id: 108,
    email: "hal@zulip.com",
};

const harry = {
    full_name: "Harry",
    user_id: 109,
    email: "harry@zulip.com",
};

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
    const fake_this = {
        query: "",
        $element: {},
    };
    let caret_called1 = false;
    let caret_called2 = false;
    fake_this.$element.caret = function (...args) {
        if (args.length === 0) {
            // .caret() used in split_at_cursor
            caret_called1 = true;
            return fake_this.query.length;
        }
        const [arg1, arg2] = args;
        // .caret() used in setTimeout
        assert.equal(arg1, arg2);
        caret_called2 = true;
        return this;
    };
    let range_called = false;
    fake_this.$element.range = function (...args) {
        const [arg1, arg2] = args;
        // .range() used in setTimeout
        assert.ok(arg2 > arg1);
        range_called = true;
        return this;
    };
    autosize_called = false;
    set_timeout_called = false;

    // emoji
    fake_this.completing = "emoji";
    fake_this.query = ":octo";
    fake_this.token = "octo";
    const item = {
        emoji_name: "octopus",
    };

    let actual_value = ct.content_typeahead_selected.call(fake_this, item);
    let expected_value = ":octopus: ";
    assert.equal(actual_value, expected_value);

    fake_this.query = " :octo";
    fake_this.token = "octo";
    actual_value = ct.content_typeahead_selected.call(fake_this, item);
    expected_value = " :octopus: ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "{:octo";
    fake_this.token = "octo";
    actual_value = ct.content_typeahead_selected.call(fake_this, item);
    expected_value = "{ :octopus: ";
    assert.equal(actual_value, expected_value);

    // mention
    fake_this.completing = "mention";

    override(compose_validate, "warn_if_mentioning_unsubscribed_user", () => {});

    fake_this.query = "@**Mark Tw";
    fake_this.token = "Mark Tw";
    actual_value = ct.content_typeahead_selected.call(fake_this, twin1);
    expected_value = "@**Mark Twin|105** ";
    assert.equal(actual_value, expected_value);

    let warned_for_mention = false;
    override(compose_validate, "warn_if_mentioning_unsubscribed_user", (mentioned) => {
        assert.equal(mentioned, othello);
        warned_for_mention = true;
    });

    fake_this.query = "@oth";
    fake_this.token = "oth";
    actual_value = ct.content_typeahead_selected.call(fake_this, othello);
    expected_value = "@**Othello, the Moor of Venice** ";
    assert.equal(actual_value, expected_value);
    assert.ok(warned_for_mention);

    fake_this.query = "Hello @oth";
    fake_this.token = "oth";
    actual_value = ct.content_typeahead_selected.call(fake_this, othello);
    expected_value = "Hello @**Othello, the Moor of Venice** ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "@**oth";
    fake_this.token = "oth";
    actual_value = ct.content_typeahead_selected.call(fake_this, othello);
    expected_value = "@**Othello, the Moor of Venice** ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "@*oth";
    fake_this.token = "oth";
    actual_value = ct.content_typeahead_selected.call(fake_this, othello);
    expected_value = "@**Othello, the Moor of Venice** ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "@back";
    fake_this.token = "back";
    with_overrides(({disallow}) => {
        disallow(compose_validate, "warn_if_mentioning_unsubscribed_user");
        actual_value = ct.content_typeahead_selected.call(fake_this, backend);
    });
    expected_value = "@*Backend* ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "@*back";
    fake_this.token = "back";
    actual_value = ct.content_typeahead_selected.call(fake_this, backend);
    expected_value = "@*Backend* ";
    assert.equal(actual_value, expected_value);

    // silent mention
    fake_this.completing = "silent_mention";
    fake_this.query = "@_kin";
    fake_this.token = "kin";
    with_overrides(({disallow}) => {
        disallow(compose_validate, "warn_if_mentioning_unsubscribed_user");
        actual_value = ct.content_typeahead_selected.call(fake_this, hamlet);
    });

    expected_value = "@_**King Hamlet** ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "Hello @_kin";
    fake_this.token = "kin";
    actual_value = ct.content_typeahead_selected.call(fake_this, hamlet);
    expected_value = "Hello @_**King Hamlet** ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "@_*kin";
    fake_this.token = "kin";
    actual_value = ct.content_typeahead_selected.call(fake_this, hamlet);
    expected_value = "@_**King Hamlet** ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "@_**kin";
    fake_this.token = "kin";
    actual_value = ct.content_typeahead_selected.call(fake_this, hamlet);
    expected_value = "@_**King Hamlet** ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "@_back";
    fake_this.token = "back";
    with_overrides(({disallow}) => {
        disallow(compose_validate, "warn_if_mentioning_unsubscribed_user");
        actual_value = ct.content_typeahead_selected.call(fake_this, backend);
    });
    expected_value = "@_*Backend* ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "@_*back";
    fake_this.token = "back";
    actual_value = ct.content_typeahead_selected.call(fake_this, backend);
    expected_value = "@_*Backend* ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "/m";
    fake_this.completing = "slash";
    actual_value = ct.content_typeahead_selected.call(fake_this, me_slash);
    expected_value = "/me ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "/da";
    fake_this.completing = "slash";
    actual_value = ct.content_typeahead_selected.call(fake_this, dark_slash);
    expected_value = "/dark ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "/ni";
    fake_this.completing = "slash";
    actual_value = ct.content_typeahead_selected.call(fake_this, dark_slash);
    expected_value = "/dark ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "/li";
    fake_this.completing = "slash";
    actual_value = ct.content_typeahead_selected.call(fake_this, light_slash);
    expected_value = "/light ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "/da";
    fake_this.completing = "slash";
    actual_value = ct.content_typeahead_selected.call(fake_this, light_slash);
    expected_value = "/light ";
    assert.equal(actual_value, expected_value);

    // stream
    fake_this.completing = "stream";
    let warned_for_stream_link = false;
    override(compose_validate, "warn_if_private_stream_is_linked", (linked_stream) => {
        assert.equal(linked_stream, sweden_stream);
        warned_for_stream_link = true;
    });

    fake_this.query = "#swed";
    fake_this.token = "swed";
    actual_value = ct.content_typeahead_selected.call(fake_this, sweden_stream);
    expected_value = "#**Sweden** ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "Hello #swed";
    fake_this.token = "swed";
    actual_value = ct.content_typeahead_selected.call(fake_this, sweden_stream);
    expected_value = "Hello #**Sweden** ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "#**swed";
    fake_this.token = "swed";
    actual_value = ct.content_typeahead_selected.call(fake_this, sweden_stream);
    expected_value = "#**Sweden** ";
    assert.equal(actual_value, expected_value);

    // topic_list
    fake_this.completing = "topic_list";

    fake_this.query = "Hello #**Sweden>test";
    fake_this.token = "test";
    actual_value = ct.content_typeahead_selected.call(fake_this, "testing");
    expected_value = "Hello #**Sweden>testing** ";
    assert.equal(actual_value, expected_value);

    fake_this.query = "Hello #**Sweden>";
    fake_this.token = "";
    actual_value = ct.content_typeahead_selected.call(fake_this, "testing");
    expected_value = "Hello #**Sweden>testing** ";
    assert.equal(actual_value, expected_value);

    // syntax
    fake_this.completing = "syntax";

    fake_this.query = "~~~p";
    fake_this.token = "p";
    actual_value = ct.content_typeahead_selected.call(fake_this, "python");
    expected_value = "~~~python\n\n~~~";
    assert.equal(actual_value, expected_value);

    fake_this.query = "Hello ~~~p";
    fake_this.token = "p";
    actual_value = ct.content_typeahead_selected.call(fake_this, "python");
    expected_value = "Hello ~~~python\n\n~~~";
    assert.equal(actual_value, expected_value);

    fake_this.query = "```p";
    fake_this.token = "p";
    actual_value = ct.content_typeahead_selected.call(fake_this, "python");
    expected_value = "```python\n\n```";
    assert.equal(actual_value, expected_value);

    fake_this.query = "```spo";
    fake_this.token = "spo";
    actual_value = ct.content_typeahead_selected.call(fake_this, "spoiler");
    expected_value = "```spoiler translated: Header\n\n```";
    assert.equal(actual_value, expected_value);

    // Test special case to not close code blocks if there is text afterward
    fake_this.query = "```p\nsome existing code";
    fake_this.token = "p";
    fake_this.$element.caret = () => 4; // Put cursor right after ```p
    actual_value = ct.content_typeahead_selected.call(fake_this, "python");
    expected_value = "```python\nsome existing code";
    assert.equal(actual_value, expected_value);

    fake_this.completing = "something-else";

    fake_this.query = "foo";
    actual_value = ct.content_typeahead_selected.call(fake_this, {});
    expected_value = fake_this.query;
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
    mock_stream_header_colorblock();
    mock_banners();
    override_rewire(compose_recipient, "on_compose_select_recipient_update", noop);

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
    override(stream_topic_history_util, "get_server_history", () => {});

    let topic_typeahead_called = false;
    $("#stream_message_recipient_topic").typeahead = (options) => {
        override_rewire(stream_topic_history, "get_recent_topic_names", (stream_id) => {
            assert.equal(stream_id, sweden_stream.stream_id);
            return sweden_topics_to_show;
        });

        compose_state.set_stream_id(sweden_stream.stream_id);
        let actual_value = options.source();
        // Topics should be sorted alphabetically, not by addition order.
        let expected_value = sweden_topics_to_show;
        assert.deepEqual(actual_value, expected_value);

        // options.highlighter()
        options.query = "Kro";
        actual_value = options.highlighter("kronor");
        expected_value = "<strong>kronor</strong>";
        assert.equal(actual_value, expected_value);

        // Highlighted content should be escaped.
        options.query = "<";
        actual_value = options.highlighter("<&>");
        expected_value = "<strong>&lt;&amp;&gt;</strong>";
        assert.equal(actual_value, expected_value);

        options.query = "even m";
        actual_value = options.highlighter("even more ice");
        expected_value = "<strong>even more ice</strong>";
        assert.equal(actual_value, expected_value);

        // options.sorter()
        //
        // Notice that alphabetical sorting isn't managed by this sorter,
        // it is a result of the topics already being sorted after adding
        // them with add_topic().
        options.query = "furniture";
        actual_value = options.sorter(["furniture"]);
        expected_value = ["furniture"];
        assert.deepEqual(actual_value, expected_value);

        // A literal match at the beginning of an element puts it at the top.
        options.query = "ice";
        actual_value = options.sorter(["even more ice", "ice", "more ice"]);
        expected_value = ["ice", "even more ice", "more ice"];
        assert.deepEqual(actual_value, expected_value);

        // The sorter should return the query as the first element if there
        // isn't a topic with such name.
        // This only happens if typeahead is providing other suggestions.
        options.query = "e"; // Letter present in "furniture" and "ice"
        actual_value = options.sorter(["furniture", "ice"]);
        expected_value = ["e", "furniture", "ice"];
        assert.deepEqual(actual_value, expected_value);

        // Don't make any suggestions if this query doesn't match any
        // existing topic.
        options.query = "non-existing-topic";
        actual_value = options.sorter([]);
        expected_value = [];
        assert.deepEqual(actual_value, expected_value);

        topic_typeahead_called = true;

        // Unset the stream.
        compose_state.set_stream_id("");
    };

    let pm_recipient_typeahead_called = false;
    $("#private_message_recipient").typeahead = (options) => {
        pill_items = [];

        // This should match the users added at the beginning of this test file.
        let actual_value = options.source("");
        let expected_value = [
            ali,
            alice,
            cordelia,
            hal,
            gael,
            harry,
            hamlet,
            lear,
            twin1,
            twin2,
            othello,
            hamletcharacters,
            backend,
            call_center,
        ];
        actual_value.sort((a, b) => a.user_id - b.user_id);
        expected_value.sort((a, b) => a.user_id - b.user_id);
        assert.deepEqual(actual_value, expected_value);

        function matcher(query, person) {
            query = typeahead.clean_query_lowercase(query);
            return ct.query_matches_person(query, person);
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
        actual_value = sorter(query, [othello]);
        expected_value = [othello];
        assert.deepEqual(actual_value, expected_value);

        query = "Ali";
        actual_value = sorter(query, [alice, ali]);
        expected_value = [ali, alice];
        assert.deepEqual(actual_value, expected_value);

        // A literal match at the beginning of an element puts it at the top.
        query = "co"; // Matches everything ("x@zulip.COm")
        actual_value = sorter(query, [othello, deactivated_user, cordelia]);
        expected_value = [cordelia, deactivated_user, othello];
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

        pill_items = [{user_id: lear.user_id}];
        appended_names = [];
        cleared = false;
        options.updater(hamletcharacters, event);
        assert.deepEqual(appended_names, []);
        assert.ok(cleared);

        pm_recipient_typeahead_called = true;
    };

    let compose_textarea_typeahead_called = false;
    $("#compose-textarea").typeahead = (options) => {
        // options.source()
        //
        // For now we only test that get_sorted_filtered_items has been
        // properly set as the .source(). All its features are tested later on
        // in test_begins_typeahead().
        let fake_this = {
            $element: {},
        };
        let caret_called = false;
        fake_this.$element.caret = () => {
            caret_called = true;
            return 7;
        };
        fake_this.$element.closest = () => [];
        fake_this.options = options;
        let actual_value = options.source.call(fake_this, "test #s");
        assert.deepEqual(sorted_names_from(actual_value), ["Sweden", "The Netherlands"]);
        assert.ok(caret_called);

        othello.delivery_email = "othello@zulip.com";
        // options.highlighter()
        //
        // Again, here we only verify that the highlighter has been set to
        // content_highlighter.
        fake_this = {completing: "mention", token: "othello"};
        actual_value = options.highlighter.call(fake_this, othello);
        expected_value =
            `    <span class="user_circle_empty user_circle"></span>\n` +
            `    <img class="typeahead-image" src="http://zulip.zulipdev.com/avatar/${othello.user_id}?s&#x3D;50" />\n` +
            `<strong>Othello, the Moor of Venice</strong>&nbsp;&nbsp;\n` +
            `<small class="autocomplete_secondary">othello@zulip.com</small>\n`;
        assert.equal(actual_value, expected_value);
        // Reset the email such that this does not affect further tests.
        othello.delivery_email = null;

        fake_this = {completing: "mention", token: "hamletcharacters"};
        actual_value = options.highlighter.call(fake_this, hamletcharacters);
        expected_value =
            '    <i class="typeahead-image icon fa fa-group no-presence-circle" aria-hidden="true"></i>\n<strong>hamletcharacters</strong>&nbsp;&nbsp;\n<small class="autocomplete_secondary">Characters of Hamlet</small>\n';
        assert.equal(actual_value, expected_value);

        // matching

        function match(fake_this, item) {
            const token = fake_this.token;
            const completing = fake_this.completing;

            return ct.compose_content_matcher(completing, token)(item);
        }

        fake_this = {completing: "emoji", token: "ta"};
        assert.equal(match(fake_this, make_emoji(emoji_tada)), true);
        assert.equal(match(fake_this, make_emoji(emoji_moneybag)), false);

        fake_this = {completing: "stream", token: "swed"};
        assert.equal(match(fake_this, sweden_stream), true);
        assert.equal(match(fake_this, denmark_stream), false);

        fake_this = {completing: "syntax", token: "py"};
        assert.equal(match(fake_this, "python"), true);
        assert.equal(match(fake_this, "javascript"), false);

        fake_this = {completing: "non-existing-completion"};
        assert.equal(match(fake_this), undefined);

        function sort_items(fake_this, item) {
            const token = fake_this.token;
            const completing = fake_this.completing;

            return ct.sort_results(completing, item, token);
        }

        // options.sorter()
        fake_this = {completing: "emoji", token: "ta"};
        actual_value = sort_items(fake_this, [make_emoji(emoji_stadium), make_emoji(emoji_tada)]);
        expected_value = [make_emoji(emoji_tada), make_emoji(emoji_stadium)];
        assert.deepEqual(actual_value, expected_value);

        fake_this = {completing: "emoji", token: "th"};
        actual_value = sort_items(fake_this, [
            make_emoji(emoji_thermometer),
            make_emoji(emoji_thumbs_up),
        ]);
        expected_value = [make_emoji(emoji_thumbs_up), make_emoji(emoji_thermometer)];
        assert.deepEqual(actual_value, expected_value);

        fake_this = {completing: "emoji", token: "he"};
        actual_value = sort_items(fake_this, [
            make_emoji(emoji_headphones),
            make_emoji(emoji_heart),
        ]);
        expected_value = [make_emoji(emoji_heart), make_emoji(emoji_headphones)];
        assert.deepEqual(actual_value, expected_value);

        fake_this = {completing: "slash", token: "m"};
        actual_value = sort_items(fake_this, [my_slash, me_slash]);
        expected_value = [me_slash, my_slash];
        assert.deepEqual(actual_value, expected_value);

        fake_this = {completing: "slash", token: "da"};
        actual_value = sort_items(fake_this, [dark_slash, light_slash]);
        expected_value = [dark_slash, light_slash];
        assert.deepEqual(actual_value, expected_value);

        fake_this = {completing: "stream", token: "de"};
        actual_value = sort_items(fake_this, [sweden_stream, denmark_stream]);
        expected_value = [denmark_stream, sweden_stream];
        assert.deepEqual(actual_value, expected_value);

        // Matches in the descriptions affect the order as well.
        // Testing "co" for "cold", in both streams' description. It's at the
        // beginning of Sweden's description, so that one should go first.
        fake_this = {completing: "stream", token: "co"};
        actual_value = sort_items(fake_this, [denmark_stream, sweden_stream]);
        expected_value = [sweden_stream, denmark_stream];
        assert.deepEqual(actual_value, expected_value);

        fake_this = {completing: "syntax", token: "ap"};
        actual_value = sort_items(fake_this, ["abap", "applescript"]);
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
        fake_this = {completing: "stream", token: "s"};
        actual_value = sort_items(fake_this, [sweden_stream, serbia_stream]);
        expected_value = [sweden_stream, serbia_stream];
        assert.deepEqual(actual_value, expected_value);
        // Subscribed stream is inactive
        override(
            user_settings,
            "demote_inactive_streams",
            settings_config.demote_inactive_streams_values.always.code,
        );

        stream_list_sort.set_filter_out_inactives();
        actual_value = sort_items(fake_this, [sweden_stream, serbia_stream]);
        expected_value = [sweden_stream, serbia_stream];
        assert.deepEqual(actual_value, expected_value);

        fake_this = {completing: "stream", token: "ser"};
        actual_value = sort_items(fake_this, [denmark_stream, serbia_stream]);
        expected_value = [serbia_stream, denmark_stream];
        assert.deepEqual(actual_value, expected_value);

        fake_this = {completing: "non-existing-completion"};
        assert.equal(sort_items(fake_this), undefined);

        compose_textarea_typeahead_called = true;
    };

    user_settings.enter_sends = false;
    let compose_finish_called = false;
    override_rewire(compose, "finish", () => {
        compose_finish_called = true;
    });

    ct.initialize({
        on_enter_send: compose.finish,
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

    // Set up jquery functions used in compose_textarea Enter
    // handler.
    let range_length = 0;
    $("#compose-textarea").range = () => ({
        length: range_length,
        range: noop,
        start: 0,
        end: 0 + range_length,
    });
    $("#compose-textarea").caret = noop;

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

    // Cover case where there's a least one character there.
    range_length = 2;
    $("form#send_message_form").trigger(event);

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
    $("#stream_message_recipient_topic").off("mouseup");
    event.type = "keyup";
    $("form#send_message_form").trigger(event);
    event.key = "Tab";
    event.shiftKey = false;
    $("form#send_message_form").trigger(event);
    event.key = "a";
    $("form#send_message_form").trigger(event);

    $("#stream_message_recipient_topic").off("focus");
    $("#private_message_recipient").off("focus");
    $("form#send_message_form").off("keydown");
    $("form#send_message_form").off("keyup");
    $("#private_message_recipient").off("blur");
    $("#send_later").css = noop;
    ct.initialize({
        on_enter_send: compose.finish,
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
    override(stream_topic_history_util, "get_server_history", () => {});

    const begin_typehead_this = {
        options: {
            completions: {
                emoji: true,
                mention: true,
                silent_mention: true,
                slash: true,
                stream: true,
                syntax: true,
                topic: true,
                timestamp: true,
            },
        },
    };

    function get_values(input, rest) {
        // Stub out split_at_cursor that uses $(':focus')
        override_rewire(ct, "split_at_cursor", () => [input, rest]);
        const values = ct.get_candidates.call(begin_typehead_this, input);
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
    assert.equal(ct.tokenize_compose_str("foo #streams@foo"), "#streams@foo");
});

test("content_highlighter", ({override_rewire}) => {
    let fake_this = {completing: "emoji"};
    const emoji = {emoji_name: "person shrugging", emoji_url: "¯\\_(ツ)_/¯"};
    let th_render_typeahead_item_called = false;
    override_rewire(typeahead_helper, "render_emoji", (item) => {
        assert.deepEqual(item, emoji);
        th_render_typeahead_item_called = true;
    });
    ct.content_highlighter.call(fake_this, emoji);

    fake_this = {completing: "mention"};
    let th_render_person_called = false;
    override_rewire(typeahead_helper, "render_person", (person) => {
        assert.deepEqual(person, othello);
        th_render_person_called = true;
    });
    ct.content_highlighter.call(fake_this, othello);

    let th_render_user_group_called = false;
    override_rewire(typeahead_helper, "render_user_group", (user_group) => {
        assert.deepEqual(user_group, backend);
        th_render_user_group_called = true;
    });
    ct.content_highlighter.call(fake_this, backend);

    // We don't have any fancy rendering for slash commands yet.
    fake_this = {completing: "slash"};
    let th_render_slash_command_called = false;
    const me_slash = {
        text: "/me is excited (Display action text)",
    };
    override_rewire(typeahead_helper, "render_typeahead_item", (item) => {
        assert.deepEqual(item, {
            primary: "/me is excited (Display action text)",
        });
        th_render_slash_command_called = true;
    });
    ct.content_highlighter.call(fake_this, me_slash);

    fake_this = {completing: "stream"};
    let th_render_stream_called = false;
    override_rewire(typeahead_helper, "render_stream", (stream) => {
        assert.deepEqual(stream, denmark_stream);
        th_render_stream_called = true;
    });
    ct.content_highlighter.call(fake_this, denmark_stream);

    fake_this = {completing: "syntax"};
    th_render_typeahead_item_called = false;
    override_rewire(typeahead_helper, "render_typeahead_item", (item) => {
        assert.deepEqual(item, {primary: "py"});
        th_render_typeahead_item_called = true;
    });
    ct.content_highlighter.call(fake_this, "py");

    fake_this = {completing: "something-else"};
    assert.ok(!ct.content_highlighter.call(fake_this));

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
    page_params.user_id = 101;
    let suggestions = ct.filter_and_sort_mentions(is_silent, "al");

    const mention_all = ct.broadcast_mentions()[0];
    assert.deepEqual(suggestions, [mention_all, ali, alice, hal, call_center]);

    // call_center group is shown in typeahead even when user is member of
    // one of the subgroups of can_mention_group.
    page_params.user_id = 104;
    suggestions = ct.filter_and_sort_mentions(is_silent, "al");
    assert.deepEqual(suggestions, [mention_all, ali, alice, hal, call_center]);

    // call_center group is not shown in typeahead when user is neither
    // a direct member of can_mention_group nor a member of any of its
    // recursive subgroups.
    page_params.user_id = 102;
    suggestions = ct.filter_and_sort_mentions(is_silent, "al");
    assert.deepEqual(suggestions, [mention_all, ali, alice, hal]);
});

test("filter_and_sort_mentions (silent)", () => {
    const is_silent = true;

    let suggestions = ct.filter_and_sort_mentions(is_silent, "al");

    assert.deepEqual(suggestions, [ali, alice, hal, call_center]);

    // call_center group is shown in typeahead irrespective of whether
    // user is member of can_mention_group or its subgroups for a
    // silent mention.
    page_params.user_id = 102;
    suggestions = ct.filter_and_sort_mentions(is_silent, "al");
    assert.deepEqual(suggestions, [ali, alice, hal, call_center]);
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
            emoji_name: "tada",
            emoji_code: "1f389",
            reaction_type: "unicode_emoji",
            is_realm_emoji: false,
        },
        {
            emoji_name: "panda_face",
            emoji_code: "1f43c",
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
    assert_mentions_matches("cordelia", [cordelia]);
    assert_mentions_matches("cordelia, le", [cordelia]);
    assert_mentions_matches("cordelia, le ", []);
    assert_mentions_matches("moor", [othello]);
    assert_mentions_matches("moor ", [othello]);
    assert_mentions_matches("moor of", [othello]);
    assert_mentions_matches("moor of ven", [othello]);
    assert_mentions_matches("oor", [othello]);
    assert_mentions_matches("oor ", []);
    assert_mentions_matches("oor o", []);
    assert_mentions_matches("oor of venice", []);
    assert_mentions_matches("King ", [hamlet, lear]);
    assert_mentions_matches("King H", [hamlet]);
    assert_mentions_matches("King L", [lear]);
    assert_mentions_matches("delia lear", []);
    assert_mentions_matches("Mark Tw", [twin1, twin2]);

    // Earlier user group and stream mentions were autocompleted by their
    // description too. This is now removed as it often led to unexpected
    // behaviour, and did not have any great discoverability advantage.
    page_params.user_id = 101;
    // Autocomplete user group mentions by group name.
    assert_mentions_matches("hamletchar", [hamletcharacters]);

    // Verify we're not matching on a terms that only appear in the description.
    assert_mentions_matches("characters of", []);

    // Verify we suggest only the first matching wildcard mention,
    // irrespective of how many equivalent wildcard mentions match.
    const mention_everyone = ct.broadcast_mentions()[1];
    // Here, we suggest only "everyone" instead of both the matching
    // "everyone" and "stream" wildcard mentions.
    assert_mentions_matches("e", [
        mention_everyone,
        hal,
        alice,
        cordelia,
        gael,
        hamlet,
        lear,
        othello,
        hamletcharacters,
        call_center,
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
        We will simulate that we talk to Hal and Harry,
        while we don't talk to King Hamlet.  This will
        knock King Hamlet out of consideration in the
        filtering pass.  Then Hal will be truncated in
        the sorting step.
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
    assert.deepEqual(results, [harry, hamletcharacters]);

    // Now let's exclude Hal.
    user_ids = [hamlet.user_id, harry.user_id];

    results = ct.get_person_suggestions("Ha", opts);
    assert.deepEqual(results, [harry, hamletcharacters]);

    user_ids = [hamlet.user_id, harry.user_id, hal.user_id];

    results = ct.get_person_suggestions("Ha", opts);
    assert.deepEqual(results, [harry, hamletcharacters]);

    people.deactivate(harry);
    results = ct.get_person_suggestions("Ha", opts);
    // harry is excluded since it has been deactivated.
    assert.deepEqual(results, [hamletcharacters, hal]);
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
    assert.deepEqual(results, [cordelia]);

    // Mute Cordelia, and test that she's excluded from results.
    muted_users.add_muted_user(cordelia.user_id);
    results = ct.get_person_suggestions("corde", opts);
    assert.deepEqual(results, []);

    // Make sure our muting logic doesn't break wildcard mentions
    // or user group mentions.
    results = ct.get_person_suggestions("all", opts);
    const mention_all = ct.broadcast_mentions()[0];
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
    mock_stream_header_colorblock();
    mock_banners();
    override_rewire(compose_recipient, "on_compose_select_recipient_update", () => {});

    // When viewing no stream, sorting is alphabetical
    compose_state.set_stream_id("");
    results = ct.get_pm_people("li");
    assert.deepEqual(results, [ali, alice, cordelia]);

    // When viewing denmark stream, subscriber cordelia is placed higher
    compose_state.set_stream_id(denmark_stream.stream_id);
    results = ct.get_pm_people("li");
    assert.deepEqual(results, [cordelia, ali, alice]);

    // Simulating just alice being subscribed to denmark.
    override_rewire(
        stream_data,
        "is_user_subscribed",
        (stream_id, user_id) => stream_id === denmark_stream.stream_id && user_id === alice.user_id,
    );

    // When viewing denmark stream to which alice is subscribed, ali is not
    // 1st despite having an exact name match with the query.
    results = ct.get_pm_people("ali");
    assert.deepEqual(results, [alice, ali]);
});
