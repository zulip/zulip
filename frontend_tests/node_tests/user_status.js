"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");

const channel = mock_esm("../../static/js/channel");

const user_status = zrequire("user_status");
const emoji_codes = zrequire("../generated/emoji/emoji_codes.json");
const emoji = zrequire("../shared/js/emoji");

const emoji_params = {
    realm_emoji: {
        991: {
            id: "991",
            name: "realm_emoji",
            source_url: "/url/for/991",
            deactivated: false,
        },
    },
    emoji_codes,
};

emoji.initialize(emoji_params);

function initialize() {
    const params = {
        user_status: {
            1: {away: true, status_text: "in a meeting"},
            2: {away: true},
            3: {away: true},
            4: {emoji_name: "smiley", emoji_code: "1f603", reaction_type: "unicode_emoji"},
        },
    };
    user_status.initialize(params);
}

run_test("basics", () => {
    initialize();
    assert.ok(user_status.is_away(2));
    assert.ok(!user_status.is_away(99));

    assert.ok(!user_status.is_away(4));
    user_status.set_away(4);
    assert.ok(user_status.is_away(4));
    user_status.revoke_away(4);
    assert.ok(!user_status.is_away(4));

    assert.equal(user_status.get_status_text(1), "in a meeting");

    user_status.set_status_text({
        user_id: 2,
        status_text: "out to lunch",
    });
    assert.equal(user_status.get_status_text(2), "out to lunch");

    user_status.set_status_text({
        user_id: 2,
        status_text: "",
    });
    assert.equal(user_status.get_status_text(2), undefined);

    user_status.set_status_emoji({
        user_id: 2,
        emoji_name: "smiley",
        emoji_code: "1f603",
        reaction_type: "unicode_emoji",
    });
    assert.deepEqual(user_status.get_status_emoji(2), {
        emoji_name: "smiley",
        emoji_code: "1f603",
        reaction_type: "unicode_emoji",
        // Extra parameters that were added by `emoji.get_emoji_details_by_name`
        emoji_alt_code: false,
    });

    user_status.set_status_emoji({
        user_id: 2,
        emoji_name: "",
        emoji_code: "",
        reaction_type: "",
    });
    assert.deepEqual(user_status.get_status_emoji(2), undefined);
});

run_test("server", () => {
    initialize();

    let sent_data;
    let success;

    channel.post = (opts) => {
        sent_data = opts.data;
        assert.equal(opts.url, "/json/users/me/status");
        success = opts.success;
    };

    assert.equal(sent_data, undefined);

    user_status.server_set_away();
    assert.deepEqual(sent_data, {
        away: true,
        status_text: undefined,
        emoji_code: undefined,
        emoji_name: undefined,
        reaction_type: undefined,
    });

    user_status.server_revoke_away();
    assert.deepEqual(sent_data, {
        away: false,
        status_text: undefined,
        emoji_code: undefined,
        emoji_name: undefined,
        reaction_type: undefined,
    });

    let called;

    user_status.server_update({
        status_text: "out to lunch",
        success: () => {
            called = true;
        },
    });

    success();
    assert.ok(called);
});

run_test("defensive checks", () => {
    blueslip.expect("error", "need ints for user_id", 2);
    user_status.set_away("string");
    user_status.revoke_away("string");
});
