"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const {page_params, user_settings} = require("./lib/zpage_params");

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

    page_params.is_admin = true;
    assert.equal(can_change_email(), true);

    page_params.is_admin = false;
    page_params.realm_email_changes_disabled = true;
    assert.equal(can_change_email(), false);

    page_params.realm_email_changes_disabled = false;
    assert.equal(can_change_email(), true);
});

run_test("user_can_change_name", () => {
    const can_change_name = settings_data.user_can_change_name;

    page_params.is_admin = true;
    assert.equal(can_change_name(), true);

    page_params.is_admin = false;
    page_params.realm_name_changes_disabled = true;
    page_params.server_name_changes_disabled = false;
    assert.equal(can_change_name(), false);

    page_params.realm_name_changes_disabled = false;
    page_params.server_name_changes_disabled = false;
    assert.equal(can_change_name(), true);

    page_params.realm_name_changes_disabled = false;
    page_params.server_name_changes_disabled = true;
    assert.equal(can_change_name(), false);
});

run_test("user_can_change_avatar", () => {
    const can_change_avatar = settings_data.user_can_change_avatar;

    page_params.is_admin = true;
    assert.equal(can_change_avatar(), true);

    page_params.is_admin = false;
    page_params.realm_avatar_changes_disabled = true;
    page_params.server_avatar_changes_disabled = false;
    assert.equal(can_change_avatar(), false);

    page_params.realm_avatar_changes_disabled = false;
    page_params.server_avatar_changes_disabled = false;
    assert.equal(can_change_avatar(), true);

    page_params.realm_avatar_changes_disabled = false;
    page_params.server_avatar_changes_disabled = true;
    assert.equal(can_change_avatar(), false);
});

run_test("user_can_change_logo", () => {
    const can_change_logo = settings_data.user_can_change_logo;

    page_params.is_admin = true;
    page_params.zulip_plan_is_not_limited = true;
    assert.equal(can_change_logo(), true);

    page_params.is_admin = false;
    page_params.zulip_plan_is_not_limited = false;
    assert.equal(can_change_logo(), false);

    page_params.is_admin = true;
    page_params.zulip_plan_is_not_limited = false;
    assert.equal(can_change_logo(), false);

    page_params.is_admin = false;
    page_params.zulip_plan_is_not_limited = true;
    assert.equal(can_change_logo(), false);
});

