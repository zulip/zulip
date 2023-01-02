"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const unread = mock_esm("../../static/js/unread");

mock_esm("../../static/js/user_status", {
    get_status_emoji: () => ({
        emoji_code: 20,
    }),
});

const narrow_state = zrequire("narrow_state");
const people = zrequire("people");
const pm_conversations = zrequire("pm_conversations");
const pm_list_data = zrequire("pm_list_data");

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
const shiv = {
    email: "shiv@zulip.com",
    user_id: 106,
    full_name: "Shiv",
};
const desdemona = {
    email: "desdemona@zulip.com",
    user_id: 107,
    full_name: "Desdemona",
};
const lago = {
    email: "lago@zulip.com",
    user_id: 108,
    full_name: "Lago",
};
const aaron = {
    email: "aaron@zulip.com",
    user_id: 109,
    full_name: "Aaron",
};
const jai = {
    email: "jai@zulip.com",
    user_id: 110,
    full_name: "Jai",
};
const shivam = {
    email: "shivam@zulip.com",
    user_id: 111,
    full_name: "Shivam",
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
people.add_active_user(shiv);
people.add_active_user(desdemona);
people.add_active_user(lago);
people.add_active_user(aaron);
people.add_active_user(jai);
people.add_active_user(shivam);
people.add_active_user(bot_test);
people.initialize_current_user(me.user_id);

function test(label, f) {
    run_test(label, (helpers) => {
        narrow_state.reset_current_filter();
        pm_conversations.clear_for_testing();
        f(helpers);
    });
}

function get_list_info(zoomed) {
    return pm_list_data.get_list_info(zoomed);
}

test("get_conversations", ({override}) => {
    pm_conversations.recent.insert([alice.user_id, bob.user_id], 1);
    pm_conversations.recent.insert([me.user_id], 2);
    let num_unread_for_user_ids_string = 1;
    override(unread, "num_unread_for_user_ids_string", () => num_unread_for_user_ids_string);

    assert.equal(narrow_state.filter(), undefined);

    const expected_data = [
        {
            is_active: false,
            is_group: false,
            is_zero: false,
            recipients: "Me Myself",
            unread: 1,
            url: "#narrow/pm-with/103-Me-Myself",
            user_circle_class: "user_circle_empty",
            user_ids_string: "103",
            status_emoji_info: {
                emoji_code: 20,
            },
        },
        {
            recipients: "Alice, Bob",
            user_ids_string: "101,102",
            unread: 1,
            is_zero: false,
            is_active: false,
            url: "#narrow/pm-with/101,102-group",
            user_circle_class: undefined,
            is_group: true,
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
            url: "#narrow/pm-with/314-Outgoing-webhook",
            status_emoji_info: undefined,
            user_circle_class: "user_circle_green",
            is_group: false,
        },
        {
            recipients: "Alice, Bob",
            user_ids_string: "101,102",
            unread: 1,
            is_zero: false,
            is_active: false,
            url: "#narrow/pm-with/101,102-group",
            user_circle_class: undefined,
            status_emoji_info: undefined,
            is_group: true,
        },
    ];

    const pm_data = pm_list_data.get_conversations();
    assert.deepEqual(pm_data, expected_data);
});

test("get_active_user_ids_string", () => {
    assert.equal(pm_list_data.get_active_user_ids_string(), undefined);

    function set_filter_result(emails) {
        const active_filter = {
            operands: (operand) => {
                assert.equal(operand, "pm-with");
                return emails;
            },
        };
        narrow_state.set_current_filter(active_filter);
    }

    set_filter_result([]);
    assert.equal(pm_list_data.get_active_user_ids_string(), undefined);

    set_filter_result(["bob@zulip.com,alice@zulip.com"]);
    assert.equal(pm_list_data.get_active_user_ids_string(), "101,102");
});

function private_filter() {
    return {
        operands: (operand) => {
            assert.equal(operand, "is");
            return ["private", "starred"];
        },
    };
}

test("is_all_privates", () => {
    assert.equal(narrow_state.filter(), undefined);
    assert.equal(pm_list_data.is_all_privates(), false);

    narrow_state.set_current_filter(private_filter());
    assert.equal(pm_list_data.is_all_privates(), true);
});

test("get_list_info", ({override}) => {
    let list_info;
    assert.equal(narrow_state.filter(), undefined);

    // Initialize an empty list to start.
    const empty_list_info = get_list_info();

    assert.deepEqual(empty_list_info, {
        conversations_to_be_shown: [],
        more_conversations_unread_count: 0,
    });

    // TODO: We should just initialize a Filter object with `new
    // Filter` rather than creating a mock.
    function set_filter_result(emails) {
        const active_filter = {
            operands: (operand) => {
                assert.equal(operand, "pm-with");
                return emails;
            },
        };
        narrow_state.set_current_filter(active_filter);
    }
    set_filter_result([]);
    assert.equal(pm_list_data.get_active_user_ids_string(), undefined);

    // Mock to arrange that each user has exactly 1 unread.
    const num_unread_for_user_ids_string = 1;
    override(unread, "num_unread_for_user_ids_string", () => num_unread_for_user_ids_string);

    // Initially, we append 2 conversations and check for the
    // `conversations_to_be_shown` returned in list_info.
    pm_conversations.recent.insert([alice.user_id, bob.user_id], 1);
    pm_conversations.recent.insert([me.user_id], 2);

    list_info = get_list_info(false);
    const expected_list_info = [
        {
            is_active: false,
            is_group: false,
            is_zero: false,
            recipients: "Me Myself",
            status_emoji_info: {
                emoji_code: 20,
            },
            unread: 1,
            url: "#narrow/pm-with/103-Me-Myself",
            user_circle_class: "user_circle_empty",
            user_ids_string: "103",
        },
        {
            recipients: "Alice, Bob",
            user_ids_string: "101,102",
            unread: 1,
            is_active: false,
            url: "#narrow/pm-with/101,102-group",
            user_circle_class: undefined,
            status_emoji_info: undefined,
            is_group: true,
            is_zero: false,
        },
    ];

    assert.deepEqual(list_info, {
        conversations_to_be_shown: expected_list_info,
        more_conversations_unread_count: 0,
    });

    // Now, add additional conversations until we exceed
    // `max_conversations_to_show_with_unreads`.

    pm_conversations.recent.insert([zoe.user_id], 3);
    pm_conversations.recent.insert([cardelio.user_id], 4);
    pm_conversations.recent.insert([zoe.user_id, cardelio.user_id], 5);
    pm_conversations.recent.insert([shiv.user_id], 6);
    pm_conversations.recent.insert([cardelio.user_id, shiv.user_id], 7);
    pm_conversations.recent.insert([desdemona.user_id], 8);

    // We've now added a total of 8 conversations, which is the value
    // of `max_conversations_to_show_with_unreads` so even now, the
    // number of unreads in `more conversations` li-item should be 0.
    list_info = get_list_info(false);

    assert.deepEqual(list_info.conversations_to_be_shown.length, 8);
    assert.deepEqual(list_info.more_conversations_unread_count, 0);

    // Verify just the ordering of the conversations with unreads.
    assert.deepEqual(
        list_info.conversations_to_be_shown.map((conversation) => conversation.recipients),
        [
            "Desdemona",
            "Cardelio, Shiv",
            "Shiv",
            "Cardelio, Zoe",
            "Cardelio",
            "Zoe",
            "Me Myself",
            "Alice, Bob",
        ],
    );

    // After adding two more conversations, there will be 10
    // conversations, which exceeds
    // `max_conversations_to_show_with_unreads`. Verify that the
    // oldest conversations are not shown and their unreads are counted in
    // more_conversations_unread_count.

    pm_conversations.recent.insert([lago.user_id], 9);
    pm_conversations.recent.insert([zoe.user_id, lago.user_id], 10);
    list_info = get_list_info(false);
    assert.deepEqual(list_info.conversations_to_be_shown.length, 8);
    assert.deepEqual(list_info.more_conversations_unread_count, 2);
    assert.deepEqual(
        list_info.conversations_to_be_shown.map((conversation) => conversation.recipients),
        [
            "Lago, Zoe",
            "Lago",
            "Desdemona",
            "Cardelio, Shiv",
            "Shiv",
            "Cardelio, Zoe",
            "Cardelio",
            "Zoe",
        ],
    );

    // If we are narrowed to an older conversation, then that one gets
    // included in the list despite not being among the 8 most recent.

    set_filter_result(["alice@zulip.com,bob@zulip.com"]);
    list_info = get_list_info(false);
    assert.deepEqual(list_info.conversations_to_be_shown.length, 9);
    assert.deepEqual(list_info.more_conversations_unread_count, 1);
    assert.deepEqual(
        list_info.conversations_to_be_shown.map((conversation) => conversation.recipients),
        [
            "Lago, Zoe",
            "Lago",
            "Desdemona",
            "Cardelio, Shiv",
            "Shiv",
            "Cardelio, Zoe",
            "Cardelio",
            "Zoe",
            "Alice, Bob",
        ],
    );

    // Verify that if the list is zoomed, we'll include all 10
    // conversations in the correct order.

    list_info = get_list_info(true);
    assert.deepEqual(list_info.conversations_to_be_shown.length, 10);
    assert.deepEqual(
        list_info.conversations_to_be_shown.map((conversation) => conversation.recipients),
        [
            "Lago, Zoe",
            "Lago",
            "Desdemona",
            "Cardelio, Shiv",
            "Shiv",
            "Cardelio, Zoe",
            "Cardelio",
            "Zoe",
            "Me Myself",
            "Alice, Bob",
        ],
    );

    // We now test some no unreads cases.
    override(unread, "num_unread_for_user_ids_string", () => 0);
    pm_conversations.clear_for_testing();
    pm_conversations.recent.insert([alice.user_id], 1);
    pm_conversations.recent.insert([bob.user_id], 2);
    pm_conversations.recent.insert([me.user_id], 3);
    pm_conversations.recent.insert([zoe.user_id], 4);
    pm_conversations.recent.insert([cardelio.user_id], 5);
    pm_conversations.recent.insert([shiv.user_id], 6);
    pm_conversations.recent.insert([alice.user_id, bob.user_id], 7);

    // We have 7 conversations in total, but only most recent 5 are visible.
    list_info = get_list_info(false);
    assert.deepEqual(list_info.conversations_to_be_shown.length, 5);

    // If we set the oldest conversation as active, it will
    // also be included in the list with the most recent 5.

    set_filter_result(["alice@zulip.com"]);
    assert.equal(pm_list_data.get_active_user_ids_string(), "101");
    list_info = get_list_info(false);
    assert.deepEqual(list_info.conversations_to_be_shown.length, 6);
    assert.deepEqual(list_info.conversations_to_be_shown[5], {
        recipients: "Alice",
        user_ids_string: "101",
        unread: 0,
        is_zero: true,
        is_active: true,
        url: "#narrow/pm-with/101-Alice",
        status_emoji_info: {emoji_code: 20},
        user_circle_class: "user_circle_empty",
        is_group: false,
    });
    assert.deepEqual(
        list_info.conversations_to_be_shown.map((conversation) => conversation.recipients),
        ["Alice, Bob", "Shiv", "Cardelio", "Zoe", "Me Myself", "Alice"],
    );
});
