"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {make_stub} = require("./lib/stub");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");
const {page_params, user_settings} = require("./lib/zpage_params");

const alice_user_id = 5;

const sample_message = {
    id: 1001,
    reactions: [
        {emoji_name: "smile", user_id: 5, reaction_type: "unicode_emoji", emoji_code: "1f642"},
        {emoji_name: "smile", user_id: 6, reaction_type: "unicode_emoji", emoji_code: "1f642"},
        {emoji_name: "frown", user_id: 7, reaction_type: "unicode_emoji", emoji_code: "1f641"},

        {emoji_name: "tada", user_id: 7, reaction_type: "unicode_emoji", emoji_code: "1f389"},
        {emoji_name: "tada", user_id: 8, reaction_type: "unicode_emoji", emoji_code: "1f389"},

        {emoji_name: "rocket", user_id: 5, reaction_type: "unicode_emoji", emoji_code: "1f680"},
        {emoji_name: "rocket", user_id: 6, reaction_type: "unicode_emoji", emoji_code: "1f680"},
        {emoji_name: "rocket", user_id: 7, reaction_type: "unicode_emoji", emoji_code: "1f680"},

        {emoji_name: "wave", user_id: 6, reaction_type: "unicode_emoji", emoji_code: "1f44b"},
        {emoji_name: "wave", user_id: 7, reaction_type: "unicode_emoji", emoji_code: "1f44b"},
        {emoji_name: "wave", user_id: 8, reaction_type: "unicode_emoji", emoji_code: "1f44b"},

        {
            emoji_name: "inactive_realm_emoji",
            user_id: 5,
            reaction_type: "realm_emoji",
            emoji_code: "992",
        },
    ],
};

const channel = mock_esm("../src/channel");
const message_store = mock_esm("../src/message_store");
const spectators = mock_esm("../src/spectators", {
    login_to_access() {},
});

set_global("document", "document-stub");

const emoji = zrequire("emoji");
const emoji_codes = zrequire("../../static/generated/emoji/emoji_codes.json");
const people = zrequire("people");
const reactions = zrequire("reactions");

const emoji_params = {
    realm_emoji: {
        991: {
            id: "991",
            name: "realm_emoji",
            source_url: "/url/for/991",
            deactivated: false,
        },
        992: {
            id: "992",
            name: "inactive_realm_emoji",
            source_url: "/url/for/992",
            still_url: "/still/url/for/992",
            deactivated: true,
        },
    },
    emoji_codes,
};

emoji.initialize(emoji_params);

const alice = {
    email: "alice@example.com",
    user_id: alice_user_id,
    full_name: "Alice",
};
const bob = {
    email: "bob@example.com",
    user_id: 6,
    full_name: "Bob van Roberts",
};
const cali = {
    email: "cali@example.com",
    user_id: 7,
    full_name: "Cali",
};
const alexus = {
    email: "alexus@example.com",
    user_id: 8,
    full_name: "Alexus",
};
people.add_active_user(alice);
people.add_active_user(bob);
people.add_active_user(cali);
people.add_active_user(alexus);

function test(label, f) {
    run_test(label, (helpers) => {
        page_params.user_id = alice_user_id;
        f(helpers);
    });
}

test("basics", () => {
    const message = {...sample_message};

    const result = reactions.get_message_reactions(message);
    assert.ok(reactions.current_user_has_reacted_to_emoji(message, "unicode_emoji,1f642"));
    assert.ok(!reactions.current_user_has_reacted_to_emoji(message, "bogus"));

    result.sort((a, b) => a.count - b.count);

    const expected_result = [
        {
            emoji_name: "frown",
            reaction_type: "unicode_emoji",
            emoji_code: "1f641",
            local_id: "unicode_emoji,1f641",
            count: 1,
            vote_text: "1",
            user_ids: [7],
            label: "translated: Cali reacted with :frown:",
            emoji_alt_code: false,
            class: "message_reaction",
            is_realm_emoji: false,
        },
        {
            emoji_name: "inactive_realm_emoji",
            reaction_type: "realm_emoji",
            emoji_code: "992",
            local_id: "realm_emoji,992",
            count: 1,
            vote_text: "1",
            user_ids: [5],
            label: "translated: You (click to remove) reacted with :inactive_realm_emoji:",
            emoji_alt_code: false,
            is_realm_emoji: true,
            url: "/url/for/992",
            still_url: "/still/url/for/992",
            class: "message_reaction reacted",
        },
        {
            emoji_name: "smile",
            reaction_type: "unicode_emoji",
            emoji_code: "1f642",
            local_id: "unicode_emoji,1f642",
            count: 2,
            vote_text: "2",
            user_ids: [5, 6],
            label: "translated: You (click to remove) and Bob van Roberts reacted with :smile:",
            emoji_alt_code: false,
            class: "message_reaction reacted",
            is_realm_emoji: false,
        },
        {
            emoji_name: "tada",
            reaction_type: "unicode_emoji",
            emoji_code: "1f389",
            local_id: "unicode_emoji,1f389",
            count: 2,
            vote_text: "2",
            user_ids: [7, 8],
            label: "translated: Cali and Alexus reacted with :tada:",
            emoji_alt_code: false,
            class: "message_reaction",
            is_realm_emoji: false,
        },
        {
            emoji_name: "rocket",
            reaction_type: "unicode_emoji",
            emoji_code: "1f680",
            local_id: "unicode_emoji,1f680",
            count: 3,
            vote_text: "3",
            user_ids: [5, 6, 7],
            label: "translated: You (click to remove), Bob van Roberts and Cali reacted with :rocket:",
            emoji_alt_code: false,
            class: "message_reaction reacted",
            is_realm_emoji: false,
        },
        {
            emoji_name: "wave",
            reaction_type: "unicode_emoji",
            emoji_code: "1f44b",
            local_id: "unicode_emoji,1f44b",
            count: 3,
            vote_text: "3",
            user_ids: [6, 7, 8],
            label: "translated: Bob van Roberts, Cali and Alexus reacted with :wave:",
            emoji_alt_code: false,
            class: "message_reaction",
            is_realm_emoji: false,
        },
    ];
    assert.deepEqual(result, expected_result);
});

