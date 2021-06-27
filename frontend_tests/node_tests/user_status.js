"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");

const channel = mock_esm("../../static/js/channel");
const user_status = zrequire("user_status");
const emoji_codes = zrequire("../generated/emoji/emoji_codes.json");
const emoji = zrequire("../shared/js/emoji");
const {page_params} = require("../zjsunit/zpage_params");

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

run_test("get_extra_emoji_info", () => {
    page_params.emojiset = "text";

    let emoji_info = {};

    emoji_info = user_status.get_emoji_info(emoji_info);
    assert.deepEqual(emoji_info, {});

    emoji_info = {emoji_name: "smile"};

    emoji_info = user_status.get_emoji_info(emoji_info);
    assert.deepEqual(emoji_info, {
        emoji_name: "smile",
        emoji_alt_code: true,
    });

    page_params.emojiset = "google";

    // Test adding an unicode_emoji.
    emoji_info = {emoji_name: "smile", emoji_code: "1f642", reaction_type: "unicode_emoji"};

    emoji_info = user_status.get_emoji_info(emoji_info);
    assert.deepEqual(emoji_info, {
        emoji_name: "smile",
        emoji_alt_code: false,
        reaction_type: "unicode_emoji",
        emoji_code: "1f642",
    });

    // Test adding an unicode_emoji's name only.
    // It should fill in other details automatically.
    emoji_info = {emoji_name: "smile"};

    emoji_info = user_status.get_emoji_info(emoji_info);
    assert.deepEqual(emoji_info, {
        emoji_name: "smile",
        emoji_alt_code: false,
        reaction_type: "unicode_emoji",
        emoji_code: "1f642",
    });

    // Test adding zulip emoji.
    emoji_info = {emoji_name: "zulip", emoji_code: "zulip", reaction_type: "zulip_extra_emoji"};

    emoji_info = user_status.get_emoji_info(emoji_info);
    assert.deepEqual(emoji_info, {
        emoji_name: "zulip",
        emoji_alt_code: false,
        reaction_type: "zulip_extra_emoji",
        emoji_code: "zulip",
        url: "/static/generated/emoji/images/emoji/unicode/zulip.png",
    });

    // Test adding zulip emoji's name only.
    emoji_info = {emoji_name: "zulip"};

    emoji_info = user_status.get_emoji_info(emoji_info);
    assert.deepEqual(emoji_info, {
        emoji_name: "zulip",
        emoji_alt_code: false,
        reaction_type: "zulip_extra_emoji",
        emoji_code: "zulip",
        url: "/static/generated/emoji/images/emoji/unicode/zulip.png",
    });

    // Test adding realm_emoji emoji.
    emoji_info = {
        emoji_name: "realm_emoji",
        emoji_code: "991",
        reaction_type: "realm_emoji",
    };

    emoji_info = user_status.get_emoji_info(emoji_info);
    assert.deepEqual(emoji_info, {
        emoji_name: "realm_emoji",
        emoji_alt_code: false,
        reaction_type: "realm_emoji",
        emoji_code: "991",
        url: "/url/for/991",
    });

    // Test adding only realm_emoji's name only.
    // It should fill in other details automatically.
    emoji_info = {
        emoji_name: "realm_emoji",
    };

    emoji_info = user_status.get_emoji_info(emoji_info);
    assert.deepEqual(emoji_info, {
        emoji_name: "realm_emoji",
        emoji_alt_code: false,
        reaction_type: "realm_emoji",
        emoji_code: "991",
        url: "/url/for/991",
    });

    // Test sending an unknown emoji.
    emoji_info = {emoji_name: "unknown-emoji"};
    blueslip.expect("warn", "Bad emoji name: " + emoji_info.emoji_name);
    emoji_info = user_status.get_emoji_info(emoji_info);
    assert.deepEqual(emoji_info, {});
});

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
    assert.deepEqual(sent_data, {away: true, status_text: undefined});

    user_status.server_revoke_away();
    assert.deepEqual(sent_data, {away: false, status_text: undefined});

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
