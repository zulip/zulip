"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const unread = mock_esm("../src/unread");

mock_esm("../src/user_status", {
    get_status_emoji: () => ({
        emoji_code: "20",
    }),
});

const {Filter} = zrequire("filter");
const narrow_state = zrequire("narrow_state");
const people = zrequire("people");
const pm_conversations = zrequire("pm_conversations");
const pm_list_data = zrequire("pm_list_data");
const message_lists = zrequire("message_lists");

const alice = {
    email: "alice@zulip.com",
    user_id: 101,
    full_name: "Alice",
};
const bob = {
    email: "bob@zulip.com",
    user_id: 102,
    full_name: "Bob",
};
const me = {
    email: "me@zulip.com",
    user_id: 103,
    full_name: "Me Myself",
};
const zoe = {
    email: "zoe@zulip.com",
    user_id: 104,
    full_name: "Zoe",
};
const cardelio = {
    email: "cardelio@zulip.com",
    user_id: 105,
    full_name: "Cardelio",
};
const iago = {
    email: "iago@zulip.com",
    user_id: 106,
    full_name: "Iago",
};
const bot_test = {
    email: "outgoingwebhook@zulip.com",
    user_id: 314,
    full_name: "Outgoing webhook",
    is_admin: false,
    is_bot: true,
};
people.add_active_user(alice);
people.add_active_user(bob);
people.add_active_user(me);
people.add_active_user(zoe);
people.add_active_user(cardelio);
people.add_active_user(iago);
people.add_active_user(bot_test);
people.initialize_current_user(me.user_id);

function test(label, f) {
    run_test(label, (helpers) => {
        message_lists.set_current(undefined);
        pm_conversations.clear_for_testing();
        f(helpers);
    });
}

function set_pm_with_filter(emails) {
    const active_filter = new Filter([{operator: "dm", operand: emails}]);
    message_lists.set_current({
        data: {
            filter: active_filter,
        },
    });
}

function check_list_info(list, length, more_unread, recipients_array) {
    assert.deepEqual(list.conversations_to_be_shown.length, length);
    assert.deepEqual(list.more_conversations_unread_count, more_unread);
    assert.deepEqual(
        list.conversations_to_be_shown.map((conversation) => conversation.recipients),
        recipients_array,
    );
}

test("get_conversations", ({override}) => {
    pm_conversations.recent.insert([alice.user_id, bob.user_id], 1);
    pm_conversations.recent.insert([me.user_id], 2);
    let num_unread_for_user_ids_string = 1;
    override(unread, "num_unread_for_user_ids_string", () => num_unread_for_user_ids_string);

    assert.equal(narrow_state.filter(), undefined);

    const expected_data = [
        {
            is_bot: false,
            is_active: false,
            is_group: false,
            is_zero: false,
            recipients: "Me Myself",
            unread: 1,
            url: "#narrow/dm/103-Me-Myself",
            user_circle_class: "user_circle_empty",
            user_ids_string: "103",
            status_emoji_info: {
                emoji_code: "20",
            },
        },
        {
            recipients: "Alice, Bob",
            user_ids_string: "101,102",
            unread: 1,
            is_zero: false,
            is_active: false,
            url: "#narrow/dm/101,102-group",
            user_circle_class: undefined,
            is_group: true,
            is_bot: false,
            status_emoji_info: undefined,
        },
    ];

    let pm_data = pm_list_data.get_conversations();
    assert.deepEqual(pm_data, expected_data);

    num_unread_for_user_ids_string = 0;

    pm_data = pm_list_data.get_conversations();
    expected_data[0].unread = 0;
    expected_data[0].is_zero = true;
    expected_data[1].unread = 0;
    expected_data[1].is_zero = true;
    assert.deepEqual(pm_data, expected_data);

    pm_data = pm_list_data.get_conversations();
    assert.deepEqual(pm_data, expected_data);

    expected_data.unshift({
        recipients: "Iago",
        user_ids_string: "106",
        unread: 0,
        is_zero: true,
        is_active: true,
        url: "#narrow/dm/106-Iago",
        status_emoji_info: {emoji_code: "20"},
        user_circle_class: "user_circle_empty",
        is_group: false,
        is_bot: false,
    });
    set_pm_with_filter("iago@zulip.com");
    pm_data = pm_list_data.get_conversations();
    assert.deepEqual(pm_data, expected_data);
});