test("unknown realm emojis (add)", () => {
    assert.throws(
        () =>
            reactions.view.insert_new_reaction(
                {
                    reaction_type: "realm_emoji",
                    emoji_name: "false_emoji",
                    emoji_code: "broken",
                },
                1000,
                alice.user_id,
            ),
        {
            name: "Error",
            message: "Cannot find realm emoji for code 'broken'.",
        },
    );
});

test("unknown realm emojis (insert)", () => {
    assert.throws(
        () =>
            reactions.view.insert_new_reaction(
                {
                    reaction_type: "realm_emoji",
                    emoji_name: "fake_emoji",
                    emoji_code: "bogus",
                },
                1000,
                bob.user_id,
            ),
        {
            name: "Error",
            message: "Cannot find realm emoji for code 'bogus'.",
        },
    );
});

test("sending", ({override, override_rewire}) => {
    const message = {...sample_message};
    assert.equal(message.id, 1001);
    override(message_store, "get", (message_id) => {
        assert.equal(message_id, message.id);
        return message;
    });

    let emoji_name = "smile"; // should be a current reaction

    override_rewire(reactions, "add_reaction", () => {});
    override_rewire(reactions, "remove_reaction", () => {});

    {
        const stub = make_stub();
        channel.del = stub.f;
        reactions.toggle_emoji_reaction(message.id, emoji_name);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("args").args;
        assert.equal(args.url, "/json/messages/1001/reactions");
        assert.deepEqual(args.data, {
            reaction_type: "unicode_emoji",
            emoji_name: "smile",
            emoji_code: "1f642",
        });
        // args.success() does nothing; just make sure it doesn't crash
        args.success();

        // similarly, we only exercise the failure codepath
        // Since this path calls blueslip.warn, we need to handle it.
        blueslip.expect("error", "XHR error message.");
        channel.xhr_error_message = () => "XHR error message.";
        args.error({readyState: 4, responseJSON: {msg: "Some error message"}});
    }
    emoji_name = "alien"; // not set yet
    {
        const stub = make_stub();
        channel.post = stub.f;
        reactions.toggle_emoji_reaction(message.id, emoji_name);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("args").args;
        assert.equal(args.url, "/json/messages/1001/reactions");
        assert.deepEqual(args.data, {
            reaction_type: "unicode_emoji",
            emoji_name: "alien",
            emoji_code: "1f47d",
        });
    }

    emoji_name = "inactive_realm_emoji";
    {
        // Test removing a deactivated realm emoji. A user can interact with a
        // deactivated realm emoji only by clicking on a reaction, hence, only
        // `process_reaction_click()` codepath supports deleting/adding a deactivated
        // realm emoji.
        const stub = make_stub();
        channel.del = stub.f;
        reactions.process_reaction_click(message.id, "realm_emoji,992");
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("args").args;
        assert.equal(args.url, "/json/messages/1001/reactions");
        assert.deepEqual(args.data, {
            reaction_type: "realm_emoji",
            emoji_name: "inactive_realm_emoji",
            emoji_code: "992",
        });
    }

    emoji_name = "zulip"; // Test adding zulip emoji.
    {
        const stub = make_stub();
        channel.post = stub.f;
        reactions.toggle_emoji_reaction(message.id, emoji_name);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("args").args;
        assert.equal(args.url, "/json/messages/1001/reactions");
        assert.deepEqual(args.data, {
            reaction_type: "zulip_extra_emoji",
            emoji_name: "zulip",
            emoji_code: "zulip",
            still_url: null,
            url: "/static/generated/emoji/images/emoji/unicode/zulip.png",
        });
    }

    emoji_name = "unknown-emoji"; // Test sending an emoji unknown to frontend.
    assert.throws(() => reactions.toggle_emoji_reaction(message.id, emoji_name), {
        name: "Error",
        message: "Bad emoji name: unknown-emoji",
    });
});

