"use strict";

const people = zrequire("people");

const return_false = function () {
    return false;
};
const return_true = function () {
    return true;
};
set_global("reload_state", {
    is_in_progress: return_false,
});

const me = {
    email: "me@example.com",
    user_id: 30,
    full_name: "Me Myself",
    timezone: "US/Pacific",
};

people.init();
people.add_active_user(me);
people.initialize_current_user(me.user_id);

run_test("report_late_add", () => {
    blueslip.expect("error", "Added user late: user_id=55 email=foo@example.com");
    people.report_late_add(55, "foo@example.com");

    blueslip.expect("log", "Added user late: user_id=55 email=foo@example.com");
    reload_state.is_in_progress = return_true;
    people.report_late_add(55, "foo@example.com");
});

run_test("is_my_user_id", () => {
    blueslip.expect("error", "user_id is a string in my_user_id: 999");
    assert.equal(people.is_my_user_id("999"), false);

    blueslip.expect("error", "user_id is a string in my_user_id: 30");
    assert.equal(people.is_my_user_id(me.user_id.toString()), true);
});

run_test("blueslip", () => {
    const unknown_email = "alicebobfred@example.com";

    blueslip.expect("debug", "User email operand unknown: " + unknown_email);
    people.id_matches_email_operand(42, unknown_email);

    blueslip.expect("error", "Unknown user_id: 9999");
    people.get_actual_name_from_user_id(9999);

    blueslip.expect("error", "Unknown email for get_user_id: " + unknown_email);
    people.get_user_id(unknown_email);

    blueslip.expect("warn", "No user_id provided for person@example.com");
    const person = {
        email: "person@example.com",
        user_id: undefined,
        full_name: "Person Person",
    };
    people.add_active_user(person);

    blueslip.expect("error", "No user_id found for person@example.com");
    const user_id = people.get_user_id("person@example.com");
    assert.equal(user_id, undefined);

    blueslip.expect("warn", "Unknown user ids: 1,2");
    people.user_ids_string_to_emails_string("1,2");

    blueslip.expect("warn", "Unknown emails: " + unknown_email);
    people.email_list_to_user_ids_string([unknown_email]);

    let message = {
        type: "private",
        display_recipient: [],
        sender_id: me.user_id,
    };
    blueslip.expect("error", "Empty recipient list in message", 4);
    people.pm_with_user_ids(message);
    people.group_pm_with_user_ids(message);
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
    blueslip.expect("error", "Unknown user id in message: 42");
    const reply_to = people.pm_reply_to(message);
    assert(reply_to.includes("?"));

    people.pm_with_user_ids = function () {
        return [42];
    };
    people.get_by_user_id = function () {
        return;
    };
    blueslip.expect("error", "Unknown people in message");
    const uri = people.pm_with_url({});
    assert.equal(uri.indexOf("unk"), uri.length - 3);

    blueslip.expect("error", "Undefined field id");
    assert.equal(people.my_custom_profile_data(undefined), undefined);

    blueslip.expect("error", "Trying to set undefined field id");
    people.set_custom_profile_field_data(maria.user_id, {});
});
