"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {page_params} = require("./lib/zpage_params");

const {Filter} = zrequire("filter");
const narrow_state = zrequire("narrow_state");
const people = zrequire("people");
const typing_data = zrequire("typing_data");
const typing_events = zrequire("typing_events");

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
    override(page_params, "user_id", anna.user_id);
    const group = [anna.user_id, vronsky.user_id, levin.user_id, kitty.user_id];
    const group_emails = `${anna.email},${vronsky.email},${levin.email},${kitty.email}`;
    narrow_state.set_current_filter(new Filter([{operator: "dm", operand: group_emails}]));

    const $typing_notifications = $("#typing_notifications");

    mock_template("typing_notifications.hbs", true, (_args, rendered_html) => rendered_html);

    // Having only two(<MAX_USERS_TO_DISPLAY_NAME) typists, both of them
    // should be rendered but not 'Several people are typing…'
    typing_data.add_typist(group, anna.user_id);
    typing_data.add_typist(group, vronsky.user_id);
    typing_events.render_notifications_for_narrow();
    assert.ok($typing_notifications.visible());
    assert.ok($typing_notifications.html().includes(`${anna.full_name} is typing…`));
    assert.ok($typing_notifications.html().includes(`${vronsky.full_name} is typing…`));
    assert.ok(!$typing_notifications.html().includes("Several people are typing…"));

    // Having 3(=MAX_USERS_TO_DISPLAY_NAME) typists should also display only names
    typing_data.add_typist(group, levin.user_id);
    typing_events.render_notifications_for_narrow();
    assert.ok($typing_notifications.visible());
    assert.ok($typing_notifications.html().includes(`${anna.full_name} is typing…`));
    assert.ok($typing_notifications.html().includes(`${vronsky.full_name} is typing…`));
    assert.ok($typing_notifications.html().includes(`${levin.full_name} is typing…`));
    assert.ok(!$typing_notifications.html().includes("Several people are typing…"));

    // Having 4(>MAX_USERS_TO_DISPLAY_NAME) typists should display "Several people are typing…"
    typing_data.add_typist(group, kitty.user_id);
    typing_events.render_notifications_for_narrow();
    assert.ok($typing_notifications.visible());
    assert.ok($typing_notifications.html().includes("Several people are typing…"));
    assert.ok(!$typing_notifications.html().includes(`${anna.full_name} is typing…`));
    assert.ok(!$typing_notifications.html().includes(`${vronsky.full_name} is typing…`));
    assert.ok(!$typing_notifications.html().includes(`${levin.full_name} is typing…`));
    assert.ok(!$typing_notifications.html().includes(`${kitty.full_name} is typing…`));

    // #typing_notifications should be hidden when there are no typists.
    typing_data.remove_typist(group, anna.user_id);
    typing_data.remove_typist(group, vronsky.user_id);
    typing_data.remove_typist(group, levin.user_id);
    typing_data.remove_typist(group, kitty.user_id);
    typing_events.render_notifications_for_narrow();
    assert.ok(!$typing_notifications.visible());
});