function test_policy(label, policy, validation_func) {
    run_test(label, () => {
        page_params.is_admin = true;
        page_params[policy] = settings_config.common_policy_values.by_admins_only.code;
        assert.equal(validation_func(), true);

        page_params.is_admin = false;
        assert.equal(validation_func(), false);

        page_params.is_moderator = true;
        page_params[policy] = settings_config.common_policy_values.by_moderators_only.code;
        assert.equal(validation_func(), true);

        page_params.is_moderator = false;
        assert.equal(validation_func(), false);

        page_params.is_guest = true;
        page_params[policy] = settings_config.common_policy_values.by_members.code;
        assert.equal(validation_func(), false);

        page_params.is_guest = false;
        assert.equal(validation_func(), true);

        page_params.is_spectator = true;
        page_params[policy] = settings_config.common_policy_values.by_members.code;
        assert.equal(validation_func(), false);

        page_params.is_spectator = false;
        assert.equal(validation_func(), true);

        page_params[policy] = settings_config.common_policy_values.by_full_members.code;
        page_params.user_id = 30;
        isaac.date_joined = new Date(Date.now());
        settings_data.initialize(isaac.date_joined);
        page_params.realm_waiting_period_threshold = 10;
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
        page_params.is_admin = true;
        page_params[policy] = settings_config.common_message_policy_values.by_admins_only.code;
        assert.equal(validation_func(), true);

        page_params.is_admin = false;
        page_params.is_moderator = true;
        assert.equal(validation_func(), false);

        page_params[policy] = settings_config.common_message_policy_values.by_moderators_only.code;
        assert.equal(validation_func(), true);

        page_params.is_moderator = false;
        assert.equal(validation_func(), false);

        page_params.is_guest = true;
        page_params[policy] = settings_config.common_message_policy_values.by_everyone.code;
        assert.equal(validation_func(), true);

        page_params[policy] = settings_config.common_message_policy_values.by_members.code;
        assert.equal(validation_func(), false);

        page_params.is_guest = false;
        assert.equal(validation_func(), true);

        page_params[policy] = settings_config.common_message_policy_values.by_full_members.code;
        page_params.user_id = 30;
        isaac.date_joined = new Date(Date.now());
        page_params.realm_waiting_period_threshold = 10;
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
    page_params.is_admin = true;
    page_params.is_guest = false;
    page_params.realm_edit_topic_policy = settings_config.edit_topic_policy_values.nobody.code;
    assert.equal(settings_data.user_can_move_messages_to_another_topic(), false);
});

run_test("user_can_move_messages_between_streams_nobody_case", () => {
    page_params.is_admin = true;
    page_params.is_guest = false;
    page_params.realm_move_messages_between_streams_policy =
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
    page_params.is_admin = true;
    page_params.is_guest = false;
    page_params.realm_invite_to_realm_policy =
        settings_config.email_invite_to_realm_policy_values.nobody.code;
    assert.equal(settings_data.user_can_invite_users_by_email(), false);
});

run_test("user_can_create_web_public_streams", () => {
    page_params.is_owner = true;
    page_params.server_web_public_streams_enabled = true;
    page_params.realm_enable_spectator_access = true;
    page_params.realm_create_web_public_stream_policy =
        settings_config.create_web_public_stream_policy_values.nobody.code;
    assert.equal(settings_data.user_can_create_web_public_streams(), false);

    page_params.realm_create_web_public_stream_policy =
        settings_config.create_web_public_stream_policy_values.by_owners_only.code;
    assert.equal(settings_data.user_can_create_web_public_streams(), true);

    page_params.realm_enable_spectator_access = false;
    page_params.server_web_public_streams_enabled = true;
    assert.equal(settings_data.user_can_create_web_public_streams(), false);

    page_params.realm_enable_spectator_access = true;
    page_params.server_web_public_streams_enabled = false;
    assert.equal(settings_data.user_can_create_web_public_streams(), false);

    page_params.realm_enable_spectator_access = false;
    page_params.server_web_public_streams_enabled = false;
    assert.equal(settings_data.user_can_create_web_public_streams(), false);

    page_params.realm_enable_spectator_access = true;
    page_params.server_web_public_streams_enabled = true;
    page_params.is_owner = false;
    page_params.is_admin = true;
    assert.equal(settings_data.user_can_create_web_public_streams(), false);

    page_params.realm_create_web_public_stream_policy =
        settings_config.create_web_public_stream_policy_values.by_admins_only.code;
    assert.equal(settings_data.user_can_create_web_public_streams(), true);

    page_params.is_admin = false;
    page_params.is_moderator = true;
    assert.equal(settings_data.user_can_create_web_public_streams(), false);

    page_params.realm_create_web_public_stream_policy =
        settings_config.create_web_public_stream_policy_values.by_moderators_only.code;
    assert.equal(settings_data.user_can_create_web_public_streams(), true);

    page_params.is_moderator = false;
    assert.equal(settings_data.user_can_create_web_public_streams(), false);
});

run_test("user_email_not_configured", () => {
    const user_email_not_configured = settings_data.user_email_not_configured;

    page_params.is_owner = false;
    assert.equal(user_email_not_configured(), false);

    page_params.is_owner = true;
    page_params.delivery_email = "";
    assert.equal(user_email_not_configured(), true);

    page_params.delivery_email = "name@example.com";
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

    page_params.realm_create_multiuse_invite_group = 1;
    page_params.user_id = admin_user_id;
    assert.equal(settings_data.user_can_create_multiuse_invite(), true);

    page_params.user_id = moderator_user_id;
    assert.equal(settings_data.user_can_create_multiuse_invite(), false);

    page_params.realm_create_multiuse_invite_group = 2;
    page_params.user_id = moderator_user_id;
    assert.equal(settings_data.user_can_create_multiuse_invite(), true);

    page_params.user_id = member_user_id;
    assert.equal(settings_data.user_can_create_multiuse_invite(), false);
});
