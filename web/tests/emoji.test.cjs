"use strict";

const assert = require("node:assert/strict");

const events = require("./lib/events.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

let is_emoji_supported_result = true;
mock_esm("is-emoji-supported", {
    isEmojiSupported: () => is_emoji_supported_result,
});

const emoji_codes = zrequire("../../static/generated/emoji/emoji_codes.json");
const {initialize_user_settings} = zrequire("user_settings");

const emoji = zrequire("emoji");

const user_settings = {};
initialize_user_settings({user_settings});

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
        emoji_code: "1f604",
        reaction_type: "unicode_emoji",
    });

    // Test adding an unicode_emoji.
    emoji_name = "smile";

    result = emoji.get_emoji_details_by_name(emoji_name);
    assert.deepEqual(result, {
        emoji_name: "smile",
        reaction_type: "unicode_emoji",
        emoji_code: "1f604",
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

run_test("get_native_emoji_info", ({override}) => {
    // get_native_emoji_info returns {unicode_emoji: char} when the emojiset
    // is "native" and the emoji is a supported Unicode emoji.

    const smile_details = {
        emoji_name: "smile",
        emoji_code: "1f604",
        reaction_type: "unicode_emoji",
    };

    // With emojiset="native" and a supported Unicode emoji, it should
    // return the Unicode character.
    override(user_settings, "emojiset", "native");
    is_emoji_supported_result = true;
    let result = emoji.get_native_emoji_info(smile_details);
    assert.deepEqual(result, {unicode_emoji: "\uD83D\uDE04"});

    // With emojiset="google" (non-native), it should return an empty object
    // even for a supported Unicode emoji.
    override(user_settings, "emojiset", "google");
    result = emoji.get_native_emoji_info(smile_details);
    assert.deepEqual(result, {});

    // With emojiset="text", it should return an empty object.
    override(user_settings, "emojiset", "text");
    result = emoji.get_native_emoji_info(smile_details);
    assert.deepEqual(result, {});

    // With emojiset="twitter", it should return an empty object.
    override(user_settings, "emojiset", "twitter");
    result = emoji.get_native_emoji_info(smile_details);
    assert.deepEqual(result, {});

    // With emojiset="native" but an unsupported emoji, it should return
    // an empty object.
    override(user_settings, "emojiset", "native");
    is_emoji_supported_result = false;
    result = emoji.get_native_emoji_info(smile_details);
    assert.deepEqual(result, {});

    // With emojiset="native" and a realm emoji (not unicode_emoji),
    // it should return an empty object regardless of support.
    is_emoji_supported_result = true;
    const realm_emoji_details = {
        emoji_name: "spain",
        emoji_code: "101",
        reaction_type: "realm_emoji",
        url: "/some/path/to/spain.gif",
    };
    result = emoji.get_native_emoji_info(realm_emoji_details);
    assert.deepEqual(result, {});

    // With emojiset="native" and a zulip_extra_emoji, it should
    // return an empty object.
    const zulip_emoji_details = {
        emoji_name: "zulip",
        emoji_code: "zulip",
        reaction_type: "zulip_extra_emoji",
        url: "/static/generated/emoji/images/emoji/unicode/zulip.png",
    };
    result = emoji.get_native_emoji_info(zulip_emoji_details);
    assert.deepEqual(result, {});

    // Multi-codepoint emoji (e.g., flags with dash-separated hex codes)
    // should produce the correct joined Unicode character.
    is_emoji_supported_result = true;
    const flag_details = {
        emoji_name: "united_states",
        emoji_code: "1f1fa-1f1f8",
        reaction_type: "unicode_emoji",
    };
    result = emoji.get_native_emoji_info(flag_details);
    assert.deepEqual(result, {unicode_emoji: "\uD83C\uDDFA\uD83C\uDDF8"});
});