test("prevent_simultaneous_requests_updating_reaction", ({override, override_rewire}) => {
    const message = {...sample_message};
    override(message_store, "get", (message_id) => {
        assert.equal(message_id, message.id);
        return message;
    });
    override_rewire(reactions, "add_reaction", () => {});
    const stub = make_stub();
    channel.post = stub.f;

    // Verify that two requests to add the same reaction in a row only
    // result in a single request to the server.
    reactions.toggle_emoji_reaction(message.id, "cow");
    reactions.toggle_emoji_reaction(message.id, "cow");

    assert.equal(stub.num_calls, 1);
});

function stub_reactions(message_id) {
    const $message_row = $.create("message-row-stub");
    const $message_reactions = $.create("reactions-stub");
    $(".message-list").set_find_results(`[zid='${CSS.escape(message_id)}']`, $message_row);
    $message_row.set_find_results(".message_reactions", $message_reactions);
    return $message_reactions;
}

function stub_reaction(message_id, local_id) {
    const $reaction = $.create("reaction-stub");
    stub_reactions(message_id).set_find_results(
        `[data-reaction-id='${CSS.escape(local_id)}']`,
        $reaction,
    );
    return $reaction;
}

test("get_vote_text (more than 3 reactions)", () => {
    const user_ids = [5, 6, 7];
    const message = {...sample_message};

    user_settings.display_emoji_reaction_users = true;
    assert.equal(
        "translated: You, Bob van Roberts, Cali",
        reactions.get_vote_text({user_ids}, message),
    );
});

test("get_vote_text (3 reactions)", () => {
    const user_ids = [5, 6, 7];
    const message = {...sample_message};

    // slicing the reactions array to only include first 3 reactions
    message.reactions = message.reactions.slice(0, 3);

    user_settings.display_emoji_reaction_users = true;
    assert.equal(
        "translated: You, Bob van Roberts, Cali",
        reactions.get_vote_text({user_ids}, message),
    );
});

test("update_vote_text_on_message", ({override_rewire}) => {
    // the vote_text in this message is intentionally wrong.
    // After calling update_vote_text_on_message(), we
    // will check if the vote_text has been correctly updated.
    const message = {
        id: 1001,
        reactions: [
            {
                emoji_name: "wave",
                user_id: 5,
                reaction_type: "unicode_emoji",
                emoji_code: "1f44b",
                vote_text: "2",
            },
            {
                emoji_name: "wave",
                user_id: 6,
                reaction_type: "unicode_emoji",
                emoji_code: "1f44b",
                vote_text: "2",
            },

            {
                emoji_name: "inactive_realm_emoji",
                user_id: 5,
                reaction_type: "realm_emoji",
                emoji_code: "992",
                vote_text: "1",
            },
        ],
    };

    user_settings.display_emoji_reaction_users = true;

    override_rewire(reactions, "find_reaction", () => {});
    override_rewire(reactions, "set_reaction_vote_text", () => {});

    reactions.update_vote_text_on_message(message);

    const updated_message = {
        clean_reactions: new Map(
            Object.entries({
                "realm_emoji,992": {
                    class: "message_reaction reacted",
                    count: 1,
                    emoji_alt_code: false,
                    emoji_code: "992",
                    emoji_name: "inactive_realm_emoji",
                    is_realm_emoji: true,
                    label: "translated: You (click to remove) reacted with :inactive_realm_emoji:",
                    local_id: "realm_emoji,992",
                    reaction_type: "realm_emoji",
                    still_url: "/still/url/for/992",
                    url: "/url/for/992",
                    user_ids: [5],
                    vote_text: "translated: You",
                },
                "unicode_emoji,1f44b": {
                    class: "message_reaction reacted",
                    count: 2,
                    emoji_alt_code: false,
                    emoji_code: "1f44b",
                    emoji_name: "wave",
                    is_realm_emoji: false,
                    label: "translated: You (click to remove) and Bob van Roberts reacted with :wave:",
                    local_id: "unicode_emoji,1f44b",
                    reaction_type: "unicode_emoji",
                    user_ids: [5, 6],
                    vote_text: "translated: You, Bob van Roberts",
                },
            }),
        ),
        id: 1001,
    };
    // message.reactions is deleted too.
    assert.deepEqual(message, updated_message);
});

