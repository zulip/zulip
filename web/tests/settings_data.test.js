"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const {current_user, page_params, realm, user_settings} = require("./lib/zpage_params");

const settings_data = zrequire("settings_data");
const settings_config = zrequire("settings_config");
const user_groups = zrequire("user_groups");

/*
    Some methods in settings_data are fairly
    trivial, so the meaningful tests happen
    at the higher layers, such as when we
    test people.js.
*/

const isaac = {
    email: "isaac@example.com",
    delivery_email: "isaac-delivery@example.com",
    user_id: 30,
    full_name: "Isaac",
};

run_test("user_can_change_email", () => {
    const can_change_email = settings_data.user_can_change_email;

    current_user.is_admin = true;
    assert.equal(can_change_email(), true);

    current_user.is_admin = false;
    realm.realm_email_changes_disabled = true;
    assert.equal(can_change_email(), false);

    realm.realm_email_changes_disabled = false;
    assert.equal(can_change_email(), true);
});

run_test("user_can_change_name", () => {
    const can_change_name = settings_data.user_can_change_name;

    current_user.is_admin = true;
    assert.equal(can_change_name(), true);

    current_user.is_admin = false;
    realm.realm_name_changes_disabled = true;
    realm.server_name_changes_disabled = false;
    assert.equal(can_change_name(), false);

    realm.realm_name_changes_disabled = false;
    realm.server_name_changes_disabled = false;
    assert.equal(can_change_name(), true);

    realm.realm_name_changes_disabled = false;
    realm.server_name_changes_disabled = true;
    assert.equal(can_change_name(), false);
});

run_test("user_can_change_avatar", () => {
    const can_change_avatar = settings_data.user_can_change_avatar;

    current_user.is_admin = true;
    assert.equal(can_change_avatar(), true);

    current_user.is_admin = false;
    realm.realm_avatar_changes_disabled = true;
    realm.server_avatar_changes_disabled = false;
    assert.equal(can_change_avatar(), false);

    realm.realm_avatar_changes_disabled = false;
    realm.server_avatar_changes_disabled = false;
    assert.equal(can_change_avatar(), true);

    realm.realm_avatar_changes_disabled = false;
    realm.server_avatar_changes_disabled = true;
    assert.equal(can_change_avatar(), false);
});

run_test("user_can_change_logo", () => {
    const can_change_logo = settings_data.user_can_change_logo;

    current_user.is_admin = true;
    realm.zulip_plan_is_not_limited = true;
    assert.equal(can_change_logo(), true);

    current_user.is_admin = false;
    realm.zulip_plan_is_not_limited = false;
    assert.equal(can_change_logo(), false);

    current_user.is_admin = true;
    realm.zulip_plan_is_not_limited = false;
    assert.equal(can_change_logo(), false);

    current_user.is_admin = false;
    realm.zulip_plan_is_not_limited = true;
    assert.equal(can_change_logo(), false);
});

function test_policy(label, policy, validation_func) {
    run_test(label, () => {
        current_user.is_admin = true;
        realm[policy] = settings_config.common_policy_values.by_admins_only.code;
        assert.equal(validation_func(), true);

        current_user.is_admin = false;
        assert.equal(validation_func(), false);

        current_user.is_moderator = true;
        realm[policy] = settings_config.common_policy_values.by_moderators_only.code;
        assert.equal(validation_func(), true);

        current_user.is_moderator = false;
        assert.equal(validation_func(), false);

        current_user.is_guest = true;
        realm[policy] = settings_config.common_policy_values.by_members.code;
        assert.equal(validation_func(), false);

        current_user.is_guest = false;
        assert.equal(validation_func(), true);

        page_params.is_spectator = true;
        realm[policy] = settings_config.common_policy_values.by_members.code;
        assert.equal(validation_func(), false);

        page_params.is_spectator = false;
        assert.equal(validation_func(), true);

        realm[policy] = settings_config.common_policy_values.by_full_members.code;
        current_user.user_id = 30;
        isaac.date_joined = new Date(Date.now());
        settings_data.initialize(isaac.date_joined);
        realm.realm_waiting_period_threshold = 10;
        assert.equal(validation_func(), false);

        isaac.date_joined = new Date(Date.now() - 20 * 86400000);
        settings_data.initialize(isaac.date_joined);
        assert.equal(validation_func(), true);
    });
}

test_policy(
    "user_can_create_private_streams",
    "realm_create_private_stream_policy",
    settings_data.user_can_create_private_streams,
);
test_policy(
    "user_can_create_public_streams",
    "realm_create_public_stream_policy",
    settings_data.user_can_create_public_streams,
);
test_policy(
    "user_can_subscribe_other_users",
    "realm_invite_to_stream_policy",
    settings_data.user_can_subscribe_other_users,
);
test_policy(
    "user_can_invite_others_to_realm",
    "realm_invite_to_realm_policy",
    settings_data.user_can_invite_users_by_email,
);
test_policy(
    "user_can_move_messages_between_streams",
    "realm_move_messages_between_streams_policy",
    settings_data.user_can_move_messages_between_streams,
);
test_policy(
    "user_can_edit_user_groups",
    "realm_user_group_edit_policy",
    settings_data.user_can_edit_user_groups,
);
test_policy(
    "user_can_add_custom_emoji",
    "realm_add_custom_emoji_policy",
    settings_data.user_can_add_custom_emoji,
);

