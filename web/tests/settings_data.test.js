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
    "user_can_create_user_groups",
    "realm_user_group_edit_policy",
    settings_data.user_can_create_user_groups,
);
test_policy(
    "user_can_edit_all_user_groups",
    "realm_user_group_edit_policy",
    settings_data.user_can_edit_all_user_groups,
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

test_realm_group_settings(
    "realm_can_delete_any_message_group",
    settings_data.user_can_delete_any_message,
);

test_message_policy(
    "user_can_delete_own_message",
    "realm_delete_own_message_policy",
    settings_data.user_can_delete_own_message,
);

run_test("using_dark_theme", () => {
    user_settings.color_scheme = settings_config.color_scheme_values.dark.code;
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

    user_settings.color_scheme = settings_config.color_scheme_values.light.code;
    assert.equal(settings_data.using_dark_theme(), false);
});

run_test("user_can_invite_others_to_realm_nobody_case", () => {
    current_user.is_admin = true;
    current_user.is_guest = false;
    realm.realm_invite_to_realm_policy =
        settings_config.email_invite_to_realm_policy_values.nobody.code;
    assert.equal(settings_data.user_can_invite_users_by_email(), false);
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

function test_realm_group_settings(setting_name, validation_func) {
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
    page_params.is_spectator = true;
    assert.equal(validation_func(), false);

    page_params.is_spectator = false;
    realm[setting_name] = 1;
    current_user.user_id = admin_user_id;
    assert.equal(validation_func(), true);

    current_user.user_id = moderator_user_id;
    assert.equal(validation_func(), false);

    realm[setting_name] = 2;
    current_user.user_id = moderator_user_id;
    assert.equal(validation_func(), true);

    current_user.user_id = member_user_id;
    assert.equal(validation_func(), false);
}

run_test("user_can_create_multiuse_invite", () => {
    test_realm_group_settings(
        "realm_create_multiuse_invite_group",
        settings_data.user_can_create_multiuse_invite,
    );
});

run_test("can_edit_user_group", () => {
    const admins = {
        description: "Administrators",
        name: "role:administrators",
        id: 1,
        members: new Set([1]),
        is_system_group: true,
        direct_subgroup_ids: new Set([]),
        can_manage_group: 4,
        can_mention_group: 1,
    };
    const moderators = {
        description: "Moderators",
        name: "role:moderators",
        id: 2,
        members: new Set([2]),
        is_system_group: true,
        direct_subgroup_ids: new Set([1]),
        can_manage_group: 4,
        can_mention_group: 1,
    };
    const members = {
        description: "Members",
        name: "role:members",
        id: 3,
        members: new Set([3]),
        is_system_group: true,
        direct_subgroup_ids: new Set([1, 2]),
        can_manage_group: 4,
        can_mention_group: 4,
    };
    const nobody = {
        description: "Nobody",
        name: "role:nobody",
        id: 4,
        members: new Set([]),
        is_system_group: true,
        direct_subgroup_ids: new Set([]),
        can_manage_group: 4,
        can_mention_group: 2,
    };
    const students = {
        description: "Students group",
        name: "Students",
        id: 5,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4, 5]),
        can_manage_group: 4,
        can_mention_group: 3,
    };
    user_groups.initialize({
        realm_user_groups: [admins, moderators, members, nobody, students],
    });

    page_params.is_spectator = true;
    assert.ok(!settings_data.can_edit_user_group(students.id));

    page_params.is_spectator = false;
    realm.realm_user_group_edit_policy = settings_config.common_policy_values.by_admins_only.code;
    current_user.user_id = 3;
    assert.ok(!settings_data.can_edit_user_group(students.id));

    current_user.is_admin = true;
    assert.ok(settings_data.can_edit_user_group(students.id));

    current_user.is_admin = false;
    current_user.is_moderator = true;
    assert.ok(!settings_data.can_edit_user_group(students.id));

    realm.realm_user_group_edit_policy = settings_config.common_policy_values.by_members.code;
    current_user.is_moderator = false;
    current_user.is_guest = false;
    assert.ok(!settings_data.can_edit_user_group(students.id));

    current_user.user_id = 2;
    assert.ok(settings_data.can_edit_user_group(students.id));

    realm.realm_user_group_edit_policy = settings_config.common_policy_values.by_admins_only.code;
    assert.ok(!settings_data.can_edit_user_group(students.id));

    const event = {
        group_id: students.id,
        data: {
            can_manage_group: members.id,
        },
    };
    user_groups.update(event);
    assert.ok(settings_data.can_edit_user_group(students.id));

    current_user.user_id = 3;
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
    page_params.is_spectator = true;
    assert.ok(settings_data.user_can_access_all_other_users());

    page_params.is_spectator = false;
    current_user.user_id = member_user_id;
    assert.ok(settings_data.user_can_access_all_other_users());

    current_user.user_id = guest_user_id;
    assert.ok(!settings_data.user_can_access_all_other_users());

    realm.realm_can_access_all_users_group = everyone.id;
    assert.ok(settings_data.user_can_access_all_other_users());
});

run_test("user_can_create_public_streams", () => {
    test_realm_group_settings(
        "realm_can_create_public_channel_group",
        settings_data.user_can_create_public_streams,
    );
});

run_test("user_can_create_private_streams", () => {
    test_realm_group_settings(
        "realm_can_create_private_channel_group",
        settings_data.user_can_create_private_streams,
    );
});

run_test("user_can_create_web_public_streams", () => {
    realm.server_web_public_streams_enabled = true;
    realm.realm_enable_spectator_access = true;

    test_realm_group_settings(
        "realm_can_create_web_public_channel_group",
        settings_data.user_can_create_web_public_streams,
    );
    const owner_user_id = 4;
    const owners = {
        name: "Admins",
        id: 3,
        members: new Set([owner_user_id]),
        is_system_group: true,
        direct_subgroup_ids: new Set([]),
    };
    current_user.user_id = owner_user_id;
    user_groups.initialize({realm_user_groups: [owners]});

    realm.server_web_public_streams_enabled = true;
    realm.realm_enable_spectator_access = true;
    realm.realm_can_create_web_public_channel_group = owners.id;
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
});