test("find_reaction", () => {
    const message_id = 99;
    const local_id = "unicode_emoji,1f44b";
    const $reaction = stub_reaction(message_id, local_id);

    assert.equal(reactions.find_reaction(message_id, local_id), $reaction);
});

test("get_reaction_section", () => {
    const $message_reactions = stub_reactions(555);

    const $section = reactions.get_reaction_section(555);

    assert.equal($section, $message_reactions);
});

test("emoji_reaction_title", ({override}) => {
    const message = {...sample_message};
    override(message_store, "get", () => message);
    const local_id = "unicode_emoji,1f642";

    assert.equal(
        reactions.get_reaction_title_data(message.id, local_id),
        "translated: You (click to remove) and Bob van Roberts reacted with :smile:",
    );
});

test("add_reaction/remove_reaction", ({override}) => {
    // This function tests reaction events by mocking out calls to
    // the view.

    const message = {
        id: 2001,
        reactions: [],
    };

    user_settings.display_emoji_reaction_users = true;

    override(message_store, "get", () => message);

    let view_calls = [];

    override(reactions.view, "insert_new_reaction", (clean_reaction_object, message, user_id) => {
        view_calls.push({
            name: "insert_new_reaction",
            clean_reaction_object,
            message,
            user_id,
        });
    });
    override(
        reactions.view,
        "update_existing_reaction",
        (clean_reaction_object, message, user_id) => {
            view_calls.push({
                name: "update_existing_reaction",
                clean_reaction_object,
                message,
                user_id,
            });
        },
    );
    override(reactions.view, "remove_reaction", (clean_reaction_object, message, user_id) => {
        view_calls.push({name: "remove_reaction", clean_reaction_object, message, user_id});
    });

    function test_view_calls(test_params) {
        view_calls = [];

        test_params.run_code();

        assert.deepEqual(view_calls, test_params.expected_view_calls);
        assert.deepEqual(
            new Set(reactions.get_emojis_used_by_user_for_message_id(message.message_id)),
            new Set(test_params.alice_emojis),
        );
    }

    const alice_8ball_event = {
        message_id: 2001,
        reaction_type: "unicode_emoji",
        emoji_name: "8ball",
        emoji_code: "1f3b1",
        user_id: alice.user_id,
    };

    const bob_8ball_event = {
        message_id: 2001,
        reaction_type: "unicode_emoji",
        emoji_name: "8ball",
        emoji_code: "1f3b1",
        user_id: bob.user_id,
    };

    const cali_airplane_event = {
        message_id: 2001,
        reaction_type: "unicode_emoji",
        emoji_name: "airplane",
        emoji_code: "2708",
        user_id: cali.user_id,
    };

    const clean_reaction_object_alice = {
        class: "message_reaction reacted",
        count: 1,
        emoji_alt_code: false,
        emoji_code: alice_8ball_event.emoji_code,
        emoji_name: alice_8ball_event.emoji_name,
        is_realm_emoji: false,
        label: "translated: You (click to remove) reacted with :8ball:",
        local_id: "unicode_emoji,1f3b1",
        reaction_type: alice_8ball_event.reaction_type,
        user_ids: [alice.user_id],
        vote_text: "translated: You",
    };
    test_view_calls({
        run_code() {
            reactions.add_reaction(alice_8ball_event);
        },
        expected_view_calls: [
            {
                name: "insert_new_reaction",
                clean_reaction_object: clean_reaction_object_alice,
                message: {
                    id: alice_8ball_event.message_id,
                    clean_reactions: new Map(
                        Object.entries({
                            "unicode_emoji,1f3b1": clean_reaction_object_alice,
                        }),
                    ),
                },
                user_id: alice_8ball_event.user_id,
            },
        ],
        alice_emojis: ["8ball"],
    });

    // Add redundant reaction.
    test_view_calls({
        run_code() {
            reactions.add_reaction(alice_8ball_event);
        },
        expected_view_calls: [],
        alice_emojis: ["8ball"],
    });

    const clean_reaction_object_bob = {
        class: "message_reaction reacted",
        count: 2,
        emoji_alt_code: false,
        emoji_code: bob_8ball_event.emoji_code,
        emoji_name: bob_8ball_event.emoji_name,
        is_realm_emoji: false,
        label: "translated: You (click to remove) and Bob van Roberts reacted with :8ball:",
        local_id: "unicode_emoji,1f3b1",
        reaction_type: bob_8ball_event.reaction_type,
        user_ids: [alice.user_id, bob.user_id],
        vote_text: "translated: You, Bob van Roberts",
    };
    test_view_calls({
        run_code() {
            reactions.add_reaction(bob_8ball_event);
        },
        expected_view_calls: [
            {
                name: "update_existing_reaction",
                clean_reaction_object: clean_reaction_object_bob,
                message: {
                    id: bob_8ball_event.message_id,
                    clean_reactions: new Map(
                        Object.entries({
                            "unicode_emoji,1f3b1": clean_reaction_object_bob,
                        }),
                    ),
                },
                user_id: bob_8ball_event.user_id,
            },
        ],
        alice_emojis: ["8ball"],
    });

    const clean_reaction_object_cali = {
        class: "message_reaction",
        count: 1,
        emoji_alt_code: false,
        emoji_code: cali_airplane_event.emoji_code,
        emoji_name: cali_airplane_event.emoji_name,
        is_realm_emoji: false,
        label: "translated: Cali reacted with :airplane:",
        local_id: "unicode_emoji,2708",
        reaction_type: cali_airplane_event.reaction_type,
        user_ids: [cali.user_id],
        vote_text: "Cali",
    };
    test_view_calls({
        run_code() {
            reactions.add_reaction(cali_airplane_event);
        },
        expected_view_calls: [
            {
                name: "insert_new_reaction",
                clean_reaction_object: clean_reaction_object_cali,
                message: {
                    id: cali_airplane_event.message_id,
                    clean_reactions: new Map(
                        Object.entries({
                            "unicode_emoji,1f3b1": clean_reaction_object_bob,
                            "unicode_emoji,2708": clean_reaction_object_cali,
                        }),
                    ),
                },
                user_id: cali_airplane_event.user_id,
            },
        ],
        alice_emojis: ["8ball"],
    });

    test_view_calls({
        run_code() {
            reactions.remove_reaction(bob_8ball_event);
        },
        expected_view_calls: [
            {
                name: "remove_reaction",
                clean_reaction_object: clean_reaction_object_alice,
                message: {
                    clean_reactions: new Map(
                        Object.entries({
                            "unicode_emoji,1f3b1": clean_reaction_object_alice,
                            "unicode_emoji,2708": clean_reaction_object_cali,
                        }),
                    ),
                    id: bob_8ball_event.message_id,
                },
                user_id: bob_8ball_event.user_id,
            },
        ],
        alice_emojis: ["8ball"],
    });

    test_view_calls({
        run_code() {
            reactions.remove_reaction(alice_8ball_event);
        },
        expected_view_calls: [
            {
                name: "remove_reaction",
                clean_reaction_object: {
                    count: 0,
                    class: "message_reaction",
                    emoji_alt_code: false,
                    emoji_code: alice_8ball_event.emoji_code,
                    emoji_name: alice_8ball_event.emoji_name,
                    is_realm_emoji: false,
                    label: "translated:  and  reacted with :8ball:",
                    local_id: "unicode_emoji,1f3b1",
                    reaction_type: alice_8ball_event.reaction_type,
                    user_ids: [],
                    vote_text: "",
                },
                message: {
                    clean_reactions: new Map(
                        Object.entries({
                            "unicode_emoji,2708": clean_reaction_object_cali,
                        }),
                    ),
                    id: alice_8ball_event.message_id,
                },
                user_id: alice_8ball_event.user_id,
            },
        ],
        alice_emojis: [],
    });

    // Test redundant remove.
    test_view_calls({
        run_code() {
            reactions.remove_reaction(alice_8ball_event);
        },
        expected_view_calls: [],
        alice_emojis: [],
    });
});

