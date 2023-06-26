"use strict";

const {strict: assert} = require("assert");

const events = require("./lib/events");
const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");

const emoji_codes = zrequire("../../static/generated/emoji/emoji_codes.json");

const emoji = zrequire("emoji");

const realm_emoji = events.test_realm_emojis;

run_test("sanity check", () => {
    // Invalid emoji data
    emoji_codes.names = [...emoji_codes.names, "invalid_emoji"];
    blueslip.expect("error", "No codepoint for emoji name invalid_emoji");
    emoji.initialize({realm_emoji, emoji_codes});

    // Valid data
    emoji_codes.names = emoji_codes.names.filter((name) => name !== "invalid_emoji");
    emoji.initialize({realm_emoji, emoji_codes});
    assert.equal(emoji.get_server_realm_emoji_data(), realm_emoji);
});

run_test("get_canonical_name", () => {
    let canonical_name = emoji.get_canonical_name("green_tick");
    assert.equal(canonical_name, "green_tick");

    canonical_name = emoji.get_canonical_name("thumbs_up");
    assert.equal(canonical_name, "+1");

    canonical_name = emoji.get_canonical_name("+1");
    assert.equal(canonical_name, "+1");

    canonical_name = emoji.get_canonical_name("airplane");
    assert.equal(canonical_name, "airplane");

    canonical_name = emoji.get_canonical_name("non_existent");
    assert.equal(canonical_name, undefined);
});

run_test("get_emoji_* API", () => {
    assert.equal(emoji.get_emoji_name("1f384"), "holiday_tree");
    assert.equal(emoji.get_emoji_name("1f951"), "avocado");
    assert.equal(emoji.get_emoji_name("bogus"), undefined);

    assert.equal(emoji.get_emoji_codepoint("avocado"), "1f951");
    assert.equal(emoji.get_emoji_codepoint("holiday_tree"), "1f384");
    assert.equal(emoji.get_emoji_codepoint("bogus"), undefined);

    assert.equal(emoji.get_realm_emoji_url("spain"), "/some/path/to/spain.gif");
});

run_test("get_emoji_details_by_name", () => {
    let emoji_name = "smile";

    let result = emoji.get_emoji_details_by_name(emoji_name);
    assert.deepEqual(result, {
        emoji_name: "smile",
        emoji_code: "1f642",
        reaction_type: "unicode_emoji",
    });

    // Test adding an unicode_emoji.
    emoji_name = "smile";

    result = emoji.get_emoji_details_by_name(emoji_name);
    assert.deepEqual(result, {
        emoji_name: "smile",
        reaction_type: "unicode_emoji",
        emoji_code: "1f642",
    });

    // Test adding zulip emoji.
    emoji_name = "zulip";

    result = emoji.get_emoji_details_by_name(emoji_name);
    assert.deepEqual(result, {
        emoji_name: "zulip",
        reaction_type: "zulip_extra_emoji",
        emoji_code: "zulip",
        url: "/static/generated/emoji/images/emoji/unicode/zulip.png",
        still_url: null,
    });

    // Test adding realm emoji.
    emoji_name = "spain";

    emoji_name = emoji.get_emoji_details_by_name(emoji_name);
    assert.deepEqual(emoji_name, {
        emoji_name: "spain",
        reaction_type: "realm_emoji",
        emoji_code: "101",
        url: "/some/path/to/spain.gif",
        still_url: "/some/path/to/spain.png",
    });

    emoji_name = "green_tick";
    emoji_name = emoji.get_emoji_details_by_name(emoji_name);
    assert.deepEqual(emoji_name, {
        emoji_name: "green_tick",
        reaction_type: "realm_emoji",
        emoji_code: "102",
        url: "/some/path/to/emoji",
        still_url: null,
    });

    // Test sending without emoji name.
    assert.throws(
        () => {
            emoji.get_emoji_details_by_name();
        },
        {
            name: "Error",
            message: "Emoji name must be passed.",
        },
    );

    // Test sending an unknown emoji.
    emoji_name = "unknown-emoji";
    assert.throws(
        () => {
            emoji.get_emoji_details_by_name(emoji_name);
        },
        {
            name: "Error",
            message: "Bad emoji name: unknown-emoji",
        },
    );
});
