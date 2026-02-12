"use strict";

/**
 * One-off script to populate unified_expected_output in markdown_test_cases.json.
 *
 * Run via: ./tools/test-js-with-node generate_unified_expected_output
 *
 * This reuses the test framework's module loading infrastructure and
 * the same test setup as markdown.test.cjs.
 */

const fs = require("node:fs");
const path = require("node:path");

const {make_realm} = require("./lib/example_realm.cjs");
const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

set_global("document", {compatMode: "CSS1Compat"});

mock_esm("../src/settings_data", {
    user_can_access_all_other_users: () => false,
});

const emoji = zrequire("emoji");
const emoji_codes = zrequire("../../static/generated/emoji/emoji_codes.json");
const linkifiers = zrequire("linkifiers");
const fenced_code = zrequire("fenced_code");
const markdown_config = zrequire("markdown_config");
const markdown = zrequire("markdown");
const {create_unified_processor} = zrequire("markdown_unified");
const people = zrequire("people");
const pygments_data = zrequire("pygments_data");
const {set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const user_groups = zrequire("user_groups");
const settings_config = zrequire("settings_config");
const {initialize_user_settings} = zrequire("user_settings");

const REALM_EMPTY_TOPIC_DISPLAY_NAME = "general chat";
set_realm(make_realm({realm_empty_topic_display_name: REALM_EMPTY_TOPIC_DISPLAY_NAME}));
const user_settings = {
    web_channel_default_view: settings_config.web_channel_default_view_values.channel_feed.code,
};
initialize_user_settings({user_settings});

const example_realm_linkifiers = [
    {
        pattern: "#(?P<id>[0-9]{2,8})",
        url_template: "https://trac.example.com/ticket/{id}",
        id: 1,
    },
    {
        pattern: "ZBUG_(?P<id>[0-9]{2,8})",
        url_template: "https://trac2.zulip.net/ticket/{id}",
        id: 2,
    },
    {
        pattern: "ZGROUP_(?P<id>[0-9]{2,8}):(?P<zone>[0-9]{1,8})",
        url_template: "https://zone_{zone}.zulip.net/ticket/{id}",
        id: 3,
    },
    {
        pattern:
            "FOO_(?P<id>[a-f]{5});(?P<zone>[a-f]);(?P<domain>[a-z]+);(?P<location>[a-z]+);(?P<name>[a-z]{2,8});(?P<chapter>[0-9]{2,3});(?P<fragment>[a-z]{2,8})",
        url_template:
            "https://zone_{zone}{.domain}.net/ticket{/location}{/id}{?name,chapter}{#fragment:5}",
        id: 4,
    },
];

const emoji_params = {
    realm_emoji: {
        1: {
            id: 1,
            name: "burrito",
            source_url: "/static/generated/emoji/images/emoji/burrito.png",
            deactivated: false,
        },
    },
    emoji_codes,
};

emoji.initialize(emoji_params);
fenced_code.initialize(pygments_data);

const cordelia = {
    full_name: "Cordelia, Lear's daughter",
    user_id: 101,
    email: "cordelia@zulip.com",
};
people.add_active_user(cordelia);
people.add_active_user({full_name: "Leo", user_id: 102, email: "leo@zulip.com"});
people.add_active_user({
    full_name: "Bobby <h1>Tables</h1>",
    user_id: 103,
    email: "bobby@zulip.com",
});
people.add_active_user({full_name: "Mark Twin", user_id: 104, email: "twin1@zulip.com"});
people.add_active_user({full_name: "Mark Twin", user_id: 105, email: "twin2@zulip.com"});
people.add_active_user({
    full_name: "Brother of Bobby|123",
    user_id: 106,
    email: "bobby2@zulip.com",
});
people.add_active_user({full_name: "& & &amp;", user_id: 107, email: "ampampamp@zulip.com"});
people.add_active_user({full_name: "Zoe", user_id: 7, email: "zoe@zulip.com"});
people.add_inaccessible_user(108);
people.initialize_current_user(cordelia.user_id);

user_groups.add({
    name: "hamletcharacters",
    id: 1,
    description: "Characters of Hamlet",
    members: [cordelia.user_id],
});
user_groups.add({name: "Backend", id: 2, description: "Backend team", members: []});
user_groups.add({
    name: "Bobby <h1>Tables</h1>",
    id: 3,
    description: "HTML syntax to check for Markdown edge cases.",
    members: [],
});
user_groups.add({name: "& & &amp;", id: 4, description: "Check ampersand escaping", members: []});

stream_data.add_sub_for_tests({
    subscribed: false,
    color: "blue",
    name: "Denmark",
    stream_id: 1,
    is_muted: true,
});
stream_data.add_sub_for_tests({
    subscribed: true,
    color: "red",
    name: "social",
    stream_id: 2,
    is_muted: false,
    invite_only: true,
});
stream_data.add_sub_for_tests({
    subscribed: true,
    color: "green",
    name: "Bobby <h1>Tables</h1>",
    stream_id: 3,
    is_muted: false,
});
stream_data.add_sub_for_tests({
    subscribed: true,
    color: "yellow",
    name: "Bobby <h1",
    stream_id: 4,
    is_muted: false,
});
stream_data.add_sub_for_tests({
    subscribed: true,
    color: "orange",
    name: "& & &amp;",
    stream_id: 5,
    is_muted: false,
});

markdown.initialize(markdown_config.get_helpers());
linkifiers.initialize(example_realm_linkifiers);

run_test("generate_unified_expected_output", ({override}) => {
    page_params.realm_users = [];
    linkifiers.update_linkifier_rules(example_realm_linkifiers);

    const fixtures_path = path.resolve(
        __dirname,
        "../../zerver/tests/fixtures/markdown_test_cases.json",
    );
    const markdown_test_cases = JSON.parse(fs.readFileSync(fixtures_path, "utf8"));
    const tests = markdown_test_cases.regular_tests;
    const unified = create_unified_processor();
    markdown.set_unified_processor(unified);

    let updated = 0;
    let already_passing = 0;

    for (const test of tests) {
        delete test.unified_expected_output;

        if (test.ignore === true || test.backend_only_rendering) {
            continue;
        }

        override(user_settings, "translate_emoticons", test.translate_emoticons || false);

        try {
            const message = markdown.render(test.input);
            const output = message.content;
            const expected = test.expected_output;

            if (output === expected) {
                already_passing += 1;
            } else {
                test.unified_expected_output = output;
                updated += 1;
            }
        } catch (error) {
            test.unified_expected_output = `ERROR: ${error.message}`;
            updated += 1;
        }
    }

    markdown.set_unified_processor(undefined);

    fs.writeFileSync(fixtures_path, JSON.stringify(markdown_test_cases, null, 2) + "\n");
    console.info(
        `\nWrote unified_expected_output: ${updated} divergent, ${already_passing} already passing.`,
    );
});