test("view.insert_new_reaction (me w/unicode emoji)", ({mock_template}) => {
    const clean_reaction_object = {
        class: "message_reaction",
        count: 1,
        emoji_alt_code: false,
        emoji_code: "1f3b1",
        emoji_name: "8ball",
        is_realm_emoji: false,
        label: "translated: You (click to remove) reacted with :8ball:",
        local_id: "unicode_emoji,1f3b1",
        reaction_type: "unicode_emoji",
        user_ids: [alice.user_id],
    };
    const message_id = 501;

    const $message_reactions = stub_reactions(message_id);
    const $reaction_button = $.create("reaction-button-stub");
    $message_reactions.find = () => $reaction_button;
    $reaction_button.find = (selector) => {
        assert.equal(selector, ".message_reaction_count");
        return $.create("message-reaction-count-stub");
    };

    mock_template("message_reaction.hbs", false, (data) => {
        assert.deepEqual(data, {
            count: 1,
            emoji_alt_code: false,
            emoji_name: "8ball",
            emoji_code: "1f3b1",
            local_id: "unicode_emoji,1f3b1",
            class: "message_reaction reacted",
            message_id,
            label: "translated: You (click to remove) reacted with :8ball:",
            reaction_type: clean_reaction_object.reaction_type,
            is_realm_emoji: false,
            vote_text: "",
        });
        return "<new-reaction-stub>";
    });

    let insert_called;
    $("<new-reaction-stub>").insertBefore = (element) => {
        assert.equal(element, $reaction_button);
        insert_called = true;
    };

    reactions.view.insert_new_reaction(
        clean_reaction_object,
        {
            id: message_id,
            reactions: [
                {
                    emoji_name: "8ball",
                    user_id: alice.user_id,
                    reaction_type: "unicode_emoji",
                    emoji_code: "1f3b1",
                },
            ],
        },
        alice.user_id,
    );
    assert.ok(insert_called);
});