test("get_conversations bot", ({override}) => {
    pm_conversations.recent.insert([alice.user_id, bob.user_id], 1);
    pm_conversations.recent.insert([bot_test.user_id], 2);

    override(unread, "num_unread_for_user_ids_string", () => 1);

    assert.equal(narrow_state.filter(), undefined);

    const expected_data = [
        {
            recipients: "Outgoing webhook",
            user_ids_string: "314",
            unread: 1,
            is_zero: false,
            is_active: false,
            url: "#narrow/dm/314-Outgoing-webhook",
            status_emoji_info: undefined,
            user_circle_class: "user_circle_empty",
            is_group: false,
            is_bot: true,
        },
        {
            recipients: "Alice, Bob",
            user_ids_string: "101,102",
            unread: 1,
            is_zero: false,
            is_active: false,
            url: "#narrow/dm/101,102-group",
            user_circle_class: undefined,
            status_emoji_info: undefined,
            is_group: true,
            is_bot: false,
        },
    ];

    const pm_data = pm_list_data.get_conversations();
    assert.deepEqual(pm_data, expected_data);
});

test("get_active_user_ids_string", () => {
    assert.equal(pm_list_data.get_active_user_ids_string(), undefined);

    const stream_filter = new Filter([{operator: "stream", operand: "test"}]);
    message_lists.set_current({
        data: {
            filter: stream_filter,
        },
    });
    assert.equal(pm_list_data.get_active_user_ids_string(), undefined);

    set_pm_with_filter("bob@zulip.com,alice@zulip.com");
    assert.equal(pm_list_data.get_active_user_ids_string(), "101,102");
});

test("get_list_info_unread_messages", ({override}) => {
    let list_info;
    assert.equal(narrow_state.filter(), undefined);

    // Initialize an empty list to start.
    list_info = pm_list_data.get_list_info(false);
    check_list_info(list_info, 0, 0, []);

    // Mock to arrange that each user has exactly 1 unread.
    override(unread, "num_unread_for_user_ids_string", () => 1);

    // Initially, append 2 conversations and check for the
    // `conversations_to_be_shown` returned in list_info.
    pm_conversations.recent.insert([alice.user_id], 1);
    pm_conversations.recent.insert([me.user_id], 2);

    list_info = pm_list_data.get_list_info(false);
    check_list_info(list_info, 2, 0, ["Me Myself", "Alice"]);

    // Visible conversations are limited to value of
    // `max_conversations_to_show_with_unreads`.
    // Verify that the oldest conversations are not shown and
    // their unreads are counted in more_conversations_unread_count.
    pm_conversations.recent.insert([bob.user_id], 3);
    pm_conversations.recent.insert([alice.user_id, bob.user_id], 4);
    pm_conversations.recent.insert([zoe.user_id], 5);
    pm_conversations.recent.insert([zoe.user_id, bob.user_id], 6);
    pm_conversations.recent.insert([zoe.user_id, alice.user_id], 7);
    pm_conversations.recent.insert([zoe.user_id, bob.user_id, alice.user_id], 8);
    pm_conversations.recent.insert([cardelio.user_id, zoe.user_id], 9);
    pm_conversations.recent.insert([cardelio.user_id, bob.user_id], 10);
    pm_conversations.recent.insert([cardelio.user_id, alice.user_id], 11);
    pm_conversations.recent.insert([cardelio.user_id, zoe.user_id, bob.user_id], 12);
    pm_conversations.recent.insert([cardelio.user_id, zoe.user_id, alice.user_id], 13);
    pm_conversations.recent.insert([cardelio.user_id, bob.user_id, alice.user_id], 14);
    pm_conversations.recent.insert([cardelio.user_id, bob.user_id, alice.user_id, zoe.user_id], 15);
    pm_conversations.recent.insert([cardelio.user_id], 16);
    pm_conversations.recent.insert([iago.user_id], 17);

    list_info = pm_list_data.get_list_info(false);
    check_list_info(list_info, 15, 2, [
        "Iago",
        "Cardelio",
        "Alice, Bob, Cardelio, Zoe",
        "Alice, Bob, Cardelio",
        "Alice, Cardelio, Zoe",
        "Bob, Cardelio, Zoe",
        "Alice, Cardelio",
        "Bob, Cardelio",
        "Cardelio, Zoe",
        "Alice, Bob, Zoe",
        "Alice, Zoe",
        "Bob, Zoe",
        "Zoe",
        "Alice, Bob",
        "Bob",
    ]);

    // Narrowing to direct messages with Alice adds older
    // one-on-one conversation with her to the list and one
    // unread is removed from more_conversations_unread_count.
    set_pm_with_filter("alice@zulip.com");
    list_info = pm_list_data.get_list_info(false);
    check_list_info(list_info, 16, 1, [
        "Iago",
        "Cardelio",
        "Alice, Bob, Cardelio, Zoe",
        "Alice, Bob, Cardelio",
        "Alice, Cardelio, Zoe",
        "Bob, Cardelio, Zoe",
        "Alice, Cardelio",
        "Bob, Cardelio",
        "Cardelio, Zoe",
        "Alice, Bob, Zoe",
        "Alice, Zoe",
        "Bob, Zoe",
        "Zoe",
        "Alice, Bob",
        "Bob",
        "Alice",
    ]);

    // Zooming will show all conversations and there will
    // be no unreads in more_conversations_unread_count.
    list_info = pm_list_data.get_list_info(true);
    check_list_info(list_info, 17, 0, [
        "Iago",
        "Cardelio",
        "Alice, Bob, Cardelio, Zoe",
        "Alice, Bob, Cardelio",
        "Alice, Cardelio, Zoe",
        "Bob, Cardelio, Zoe",
        "Alice, Cardelio",
        "Bob, Cardelio",
        "Cardelio, Zoe",
        "Alice, Bob, Zoe",
        "Alice, Zoe",
        "Bob, Zoe",
        "Zoe",
        "Alice, Bob",
        "Bob",
        "Me Myself",
        "Alice",
    ]);
});

