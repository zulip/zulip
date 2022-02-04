"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {make_stub} = require("../zjsunit/stub");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");
const $ = require("../zjsunit/zjquery");
const {page_params} = require("../zjsunit/zpage_params");

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

const channel = mock_esm("../../static/js/channel");
const emoji_picker = mock_esm("../../static/js/emoji_picker", {
    hide_emoji_popover() {},
});
const message_lists = mock_esm("../../static/js/message_lists");
const message_store = mock_esm("../../static/js/message_store");
const spectators = mock_esm("../../static/js/spectators", {
    login_to_access() {},
});

message_lists.current = {
    selected_message() {
        return {sent_by_me: true};
    },
    selected_row() {
        return $(".selected-row");
    },
    selected_id() {
        return 42;
    },
};
set_global("document", "document-stub");

const emoji_codes = zrequire("../generated/emoji/emoji_codes.json");
const emoji = zrequire("../shared/js/emoji");
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
    run_test(label, ({override, override_rewire, mock_template}) => {
        page_params.user_id = alice_user_id;
        f({override, override_rewire, mock_template});
    });
}

test("open_reactions_popover (sent by me)", () => {
    message_lists.current.selected_message = () => ({sent_by_me: true});
    $(".selected-row").set_find_results(".actions_hover", ["action-stub"]);

    let called = false;
    emoji_picker.toggle_emoji_popover = (target, id) => {
        called = true;
        assert.equal(id, 42);
        assert.equal(target, "action-stub");
    };

    assert.ok(reactions.open_reactions_popover());
    assert.ok(called);
});

test("open_reactions_popover (not sent by me)", () => {
    message_lists.current.selected_message = () => ({sent_by_me: false});
    $(".selected-row").set_find_results(".reaction_button", ["reaction-stub"]);

    let called = false;
    emoji_picker.toggle_emoji_popover = (target, id) => {
        called = true;
        assert.equal(id, 42);
        assert.equal(target, "reaction-stub");
    };

    assert.ok(reactions.open_reactions_popover());
    assert.ok(called);
});

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
            vote_text: "Cali",
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
            vote_text: "Alice",
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
            reactions.view.insert_new_reaction({
                reaction_type: "realm_emoji",
                emoji_name: "false_emoji",
                emoji_code: "broken",
                user_id: alice.user_id,
            }),
        {
            name: "Error",
            message: "Cannot find realm emoji for code 'broken'.",
        },
    );
});

test("unknown realm emojis (insert)", () => {
    assert.throws(
        () =>
            reactions.view.insert_new_reaction({
                reaction_type: "realm_emoji",
                emoji_name: "fake_emoji",
                emoji_code: "bogus",
                user_id: bob.user_id,
            }),
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
        blueslip.expect("warn", "XHR error message.");
        channel.xhr_error_message = () => "XHR error message.";
        args.error();
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
            url: "/static/generated/emoji/images/emoji/unicode/zulip.png",
        });
    }

    emoji_name = "unknown-emoji"; // Test sending an emoji unknown to frontend.
    assert.throws(() => reactions.toggle_emoji_reaction(message.id, emoji_name), {
        name: "Error",
        message: "Bad emoji name: unknown-emoji",
    });
});

test("set_reaction_count", () => {
    const name_or_count_element = $.create("count-stub");
    const reaction_element = $.create("reaction-stub");
    const user_list = [5, 6, 7, 8];

    reaction_element.set_find_results(".message_reaction_count", name_or_count_element);

    reactions.set_reaction_count(reaction_element, user_list);

    assert.equal(name_or_count_element.text(), "4");
});

test("find_reaction", ({override_rewire}) => {
    const message_id = 99;
    const local_id = "unicode_emoji,1f44b";
    const reaction_section = $.create("section-stub");

    const reaction_stub = "reaction-stub";
    reaction_section.set_find_results(
        `[data-reaction-id='${CSS.escape(local_id)}']`,
        reaction_stub,
    );

    override_rewire(reactions, "get_reaction_section", (arg) => {
        assert.equal(arg, message_id);
        return reaction_section;
    });

    assert.equal(reactions.find_reaction(message_id, local_id), reaction_stub);
});

