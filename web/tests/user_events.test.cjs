"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const message_live_update = mock_esm("../src/message_live_update");
const navbar_alerts = mock_esm("../src/navbar_alerts");
const settings_account = mock_esm("../src/settings_account", {
    maybe_update_deactivate_account_button() {},
    update_email() {},
    update_full_name() {},
    update_account_settings_display() {},
});
const settings_users = mock_esm("../src/settings_users", {
    update_user_data() {},
    update_view_on_deactivate() {},
    update_view_on_reactivate() {},
});
mock_esm("../src/user_profile", {
    update_profile_modal_ui() {},
    update_user_custom_profile_fields() {},
});
const stream_events = mock_esm("../src/stream_events");

const buddy_list = mock_esm("../src/buddy_list", {
    BuddyList: class {
        insert_or_move = noop;
    },
});

const buddy_data = new buddy_list.BuddyList();
buddy_list.buddy_list = buddy_data;

mock_esm("../src/activity_ui", {
    redraw() {},
});
mock_esm("../src/compose_state", {
    update_email() {},
});
mock_esm("../src/pm_list", {
    update_private_messages() {},
});
mock_esm("../src/settings", {
    update_lock_icon_in_sidebar() {},
});
mock_esm("../src/settings_linkifiers", {
    maybe_disable_widgets() {},
});
mock_esm("../src/settings_org", {
    maybe_disable_widgets() {},
    enable_or_disable_group_permission_settings() {},
});
mock_esm("../src/settings_profile_fields", {
    maybe_disable_widgets() {},
});
mock_esm("../src/settings_realm_user_settings_defaults", {
    maybe_disable_widgets() {},
});
mock_esm("../src/settings_streams", {
    maybe_disable_widgets() {},
});

const people = zrequire("people");
const settings_config = zrequire("settings_config");
const {set_current_user, set_realm} = zrequire("state_data");
const user_events = zrequire("user_events");

const current_user = {};
set_current_user(current_user);
set_realm({});

const me = {
    email: "me@example.com",
    user_id: 30,
    full_name: "Me Myself",
    is_admin: true,
    role: settings_config.user_role_values.member.code,
};

function initialize() {
    people.init();
    people.add_active_user(me);
    people.initialize_current_user(me.user_id);
}

initialize();

run_test("updates", ({override}) => {
    let person;

    const isaac = {
        email: "isaac@example.com",
        delivery_email: null,
        user_id: 32,
        full_name: "Isaac Newton",
    };
    people.add_active_user(isaac);

    override(navbar_alerts, "maybe_toggle_empty_required_profile_fields_banner", noop);
    user_events.update_person({
        user_id: isaac.user_id,
        role: settings_config.user_role_values.guest.code,
    });
    person = people.get_by_email(isaac.email);
    assert.ok(person.is_guest);
    assert.equal(person.role, settings_config.user_role_values.guest.code);
    user_events.update_person({
        user_id: isaac.user_id,
        role: settings_config.user_role_values.member.code,
    });
    person = people.get_by_email(isaac.email);
    assert.ok(!person.is_guest);
    assert.equal(person.role, settings_config.user_role_values.member.code);

    user_events.update_person({
        user_id: isaac.user_id,
        role: settings_config.user_role_values.moderator.code,
    });
    person = people.get_by_email(isaac.email);
    assert.equal(person.is_moderator, true);
    assert.equal(person.role, settings_config.user_role_values.moderator.code);

    user_events.update_person({
        user_id: isaac.user_id,
        role: settings_config.user_role_values.admin.code,
    });
    person = people.get_by_email(isaac.email);
    assert.equal(person.full_name, "Isaac Newton");
    assert.equal(person.is_moderator, true);
    assert.equal(person.is_admin, true);
    assert.equal(person.role, settings_config.user_role_values.admin.code);

    user_events.update_person({
        user_id: isaac.user_id,
        role: settings_config.user_role_values.owner.code,
    });
    assert.equal(person.is_admin, true);
    assert.equal(person.is_owner, true);
    assert.equal(person.role, settings_config.user_role_values.owner.code);

    person = people.get_by_email(me.email);
    assert.equal(person.role, settings_config.user_role_values.member.code);

    person = people.get_by_email(me.email);
    assert.equal(person.user_id, me.user_id);
    assert.equal(person.role, settings_config.user_role_values.member.code);

    person = people.get_by_email(isaac.email);
    assert.equal(person.user_id, isaac.user_id);
    assert.equal(person.role, settings_config.user_role_values.owner.code);

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
    assert.ok(!current_user.is_admin);

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

    person = people.get_by_email(isaac.email);
    assert.equal(person.delivery_email, null);
    user_events.update_person({
        user_id: isaac.user_id,
        delivery_email: "isaac-delivery@example.com",
    });
    person = people.get_by_email(isaac.email);
    assert.equal(person.delivery_email, "isaac-delivery@example.com");

    user_events.update_person({user_id: isaac.user_id, delivery_email: null});
    person = people.get_by_email(isaac.email);
    assert.equal(person.delivery_email, null);

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
    assert.ok(person.timezone);

    blueslip.expect("error", "Got update_person event for unexpected user");
    blueslip.expect("error", "Unknown user_id in maybe_get_user_by_id");
    assert.ok(!user_events.update_person({user_id: 29, full_name: "Sir Isaac Newton"}));

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

    let confirm_banner_hidden = false;
    settings_account.hide_confirm_email_banner = () => {
        confirm_banner_hidden = true;
    };

    user_events.update_person({user_id: me.user_id, delivery_email: "you@example.org"});
    assert.ok(updated);
    assert.ok(confirm_banner_hidden);

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

    let user_removed_from_streams = false;
    stream_events.remove_deactivated_user_from_all_streams = (user_id) => {
        assert.equal(user_id, isaac.user_id);
        user_removed_from_streams = true;
    };
    buddy_list.BuddyList.insert_or_move = noop;
    user_events.update_person({user_id: isaac.user_id, is_active: false});
    assert.ok(!people.is_person_active(isaac.user_id));
    assert.ok(user_removed_from_streams);

    user_events.update_person({user_id: isaac.user_id, is_active: true});
    assert.ok(people.is_person_active(isaac.user_id));

    stream_events.remove_deactivated_user_from_all_streams = noop;

    let bot_data_updated = false;
    settings_users.update_bot_data = (user_id) => {
        assert.equal(user_id, test_bot.user_id);
        bot_data_updated = true;
    };
    user_events.update_person({user_id: test_bot.user_id, is_active: false});
    assert.equal(bot_data_updated, true);

    bot_data_updated = false;
    user_events.update_person({user_id: test_bot.user_id, is_active: true});
    assert.ok(bot_data_updated);
});
