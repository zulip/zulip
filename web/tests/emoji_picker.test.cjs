"use strict";

const assert = require("node:assert/strict");

const _ = require("lodash");

const {make_user} = require("./lib/example_user.cjs");
const {zrequire, mock_esm} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const emoji = zrequire("emoji");
const emoji_picker = zrequire("emoji_picker");

const emoji_codes = zrequire("../../static/generated/emoji/emoji_codes.json");
const people = zrequire("people");
const {set_current_user} = zrequire("state_data");

function noop() {}

const reactions = mock_esm("../../web/src/reactions", {
    get_frequently_used_emojis_for_user_ajax: noop,
});

people.init(); // Sometimes necessary to reset state for each test

const user = make_user({
    user_id: 22,
    email: "alice@example.com",
    full_name: "Alice",
});
people.add_active_user(user);

set_current_user(user);

people.add_valid_user_id(user.user_id);

run_test("initialize", async () => {
    reactions.get_frequently_used_emojis_for_user_ajax = () =>
        Promise.resolve(["+1", "tada", "slight_smile", "heart", "working_on_it", "octopus"]);
    emoji.initialize({
        realm_emoji: {},
        emoji_codes,
    });

    await emoji_picker.initialize();
    const complete_emoji_catalog = _.sortBy(emoji_picker.complete_emoji_catalog, "name");
    assert.equal(complete_emoji_catalog.length, 11);
    assert.equal(emoji.emojis_by_name.size, 1876);

    let total_emoji_in_categories = 0;

    function assert_emoji_category(ele, icon, num) {
        assert.equal(ele.icon, icon);
        assert.equal(ele.emojis.length, num);
        function check_emojis(val) {
            for (const this_emoji of ele.emojis) {
                assert.equal(this_emoji.is_realm_emoji, val);
            }
        }
        if (ele.name === "Custom") {
            check_emojis(true);
        } else {
            check_emojis(false);
            total_emoji_in_categories += ele.emojis.length;
        }
    }
    const popular_emoji_count = 6;
    const zulip_emoji_count = 1;
    function assert_category(icon, expected_count) {
        const category = complete_emoji_catalog.find((cat) => cat.icon === icon);
        assert.ok(category, `Category with icon ${icon} not found`);
        assert_emoji_category(category, icon, expected_count);
    }

    assert_category("fa-car", 195);
    assert_category("fa-hashtag", 223);
    assert_category("fa-smile-o", 168);
    assert_category("fa-star-o", popular_emoji_count);
    assert_category("fa-thumbs-o-up", 385);
    assert_category("fa-lightbulb-o", 262);
    assert_category("fa-cutlery", 135);
    assert_category("fa-flag", 269);
    assert_category("fa-cog", 1);
    assert_category("fa-leaf", 153);
    assert_category("fa-soccer-ball-o", 85);

    // The popular emoji appear twice in the picker, and the zulip emoji is special
    assert.equal(
        emoji.emojis_by_name.size,
        total_emoji_in_categories - popular_emoji_count + zulip_emoji_count,
    );
});

run_test("is_emoji_present_in_text", () => {
    const thermometer_emoji = {
        name: "thermometer",
        emoji_code: "1f321",
        reaction_type: "unicode_emoji",
    };
    const headphones_emoji = {
        name: "headphones",
        emoji_code: "1f3a7",
        reaction_type: "unicode_emoji",
    };
    assert.equal(emoji_picker.is_emoji_present_in_text("🌡", thermometer_emoji), true);
    assert.equal(
        emoji_picker.is_emoji_present_in_text("no emojis at all", thermometer_emoji),
        false,
    );
    assert.equal(emoji_picker.is_emoji_present_in_text("😎", thermometer_emoji), false);
    assert.equal(emoji_picker.is_emoji_present_in_text("😎🌡🎧", thermometer_emoji), true);
    assert.equal(emoji_picker.is_emoji_present_in_text("😎🎧", thermometer_emoji), false);
    assert.equal(emoji_picker.is_emoji_present_in_text("😎🌡🎧", headphones_emoji), true);
    assert.equal(
        emoji_picker.is_emoji_present_in_text("emojis with text 😎🌡🎧", thermometer_emoji),
        true,
    );
    assert.equal(
        emoji_picker.is_emoji_present_in_text("emojis with text no space😎🌡🎧", headphones_emoji),
        true,
    );
});
