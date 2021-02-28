"use strict";

const {strict: assert} = require("assert");

const {rewiremock, set_global, use} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

rewiremock("../../static/js/activity").with({
    redraw() {},
});

rewiremock("../../static/js/settings_linkifiers").with({
    maybe_disable_widgets() {},
});
rewiremock("../../static/js/settings_org").with({
    maybe_disable_widgets() {},
});
rewiremock("../../static/js/settings_profile_fields").with({
    maybe_disable_widgets() {},
});
rewiremock("../../static/js/settings_streams").with({
    maybe_disable_widgets() {},
});
rewiremock("../../static/js/settings_users").with({
    update_user_data() {},
});

rewiremock("../../static/js/gear_menu").with({
    update_org_settings_menu_item() {},
});
const page_params = set_global("page_params", {
    is_admin: true,
});

rewiremock("../../static/js/pm_list").with({
    update_private_messages() {},
});

rewiremock("../../static/js/narrow_state").with({
    update_email() {},
});

rewiremock("../../static/js/compose").with({
    update_email() {},
});

const settings_account = {
    update_email() {},
    update_full_name() {},
};

rewiremock("../../static/js/settings_account").with(settings_account);

const message_live_update = rewiremock("../../static/js/message_live_update").with({});

const {people, settings_config, user_events} = use(
    "fold_dict",
    "people",
    "settings_config",
    "user_events",
);

const me = {
    email: "me@example.com",
    user_id: 30,
    full_name: "Me Myself",
    is_admin: true,
};

function initialize() {
    people.init();
    people.add_active_user(me);
    people.initialize_current_user(me.user_id);
}

initialize();

run_test("updates", () => {
    let person;

    const isaac = {
        email: "isaac@example.com",
        user_id: 32,
        full_name: "Isaac Newton",
    };
    people.add_active_user(isaac);

    user_events.update_person({
        user_id: isaac.user_id,
        role: settings_config.user_role_values.guest.code,
    });
    person = people.get_by_email(isaac.email);
    assert(person.is_guest);
    user_events.update_person({
        user_id: isaac.user_id,
        role: settings_config.user_role_values.member.code,
    });
    person = people.get_by_email(isaac.email);
    assert(!person.is_guest);

    user_events.update_person({
        user_id: isaac.user_id,
        role: settings_config.user_role_values.admin.code,
    });
    person = people.get_by_email(isaac.email);
    assert.equal(person.full_name, "Isaac Newton");
    assert.equal(person.is_admin, true);

    user_events.update_person({
        user_id: isaac.user_id,
        role: settings_config.user_role_values.owner.code,
    });
    assert.equal(person.is_admin, true);
    assert.equal(person.is_owner, true);

    let user_id;
    let full_name;
    message_live_update.update_user_full_name = (user_id_arg, full_name_arg) => {
        user_id = user_id_arg;
        full_name = full_name_arg;
    };

    user_events.update_person({user_id: isaac.user_id, full_name: "Sir Isaac"});
    person = people.get_by_email(isaac.email);
    assert.equal(person.full_name, "Sir Isaac");
    assert.equal(person.is_admin, true);
    assert.equal(user_id, isaac.user_id);
    assert.equal(full_name, "Sir Isaac");

    user_events.update_person({
        user_id: me.user_id,
        role: settings_config.user_role_values.member.code,
    });
    assert(!page_params.is_admin);

    user_events.update_person({user_id: me.user_id, full_name: "Me V2"});
    assert.equal(people.my_full_name(), "Me V2");
    assert.equal(user_id, me.user_id);
    assert.equal(full_name, "Me V2");

    user_events.update_person({user_id: isaac.user_id, new_email: "newton@example.com"});
    person = people.get_by_user_id(isaac.user_id);
    assert.equal(person.email, "newton@example.com");
    assert.equal(person.full_name, "Sir Isaac");

    user_events.update_person({user_id: me.user_id, new_email: "meforu@example.com"});
    person = people.get_by_user_id(me.user_id);
    assert.equal(person.email, "meforu@example.com");
    assert.equal(person.full_name, "Me V2");

    let avatar_url;
    message_live_update.update_avatar = (user_id_arg, avatar_url_arg) => {
        user_id = user_id_arg;
        avatar_url = avatar_url_arg;
    };

    user_events.update_person({user_id: isaac.user_id, full_name: "Sir Isaac"});
    person = people.get_by_email(isaac.email);
    assert.equal(person.full_name, "Sir Isaac");
    assert.equal(person.is_admin, true);
    assert.equal(user_id, isaac.user_id);
    assert.equal(full_name, "Sir Isaac");

    user_events.update_person({user_id: isaac.user_id, avatar_url: "http://gravatar.com/123456"});
    person = people.get_by_email(isaac.email);
    assert.equal(person.full_name, "Sir Isaac");
    assert.equal(user_id, isaac.user_id);
    assert.equal(person.avatar_url, avatar_url);

    user_events.update_person({user_id: me.user_id, avatar_url: "http://gravatar.com/789456"});
    person = people.get_by_email(me.email);
    assert.equal(person.full_name, "Me V2");
    assert.equal(user_id, me.user_id);
    assert.equal(person.avatar_url, avatar_url);

    user_events.update_person({user_id: me.user_id, timezone: "UTC"});
    person = people.get_by_email(me.email);
    assert(person.timezone);

    blueslip.expect("error", "Got update_person event for unexpected user 29");
    blueslip.expect("error", "Unknown user_id in get_by_user_id: 29");
    assert(!user_events.update_person({user_id: 29, full_name: "Sir Isaac Newton"}));

    me.profile_data = {};
    user_events.update_person({
        user_id: me.user_id,
        custom_profile_field: {id: 3, value: "Value", rendered_value: "<p>Value</p>"},
    });
    person = people.get_by_email(me.email);
    assert.equal(person.profile_data[3].value, "Value");
    assert.equal(person.profile_data[3].rendered_value, "<p>Value</p>");

    let updated = false;
    settings_account.update_email = (email) => {
        assert.equal(email, "you@example.org");
        updated = true;
    };

    user_events.update_person({user_id: me.user_id, delivery_email: "you@example.org"});
    assert(updated);

    const test_bot = {
        email: "test-bot@example.com",
        user_id: 35,
        full_name: "Test Bot",
        is_bot: true,
        bot_owner_id: isaac.id,
    };
    people.add_active_user(test_bot);

    user_events.update_person({user_id: test_bot.user_id, bot_owner_id: me.user_id});
    person = people.get_by_email(test_bot.email);
    assert.equal(person.bot_owner_id, me.user_id);
});
