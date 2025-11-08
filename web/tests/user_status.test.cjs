"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const channel = mock_esm("../src/channel");

const user_status = zrequire("user_status");
const emoji_codes = zrequire("../../static/generated/emoji/emoji_codes.json");
const emoji = zrequire("emoji");
const {initialize_user_settings} = zrequire("user_settings");

initialize_user_settings({user_settings: {}});

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
            1: {status_text: "in a meeting"},
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
        id: 1,
        user_id: 5,
        type: "user_status",
        emoji_code: "991",
        emoji_name: "example_realm_emoji",
        reaction_type: "realm_emoji",
        status_text: "",
    });

    assert.deepEqual(user_status.get_status_emoji(5), {
        emoji_alt_code: false,
        emoji_code: "991",
        emoji_name: "example_realm_emoji",
        reaction_type: "realm_emoji",
        still_url: "/url/still/991",
        url: "/url/for/991",
    });

    assert.equal(user_status.get_status_text(1), "in a meeting");

    user_status.set_status_text({
        id: 2,
        user_id: 2,
        type: "user_status",
        status_text: "out to lunch",
        emoji_name: "",
        emoji_code: "",
        reaction_type: "",
    });
    assert.equal(user_status.get_status_text(2), "out to lunch");

    user_status.set_status_text({
        user_id: 2,
        status_text: "",
    });
    assert.equal(user_status.get_status_text(2), undefined);

    user_status.set_status_emoji({
        id: 3,
        user_id: 2,
        type: "user_status",
        emoji_name: "smiley",
        emoji_code: "1f603",
        reaction_type: "unicode_emoji",
        status_text: "",
    });
    assert.deepEqual(user_status.get_status_emoji(2), {
        emoji_name: "smiley",
        emoji_code: "1f603",
        reaction_type: "unicode_emoji",
        emoji_alt_code: false,
    });

    user_status.set_status_emoji({
        id: 4,
        user_id: 2,
        type: "user_status",
        emoji_name: "",
        emoji_code: "",
        reaction_type: "unicode_emoji",
        status_text: "",
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

    let called;

    user_status.server_update_status({
        status_text: "out to lunch",
        success() {
            called = true;
        },
    });

    success();
    assert.ok(called);
});

run_test("defensive checks", () => {
    assert.throws(
        () =>
            user_status.set_status_emoji({
                id: 1,
                status_text: "",
                type: "user_status",
                user_id: 5,
                emoji_name: "emoji",
                // no status code or reaction type.
            }),
        {
            name: "$ZodError",
        },
    );

    assert.throws(
        () =>
            user_status.set_status_emoji({
                id: 2,
                type: "user_status",
                user_id: 5,
                reaction_type: "realm_emoji",
                emoji_name: "does_not_exist",
                emoji_code: "fake_code",
                status_text: "",
            }),
        {
            name: "Error",
            message: "Cannot find realm emoji for code 'fake_code'.",
        },
    );
});
