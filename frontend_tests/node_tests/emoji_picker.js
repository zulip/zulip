"use strict";

const {strict: assert} = require("assert");

const _ = require("lodash");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const emoji = zrequire("emoji", "shared/js/emoji");
zrequire("emoji_picker");

const emoji_codes = zrequire("emoji_codes", "generated/emoji/emoji_codes.json");

run_test("initialize", () => {
    emoji.initialize({
        realm_emoji: {},
        emoji_codes,
    });
    emoji_picker.initialize();

    const complete_emoji_catalog = _.sortBy(emoji_picker.complete_emoji_catalog, "name");
    assert.equal(complete_emoji_catalog.length, 11);
    assert.equal(emoji.emojis_by_name.size, 1037);

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
    assert_emoji_category(complete_emoji_catalog.pop(), "fa-car", 170);
    assert_emoji_category(complete_emoji_catalog.pop(), "fa-hashtag", 182);
    assert_emoji_category(complete_emoji_catalog.pop(), "fa-smile-o", 129);
    assert_emoji_category(complete_emoji_catalog.pop(), "fa-star-o", popular_emoji_count);
    assert_emoji_category(complete_emoji_catalog.pop(), "fa-thumbs-o-up", 102);
    assert_emoji_category(complete_emoji_catalog.pop(), "fa-lightbulb-o", 189);
    assert_emoji_category(complete_emoji_catalog.pop(), "fa-cutlery", 92);
    assert_emoji_category(complete_emoji_catalog.pop(), "fa-flag", 5);
    assert_emoji_category(complete_emoji_catalog.pop(), "fa-cog", 1);
    assert_emoji_category(complete_emoji_catalog.pop(), "fa-leaf", 104);
    assert_emoji_category(complete_emoji_catalog.pop(), "fa-soccer-ball-o", 63);

    // The popular emoji appear twice in the picker, and the zulip emoji is special
    assert.equal(
        emoji.emojis_by_name.size,
        total_emoji_in_categories - popular_emoji_count + zulip_emoji_count,
    );
});
