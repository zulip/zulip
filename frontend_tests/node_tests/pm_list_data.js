"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const narrow_state = mock_esm("../../static/js/narrow_state");
const unread = mock_esm("../../static/js/unread");

mock_esm("../../static/js/user_status", {
    is_away: () => false,
    get_status_emoji: () => ({
        emoji_code: 20,
    }),
});

const people = zrequire("people");
const pm_conversations = zrequire("pm_conversations");
const pm_list = zrequire("pm_list");
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
const aaron = {
    email: "aaron@zulip.com",
    user_id: 103,
    full_name: "Aaron",
};
const zoe = {
    email: "zoe@zulip.com",
    user_id: 104,
    full_name: "Zoe",
};
const cordelio = {
    email: "cordelio@zulip.com",
    user_id: 105,
    full_name: "Cordelio",
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
const me = {
    email: "me@zulip.com",
    user_id: 109,
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
people.add_active_user(aaron);
people.add_active_user(zoe);
people.add_active_user(cordelio);
people.add_active_user(shiv);
people.add_active_user(desdemona);
people.add_active_user(lago);
people.add_active_user(me);
people.add_active_user(bot_test);

people.initialize_current_user(me.user_id);

function get_list_info(zoomed) {
    return pm_list_data.get_list_info(zoomed);
}

function test(label, f) {
    run_test(label, ({override, override_rewire}) => {
        pm_conversations.clear_for_testing();
        pm_list.clear_for_testing();
        f({override, override_rewire});
    });
}

test("get_list_info_with_default_view", ({override}) => {
    let list_info;
    const timestamp = 0;
    override(narrow_state, "filter", () => {});

    // we declare a empty list to make sure we don't have any PM thread present already.
    const empty_list_info = get_list_info();

    assert.deepEqual(empty_list_info, {
        convos_to_be_shown: [],
        more_convos_unread_count: 0,
    });

    // we would allot the number of unreads to always be 1 in each PM thread.
    const num_unread_for_person = 1;

    // intially we append 2 conversations and check for the `convos_to_be_shown` in list_info returned.
    pm_conversations.recent.insert([101, 102], timestamp);
    pm_conversations.recent.insert([103], timestamp);

    override(unread, "num_unread_for_person", () => num_unread_for_person);

    list_info = get_list_info();

    const expected_list_info = [
        {
            is_active: false,
            is_group: false,
            is_zero: false,
            recipients: "Aaron",
            status_emoji_info: {
                emoji_code: 20,
            },
            unread: 1,
            url: "#narrow/pm-with/103-aaron",
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
        convos_to_be_shown: expected_list_info,
        more_convos_unread_count: 0,
    });

    // Now we need to test that until the number of conversations reach `max_convos_to_show_with_unreads`
    // we have all those conversations shown in default view itself.

    // To check this we go with checking the number of unreads present in `more conversations` li-item.
    pm_conversations.recent.insert([104], timestamp);
    pm_conversations.recent.insert([105], timestamp);
    pm_conversations.recent.insert([106], timestamp);
    pm_conversations.recent.insert([107], timestamp);
    pm_conversations.recent.insert([108], timestamp);
    pm_conversations.recent.insert([107, 108], timestamp);

    // We added a total of 8 conversations, which is the value of `max_convos_to_show_with_unreads`
    // so even now, the number of unreads in `more conversations` li-item should be 0.
    list_info = get_list_info();

    assert.deepEqual(list_info.more_convos_unread_count, 0);

    // Now after adding one more PM, the length in default view would be 9 which would
    // exceed `max_convos_to_show_with_unreads`, so the number of unreads present in
    // `more conversations` li-item should be 1.
    pm_conversations.recent.insert([102, 104], timestamp);

    list_info = get_list_info();

    assert.deepEqual(list_info.more_convos_unread_count, 1);
});