test("get_list_info_no_unread_messages", ({override}) => {
    let list_info;
    override(unread, "num_unread_for_user_ids_string", () => 0);

    pm_conversations.recent.insert([alice.user_id], 1);
    pm_conversations.recent.insert([me.user_id], 2);
    pm_conversations.recent.insert([bob.user_id], 3);
    pm_conversations.recent.insert([zoe.user_id], 4);
    pm_conversations.recent.insert([cardelio.user_id], 5);
    pm_conversations.recent.insert([zoe.user_id, cardelio.user_id], 6);
    pm_conversations.recent.insert([alice.user_id, bob.user_id], 7);
    pm_conversations.recent.insert([zoe.user_id, bob.user_id], 8);
    pm_conversations.recent.insert([alice.user_id, cardelio.user_id], 9);
    pm_conversations.recent.insert([bob.user_id, cardelio.user_id], 10);

    // Visible conversations are limited to value of
    // `max_conversations_to_show`.
    list_info = pm_list_data.get_list_info(false);
    check_list_info(list_info, 8, 0, [
        "Bob, Cardelio",
        "Alice, Cardelio",
        "Bob, Zoe",
        "Alice, Bob",
        "Cardelio, Zoe",
        "Cardelio",
        "Zoe",
        "Bob",
    ]);

    // Narrowing to direct messages with Alice adds older
    // one-on-one conversation with her to the list.
    set_pm_with_filter("alice@zulip.com");
    list_info = pm_list_data.get_list_info(false);
    check_list_info(list_info, 9, 0, [
        "Bob, Cardelio",
        "Alice, Cardelio",
        "Bob, Zoe",
        "Alice, Bob",
        "Cardelio, Zoe",
        "Cardelio",
        "Zoe",
        "Bob",
        "Alice",
    ]);

    // Zooming will show all conversations.
    list_info = pm_list_data.get_list_info(true);
    check_list_info(list_info, 10, 0, [
        "Bob, Cardelio",
        "Alice, Cardelio",
        "Bob, Zoe",
        "Alice, Bob",
        "Cardelio, Zoe",
        "Cardelio",
        "Zoe",
        "Bob",
        "Me Myself",
        "Alice",
    ]);
});
