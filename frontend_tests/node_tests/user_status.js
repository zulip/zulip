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
            name: "example_realm_emoji",
            source_url: "/url/for/991",
            still_url: "/url/still/991",
            deactivated: false,
        },
        992: {
            id: "992",
            name: "deactivated_realm_emoji",
            source_url: "/url/for/992",
            still_url: "/url/still/992",
            deactivated: true,
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
            5: {
                emoji_name: "deactivated_realm_emoji",
                emoji_code: "992",
                reaction_type: "realm_emoji",
            },
        },
    };
    user_status.initialize(params);
}

run_test("basics", () => {
    initialize();

    assert.deepEqual(user_status.get_status_emoji(5), {
        emoji_code: "992",
        emoji_name: "deactivated_realm_emoji",
        reaction_type: "realm_emoji",
        url: "/url/for/992",
        still_url: "/url/still/992",
    });

    user_status.set_status_emoji({
        user_id: 5,
        emoji_code: "991",
        emoji_name: "example_realm_emoji",
        reaction_type: "realm_emoji",
    });

    assert.deepEqual(user_status.get_status_emoji(5), {
        emoji_alt_code: false,
        emoji_code: "991",
        emoji_name: "example_realm_emoji",
        reaction_type: "realm_emoji",
        still_url: "/url/still/991",
        url: "/url/for/991",
    });

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

    assert.throws(
        () =>
            user_status.set_status_emoji({
                user_id: 5,
                emoji_name: "emoji",
                // no status code or reaction type.
            }),
        {
            name: "Error",
            message: "Invalid params.",
        },
    );

    assert.throws(
        () =>
            user_status.set_status_emoji({
                user_id: 5,
                reaction_type: "realm_emoji",
                emoji_name: "does_not_exist",
                emoji_code: "fake_code",
            }),
        {
            name: "Error",
            message: "Cannot find realm emoji for code 'fake_code'.",
        },
    );
});
