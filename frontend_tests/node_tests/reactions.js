"use strict";

set_global("document", "document-stub");
set_global("$", global.make_zjquery());

const emoji_codes = zrequire("emoji_codes", "generated/emoji/emoji_codes.json");
const emoji = zrequire("emoji", "shared/js/emoji");

const people = zrequire("people");
zrequire("reactions");

set_global("page_params", {
    user_id: 5,
});

const emoji_params = {
    realm_emoji: {
        991: {
            id: "991",
            name: "realm_emoji",
            source_url: "TBD",
            deactivated: false,
        },
        992: {
            id: "992",
            name: "inactive_realm_emoji",
            source_url: "TBD",
            deactivated: true,
        },
        zulip: {
            id: "zulip",
            name: "zulip",
            source_url: "TBD",
            deactivated: false,
        },
    },
    emoji_codes,
};

emoji.initialize(emoji_params);

set_global("channel", {});
set_global("emoji_picker", {
    hide_emoji_popover() {},
});

const alice = {
    email: "alice@example.com",
    user_id: 5,
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
people.add_active_user(alice);
people.add_active_user(bob);
people.add_active_user(cali);

const message = {
    id: 1001,
    reactions: [
        {emoji_name: "smile", user_id: 5, reaction_type: "unicode_emoji", emoji_code: "1f642"},
        {emoji_name: "smile", user_id: 6, reaction_type: "unicode_emoji", emoji_code: "1f642"},
        {emoji_name: "frown", user_id: 7, reaction_type: "unicode_emoji", emoji_code: "1f641"},
        {
            emoji_name: "inactive_realm_emoji",
            user_id: 5,
            reaction_type: "realm_emoji",
            emoji_code: "992",
        },

        // add some bogus user_ids
        {emoji_name: "octopus", user_id: 8888, reaction_type: "unicode_emoji", emoji_code: "1f419"},
        {emoji_name: "frown", user_id: 9999, reaction_type: "unicode_emoji", emoji_code: "1f641"},
    ],
};

set_global("message_store", {
    get(message_id) {
        assert.equal(message_id, 1001);
        return message;
    },
});

set_global("current_msg_list", {
    selected_message() {
        return {sent_by_me: true};
    },
    selected_row() {
        return $(".selected-row");
    },
    selected_id() {
        return 42;
    },
});

run_test("open_reactions_popover", () => {
    $(".selected-row").set_find_results(".actions_hover", $(".target-action"));
    $(".selected-row").set_find_results(".reaction_button", $(".target-reaction"));

    let called = false;
    emoji_picker.toggle_emoji_popover = function (target, id) {
        called = true;
        assert.equal(id, 42);
        assert.equal(target, $(".target-reaction")[0]);
    };

    assert(reactions.open_reactions_popover());
    assert(called);

    current_msg_list.selected_message = function () {
        return {sent_by_me: false};
    };

    called = false;
    emoji_picker.toggle_emoji_popover = function (target, id) {
        called = true;
        assert.equal(id, 42);
        assert.equal(target, $(".target-action")[0]);
    };

    assert(reactions.open_reactions_popover());
    assert(called);
});

run_test("basics", () => {
    blueslip.expect("warn", "Unknown user_id 8888 in reaction for message 1001");
    blueslip.expect("warn", "Unknown user_id 9999 in reaction for message 1001");
    const result = reactions.get_message_reactions(message);
    assert(reactions.current_user_has_reacted_to_emoji(message, "unicode_emoji,1f642"));
    assert(!reactions.current_user_has_reacted_to_emoji(message, "bogus"));

    result.sort((a, b) => a.count - b.count);

    const expected_result = [
        {
            emoji_name: "frown",
            reaction_type: "unicode_emoji",
            emoji_code: "1f641",
            local_id: "unicode_emoji,1f641",
            count: 1,
            user_ids: [7],
            label: "Cali reacted with :frown:",
            emoji_alt_code: false,
            class: "message_reaction",
        },
        {
            emoji_name: "inactive_realm_emoji",
            reaction_type: "realm_emoji",
            emoji_code: "992",
            local_id: "realm_emoji,992",
            count: 1,
            user_ids: [5],
            label: "You (click to remove) reacted with :inactive_realm_emoji:",
            emoji_alt_code: false,
            is_realm_emoji: true,
            url: "TBD",
            class: "message_reaction reacted",
        },
        {
            emoji_name: "smile",
            reaction_type: "unicode_emoji",
            emoji_code: "1f642",
            local_id: "unicode_emoji,1f642",
            count: 2,
            user_ids: [5, 6],
            label: "You (click to remove) and Bob van Roberts reacted with :smile:",
            emoji_alt_code: false,
            class: "message_reaction reacted",
        },
    ];
    assert.deepEqual(result, expected_result);
});

run_test("sending", (override) => {
    const message_id = 1001; // see above for setup
    let emoji_name = "smile"; // should be a current reaction

    override("reactions.add_reaction", () => {});
    override("reactions.remove_reaction", () => {});

    global.with_stub((stub) => {
        global.channel.del = stub.f;
        reactions.toggle_emoji_reaction(message_id, emoji_name);
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
        blueslip.expect("warn", "XHR Error Message.");
        global.channel.xhr_error_message = function () {
            return "XHR Error Message.";
        };
        args.error();
    });
    emoji_name = "alien"; // not set yet
    global.with_stub((stub) => {
        global.channel.post = stub.f;
        reactions.toggle_emoji_reaction(message_id, emoji_name);
        const args = stub.get_args("args").args;
        assert.equal(args.url, "/json/messages/1001/reactions");
        assert.deepEqual(args.data, {
            reaction_type: "unicode_emoji",
            emoji_name: "alien",
            emoji_code: "1f47d",
        });
    });

    emoji_name = "inactive_realm_emoji";
    global.with_stub((stub) => {
        // Test removing a deactivated realm emoji. An user can interact with a
        // deactivated realm emoji only by clicking on a reaction, hence, only
        // `process_reaction_click()` codepath supports deleting/adding a deactivated
        // realm emoji.
        global.channel.del = stub.f;
        reactions.process_reaction_click(message_id, "realm_emoji,992");
        const args = stub.get_args("args").args;
        assert.equal(args.url, "/json/messages/1001/reactions");
        assert.deepEqual(args.data, {
            reaction_type: "realm_emoji",
            emoji_name: "inactive_realm_emoji",
            emoji_code: "992",
        });
    });

    emoji_name = "zulip"; // Test adding zulip emoji.
    global.with_stub((stub) => {
        global.channel.post = stub.f;
        reactions.toggle_emoji_reaction(message_id, emoji_name);
        const args = stub.get_args("args").args;
        assert.equal(args.url, "/json/messages/1001/reactions");
        assert.deepEqual(args.data, {
            reaction_type: "zulip_extra_emoji",
            emoji_name: "zulip",
            emoji_code: "zulip",
        });
    });

    emoji_name = "unknown-emoji"; // Test sending an emoji unknown to frontend.
    blueslip.expect("warn", "Bad emoji name: " + emoji_name);
    reactions.toggle_emoji_reaction(message_id, emoji_name);
});

run_test("set_reaction_count", () => {
    const count_element = $.create("count-stub");
    const reaction_element = $.create("reaction-stub");

    reaction_element.set_find_results(".message_reaction_count", count_element);

    reactions.set_reaction_count(reaction_element, 5);

    assert.equal(count_element.text(), "5");
});

run_test("get_reaction_section", () => {
    const message_table = $.create(".message_table");
    const message_row = $.create("some-message-row");
    const message_reactions = $.create("our-reactions-section");

    message_table.set_find_results("[zid='555']", message_row);
    message_row.set_find_results(".message_reactions", message_reactions);

    const section = reactions.get_reaction_section(555);

    assert.equal(section, message_reactions);
});

run_test("emoji_reaction_title", () => {
    const message_id = 1001;
    const local_id = "unicode_emoji,1f642";

    assert.equal(
        reactions.get_reaction_title_data(message_id, local_id),
        "You (click to remove) and Bob van Roberts reacted with :smile:",
    );
});

run_test("add_and_remove_reaction", () => {
    // Insert 8ball for Alice.
    let alice_event = {
        message_id: 1001,
        reaction_type: "unicode_emoji",
        emoji_name: "8ball",
        emoji_code: "1f3b1",
        user_id: alice.user_id,
    };

    const message_reactions = $.create("our-reactions");

    reactions.get_reaction_section = function (message_id) {
        assert.equal(message_id, 1001);
        return message_reactions;
    };

    message_reactions.find = function (selector) {
        assert.equal(selector, ".reaction_button");
        return "reaction-button-stub";
    };

    let template_called;
    global.stub_templates((template_name, data) => {
        template_called = true;
        assert.equal(template_name, "message_reaction");
        assert.equal(data.class, "message_reaction reacted");
        assert(!data.is_realm_emoji);
        assert.equal(data.message_id, 1001);
        assert.equal(data.label, "You (click to remove) reacted with :8ball:");
        return "<new reaction html>";
    });

    let insert_called;
    $("<new reaction html>").insertBefore = function (element) {
        assert.equal(element, "reaction-button-stub");
        insert_called = true;
    };

    reactions.add_reaction(alice_event);
    assert(template_called);
    assert(insert_called);

    // Testing tooltip title data for added reaction.
    const local_id = "unicode_emoji,1f3b1";
    assert.equal(
        reactions.get_reaction_title_data(alice_event.message_id, local_id),
        "You (click to remove) reacted with :8ball:",
    );

    // Running add_reaction again should not result in any changes
    template_called = false;
    insert_called = false;
    reactions.add_reaction(alice_event);
    assert(!template_called);
    assert(!insert_called);

    // Now, have Bob react to the same emoji (update).

    const bob_event = {
        message_id: 1001,
        reaction_type: "unicode_emoji",
        emoji_name: "8ball",
        emoji_code: "1f3b1",
        user_id: bob.user_id,
    };

    const count_element = $.create("count-element");
    const reaction_element = $.create("reaction-element");
    reaction_element.set_find_results(".message_reaction_count", count_element);

    message_reactions.find = function (selector) {
        assert.equal(selector, "[data-reaction-id='unicode_emoji,1f3b1']");
        return reaction_element;
    };

    reactions.add_reaction(bob_event);
    assert.equal(count_element.text(), "2");

    reactions.remove_reaction(bob_event);
    assert.equal(count_element.text(), "1");

    let current_emojis = reactions.get_emojis_used_by_user_for_message_id(1001);
    assert.deepEqual(current_emojis, ["smile", "inactive_realm_emoji", "8ball"]);

    // Next, remove Alice's reaction, which exercises removing the
    // emoji icon.
    let removed;
    reaction_element.remove = function () {
        removed = true;
    };

    reactions.remove_reaction(alice_event);
    assert(removed);

    // Running remove_reaction again should not result in any changes
    removed = false;
    reactions.remove_reaction(alice_event);
    assert(!removed);

    current_emojis = reactions.get_emojis_used_by_user_for_message_id(1001);
    assert.deepEqual(current_emojis, ["smile", "inactive_realm_emoji"]);

    // Now add Cali's realm_emoji reaction.
    const cali_event = {
        message_id: 1001,
        reaction_type: "realm_emoji",
        emoji_name: "realm_emoji",
        emoji_code: "991",
        user_id: cali.user_id,
    };

    template_called = false;
    global.stub_templates((template_name, data) => {
        assert.equal(data.class, "message_reaction");
        assert(data.is_realm_emoji);
        template_called = true;
        return "<new reaction html>";
    });

    message_reactions.find = function (selector) {
        assert.equal(selector, ".reaction_button");
        return "reaction-button-stub";
    };

    reactions.add_reaction(cali_event);
    assert(template_called);
    assert(!reaction_element.hasClass("reacted"));

    // And then have Alice update it.
    alice_event = {
        message_id: 1001,
        reaction_type: "realm_emoji",
        emoji_name: "realm_emoji",
        emoji_code: "991",
        user_id: alice.user_id,
    };

    message_reactions.find = function (selector) {
        assert.equal(selector, "[data-reaction-id='realm_emoji,991']");
        return reaction_element;
    };
    reaction_element.prop = function () {};
    reactions.add_reaction(alice_event);

    const result = reactions.get_message_reactions(message);
    assert(reaction_element.hasClass("reacted"));
    const realm_emoji_data = result.filter((v) => v.emoji_name === "realm_emoji")[0];

    assert.equal(realm_emoji_data.count, 2);
    assert.equal(realm_emoji_data.is_realm_emoji, true);

    // And then remove Alice's reaction.
    reactions.remove_reaction(alice_event);
    assert(!reaction_element.hasClass("reacted"));
});

run_test("with_view_stubs", () => {
    // This function tests reaction events by mocking out calls to
    // the view.

    const message = {
        id: 2001,
        reactions: [],
    };

    message_store.get = function () {
        return message;
    };

    function test_view_calls(test_params) {
        const calls = [];

        function add_call_func(name) {
            return function (opts) {
                calls.push({
                    name,
                    opts,
                });
            };
        }

        reactions.view = {
            insert_new_reaction: add_call_func("insert_new_reaction"),
            update_existing_reaction: add_call_func("update_existing_reaction"),
            remove_reaction: add_call_func("remove_reaction"),
        };

        test_params.run_code();

        assert.deepEqual(calls, test_params.expected_view_calls);
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
    });
});