test("get_reaction_section", () => {
    const message_table = $.create(".message_table");
    const message_row = $.create("some-message-row");
    const message_reactions = $.create("our-reactions-section");

    message_table.set_find_results(`[zid='${CSS.escape(555)}']`, message_row);
    message_row.set_find_results(".message_reactions", message_reactions);

    const section = reactions.get_reaction_section(555);

    assert.equal(section, message_reactions);
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

    override(message_store, "get", () => message);

    let view_calls = [];

    override(reactions.view, "insert_new_reaction", (opts) => {
        view_calls.push({name: "insert_new_reaction", opts});
    });
    override(reactions.view, "update_existing_reaction", (opts) => {
        view_calls.push({name: "update_existing_reaction", opts});
    });
    override(reactions.view, "remove_reaction", (opts) => {
        view_calls.push({name: "remove_reaction", opts});
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

    test_view_calls({
        run_code() {
            reactions.add_reaction(alice_8ball_event);
        },
        expected_view_calls: [
            {
                name: "insert_new_reaction",
                opts: {
                    message_id: 2001,
                    reaction_type: "unicode_emoji",
                    emoji_name: "8ball",
                    emoji_code: "1f3b1",
                    user_id: alice.user_id,
                },
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

    test_view_calls({
        run_code() {
            reactions.add_reaction(bob_8ball_event);
        },
        expected_view_calls: [
            {
                name: "update_existing_reaction",
                opts: {
                    message_id: 2001,
                    reaction_type: "unicode_emoji",
                    emoji_name: "8ball",
                    emoji_code: "1f3b1",
                    user_id: bob.user_id,
                    user_list: [alice.user_id, bob.user_id],
                },
            },
        ],
        alice_emojis: ["8ball"],
    });

    test_view_calls({
        run_code() {
            reactions.add_reaction(cali_airplane_event);
        },
        expected_view_calls: [
            {
                name: "insert_new_reaction",
                opts: {
                    message_id: 2001,
                    reaction_type: "unicode_emoji",
                    emoji_name: "airplane",
                    emoji_code: "2708",
                    user_id: cali.user_id,
                },
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
                opts: {
                    message_id: 2001,
                    reaction_type: "unicode_emoji",
                    emoji_name: "8ball",
                    emoji_code: "1f3b1",
                    user_id: bob.user_id,
                    user_list: [alice.user_id],
                },
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
                opts: {
                    message_id: 2001,
                    reaction_type: "unicode_emoji",
                    emoji_name: "8ball",
                    emoji_code: "1f3b1",
                    user_id: alice.user_id,
                    user_list: [],
                },
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

test("view.insert_new_reaction (me w/unicode emoji)", ({override_rewire, mock_template}) => {
    const opts = {
        message_id: 501,
        reaction_type: "unicode_emoji",
        emoji_name: "8ball",
        emoji_code: "1f3b1",
        user_id: alice.user_id,
    };

    const message_reactions = $.create("our-reactions");

    override_rewire(reactions, "get_reaction_section", (message_id) => {
        assert.equal(message_id, opts.message_id);
        return message_reactions;
    });

    message_reactions.find = (selector) => {
        assert.equal(selector, ".reaction_button");
        return "reaction-button-stub";
    };

    mock_template("message_reaction.hbs", false, (data) => {
        assert.deepEqual(data, {
            count: 1,
            vote_text: "Alice",
            emoji_alt_code: false,
            emoji_name: "8ball",
            emoji_code: "1f3b1",
            local_id: "unicode_emoji,1f3b1",
            class: "message_reaction reacted",
            message_id: opts.message_id,
            label: "translated: You (click to remove) reacted with :8ball:",
            reaction_type: opts.reaction_type,
            is_realm_emoji: false,
        });
        return "<new reaction html>";
    });

    let insert_called;
    $("<new reaction html>").insertBefore = (element) => {
        assert.equal(element, "reaction-button-stub");
        insert_called = true;
    };

    reactions.view.insert_new_reaction(opts);
    assert.ok(insert_called);
});

test("view.insert_new_reaction (them w/zulip emoji)", ({override_rewire, mock_template}) => {
    const opts = {
        message_id: 502,
        reaction_type: "realm_emoji",
        emoji_name: "zulip",
        emoji_code: "zulip",
        user_id: bob.user_id,
    };

    const message_reactions = $.create("our-reactions");

    override_rewire(reactions, "get_reaction_section", (message_id) => {
        assert.equal(message_id, opts.message_id);
        return message_reactions;
    });

    message_reactions.find = (selector) => {
        assert.equal(selector, ".reaction_button");
        return "reaction-button-stub";
    };

    mock_template("message_reaction.hbs", false, (data) => {
        assert.deepEqual(data, {
            count: 1,
            vote_text: "Bob van Roberts",
            url: "/static/generated/emoji/images/emoji/unicode/zulip.png",
            is_realm_emoji: true,
            emoji_alt_code: false,
            emoji_name: "zulip",
            emoji_code: "zulip",
            local_id: "realm_emoji,zulip",
            class: "message_reaction",
            message_id: opts.message_id,
            label: "translated: Bob van Roberts reacted with :zulip:",
            still_url: undefined,
            reaction_type: opts.reaction_type,
        });
        return "<new reaction html>";
    });

    let insert_called;
    $("<new reaction html>").insertBefore = (element) => {
        assert.equal(element, "reaction-button-stub");
        insert_called = true;
    };

    reactions.view.insert_new_reaction(opts);
    assert.ok(insert_called);
});

test("view.update_existing_reaction (me)", ({override_rewire}) => {
    const opts = {
        message_id: 503,
        reaction_type: "unicode_emoji",
        emoji_name: "8ball",
        emoji_code: "1f3b1",
        user_id: alice.user_id,
        user_list: [alice.user_id, bob.user_id],
    };

    const our_reaction = $.create("our-reaction-stub");

    override_rewire(reactions, "find_reaction", (message_id, local_id) => {
        assert.equal(message_id, opts.message_id);
        assert.equal(local_id, "unicode_emoji,1f3b1");
        return our_reaction;
    });

    override_rewire(reactions, "set_reaction_count", (reaction, user_list) => {
        assert.equal(reaction, our_reaction);
        assert.equal(user_list, opts.user_list);
    });

    reactions.view.update_existing_reaction(opts);

    assert.ok(our_reaction.hasClass("reacted"));
    assert.equal(
        our_reaction.attr("aria-label"),
        "translated: You (click to remove) and Bob van Roberts reacted with :8ball:",
    );
});

test("view.update_existing_reaction (them)", ({override_rewire}) => {
    const opts = {
        message_id: 504,
        reaction_type: "unicode_emoji",
        emoji_name: "8ball",
        emoji_code: "1f3b1",
        user_id: bob.user_id,
        user_list: [alice.user_id, bob.user_id, cali.user_id, alexus.user_id],
    };

    const our_reaction = $.create("our-reaction-stub");

    override_rewire(reactions, "find_reaction", (message_id, local_id) => {
        assert.equal(message_id, opts.message_id);
        assert.equal(local_id, "unicode_emoji,1f3b1");
        return our_reaction;
    });

    override_rewire(reactions, "set_reaction_count", (reaction, user_list) => {
        assert.equal(reaction, our_reaction);
        assert.equal(user_list, opts.user_list);
    });

    reactions.view.update_existing_reaction(opts);

    assert.ok(!our_reaction.hasClass("reacted"));
    assert.equal(
        our_reaction.attr("aria-label"),
        "translated: You (click to remove), Bob van Roberts, Cali and Alexus reacted with :8ball:",
    );
});

test("view.remove_reaction (me)", ({override_rewire}) => {
    const opts = {
        message_id: 505,
        reaction_type: "unicode_emoji",
        emoji_name: "8ball",
        emoji_code: "1f3b1",
        user_id: alice.user_id,
        user_list: [bob.user_id, cali.user_id],
    };

    const our_reaction = $.create("our-reaction-stub");
    our_reaction.addClass("reacted");

    override_rewire(reactions, "find_reaction", (message_id, local_id) => {
        assert.equal(message_id, opts.message_id);
        assert.equal(local_id, "unicode_emoji,1f3b1");
        return our_reaction;
    });

    override_rewire(reactions, "set_reaction_count", (reaction, user_list) => {
        assert.equal(reaction, our_reaction);
        assert.equal(user_list, opts.user_list);
    });

    reactions.view.remove_reaction(opts);

    assert.ok(!our_reaction.hasClass("reacted"));
    assert.equal(
        our_reaction.attr("aria-label"),
        "translated: Bob van Roberts and Cali reacted with :8ball:",
    );
});

test("view.remove_reaction (them)", ({override_rewire}) => {
    const opts = {
        message_id: 506,
        reaction_type: "unicode_emoji",
        emoji_name: "8ball",
        emoji_code: "1f3b1",
        user_id: bob.user_id,
        user_list: [alice.user_id],
    };

    const our_reaction = $.create("our-reaction-stub");
    our_reaction.addClass("reacted");

    override_rewire(reactions, "find_reaction", (message_id, local_id) => {
        assert.equal(message_id, opts.message_id);
        assert.equal(local_id, "unicode_emoji,1f3b1");
        return our_reaction;
    });

    override_rewire(reactions, "set_reaction_count", (reaction, user_list) => {
        assert.equal(reaction, our_reaction);
        assert.equal(user_list, opts.user_list);
    });

    our_reaction.addClass("reacted");
    reactions.view.remove_reaction(opts);

    assert.ok(our_reaction.hasClass("reacted"));
    assert.equal(
        our_reaction.attr("aria-label"),
        "translated: You (click to remove) reacted with :8ball:",
    );
});

test("view.remove_reaction (last person)", ({override_rewire}) => {
    const opts = {
        message_id: 507,
        reaction_type: "unicode_emoji",
        emoji_name: "8ball",
        emoji_code: "1f3b1",
        user_id: bob.user_id,
        user_list: [],
    };

    const our_reaction = $.create("our-reaction-stub");

    override_rewire(reactions, "find_reaction", (message_id, local_id) => {
        assert.equal(message_id, opts.message_id);
        assert.equal(local_id, "unicode_emoji,1f3b1");
        return our_reaction;
    });

    let removed;
    our_reaction.remove = () => {
        removed = true;
    };
    reactions.view.remove_reaction(opts);
    assert.ok(removed);
});

test("error_handling", ({override, override_rewire}) => {
    override(message_store, "get", () => {});

    blueslip.expect("error", "reactions: Bad message id: 55");

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

    blueslip.expect(
        "error",
        "server sent duplicate reactions for user 5 (key=unicode_emoji,1f642)",
    );
    reactions.set_clean_reactions(dup_reaction_message);
});

test("process_reaction_click undefined", ({override}) => {
    override(message_store, "get", () => undefined);
    blueslip.expect("error", "reactions: Bad message id: 55");
    blueslip.expect("error", "message_id for reaction click is unknown: 55");
    reactions.process_reaction_click(55, "whatever");
});

test("process_reaction_click bad local id", ({override}) => {
    const stub_message = {id: 4001, reactions: []};
    override(message_store, "get", () => stub_message);
    blueslip.expect(
        "error",
        "Data integrity problem for reaction bad-local-id (message some-msg-id)",
    );
    reactions.process_reaction_click("some-msg-id", "bad-local-id");
});