test("view.insert_new_reaction (them w/zulip emoji)", ({mock_template}) => {
    const clean_reaction_object = {
        class: "message_reaction",
        count: 1,
        emoji_alt_code: false,
        emoji_code: "zulip",
        emoji_name: "zulip",
        is_realm_emoji: false,
        label: "translated: Bob van Roberts reacted with :zulip:",
        local_id: "realm_emoji,zulip",
        reaction_type: "realm_emoji",
        user_ids: [bob.user_id],
    };
    const message_id = 501;

    const $message_reactions = stub_reactions(message_id);
    const $reaction_button = $.create("reaction-button-stub");
    $message_reactions.find = () => $reaction_button;
    $reaction_button.find = (selector) => {
        assert.equal(selector, ".message_reaction_count");
        return $.create("message-reaction-count-stub");
    };

    mock_template("message_reaction.hbs", false, (data) => {
        assert.deepEqual(data, {
            count: 1,
            url: "/static/generated/emoji/images/emoji/unicode/zulip.png",
            is_realm_emoji: true,
            emoji_alt_code: false,
            emoji_name: "zulip",
            emoji_code: "zulip",
            local_id: "realm_emoji,zulip",
            class: "message_reaction",
            message_id,
            label: "translated: Bob van Roberts reacted with :zulip:",
            still_url: null,
            reaction_type: clean_reaction_object.reaction_type,
            vote_text: "",
        });
        return "<new-reaction-stub>";
    });

    let insert_called;
    $("<new-reaction-stub>").insertBefore = (element) => {
        assert.equal(element, $reaction_button);
        insert_called = true;
    };

    reactions.view.insert_new_reaction(
        clean_reaction_object,
        {
            id: message_id,
            reactions: [
                {
                    emoji_name: "8ball",
                    user_id: bob.user_id,
                    reaction_type: "unicode_emoji",
                    emoji_code: "1f3b1",
                },
            ],
        },
        bob.user_id,
    );
    assert.ok(insert_called);
});

test("view.update_existing_reaction (me)", () => {
    const clean_reaction_object = {
        class: "message_reaction",
        count: 2,
        emoji_alt_code: false,
        emoji_code: "1f3b1",
        emoji_name: "8ball",
        is_realm_emoji: false,
        local_id: "unicode_emoji,1f3b1",
        reaction_type: "unicode_emoji",
        user_ids: [alice.user_id, bob.user_id],
    };
    const message_id = 503;

    const $our_reaction = stub_reaction(message_id, "unicode_emoji,1f3b1");
    const $reaction_count = $.create("reaction-count-stub");
    $our_reaction.set_find_results(".message_reaction_count", $reaction_count);

    reactions.view.update_existing_reaction(
        clean_reaction_object,
        {
            id: message_id,
            reactions: [
                {
                    emoji_code: "1f3b1",
                    emoji_name: "8ball",
                    reaction_type: "unicode_emoji",
                    user_id: alice.user_id,
                },
                {
                    emoji_code: "1f3b1",
                    emoji_name: "8ball",
                    reaction_type: "unicode_emoji",
                    user_id: bob.user_id,
                },
            ],
        },
        alice.user_id,
    );

    assert.ok($our_reaction.hasClass("reacted"));
    assert.equal(
        $our_reaction.attr("aria-label"),
        "translated: You (click to remove) and Bob van Roberts reacted with :8ball:",
    );
});

test("view.update_existing_reaction (them)", () => {
    const clean_reaction_object = {
        class: "message_reaction",
        count: 4,
        emoji_alt_code: false,
        emoji_code: "1f3b1",
        emoji_name: "8ball",
        is_realm_emoji: false,
        local_id: "unicode_emoji,1f3b1",
        reaction_type: "unicode_emoji",
        user_ids: [alice.user_id, bob.user_id, cali.user_id, alexus.user_id],
    };
    const message_id = 504;

    const $our_reaction = stub_reaction(message_id, "unicode_emoji,1f3b1");
    const $reaction_count = $.create("reaction-count-stub");
    $our_reaction.set_find_results(".message_reaction_count", $reaction_count);

    reactions.view.update_existing_reaction(
        clean_reaction_object,
        {
            id: message_id,
            reactions: [
                {
                    emoji_code: "1f3b1",
                    emoji_name: "8ball",
                    reaction_type: "unicode_emoji",
                    user_id: alice.user_id,
                },
                {
                    emoji_code: "1f3b1",
                    emoji_name: "8ball",
                    reaction_type: "unicode_emoji",
                    user_id: bob.user_id,
                },
                {
                    emoji_code: "1f3b1",
                    emoji_name: "8ball",
                    reaction_type: "unicode_emoji",
                    user_id: cali.user_id,
                },
                {
                    emoji_code: "1f3b1",
                    emoji_name: "8ball",
                    reaction_type: "unicode_emoji",
                    user_id: alexus.user_id,
                },
            ],
        },
        alexus.user_id,
    );

    assert.ok(!$our_reaction.hasClass("reacted"));
    assert.equal(
        $our_reaction.attr("aria-label"),
        "translated: You (click to remove), Bob van Roberts, Cali and Alexus reacted with :8ball:",
    );
});