run_test("error_handling", () => {
    global.message_store.get = function () {
        return;
    };

    blueslip.expect("error", "reactions: Bad message id: 55");

    const bogus_event = {
        message_id: 55,
        reaction_type: "realm_emoji",
        emoji_name: "realm_emoji",
        emoji_code: "991",
        user_id: 99,
    };

    with_field(
        reactions,
        "current_user_has_reacted_to_emoji",
        () => true,
        () => {
            reactions.toggle_emoji_reaction(55, bogus_event.emoji_name);
        },
    );

    reactions.add_reaction(bogus_event);
    reactions.remove_reaction(bogus_event);
});

message_store.get = () => message;

run_test("remove spurious user", () => {
    // get coverage for removing non-user (it should just
    // silently fail)

    const event = {
        reaction_type: "unicode_emoji",
        emoji_name: "frown",
        emoji_code: "1f641",
        message_id: message.id,
        user_id: alice.user_id,
    };

    reactions.remove_reaction(event);
});

run_test("remove last user", () => {
    function assert_names(names) {
        assert.deepEqual(
            reactions.get_message_reactions(message).map((r) => r.emoji_name),
            names,
        );
    }

    assert_names(["smile", "frown", "inactive_realm_emoji", "realm_emoji"]);

    const event = {
        reaction_type: "unicode_emoji",
        emoji_name: "frown",
        emoji_code: "1f641",
        message_id: message.id,
        user_id: cali.user_id,
    };
    reactions.remove_reaction(event);

    assert_names(["smile", "inactive_realm_emoji", "realm_emoji"]);
});