function test_message_policy(label, policy, validation_func) {
    run_test(label, () => {
        current_user.is_admin = true;
        realm[policy] = settings_config.common_message_policy_values.by_admins_only.code;
        assert.equal(validation_func(), true);

        current_user.is_admin = false;
        current_user.is_moderator = true;
        assert.equal(validation_func(), false);

        realm[policy] = settings_config.common_message_policy_values.by_moderators_only.code;
        assert.equal(validation_func(), true);

        current_user.is_moderator = false;
        assert.equal(validation_func(), false);

        current_user.is_guest = true;
        realm[policy] = settings_config.common_message_policy_values.by_everyone.code;
        assert.equal(validation_func(), true);

        realm[policy] = settings_config.common_message_policy_values.by_members.code;
        assert.equal(validation_func(), false);

        current_user.is_guest = false;
        assert.equal(validation_func(), true);

        realm[policy] = settings_config.common_message_policy_values.by_full_members.code;
        current_user.user_id = 30;
        isaac.date_joined = new Date(Date.now());
        realm.realm_waiting_period_threshold = 10;
        settings_data.initialize(isaac.date_joined);
        assert.equal(validation_func(), false);

        isaac.date_joined = new Date(Date.now() - 20 * 86400000);
        settings_data.initialize(isaac.date_joined);
        assert.equal(validation_func(), true);
    });
}

test_message_policy(
    "user_can_move_messages_to_another_topic",
    "realm_edit_topic_policy",
    settings_data.user_can_move_messages_to_another_topic,
);

run_test("user_can_move_messages_to_another_topic_nobody_case", () => {
    current_user.is_admin = true;
    current_user.is_guest = false;
    realm.realm_edit_topic_policy = settings_config.edit_topic_policy_values.nobody.code;
    assert.equal(settings_data.user_can_move_messages_to_another_topic(), false);
});

run_test("user_can_move_messages_between_streams_nobody_case", () => {
    current_user.is_admin = true;
    current_user.is_guest = false;
    realm.realm_move_messages_between_streams_policy =
        settings_config.move_messages_between_streams_policy_values.nobody.code;
    assert.equal(settings_data.user_can_move_messages_between_streams(), false);
});

test_message_policy(
    "user_can_delete_own_message",
    "realm_delete_own_message_policy",
    settings_data.user_can_delete_own_message,
);

run_test("using_dark_theme", () => {
    user_settings.color_scheme = settings_config.color_scheme_values.night.code;
    assert.equal(settings_data.using_dark_theme(), true);

    user_settings.color_scheme = settings_config.color_scheme_values.automatic.code;

    window.matchMedia = (query) => {
        assert.equal(query, "(prefers-color-scheme: dark)");
        return {matches: true};
    };
    assert.equal(settings_data.using_dark_theme(), true);

    window.matchMedia = (query) => {
        assert.equal(query, "(prefers-color-scheme: dark)");
        return {matches: false};
    };
    assert.equal(settings_data.using_dark_theme(), false);

    user_settings.color_scheme = settings_config.color_scheme_values.day.code;
    assert.equal(settings_data.using_dark_theme(), false);
});

run_test("user_can_invite_others_to_realm_nobody_case", () => {
    current_user.is_admin = true;
    current_user.is_guest = false;
    realm.realm_invite_to_realm_policy =
        settings_config.email_invite_to_realm_policy_values.nobody.code;
    assert.equal(settings_data.user_can_invite_users_by_email(), false);
});

run_test("user_can_create_web_public_streams", () => {
    current_user.is_owner = true;
    realm.server_web_public_streams_enabled = true;
    realm.realm_enable_spectator_access = true;
    realm.realm_create_web_public_stream_policy =
        settings_config.create_web_public_stream_policy_values.nobody.code;
    assert.equal(settings_data.user_can_create_web_public_streams(), false);

    realm.realm_create_web_public_stream_policy =
        settings_config.create_web_public_stream_policy_values.by_owners_only.code;
    assert.equal(settings_data.user_can_create_web_public_streams(), true);

    realm.realm_enable_spectator_access = false;
    realm.server_web_public_streams_enabled = true;
    assert.equal(settings_data.user_can_create_web_public_streams(), false);

    realm.realm_enable_spectator_access = true;
    realm.server_web_public_streams_enabled = false;
    assert.equal(settings_data.user_can_create_web_public_streams(), false);

    realm.realm_enable_spectator_access = false;
    realm.server_web_public_streams_enabled = false;
    assert.equal(settings_data.user_can_create_web_public_streams(), false);

    realm.realm_enable_spectator_access = true;
    realm.server_web_public_streams_enabled = true;
    current_user.is_owner = false;
    current_user.is_admin = true;
    assert.equal(settings_data.user_can_create_web_public_streams(), false);

    realm.realm_create_web_public_stream_policy =
        settings_config.create_web_public_stream_policy_values.by_admins_only.code;
    assert.equal(settings_data.user_can_create_web_public_streams(), true);

    current_user.is_admin = false;
    current_user.is_moderator = true;
    assert.equal(settings_data.user_can_create_web_public_streams(), false);

    realm.realm_create_web_public_stream_policy =
        settings_config.create_web_public_stream_policy_values.by_moderators_only.code;
    assert.equal(settings_data.user_can_create_web_public_streams(), true);

    current_user.is_moderator = false;
    assert.equal(settings_data.user_can_create_web_public_streams(), false);
});