test("view.remove_reaction (me)", () => {
    const clean_reaction_object = {
        class: "message_reaction",
        count: 2,
        emoji_alt_code: false,
        emoji_code: "1f3b1",
        emoji_name: "8ball",
        is_realm_emoji: false,
        local_id: "unicode_emoji,1f3b1",
        reaction_type: "unicode_emoji",
        user_ids: [bob.user_id, cali.user_id],
    };
    const message_id = 505;

    const $message_reactions = stub_reaction(message_id, "unicode_emoji,1f3b1");
    $message_reactions.addClass("reacted");
    const $reaction_button = $.create("reaction-button-stub");
    $message_reactions.find = () => $reaction_button;

    reactions.view.remove_reaction(
        clean_reaction_object,
        {
            id: message_id,
            reactions: [
                {
                    emoji_code: "1f3b1",
                    emoji_name: "8ball",
                    reaction_type: "unicode_emoji",
                    user_id: bob.user_id,
                },
                {
                    emoji_code: "1f3b1",
                    emoji_name: "8ball",
                    reaction_type: "unicode_emoji",
                    user_id: cali.user_id,
                },
            ],
        },
        alice.user_id,
    );

    assert.ok(!$message_reactions.hasClass("reacted"));
    assert.equal(
        $message_reactions.attr("aria-label"),
        "translated: Bob van Roberts and Cali reacted with :8ball:",
    );
});

test("view.remove_reaction (them)", () => {
    const clean_reaction_object = {
        class: "message_reaction",
        count: 1,
        emoji_alt_code: false,
        emoji_code: "1f3b1",
        emoji_name: "8ball",
        is_realm_emoji: false,
        local_id: "unicode_emoji,1f3b1",
        reaction_type: "unicode_emoji",
        user_ids: [alice.user_id],
    };
    const message_id = 506;

    const $message_reactions = stub_reaction(message_id, "unicode_emoji,1f3b1");
    $message_reactions.addClass("reacted");
    const $reaction_button = $.create("reaction-button-stub");
    $message_reactions.find = () => $reaction_button;

    reactions.view.remove_reaction(
        clean_reaction_object,
        {
            id: message_id,
            reactions: [
                {
                    emoji_code: "1f3b1",
                    emoji_name: "8ball",
                    reaction_type: "unicode_emoji",
                    user_id: alice.user_id,
                },
            ],
        },
        bob.user_id,
    );

    assert.ok($message_reactions.hasClass("reacted"));
    assert.equal(
        $message_reactions.attr("aria-label"),
        "translated: You (click to remove) reacted with :8ball:",
    );
});

test("view.remove_reaction (last person)", () => {
    const clean_reaction_object = {
        class: "message_reaction",
        count: 1,
        emoji_alt_code: false,
        emoji_code: "1f3b1",
        emoji_name: "8ball",
        is_realm_emoji: false,
        local_id: "unicode_emoji,1f3b1",
        reaction_type: "unicode_emoji",
        user_ids: [],
    };
    const message_id = 507;

    const $our_reaction = stub_reaction(message_id, "unicode_emoji,1f3b1");

    let removed;
    $our_reaction.remove = () => {
        removed = true;
    };
    reactions.view.remove_reaction(
        clean_reaction_object,
        {id: message_id, reactions: []},
        bob.user_id,
    );
    assert.ok(removed);
});

test("error_handling", ({override, override_rewire}) => {
    override(message_store, "get", () => {});

    blueslip.expect("error", "reactions: Bad message id");

    const bogus_event = {
        message_id: 55,
        reaction_type: "realm_emoji",
        emoji_name: "realm_emoji",
        emoji_code: "991",
        user_id: 99,
    };
    override_rewire(reactions, "current_user_has_reacted_to_emoji", () => true);
    reactions.toggle_emoji_reaction(55, bogus_event.emoji_name);

    reactions.add_reaction(bogus_event);
    reactions.remove_reaction(bogus_event);
});