run_test("local_reaction_id", () => {
    const reaction_info = {
        reaction_type: "unicode_emoji",
        emoji_code: "1f44d",
    };
    const local_id = reactions.get_local_reaction_id(reaction_info);
    assert.equal(local_id, "unicode_emoji,1f44d");
});

run_test("process_reaction_click", () => {
    const message_id = 1001;
    let expected_reaction_info = {
        reaction_type: "unicode_emoji",
        emoji_code: "1f3b1",
    };
    global.message_store.get = function (message_id) {
        assert.equal(message_id, 1001);
        return message;
    };

    expected_reaction_info = {
        reaction_type: "unicode_emoji",
        emoji_name: "smile",
        emoji_code: "1f642",
    };
    global.with_stub((stub) => {
        global.channel.del = stub.f;
        reactions.process_reaction_click(message_id, "unicode_emoji,1f642");
        const args = stub.get_args("args").args;
        assert.equal(args.url, "/json/messages/1001/reactions");
        assert.deepEqual(args.data, expected_reaction_info);
    });
});

run_test("warnings", () => {
    // Clean the slate
    delete message.clean_reactions;
    blueslip.expect("warn", "Unknown user_id 8888 in reaction for message 1001");
    blueslip.expect("warn", "Unknown user_id 9999 in reaction for message 1001");
    reactions.get_message_reactions(message);
});

run_test("code coverage", () => {
    /*
        We just silently fail in a few places in the reaction
        code, since events may come for messages that we don't
        have yet, or reactions may be for deactivated users, etc.

        Here we just cheaply ensure 100% line coverage to make
        it easy to enforce 100% coverage for more significant
        code additions.
    */
    message_store.get = (id) => {
        assert.equal(id, 42);
        return {
            reactions: [],
        };
    };

    reactions.remove_reaction({
        message_id: 42, // TODO: REACTIONS API
    });
});

run_test("duplicates", () => {
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

run_test("process_reaction_click errors", () => {
    global.message_store.get = () => undefined;
    blueslip.expect("error", "reactions: Bad message id: 55");
    blueslip.expect("error", "message_id for reaction click is unknown: 55");
    reactions.process_reaction_click(55, "whatever");

    global.message_store.get = () => message;
    blueslip.expect(
        "error",
        "Data integrity problem for reaction bad-local-id (message some-msg-id)",
    );
    reactions.process_reaction_click("some-msg-id", "bad-local-id");
});
