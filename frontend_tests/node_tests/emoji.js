"use strict";

const emoji_codes = zrequire("emoji_codes", "generated/emoji/emoji_codes.json");

const events = require("./lib/events.js");

const emoji = zrequire("emoji", "shared/js/emoji");

const realm_emoji = events.test_realm_emojis;

emoji.initialize({realm_emoji, emoji_codes});

run_test("sanity check", () => {
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

    assert.equal(emoji.get_realm_emoji_url("spain"), "/some/path/to/spain.png");
});
