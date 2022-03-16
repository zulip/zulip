"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const unread = mock_esm("../../static/js/unread");

mock_esm("../../static/js/user_status", {
    is_away: () => false,
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
people.add_active_user(bot_test);
people.initialize_current_user(me.user_id);

function test(label, f) {
    run_test(label, ({override, override_rewire}) => {
        narrow_state.reset_current_filter();
        pm_conversations.clear_for_testing();
        f({override, override_rewire});
    });
}

test("get_convos", ({override}) => {
    pm_conversations.recent.insert([alice.user_id, bob.user_id], 1);
    pm_conversations.recent.insert([me.user_id], 2);
    let num_unread_for_person = 1;
    override(unread, "num_unread_for_person", () => num_unread_for_person);

    assert.equal(narrow_state.filter(), undefined);

    const expected_data = [
        {
            is_active: false,
            is_group: false,
            is_zero: false,
            recipients: "Me Myself",
            unread: 1,
            url: "#narrow/pm-with/103-me",
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

    let pm_data = pm_list_data.get_convos();
    assert.deepEqual(pm_data, expected_data);

    num_unread_for_person = 0;

    pm_data = pm_list_data.get_convos();
    expected_data[0].unread = 0;
    expected_data[0].is_zero = true;
    expected_data[1].unread = 0;
    expected_data[1].is_zero = true;
    assert.deepEqual(pm_data, expected_data);

    pm_data = pm_list_data.get_convos();
    assert.deepEqual(pm_data, expected_data);
});

test("get_convos bot", ({override}) => {
    pm_conversations.recent.insert([alice.user_id, bob.user_id], 1);
    pm_conversations.recent.insert([bot_test.user_id], 2);

    override(unread, "num_unread_for_person", () => 1);

    assert.equal(narrow_state.filter(), undefined);

    const expected_data = [
        {
            recipients: "Outgoing webhook",
            user_ids_string: "314",
            unread: 1,
            is_zero: false,
            is_active: false,
            url: "#narrow/pm-with/314-outgoingwebhook",
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

    const pm_data = pm_list_data.get_convos();
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