test("remove spurious user", ({override}) => {
    // get coverage for removing non-user (it should just
    // silently fail)

    const message = {...sample_message};
    override(message_store, "get", () => message);

    const event = {
        reaction_type: "unicode_emoji",
        emoji_name: "frown",
        emoji_code: "1f641",
        message_id: message.id,
        user_id: alice.user_id,
    };

    reactions.remove_reaction(event);
});

test("remove last user", ({override}) => {
    const message = {...sample_message};

    override(message_store, "get", () => message);
    override(reactions.view, "remove_reaction", () => {});

    function assert_names(names) {
        assert.deepEqual(
            reactions.get_message_reactions(message).map((r) => r.emoji_name),
            names,
        );
    }

    assert_names(["smile", "frown", "tada", "rocket", "wave", "inactive_realm_emoji"]);

    const event = {
        reaction_type: "unicode_emoji",
        emoji_name: "frown",
        emoji_code: "1f641",
        message_id: message.id,
        user_id: cali.user_id,
    };
    reactions.remove_reaction(event);

    assert_names(["smile", "tada", "rocket", "wave", "inactive_realm_emoji"]);
});

test("local_reaction_id", () => {
    const reaction_info = {
        reaction_type: "unicode_emoji",
        emoji_code: "1f44d",
    };
    const local_id = reactions.get_local_reaction_id(reaction_info);
    assert.equal(local_id, "unicode_emoji,1f44d");
});

test("process_reaction_click", ({override}) => {
    override(reactions.view, "remove_reaction", () => {});

    const message = {...sample_message};
    override(message_store, "get", () => message);

    const expected_reaction_info = {
        reaction_type: "unicode_emoji",
        emoji_name: "smile",
        emoji_code: "1f642",
    };

    // Test spectator cannot react.
    page_params.is_spectator = true;
    let stub = make_stub();
    spectators.login_to_access = stub.f;
    reactions.process_reaction_click(message.id, "unicode_emoji,1f642");
    let args = stub.get_args("args").args;
    assert.equal(args, undefined);

    page_params.is_spectator = false;
    stub = make_stub();
    channel.del = stub.f;
    reactions.process_reaction_click(message.id, "unicode_emoji,1f642");
    assert.equal(stub.num_calls, 1);
    args = stub.get_args("args").args;
    assert.equal(args.url, "/json/messages/1001/reactions");
    assert.deepEqual(args.data, expected_reaction_info);
});

test("warnings", () => {
    const message = {
        id: 3001,
        reactions: [
            {emoji_name: "smile", user_id: 5, reaction_type: "unicode_emoji", emoji_code: "1f642"},
            // add some bogus user_ids
            {
                emoji_name: "octopus",
                user_id: 8888,
                reaction_type: "unicode_emoji",
                emoji_code: "1f419",
            },
            {
                emoji_name: "frown",
                user_id: 9999,
                reaction_type: "unicode_emoji",
                emoji_code: "1f641",
            },
        ],
    };
    blueslip.expect("warn", "Unknown user_id 8888 in reaction for message 3001");
    blueslip.expect("warn", "Unknown user_id 9999 in reaction for message 3001");
    reactions.get_message_reactions(message);
});

test("code coverage", ({override}) => {
    /*
        We just silently fail in a few places in the reaction
        code, since events may come for messages that we don't
        have yet, or reactions may be for deactivated users, etc.

        Here we just cheaply ensure 100% line coverage to make
        it easy to enforce 100% coverage for more significant
        code additions.
    */
    override(message_store, "get", (id) => {
        assert.equal(id, 42);
        return {
            reactions: [],
        };
    });

    reactions.remove_reaction({
        message_id: 42, // TODO: REACTIONS API
    });
});

test("duplicates", () => {
    const dup_reaction_message = {
        id: 1001,
        reactions: [
            {emoji_name: "smile", user_id: 5, reaction_type: "unicode_emoji", emoji_code: "1f642"},
            {emoji_name: "smile", user_id: 5, reaction_type: "unicode_emoji", emoji_code: "1f642"},
        ],
    };

    blueslip.expect("error", "server sent duplicate reactions");
    reactions.set_clean_reactions(dup_reaction_message);
});

test("process_reaction_click undefined", ({override}) => {
    override(message_store, "get", () => undefined);
    blueslip.expect("error", "reactions: Bad message id");
    blueslip.expect("error", "message_id for reaction click is unknown");
    reactions.process_reaction_click(55, "whatever");
});

test("process_reaction_click bad local id", ({override}) => {
    const stub_message = {id: 4001, reactions: []};
    override(message_store, "get", () => stub_message);
    blueslip.expect("error", "Data integrity problem for reaction");
    reactions.process_reaction_click("some-msg-id", "bad-local-id");
});
