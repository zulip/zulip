"use strict";

const assert = require("node:assert/strict");

const {make_message_list} = require("./lib/message_list.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const settings_data = mock_esm("../src/settings_data");

const message_lists = zrequire("message_lists");
const people = zrequire("people");
const {set_current_user, set_realm} = zrequire("state_data");
const typing_data = zrequire("typing_data");
const typing_events = zrequire("typing_events");

const current_user = {};
set_current_user(current_user);
set_realm({});

const anna = {
    email: "anna@example.com",
    full_name: "Anna Karenina",
    user_id: 8,
};

const vronsky = {
    email: "vronsky@example.com",
    full_name: "Alexei Vronsky",
    user_id: 9,
};

const levin = {
    email: "levin@example.com",
    full_name: "Konstantin Levin",
    user_id: 10,
};

const kitty = {
    email: "kitty@example.com",
    full_name: "Kitty S",
    user_id: 11,
};

people.add_active_user(anna);
people.add_active_user(vronsky);
people.add_active_user(levin);
people.add_active_user(kitty);

run_test("render_notifications_for_narrow", ({override, mock_template}) => {
    override(current_user, "user_id", anna.user_id);
    override(settings_data, "user_can_access_all_other_users", () => true);
    const group = [anna.user_id, vronsky.user_id, levin.user_id, kitty.user_id];
    const conversation_key = typing_data.get_direct_message_conversation_key(group);
    const group_emails = `${anna.email},${vronsky.email},${levin.email},${kitty.email}`;
    message_lists.set_current(make_message_list([{operator: "dm", operand: group_emails}]));

    const $typing_notifications = $("#typing_notifications");

    mock_template("typing_notifications.hbs", true, (_args, rendered_html) => rendered_html);

    // Having only two(<MAX_USERS_TO_DISPLAY_NAME) typists, both of them
    // should be rendered but not 'Several people are typing…'
    typing_data.add_typist(conversation_key, anna.user_id);
    typing_data.add_typist(conversation_key, vronsky.user_id);
    typing_events.render_notifications_for_narrow();
    assert.ok($typing_notifications.visible());
    assert.ok($typing_notifications.html().includes(`${anna.full_name} is typing…`));
    assert.ok($typing_notifications.html().includes(`${vronsky.full_name} is typing…`));
    assert.ok(!$typing_notifications.html().includes("Several people are typing…"));

    // Having 3(=MAX_USERS_TO_DISPLAY_NAME) typists should also display only names
    typing_data.add_typist(conversation_key, levin.user_id);
    typing_events.render_notifications_for_narrow();
    assert.ok($typing_notifications.visible());
    assert.ok($typing_notifications.html().includes(`${anna.full_name} is typing…`));
    assert.ok($typing_notifications.html().includes(`${vronsky.full_name} is typing…`));
    assert.ok($typing_notifications.html().includes(`${levin.full_name} is typing…`));
    assert.ok(!$typing_notifications.html().includes("Several people are typing…"));

    // Having 4(>MAX_USERS_TO_DISPLAY_NAME) typists should display "Several people are typing…"
    typing_data.add_typist(conversation_key, kitty.user_id);
    typing_events.render_notifications_for_narrow();
    assert.ok($typing_notifications.visible());
    assert.ok($typing_notifications.html().includes("Several people are typing…"));
    assert.ok(!$typing_notifications.html().includes(`${anna.full_name} is typing…`));
    assert.ok(!$typing_notifications.html().includes(`${vronsky.full_name} is typing…`));
    assert.ok(!$typing_notifications.html().includes(`${levin.full_name} is typing…`));
    assert.ok(!$typing_notifications.html().includes(`${kitty.full_name} is typing…`));

    // #typing_notifications should be hidden when there are no typists.
    typing_data.remove_typist(conversation_key, anna.user_id);
    typing_data.remove_typist(conversation_key, vronsky.user_id);
    typing_data.remove_typist(conversation_key, levin.user_id);
    typing_data.remove_typist(conversation_key, kitty.user_id);
    typing_events.render_notifications_for_narrow();
    assert.ok(!$typing_notifications.visible());

    // #typing_notifications should be hidden for inaccessible users.
    override(settings_data, "user_can_access_all_other_users", () => false);
    const inaccessible_user = people.add_inaccessible_user(20);
    typing_data.add_typist(conversation_key, inaccessible_user.user_id);
    typing_data.add_typist(conversation_key, 21);
    typing_events.render_notifications_for_narrow();
    assert.ok(!$typing_notifications.visible());
});