run_test("user_email_not_configured", () => {
    const user_email_not_configured = settings_data.user_email_not_configured;

    current_user.is_owner = false;
    assert.equal(user_email_not_configured(), false);

    current_user.is_owner = true;
    current_user.delivery_email = "";
    assert.equal(user_email_not_configured(), true);

    current_user.delivery_email = "name@example.com";
    assert.equal(user_email_not_configured(), false);
});

run_test("user_can_create_multiuse_invite", () => {
    const admin_user_id = 1;
    const moderator_user_id = 2;
    const member_user_id = 3;

    const admins = {
        name: "Admins",
        id: 1,
        members: new Set([admin_user_id]),
        is_system_group: true,
        direct_subgroup_ids: new Set([]),
    };
    const moderators = {
        name: "Moderators",
        id: 2,
        members: new Set([moderator_user_id]),
        is_system_group: true,
        direct_subgroup_ids: new Set([1]),
    };

    user_groups.initialize({realm_user_groups: [admins, moderators]});

    assert.equal(settings_data.user_can_create_multiuse_invite(), false);

    realm.realm_create_multiuse_invite_group = 1;
    current_user.user_id = admin_user_id;
    assert.equal(settings_data.user_can_create_multiuse_invite(), true);

    current_user.user_id = moderator_user_id;
    assert.equal(settings_data.user_can_create_multiuse_invite(), false);

    realm.realm_create_multiuse_invite_group = 2;
    current_user.user_id = moderator_user_id;
    assert.equal(settings_data.user_can_create_multiuse_invite(), true);

    current_user.user_id = member_user_id;
    assert.equal(settings_data.user_can_create_multiuse_invite(), false);
});

run_test("can_edit_user_group", () => {
    const students = {
        description: "Students group",
        name: "Students",
        id: 0,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4, 5]),
        can_mention_group: 2,
    };
    user_groups.initialize({
        realm_user_groups: [students],
    });

    delete current_user.user_id;
    assert.ok(!settings_data.can_edit_user_group(students.id));

    current_user.user_id = 3;
    current_user.is_guest = true;
    assert.ok(!settings_data.can_edit_user_group(students.id));

    current_user.is_guest = false;
    current_user.is_moderator = true;
    assert.ok(settings_data.can_edit_user_group(students.id));

    current_user.is_moderator = false;
    assert.ok(!settings_data.can_edit_user_group(students.id));

    current_user.user_id = 2;
    realm.realm_waiting_period_threshold = 0;
    assert.ok(settings_data.can_edit_user_group(students.id));
});

run_test("type_id_to_string", () => {
    page_params.bot_types = [
        {
            type_id: 1,
            name: "Generic bot",
            allowed: true,
        },
        {
            type_id: 2,
            name: "Incoming webhook",
            allowed: true,
        },
    ];

    assert.equal(settings_data.bot_type_id_to_string(1), "Generic bot");
    assert.equal(settings_data.bot_type_id_to_string(2), "Incoming webhook");
    assert.equal(settings_data.bot_type_id_to_string(5), undefined);
});

run_test("user_can_access_all_other_users", () => {
    const guest_user_id = 1;
    const member_user_id = 2;

    const members = {
        name: "role:members",
        id: 1,
        members: new Set([member_user_id]),
        is_system_group: true,
        direct_subgroup_ids: new Set([]),
    };
    const everyone = {
        name: "role:everyone",
        id: 2,
        members: new Set([guest_user_id]),
        is_system_group: true,
        direct_subgroup_ids: new Set([1]),
    };

    user_groups.initialize({realm_user_groups: [members, everyone]});
    realm.realm_can_access_all_users_group = members.id;

    // Test spectators case.
    current_user.user_id = undefined;
    assert.ok(settings_data.user_can_access_all_other_users());

    current_user.user_id = member_user_id;
    assert.ok(settings_data.user_can_access_all_other_users());

    current_user.user_id = guest_user_id;
    assert.ok(!settings_data.user_can_access_all_other_users());

    realm.realm_can_access_all_users_group = everyone.id;
    assert.ok(settings_data.user_can_access_all_other_users());
});
