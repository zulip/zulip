"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");

const reload_state = mock_esm("../src/reload_state", {
    is_in_progress: () => false,
});

const people = zrequire("people");

const me = {
    email: "me@example.com",
    user_id: 30,
    full_name: "Me Myself",
    timezone: "America/Los_Angeles",
};

people.init();
people.add_active_user(me);
people.initialize_current_user(me.user_id);

run_test("report_late_add", ({override}) => {
    blueslip.expect("error", "Added user late");
    people.report_late_add(55, "foo@example.com");

    blueslip.expect("log", "Added user late");
    override(reload_state, "is_in_progress", () => true);
    people.report_late_add(55, "foo@example.com");
});

run_test("is_my_user_id", () => {
    blueslip.expect("error", "user_id is a string in my_user_id", 2);
    assert.equal(people.is_my_user_id("999"), false);
    assert.equal(people.is_my_user_id(me.user_id.toString()), true);
});

run_test("blueslip", () => {
    const unknown_email = "alicebobfred@example.com";

    blueslip.expect("debug", "User email operand unknown: " + unknown_email);
    people.id_matches_email_operand(42, unknown_email);

    blueslip.expect("error", "Unknown user_id");
    people.get_actual_name_from_user_id(9999);

    blueslip.expect("error", "Unknown email for get_user_id");
    people.get_user_id(unknown_email);

    blueslip.expect("warn", "No user_id provided");
    const person = {
        email: "person@example.com",
        user_id: undefined,
        full_name: "Person Person",
    };
    people.add_active_user(person);

    blueslip.expect("error", "No user_id found for email");
    const user_id = people.get_user_id("person@example.com");
    assert.equal(user_id, undefined);

    blueslip.expect("warn", "Unknown user ids: 1,2");
    people.user_ids_string_to_emails_string("1,2");

    blueslip.expect("warn", "Unknown emails");
    people.email_list_to_user_ids_string([unknown_email]);

    let message = {
        type: "private",
        display_recipient: [],
        sender_id: me.user_id,
    };
    blueslip.expect("error", "Empty recipient list in message", 3);
    people.pm_with_user_ids(message);
    people.all_user_ids_in_pm(message);
    assert.equal(people.pm_perma_link(message), undefined);

    const charles = {
        email: "charles@example.com",
        user_id: 451,
        full_name: "Charles Dickens",
        avatar_url: "charles.com/foo.png",
    };
    const maria = {
        email: "athens@example.com",
        user_id: 452,
        full_name: "Maria Athens",
    };
    people.add_active_user(charles);
    people.add_active_user(maria);

    message = {
        type: "private",
        display_recipient: [{id: maria.user_id}, {id: 42}, {id: charles.user_id}],
        sender_id: charles.user_id,
    };
    blueslip.expect("error", "Unknown user id in message");
    const reply_to = people.pm_reply_to(message);
    assert.ok(reply_to.includes("?"));

    blueslip.expect("error", "Unknown user_id in maybe_get_user_by_id");
    blueslip.expect("error", "Unknown people in message");
    const url = people.pm_with_url({type: "private", display_recipient: [{id: 42}]});
    assert.equal(url.indexOf("unk"), url.length - 3);

    blueslip.expect("error", "Undefined field id");
    assert.equal(people.my_custom_profile_data(undefined), undefined);

    blueslip.expect("error", "Trying to set undefined field id");
    people.set_custom_profile_field_data(maria.user_id, {});
});
