"use strict";

const assert = require("node:assert/strict");

const events = require("./lib/events.cjs");
const {mock_esm, set_global, with_overrides, zrequire} = require("./lib/namespace.cjs");
const {make_stub} = require("./lib/stub.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const $ = require("./lib/zjquery.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

const event_fixtures = events.fixtures;
const test_message = events.test_message;
const test_user = events.test_user;
const typing_person1 = events.typing_person1;

set_global("requestAnimationFrame", (func) => func());

const activity_ui = mock_esm("../src/activity_ui");
const alert_words_ui = mock_esm("../src/alert_words_ui");
const attachments_ui = mock_esm("../src/attachments_ui");
const audible_notifications = mock_esm("../src/audible_notifications");
const bot_data = mock_esm("../src/bot_data");
const compose_pm_pill = mock_esm("../src/compose_pm_pill");
const {electron_bridge} = mock_esm("../src/electron_bridge", {
    electron_bridge: {},
});
const theme = mock_esm("../src/theme");
const emoji_picker = mock_esm("../src/emoji_picker");
const gear_menu = mock_esm("../src/gear_menu");
const information_density = mock_esm("../src/information_density");
const linkifiers = mock_esm("../src/linkifiers");
const compose_recipient = mock_esm("../src/compose_recipient");
const message_events = mock_esm("../src/message_events", {
    update_views_filtered_on_message_property: noop,
    update_current_view_for_topic_visibility: noop,
});
const message_lists = mock_esm("../src/message_lists");
const user_topics_ui = mock_esm("../src/user_topics_ui");
const muted_users_ui = mock_esm("../src/muted_users_ui");
const narrow_title = mock_esm("../src/narrow_title");
const navbar_alerts = mock_esm("../src/navbar_alerts");
const pm_list = mock_esm("../src/pm_list");
const reactions = mock_esm("../src/reactions", {
    generate_clean_reactions() {},
});
const realm_icon = mock_esm("../src/realm_icon");
const realm_logo = mock_esm("../src/realm_logo");
const realm_playground = mock_esm("../src/realm_playground");
const reload = mock_esm("../src/reload");
const message_reminder = mock_esm("../src/message_reminder");
const reminders_overlay_ui = mock_esm("../src/reminders_overlay_ui");
const saved_snippets = mock_esm("../src/saved_snippets");
const saved_snippets_ui = mock_esm("../src/saved_snippets_ui");
const scheduled_messages = mock_esm("../src/scheduled_messages");
const scheduled_messages_feed_ui = mock_esm("../src/scheduled_messages_feed_ui");
const scheduled_messages_overlay_ui = mock_esm("../src/scheduled_messages_overlay_ui");
const scheduled_messages_ui = mock_esm("../src/scheduled_messages_ui");
const scroll_bar = mock_esm("../src/scroll_bar");
const settings_account = mock_esm("../src/settings_account");
const settings_bots = mock_esm("../src/settings_bots");
const settings_data = mock_esm("../src/settings_data");
const settings_emoji = mock_esm("../src/settings_emoji");
const settings_exports = mock_esm("../src/settings_exports");
const settings_invites = mock_esm("../src/settings_invites");
const settings_linkifiers = mock_esm("../src/settings_linkifiers");
const settings_playgrounds = mock_esm("../src/settings_playgrounds");
const settings_notifications = mock_esm("../src/settings_notifications");
const settings_org = mock_esm("../src/settings_org");
const settings_profile_fields = mock_esm("../src/settings_profile_fields");
const settings_preferences = mock_esm("../src/settings_preferences");
const settings_realm_user_settings_defaults = mock_esm(
    "../src/settings_realm_user_settings_defaults",
);
const settings_realm_domains = mock_esm("../src/settings_realm_domains");
const settings_streams = mock_esm("../src/settings_streams");
const settings_users = mock_esm("../src/settings_users");
const sidebar_ui = mock_esm("../src/sidebar_ui");
const stream_data = mock_esm("../src/stream_data");
const stream_list = mock_esm("../src/stream_list");
const stream_settings_components = mock_esm("../src/stream_settings_components");
const stream_settings_data = mock_esm("../src/stream_settings_data");
const stream_settings_ui = mock_esm("../src/stream_settings_ui");
const stream_list_sort = mock_esm("../src/stream_list_sort");
const stream_topic_history = mock_esm("../src/stream_topic_history");
const stream_ui_updates = mock_esm("../src/stream_ui_updates", {
    update_announce_stream_option() {},
});
const submessage = mock_esm("../src/submessage");
mock_esm("../src/left_sidebar_navigation_area", {
    update_starred_count() {},
    update_scheduled_messages_row() {},
    update_reminders_row() {},
    handle_home_view_changed() {},
});
const typing_events = mock_esm("../src/typing_events");
const unread_ops = mock_esm("../src/unread_ops");
const unread_ui = mock_esm("../src/unread_ui");
const user_events = mock_esm("../src/user_events");
const user_group_edit = mock_esm("../src/user_group_edit");
const overlays = mock_esm("../src/overlays");
mock_esm("../src/giphy");
const {Filter} = zrequire("filter");
const {initialize: initialize_realm_user_settings_defaults} = zrequire(
    "realm_user_settings_defaults",
);
const {set_current_user, set_realm} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");

const realm = {};
set_realm(realm);
const current_user = {};
set_current_user(current_user);
const realm_user_settings_defaults = {};
initialize_realm_user_settings_defaults({realm_user_settings_defaults});
const user_settings = {};
initialize_user_settings({user_settings});

message_lists.update_recipient_bar_background_color = noop;
message_lists.current = {
    get_row: noop,
    rerender_view: noop,
    data: {
        get_messages_sent_by_user: () => [],
        filter: new Filter([]),
    },
};
const cached_message_list = {
    get_row: noop,
    rerender_view: noop,
    data: {
        get_messages_sent_by_user: () => [],
    },
};
message_lists.all_rendered_message_lists = () => [cached_message_list, message_lists.current];

// page_params is highly coupled to dispatching now
page_params.test_suite = false;

// For data-oriented modules, just use them, don't stub them.
const alert_words = zrequire("alert_words");
const channel_folders = zrequire("channel_folders");
const emoji = zrequire("emoji");
const message_store = zrequire("message_store");
const people = zrequire("people");
const presence = zrequire("presence");
const user_status = zrequire("user_status");
const onboarding_steps = zrequire("onboarding_steps");
const user_groups = zrequire("user_groups");

const server_events_dispatch = zrequire("server_events_dispatch");

function dispatch(ev) {
    server_events_dispatch.dispatch_normal_event(ev);
}

const me = {
    email: "me@example.com",
    user_id: 20,
    full_name: "Me Myself",
    timezone: "America/Los_Angeles",
};

people.init();
people.add_active_user(me);
people.add_active_user(test_user);
people.initialize_current_user(me.user_id);

message_store.update_message_cache(test_message);

const realm_emoji = {};
const emoji_codes = zrequire("../../static/generated/emoji/emoji_codes.json");

emoji.initialize({realm_emoji, emoji_codes});

function assert_same(actual, expected) {
    // This helper prevents us from getting false positives
    // where actual and expected are both undefined.
    assert.notEqual(expected, undefined);
    assert.deepEqual(actual, expected);
}

run_test("alert_words", ({override}) => {
    alert_words.initialize({alert_words: []});
    assert.ok(!alert_words.has_alert_word("fire"));
    assert.ok(!alert_words.has_alert_word("lunch"));

    override(alert_words_ui, "rerender_alert_words_ui", noop);
    const event = event_fixtures.alert_words;
    dispatch(event);

    assert.deepEqual(alert_words.get_word_list(), [{word: "lunch"}, {word: "fire"}]);
    assert.ok(alert_words.has_alert_word("fire"));
    assert.ok(alert_words.has_alert_word("lunch"));
});

run_test("saved_snippets", ({override}) => {
    const add_event = event_fixtures.saved_snippets__add;
    override(saved_snippets_ui, "rerender_dropdown_widget", noop);
    {
        const stub = make_stub();
        override(saved_snippets, "update_saved_snippet_dict", stub.f);

        dispatch(add_event);
        assert.equal(stub.num_calls, 1);
        assert_same(stub.get_args("event").event, add_event.saved_snippet);
    }

    const remove_event = event_fixtures.saved_snippets__remove;
    {
        const stub = make_stub();
        override(saved_snippets, "remove_saved_snippet", stub.f);

        dispatch(remove_event);
        assert.equal(stub.num_calls, 1);
        assert_same(stub.get_args("event").event, remove_event.saved_snippet_id);
    }

    const update_event = event_fixtures.saved_snippets__update;
    {
        const stub = make_stub();
        override(saved_snippets, "update_saved_snippet_dict", stub.f);

        dispatch(update_event);
        assert.equal(stub.num_calls, 1);
        assert_same(stub.get_args("event").event, update_event.saved_snippet);
    }
});

run_test("attachments", ({override}) => {
    const event = event_fixtures.attachment__add;
    const stub = make_stub();
    // attachments_ui is hard to test deeply
    override(attachments_ui, "update_attachments", stub.f);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    assert_same(stub.get_args("event").event, event);
});

run_test("user groups", ({override}) => {
    let event = event_fixtures.user_group__add;
    user_groups.add({
        id: 1,
        name: "Backend",
        creator_id: null,
        date_created: 1596713966,
        description: "Backend folks",
        members: [1, 2, 4],
        is_system_group: false,
        direct_subgroup_ids: [3, 5],
        can_add_members_group: 16,
        can_join_group: 16,
        can_leave_group: 15,
        can_manage_group: 16,
        can_mention_group: 11,
        can_remove_members_group: 16,
        deactivated: false,
    });

    {
        const user_group_settings_ui_stub = make_stub();

        override(overlays, "groups_open", () => true);
        override(user_group_edit, "add_group_to_table", user_group_settings_ui_stub.f);

        dispatch(event);

        assert.equal(user_group_settings_ui_stub.num_calls, 1);

        const group = user_groups.get_user_group_from_id(event.group.id);
        const args = user_group_settings_ui_stub.get_args("group");
        assert_same(args.group, group);
    }

    event = event_fixtures.user_group__add_members;
    {
        const user_group_edit_stub = make_stub();
        override(user_group_edit, "handle_member_edit_event", user_group_edit_stub.f);
        dispatch(event);
        assert.equal(user_group_edit_stub.num_calls, 1);
        const args = user_group_edit_stub.get_args("group_id");
        assert_same(args.group_id, event.group_id);

        const group = user_groups.get_user_group_from_id(event.group_id);
        assert.ok(group.members.has(event.user_ids[0]));
    }

    event = event_fixtures.user_group__add_subgroups;
    {
        const user_group_edit_stub = make_stub();
        override(user_group_edit, "handle_subgroup_edit_event", user_group_edit_stub.f);
        dispatch(event);
        assert.equal(user_group_edit_stub.num_calls, 1);

        const group = user_groups.get_user_group_from_id(event.group_id);
        assert.ok(group.direct_subgroup_ids.has(event.direct_subgroup_ids[0]));
    }

    event = event_fixtures.user_group__remove_members;
    {
        const user_group_edit_stub = make_stub();
        override(user_group_edit, "handle_member_edit_event", user_group_edit_stub.f);
        dispatch(event);
        assert.equal(user_group_edit_stub.num_calls, 1);
        const args = user_group_edit_stub.get_args("group_id");
        assert_same(args.group_id, event.group_id);

        const group = user_groups.get_user_group_from_id(event.group_id);
        assert.ok(!group.members.has(event.user_ids[0]));
        assert.ok(!group.members.has(event.user_ids[1]));
    }

    event = event_fixtures.user_group__remove_subgroups;
    {
        const user_group_edit_stub = make_stub();
        override(user_group_edit, "handle_subgroup_edit_event", user_group_edit_stub.f);
        dispatch(event);
        assert.equal(user_group_edit_stub.num_calls, 1);

        const group = user_groups.get_user_group_from_id(event.group_id);
        assert.ok(!group.direct_subgroup_ids.has(event.direct_subgroup_ids[0]));
    }

    event = event_fixtures.user_group__update;
    {
        const user_group_settings_ui_stub = make_stub();

        override(user_group_edit, "update_group", user_group_settings_ui_stub.f);

        dispatch(event);
        assert.equal(user_group_settings_ui_stub.num_calls, 1);

        const args = user_group_settings_ui_stub.get_args("event", "group");
        assert_same(args.event, event);

        const group = user_groups.get_user_group_from_id(event.group_id);
        assert_same(args.group, group);

        assert_same(group.name, event.data.name);
        assert_same(group.description, event.data.description);
    }
});

run_test("custom profile fields", ({override}) => {
    const event = event_fixtures.custom_profile_fields;
    override(settings_profile_fields, "populate_profile_fields", noop);
    override(settings_account, "add_custom_profile_fields_to_settings", noop);
    override(navbar_alerts, "maybe_toggle_empty_required_profile_fields_banner", noop);
    dispatch(event);
    assert_same(realm.custom_profile_fields, event.fields);
});

run_test("default_streams", ({override}) => {
    const event = event_fixtures.default_streams;
    override(settings_streams, "update_default_streams_table", noop);
    override(stream_settings_ui, "update_is_default_stream", noop);
    const stub = make_stub();
    override(stream_data, "set_realm_default_streams", stub.f);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    const args = stub.get_args("realm_default_streams");
    assert_same(args.realm_default_streams, event.default_streams);
});

run_test("onboarding_steps", () => {
    onboarding_steps.initialize({onboarding_steps: []}, () => {});
    const event = event_fixtures.onboarding_steps;
    const one_time_notices = new Set();
    for (const onboarding_step of event.onboarding_steps) {
        one_time_notices.add(onboarding_step.name);
    }
    dispatch(event);
    assert_same(onboarding_steps.ONE_TIME_NOTICES_TO_DISPLAY, one_time_notices);
});

run_test("invites_changed", ({override}) => {
    $.create("#admin-invites-list", {children: ["stub"]});
    const event = event_fixtures.invites_changed;
    const stub = make_stub();
    override(settings_invites, "set_up", stub.f);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
});

run_test("muted_topics", ({override}) => {
    const event = event_fixtures.user_topic;

    const stub = make_stub();
    override(user_topics_ui, "handle_topic_updates", stub.f);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    const args = stub.get_args("user_topic");
    assert_same(args.user_topic, event);
});

run_test("followed_topic", ({override}) => {
    const event = event_fixtures.user_topic_with_followed_policy_change;

    const stub = make_stub();
    const discard_msg_list_stub = make_stub();
    override(user_topics_ui, "handle_topic_updates", stub.f);
    override(message_events, "discard_cached_lists_with_term_type", discard_msg_list_stub.f);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    assert.equal(discard_msg_list_stub.num_calls, 1);
    const args = stub.get_args("user_topic");
    assert_same(args.user_topic, event);
});

run_test("muted_users", ({override}) => {
    const event = event_fixtures.muted_users;

    const stub = make_stub();
    override(muted_users_ui, "handle_user_updates", stub.f);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    const args = stub.get_args("muted_users");
    assert_same(args.muted_users, event.muted_users);
});

run_test("presence", ({override}) => {
    const event = event_fixtures.presence;

    const stub = make_stub();
    override(activity_ui, "update_presence_info", stub.f);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    const args = stub.get_args("user_id", "presence", "server_time");
    assert_same(args.user_id, event.user_id);
    assert_same(args.presence, event.presence);
    assert_same(args.server_time, event.server_timestamp);
});

run_test("reaction", ({override}) => {
    let event = event_fixtures.reaction__add;
    {
        const stub = make_stub();
        override(reactions, "add_reaction", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("event");
        assert_same(args.event.emoji_name, event.emoji_name);
        assert_same(args.event.message_id, event.message_id);
    }

    event = event_fixtures.reaction__remove;
    {
        const stub = make_stub();
        override(reactions, "remove_reaction", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("event");
        assert_same(args.event.emoji_name, event.emoji_name);
        assert_same(args.event.message_id, event.message_id);
    }
});

run_test("reminders", ({override}) => {
    override(reminders_overlay_ui, "rerender", noop);
    override(reminders_overlay_ui, "remove_reminder_id", noop);

    let event = event_fixtures.reminders__add;
    {
        const stub = make_stub();
        override(message_reminder, "add_reminders", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("reminders");
        assert_same(args.reminders, event.reminders);
    }
    event = event_fixtures.reminders__remove;
    {
        const stub = make_stub();
        override(message_reminder, "remove_reminder", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("reminder_id");
        assert_same(args.reminder_id, event.reminder_id);
    }
});

run_test("scheduled_messages", ({override}) => {
    override(scheduled_messages_overlay_ui, "rerender", noop);
    override(scheduled_messages_overlay_ui, "remove_scheduled_message_id", noop);
    override(scheduled_messages_feed_ui, "update_schedule_message_indicator", noop);
    override(scheduled_messages_ui, "hide_scheduled_message_success_compose_banner", noop);

    let event = event_fixtures.scheduled_messages__add;
    {
        const stub = make_stub();
        override(scheduled_messages, "add_scheduled_messages", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("scheduled_messages");
        assert_same(args.scheduled_messages, event.scheduled_messages);
    }
    event = event_fixtures.scheduled_messages__update;
    {
        const stub = make_stub();
        override(scheduled_messages, "update_scheduled_message", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("scheduled_message");
        assert_same(args.scheduled_message, event.scheduled_message);
    }
    event = event_fixtures.scheduled_messages__remove;
    {
        const stub = make_stub();
        override(scheduled_messages, "remove_scheduled_message", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("scheduled_message_id");
        assert_same(args.scheduled_message_id, event.scheduled_message_id);
    }
});

run_test("channel_folders", () => {
    channel_folders.initialize({channel_folders: []});

    const event = event_fixtures.channel_folder__add;
    {
        dispatch(event);

        const folders = channel_folders.get_channel_folders();
        assert.equal(folders.length, 1);
        assert.equal(folders[0].id, event.channel_folder.id);
        assert.equal(folders[0].name, event.channel_folder.name);
    }

    blueslip.expect("error", "Unexpected event type channel_folder/other");
    server_events_dispatch.dispatch_normal_event({type: "channel_folder", op: "other"});
});

run_test("realm settings", ({override}) => {
    override(current_user, "is_admin", true);
    override(realm, "realm_date_created", new Date("2023-01-01Z"));

    override(settings_org, "check_disable_direct_message_initiator_group_widget", noop);
    override(settings_org, "sync_realm_settings", noop);
    override(settings_bots, "update_bot_permissions_ui", noop);
    override(settings_emoji, "update_custom_emoji_ui", noop);
    override(settings_invites, "update_invite_user_panel", noop);
    override(sidebar_ui, "update_invite_user_option", noop);
    override(gear_menu, "rerender", noop);
    override(narrow_title, "redraw_title", noop);
    override(navbar_alerts, "toggle_organization_profile_incomplete_banner", noop);
    override(compose_recipient, "update_topic_inputbox_on_topics_policy_change", noop);
    override(compose_recipient, "update_compose_area_placeholder_text", noop);
    override(compose_recipient, "check_posting_policy_for_compose_box", noop);

    function test_electron_dispatch(event, fake_send_event) {
        with_overrides(({override}) => {
            override(electron_bridge, "send_event", fake_send_event);
            dispatch(event);
        });
    }

    // realm
    function test_realm_boolean(event, parameter_name) {
        override(realm, parameter_name, true);
        event = {...event};
        event.value = false;
        dispatch(event);
        assert.equal(realm[parameter_name], false);
        event = {...event};
        event.value = true;
        dispatch(event);
        assert.equal(realm[parameter_name], true);
    }

    let event = event_fixtures.realm__update__invite_required;
    test_realm_boolean(event, "realm_invite_required");

    event = event_fixtures.realm__update__want_advertise_in_communities_directory;
    test_realm_boolean(event, "realm_want_advertise_in_communities_directory");

    event = event_fixtures.realm__update__name;

    test_electron_dispatch(event, (key, val) => {
        assert_same(key, "realm_name");
        assert_same(val, "new_realm_name");
    });
    assert_same(realm.realm_name, "new_realm_name");

    event = event_fixtures.realm__update__org_type;
    dispatch(event);
    assert_same(realm.realm_org_type, 50);

    event = event_fixtures.realm__update__emails_restricted_to_domains;
    test_realm_boolean(event, "realm_emails_restricted_to_domains");

    event = event_fixtures.realm__update__disallow_disposable_email_addresses;
    test_realm_boolean(event, "realm_disallow_disposable_email_addresses");

    event = event_fixtures.realm__update__new_stream_announcements_stream_id;
    dispatch(event);
    assert_same(realm.realm_new_stream_announcements_stream_id, 42);
    override(realm, "realm_new_stream_announcements_stream_id", -1); // make sure to reset for future tests

    event = event_fixtures.realm__update__signup_announcements_stream_id;
    dispatch(event);
    assert_same(realm.realm_signup_announcements_stream_id, 41);
    override(realm, "realm_signup_announcements_stream_id", -1); // make sure to reset for future tests

    event = event_fixtures.realm__update__zulip_update_announcements_stream_id;
    dispatch(event);
    assert_same(realm.realm_zulip_update_announcements_stream_id, 42);
    override(realm, "realm_zulip_update_announcements_stream_id", -1); // make sure to reset for future tests

    event = event_fixtures.realm__update__default_code_block_language;
    dispatch(event);
    assert_same(realm.realm_default_code_block_language, "javascript");

    let update_called = false;
    stream_ui_updates.update_stream_privacy_choices = (property) => {
        assert_same(property, "can_create_web_public_channel_group");
        update_called = true;
    };
    event = event_fixtures.realm__update__enable_spectator_access;
    dispatch(event);
    assert_same(realm.realm_enable_spectator_access, true);
    assert_same(update_called, true);

    let update_stream_privacy_choices_called = false;
    stream_ui_updates.update_stream_privacy_choices = (property) => {
        assert_same(property, "can_create_public_channel_group");
        update_stream_privacy_choices_called = true;
    };

    event = event_fixtures.realm__update_dict__default;
    override(realm, "realm_create_multiuse_invite_group", 1);
    override(realm, "realm_allow_message_editing", false);
    override(realm, "realm_message_content_edit_limit_seconds", 0);
    override(realm, "realm_authentication_methods", {Google: {enabled: false, available: true}});
    override(realm, "realm_can_add_custom_emoji_group", 1);
    override(realm, "realm_can_add_subscribers_group", 1);
    override(realm, "realm_can_create_bots_group", 1);
    override(realm, "realm_can_create_public_channel_group", 1);
    override(realm, "realm_can_invite_users_group", 1);
    override(realm, "realm_can_move_messages_between_topics_group", 1);
    override(realm, "realm_can_move_messages_between_topics_group", 5);
    override(realm, "realm_direct_message_permission_group", 1);
    override(realm, "realm_topics_policy", "allow_empty_topic");
    override(realm, "realm_plan_type", 2);
    override(realm, "realm_upload_quota_mib", 5000);
    override(realm, "max_file_upload_size_mib", 10);
    override(realm, "server_supported_permission_settings", {
        realm: {
            create_multiuse_invite_group: {},
        },
    });
    override(settings_org, "populate_auth_methods", noop);
    override(user_group_edit, "update_realm_setting_in_permissions_panel", noop);
    override(overlays, "streams_open", () => true);
    override(stream_settings_components, "get_active_data", () => ({
        id: events.test_streams.devel.stream_id,
    }));
    override(stream_settings_data, "get_sub_for_settings", () => ({
        ...events.test_streams.devel,
        can_add_subscribers: false,
    }));
    let add_subscribers_element_updated = false;
    override(stream_ui_updates, "update_add_subscriptions_elements", (sub) => {
        assert.deepEqual(sub, {...events.test_streams.devel, can_add_subscribers: false});
        add_subscribers_element_updated = true;
    });
    dispatch(event);
    assert_same(realm.realm_create_multiuse_invite_group, 3);
    assert_same(realm.realm_allow_message_editing, true);
    assert_same(realm.realm_message_content_edit_limit_seconds, 5);
    assert_same(realm.realm_authentication_methods, {
        Google: {enabled: true, available: true},
    });
    assert_same(realm.realm_can_add_custom_emoji_group, 3);
    assert_same(realm.realm_can_add_subscribers_group, 3);
    assert_same(realm.realm_can_create_bots_group, 3);
    assert_same(realm.realm_can_create_public_channel_group, 3);
    assert_same(realm.realm_can_invite_users_group, 3);
    assert_same(realm.realm_can_move_messages_between_topics_group, 3);
    assert_same(realm.realm_can_resolve_topics_group, 1);
    assert_same(realm.realm_direct_message_permission_group, 3);
    assert_same(realm.realm_topics_policy, "disable_empty_topic");
    assert_same(realm.realm_plan_type, 3);
    assert_same(realm.realm_upload_quota_mib, 50000);
    assert_same(realm.max_file_upload_size_mib, 1024);
    assert_same(update_stream_privacy_choices_called, true);
    assert_same(add_subscribers_element_updated, true);

    event = event_fixtures.realm__update_dict__icon;
    override(realm_icon, "rerender", noop);

    test_electron_dispatch(event, (key, val) => {
        assert_same(key, "realm_icon_url");
        assert_same(val, "icon.png");
    });

    assert_same(realm.realm_icon_url, "icon.png");
    assert_same(realm.realm_icon_source, "U");

    override(realm_logo, "render", noop);

    event = event_fixtures.realm__update_dict__logo;
    dispatch(event);
    assert_same(realm.realm_logo_url, "logo.png");
    assert_same(realm.realm_logo_source, "U");

    event = event_fixtures.realm__update_dict__night_logo;
    dispatch(event);
    assert_same(realm.realm_night_logo_url, "night_logo.png");
    assert_same(realm.realm_night_logo_source, "U");

    event = event_fixtures.realm__deactivated;
    set_global("location", {});
    dispatch(event);
    assert_same(window.location.href, "/accounts/deactivated/");
});

run_test("realm_bot add", ({override}) => {
    const event = event_fixtures.realm_bot__add;
    const bot_stub = make_stub();
    override(bot_data, "add", bot_stub.f);
    override(settings_bots, "render_bots", noop);
    dispatch(event);

    assert.equal(bot_stub.num_calls, 1);
    const args = bot_stub.get_args("bot");
    assert_same(args.bot, event.bot);
});

run_test("realm_bot delete", ({override}) => {
    const event = event_fixtures.realm_bot__delete;
    const bot_stub = make_stub();
    override(bot_data, "del", bot_stub.f);
    override(settings_bots, "render_bots", noop);

    dispatch(event);
    assert.equal(bot_stub.num_calls, 1);
    const args = bot_stub.get_args("user_id");
    assert_same(args.user_id, event.bot.user_id);
});

run_test("realm_bot update", ({override}) => {
    const event = event_fixtures.realm_bot__update;
    const bot_stub = make_stub();
    override(bot_data, "update", bot_stub.f);
    override(settings_bots, "render_bots", noop);

    dispatch(event);

    assert.equal(bot_stub.num_calls, 1);
    const args = bot_stub.get_args("user_id", "bot");
    assert_same(args.user_id, event.bot.user_id);
    assert_same(args.bot, event.bot);
});

run_test("realm_emoji", ({override}) => {
    const event = event_fixtures.realm_emoji__update;

    const ui_func_names = [
        [settings_emoji, "populate_emoji"],
        [emoji_picker, "rebuild_catalog"],
    ];

    const ui_stubs = [];

    for (const [module, func_name] of ui_func_names) {
        const ui_stub = make_stub();
        override(module, func_name, ui_stub.f);
        ui_stubs.push(ui_stub);
    }

    // Make sure we start with nothing...
    emoji.update_emojis([]);
    assert.equal(emoji.get_realm_emoji_url("spain"), undefined);

    dispatch(event);

    // Now emoji.js knows about the spain emoji.
    assert_same(emoji.get_realm_emoji_url("spain"), "/some/path/to/spain.gif");

    // Make sure our UI modules all got dispatched the same simple way.
    for (const stub of ui_stubs) {
        assert.equal(stub.num_calls, 1);
        assert.equal(stub.last_call_args.length, 0);
    }
});

run_test("realm_linkifiers", ({override}) => {
    const event = event_fixtures.realm_linkifiers;
    override(realm, "realm_linkifiers", []);
    override(settings_linkifiers, "populate_linkifiers", noop);
    override(linkifiers, "update_linkifier_rules", noop);
    dispatch(event);
    assert_same(realm.realm_linkifiers, event.realm_linkifiers);
});

run_test("realm_playgrounds", ({override}) => {
    const event = event_fixtures.realm_playgrounds;
    override(realm, "realm_playgrounds", []);
    override(settings_playgrounds, "populate_playgrounds", noop);
    override(realm_playground, "update_playgrounds", noop);
    dispatch(event);
    assert_same(realm.realm_playgrounds, event.realm_playgrounds);
});

run_test("realm_domains", ({override}) => {
    let event = event_fixtures.realm_domains__add;
    override(realm, "realm_domains", []);
    override(settings_org, "populate_realm_domains_label", noop);
    override(settings_realm_domains, "populate_realm_domains_table", noop);
    dispatch(event);
    assert_same(realm.realm_domains, [event.realm_domain]);

    override(settings_org, "populate_realm_domains_label", noop);
    override(settings_realm_domains, "populate_realm_domains_table", noop);
    event = event_fixtures.realm_domains__change;
    dispatch(event);
    assert_same(realm.realm_domains, [event.realm_domain]);

    override(settings_org, "populate_realm_domains_label", noop);
    override(settings_realm_domains, "populate_realm_domains_table", noop);
    event = event_fixtures.realm_domains__remove;
    dispatch(event);
    assert_same(realm.realm_domains, []);
});

run_test("add_realm_user_redraw_logic", ({override}) => {
    presence.presence_info.set(999, {status: "active"});

    override(settings_account, "maybe_update_deactivate_account_button", noop);
    override(settings_exports, "update_export_consent_data_and_redraw", noop);

    const check_should_redraw_new_user_stub = make_stub();
    // make_stub().f returns true by default, so it's already doing what we want.
    override(activity_ui, "check_should_redraw_new_user", check_should_redraw_new_user_stub.f);
    const redraw_user_stub = make_stub();
    override(activity_ui, "redraw_user", redraw_user_stub.f);

    const event = event_fixtures.realm_user__add;
    event.person.user_id = 999;
    dispatch(event);

    assert.equal(redraw_user_stub.num_calls, 1);
    assert.equal(redraw_user_stub.get_args("user_id").user_id, 999);
});

run_test("realm_user", ({override}) => {
    override(settings_account, "maybe_update_deactivate_account_button", noop);
    override(activity_ui, "check_should_redraw_new_user", noop);
    override(settings_exports, "update_export_consent_data_and_redraw", noop);
    let event = event_fixtures.realm_user__add;
    dispatch({...event});
    const added_person = people.get_by_user_id(event.person.user_id);
    // sanity check a few individual fields
    assert.equal(added_person.full_name, "Test User");
    assert.equal(added_person.timezone, "America/New_York");

    // ...but really the whole struct gets copied without any
    // manipulation
    assert.deepEqual(added_person, event.person);

    assert.ok(people.is_active_user_for_popover(event.person.user_id));

    event = event_fixtures.realm_user__update;
    const stub = make_stub();
    override(user_events, "update_person", stub.f);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    let args = stub.get_args("person");
    assert_same(args.person, event.person);

    // Test bot related functions are being called.
    const add_bot_stub = make_stub();
    event = event_fixtures.realm_user__add_bot;
    override(settings_users, "redraw_bots_list", add_bot_stub.f);
    dispatch({...event});
    assert.equal(add_bot_stub.num_calls, 1);

    const update_bot_stub = make_stub();
    event = event_fixtures.realm_user__update;
    override(settings_users, "update_bot_data", update_bot_stub.f);
    dispatch(event);
    assert.equal(update_bot_stub.num_calls, 1);
    args = update_bot_stub.get_args("update_user_id", "update_bot_data");
    assert_same(args.update_user_id, event.person.user_id);

    override(settings_data, "user_can_access_all_other_users", () => false);
    event = event_fixtures.realm_user__remove;
    dispatch(event);
    const removed_person = people.get_by_user_id(event.person.user_id);
    assert.equal(removed_person.full_name, "translated: Unknown user");
});

run_test("restart", ({_override}) => {
    const event = event_fixtures.restart;
    dispatch(event);
    assert_same(realm.zulip_version, event.zulip_version);
    assert_same(realm.zulip_merge_base, event.zulip_merge_base);
});

run_test("web_reload_client", ({override}) => {
    const event = event_fixtures.web_reload_client;
    const stub = make_stub();
    override(reload, "initiate", stub.f);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    const args = stub.get_args("options");
    assert.equal(args.options.immediate, true);
});

run_test("submessage", ({override}) => {
    const event = event_fixtures.submessage;
    const stub = make_stub();
    override(submessage, "handle_event", stub.f);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    const submsg = stub.get_args("submsg").submsg;
    assert_same(submsg, {
        id: 99,
        sender_id: 42,
        msg_type: "stream",
        message_id: 56,
        content: "test",
    });
});

// For subscriptions, see dispatch_subs.test.cjs

run_test("typing", ({override}) => {
    // Simulate that we are not typing.
    override(current_user, "user_id", typing_person1.user_id + 1);

    let event = event_fixtures.typing__start;
    {
        const stub = make_stub();
        override(typing_events, "display_notification", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("event");
        assert_same(args.event.sender.user_id, typing_person1.user_id);
    }

    event = event_fixtures.typing__stop;
    {
        const stub = make_stub();
        override(typing_events, "hide_notification", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("event");
        assert_same(args.event.sender.user_id, typing_person1.user_id);
    }

    // Get line coverage--we ignore our own typing events.
    override(current_user, "user_id", typing_person1.user_id);
    event = event_fixtures.typing__start;
    dispatch(event);
    override(current_user, "user_id", undefined); // above change shouldn't effect stream_typing tests below
});

run_test("stream_typing", ({override}) => {
    const stream_typing_in_id = events.stream_typing_in_id;
    const topic_typing_in = events.topic_typing_in;
    let event = event_fixtures.stream_typing__start;
    {
        const stub = make_stub();
        override(typing_events, "display_notification", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("event");
        assert_same(args.event.sender.user_id, typing_person1.user_id);
        assert_same(args.event.message_type, "stream");
        assert_same(args.event.stream_id, stream_typing_in_id);
        assert_same(args.event.topic, topic_typing_in);
    }

    event = event_fixtures.stream_typing__stop;
    {
        const stub = make_stub();
        override(typing_events, "hide_notification", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("event");
        assert_same(args.event.sender.user_id, typing_person1.user_id);
        assert_same(args.event.message_type, "stream");
        assert_same(args.event.stream_id, stream_typing_in_id);
        assert_same(args.event.topic, topic_typing_in);
    }
});

run_test("message_edit_typing", ({override}) => {
    override(current_user, "user_id", typing_person1.user_id + 1);

    let event = event_fixtures.message_edit_typing__start;
    {
        const stub = make_stub();
        override(typing_events, "display_message_edit_notification", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("event");
        assert_same(args.event.sender_id, typing_person1.user_id);
        assert_same(args.event.message_id, event.message_id);
    }

    event = event_fixtures.message_edit_typing__stop;
    {
        const stub = make_stub();
        override(typing_events, "hide_message_edit_notification", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("event");
        assert_same(args.event.sender_id, typing_person1.user_id);
        assert_same(args.event.message_id, event.message_id);
    }

    // Get line coverage--we ignore our own typing events.
    override(current_user, "user_id", typing_person1.user_id);
    event = event_fixtures.message_edit_typing__start;
    dispatch(event);
    override(current_user, "user_id", undefined);
});

run_test("stream_typing_message_edit", ({override}) => {
    const stream_typing_in_id = events.stream_typing_in_id;

    let event = event_fixtures.channel_typing_edit_message__start;
    {
        const stub = make_stub();
        override(typing_events, "display_message_edit_notification", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("event");
        assert_same(args.event.sender_id, typing_person1.user_id);
        assert_same(args.event.recipient.type, "channel");
        assert_same(args.event.recipient.channel_id, stream_typing_in_id);
    }

    event = event_fixtures.channel_typing_edit_message__stop;
    {
        const stub = make_stub();
        override(typing_events, "hide_message_edit_notification", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("event");
        assert_same(args.event.sender_id, typing_person1.user_id);
        assert_same(args.event.recipient.type, "channel");
        assert_same(args.event.recipient.channel_id, stream_typing_in_id);
    }
});

run_test("user_settings", ({override}) => {
    settings_preferences.set_default_language_name = () => {};
    let event = event_fixtures.user_settings__default_language;
    override(user_settings, "default_language", "en");
    override(settings_preferences, "update_page", noop);
    override(information_density, "calculate_timestamp_widths", noop);
    override(overlays, "settings_open", () => true);
    dispatch(event);
    assert_same(user_settings.default_language, "fr");

    event = event_fixtures.user_settings__web_escape_navigates_to_home_view;
    override(user_settings, "web_escape_navigates_to_home_view", false);
    let toggled = [];
    $("#go-to-home-view-hotkey-help").toggleClass = (cls) => {
        toggled.push(cls);
    };
    dispatch(event);
    assert_same(user_settings.web_escape_navigates_to_home_view, true);
    assert_same(toggled, ["notdisplayed"]);

    let called = false;
    message_lists.current.rerender = () => {
        called = true;
    };
    let called_for_cached_msg_list = false;
    cached_message_list.rerender = () => {
        called_for_cached_msg_list = true;
    };
    event = event_fixtures.user_settings__twenty_four_hour_time;
    override(user_settings, "twenty_four_hour_time", false);
    dispatch(event);
    assert_same(user_settings.twenty_four_hour_time, true);
    assert_same(called, true);
    assert_same(called_for_cached_msg_list, true);

    event = event_fixtures.user_settings__translate_emoticons;
    override(user_settings, "translate_emoticons", false);
    dispatch(event);
    assert_same(user_settings.translate_emoticons, true);

    event = event_fixtures.user_settings__display_emoji_reaction_users;
    override(user_settings, "display_emoji_reaction_users", false);
    dispatch(event);
    assert_same(user_settings.display_emoji_reaction_users, true);

    event = event_fixtures.user_settings__high_contrast_mode;
    override(user_settings, "high_contrast_mode", false);
    toggled = [];
    $("body").toggleClass = (cls) => {
        toggled.push(cls);
    };
    dispatch(event);
    assert_same(user_settings.high_contrast_mode, true);
    assert_same(toggled, ["high-contrast"]);

    event = event_fixtures.user_settings__web_mark_read_on_scroll_policy;
    override(user_settings, "web_mark_read_on_scroll_policy", 3);
    override(unread_ui, "update_unread_banner", noop);
    dispatch(event);
    assert_same(user_settings.web_mark_read_on_scroll_policy, 1);

    event = event_fixtures.user_settings__web_channel_default_view;
    override(user_settings, "web_channel_default_view", 2);
    let called_create_initial_sidebar_rows = false;
    let called_update_streams_sidebar = false;
    override(stream_list, "create_initial_sidebar_rows", () => {
        called_create_initial_sidebar_rows = true;
    });
    override(stream_list, "update_streams_sidebar", () => {
        called_update_streams_sidebar = true;
    });
    dispatch(event);
    assert_same(user_settings.web_channel_default_view, 1);
    assert.equal(called_create_initial_sidebar_rows, true);
    assert.equal(called_update_streams_sidebar, true);

    event = event_fixtures.user_settings__web_font_size_px;
    override(user_settings, "web_font_size_px", 14);
    assert_same(event.value, 16);
    dispatch(event);
    assert_same(user_settings.web_font_size_px, 14);

    event = event_fixtures.user_settings__web_line_height_percent;
    override(user_settings, "web_line_height_percent", 122);
    assert_same(event.value, 130);
    dispatch(event);
    assert_same(user_settings.web_line_height_percent, 122);

    {
        const stub = make_stub();
        event = event_fixtures.user_settings__color_scheme_automatic;
        override(user_settings, "color_scheme", 2);
        override(theme, "set_theme_and_update", stub.f); // automatically checks if called
        dispatch(event);
        const args = stub.get_args("color_scheme_code");
        assert.equal(stub.num_calls, 1);
        assert.equal(user_settings.color_scheme, args.color_scheme_code);
    }

    {
        const stub = make_stub();
        event = event_fixtures.user_settings__color_scheme_dark;
        override(user_settings, "color_scheme", 1);
        override(theme, "set_theme_and_update", stub.f); // automatically checks if called
        dispatch(event);
        const args = stub.get_args("color_scheme_code");
        assert.equal(stub.num_calls, 1);
        assert.equal(user_settings.color_scheme, args.color_scheme_code);
    }

    {
        const stub = make_stub();
        event = event_fixtures.user_settings__color_scheme_light;
        override(user_settings, "color_scheme", 1);
        override(theme, "set_theme_and_update", stub.f); // automatically checks if called
        dispatch(event);
        const args = stub.get_args("color_scheme_code");
        assert.equal(stub.num_calls, 1);
        assert.equal(user_settings.color_scheme, args.color_scheme_code);
    }

    {
        event = event_fixtures.user_settings__web_home_view_recent_topics;
        override(user_settings, "web_home_view", "all_messages");
        dispatch(event);
        assert.equal(user_settings.web_home_view, "recent_topics");
    }

    {
        event = event_fixtures.user_settings__web_home_view_all_messages;
        override(user_settings, "web_home_view", "recent_topics");
        dispatch(event);
        assert.equal(user_settings.web_home_view, "all_messages");
    }

    {
        event = event_fixtures.user_settings__web_home_view_inbox;
        override(user_settings, "web_home_view", "all_messages");
        dispatch(event);
        assert.equal(user_settings.web_home_view, "inbox");
    }
    {
        event = event_fixtures.user_settings__web_animate_image_previews_always;
        override(user_settings, "web_animate_image_previews", "on_hover");
        dispatch(event);
        assert.equal(user_settings.web_animate_image_previews, "always");
    }

    {
        event = event_fixtures.user_settings__web_animate_image_previews_on_hover;
        override(user_settings, "web_animate_image_previews", "never");
        dispatch(event);
        assert.equal(user_settings.web_animate_image_previews, "on_hover");
    }

    {
        event = event_fixtures.user_settings__web_animate_image_previews_never;
        override(user_settings, "web_animate_image_previews", "always");
        dispatch(event);
        assert.equal(user_settings.web_animate_image_previews, "never");
    }

    {
        const stub = make_stub();
        event = event_fixtures.user_settings__emojiset;
        called = false;
        override(settings_preferences, "report_emojiset_change", stub.f);
        override(activity_ui, "build_user_sidebar", noop);
        override(user_settings, "emojiset", "text");
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        assert_same(called, true);
        assert_same(user_settings.emojiset, "google");
    }

    event = event_fixtures.user_settings__starred_message_counts;
    override(user_settings, "starred_message_counts", false);
    dispatch(event);
    assert_same(user_settings.starred_message_counts, true);

    event = event_fixtures.user_settings__web_left_sidebar_unreads_count_summary;
    override(sidebar_ui, "update_unread_counts_visibility", noop);
    override(user_settings, "web_left_sidebar_unreads_count_summary", true);
    dispatch(event);
    assert_same(user_settings.web_left_sidebar_unreads_count_summary, false);

    event = event_fixtures.user_settings__receives_typing_notifications;
    override(user_settings, "receives_typing_notifications", false);
    dispatch(event);
    assert_same(user_settings.receives_typing_notifications, true);

    event = event_fixtures.user_settings__receives_typing_notifications_disabled;
    override(typing_events, "disable_typing_notification", noop);
    override(user_settings, "receives_typing_notifications", true);
    dispatch(event);
    assert_same(user_settings.receives_typing_notifications, false);

    override(scroll_bar, "set_layout_width", noop);
    event = event_fixtures.user_settings__fluid_layout_width;
    override(user_settings, "fluid_layout_width", false);
    dispatch(event);
    assert_same(user_settings.fluid_layout_width, true);

    {
        const stub = make_stub();
        event = event_fixtures.user_settings__demote_inactive_streams;
        override(stream_list_sort, "set_filter_out_inactives", noop);
        override(stream_list, "update_streams_sidebar", stub.f);
        override(user_settings, "demote_inactive_streams", 1);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        assert_same(user_settings.demote_inactive_streams, 2);
    }

    {
        const stub = make_stub();
        event = event_fixtures.user_settings__web_stream_unreads_count_display_policy;
        override(stream_list, "update_dom_unread_counts_visibility", stub.f);
        override(user_settings, "web_stream_unreads_count_display_policy", 1);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        assert_same(user_settings.web_stream_unreads_count_display_policy, 2);
    }

    {
        const stub = make_stub();
        event = event_fixtures.user_settings__user_list_style;
        override(settings_preferences, "report_user_list_style_change", stub.f);
        override(user_settings, "user_list_style", 1);
        override(activity_ui, "build_user_sidebar", stub.f);
        dispatch(event);
        assert.equal(stub.num_calls, 2);
        assert_same(user_settings.user_list_style, 2);
    }

    event = event_fixtures.user_settings__enter_sends;
    override(user_settings, "enter_sends", false);
    dispatch(event);
    assert_same(user_settings.enter_sends, true);

    event = event_fixtures.user_settings__presence_disabled;
    override(user_settings, "presence_enabled", true);
    override(activity_ui, "redraw_user", noop);
    override(settings_account, "update_privacy_settings_box", noop);
    dispatch(event);
    assert_same(user_settings.presence_enabled, false);

    event = event_fixtures.user_settings__presence_enabled;
    override(activity_ui, "redraw_user", noop);
    dispatch(event);
    assert_same(user_settings.presence_enabled, true);

    {
        event = event_fixtures.user_settings__enable_stream_audible_notifications;
        const stub = make_stub();
        override(stream_ui_updates, "update_notification_setting_checkbox", stub.f);
        override(settings_notifications, "update_page", noop);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("notification_name");
        assert_same(args.notification_name, "audible_notifications");
    }

    event = event_fixtures.user_settings__notification_sound;
    override(audible_notifications, "update_notification_sound_source", noop);
    dispatch(event);

    event = event_fixtures.user_settings__email_address_visibility;
    override(user_settings, "email_address_visibility", 3);
    dispatch(event);
    assert_same(user_settings.email_address_visibility, 5);

    event = event_fixtures.user_settings__web_navigate_to_sent_message;
    override(user_settings, "web_navigate_to_sent_message", true);
    dispatch(event);
    assert_same(user_settings.web_navigate_to_sent_message, false);

    {
        const event = event_fixtures.user_settings_web_suggest_update_timezone;
        dispatch(event);
        assert.equal($("#automatically_offer_update_time_zone").prop("checked"), true);

        event.value = false;
        dispatch(event);
        assert.equal($("#automatically_offer_update_time_zone").prop("checked"), false);
    }

    event = event_fixtures.user_settings__allow_private_data_export;
    override(user_settings, "allow_private_data_export", false);
    override(settings_exports, "refresh_allow_private_data_export_banner", noop);
    dispatch(event);
    assert_same(user_settings.allow_private_data_export, true);
});

run_test("update_message (read)", ({override}) => {
    const event = event_fixtures.update_message_flags__read;

    const stub = make_stub();
    override(unread_ops, "process_read_messages_event", stub.f);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    const args = stub.get_args("message_ids");
    assert_same(args.message_ids, [999]);
});

run_test("update_message (unread)", ({override}) => {
    const event = event_fixtures.update_message_flags__read_remove;

    const stub = make_stub();
    override(unread_ops, "process_unread_messages_event", stub.f);
    dispatch(event);
    assert.equal(stub.num_calls, 1);
    const {args} = stub.get_args("args");
    assert.deepEqual(args, {
        message_ids: event.messages,
        message_details: event.message_details,
    });
});

run_test("update_message (add star)", () => {
    const event = event_fixtures.update_message_flags__starred_add;
    dispatch(event);
    const msg = message_store.get(test_message.id);
    assert.equal(msg.starred, true);
});

run_test("update_message (remove star)", () => {
    const event = event_fixtures.update_message_flags__starred_remove;
    dispatch(event);
    const msg = message_store.get(test_message.id);
    assert.equal(msg.starred, false);
});

run_test("update_message (wrong data)", () => {
    const event = {
        ...event_fixtures.update_message_flags__starred_add,
        messages: [0], // message does not exist
    };
    dispatch(event);
    // update_starred_view never gets invoked, early return is successful
});

run_test("delete_message", ({override}) => {
    const event = event_fixtures.delete_message;

    override(stream_list, "update_streams_sidebar", noop);

    const message_events_stub = make_stub();
    override(message_events, "remove_messages", message_events_stub.f);

    const unread_ops_stub = make_stub();
    override(unread_ops, "process_read_messages_event", unread_ops_stub.f);

    const stream_topic_history_stub = make_stub();
    override(stream_topic_history, "remove_messages", stream_topic_history_stub.f);

    dispatch(event);

    let args;

    args = message_events_stub.get_args("message_ids");
    assert_same(args.message_ids, [1337]);

    args = unread_ops_stub.get_args("message_ids");
    assert_same(args.message_ids, [1337]);

    args = stream_topic_history_stub.get_args("opts");
    assert_same(args.opts.stream_id, 99);
    assert_same(args.opts.topic_name, "topic1");
    assert_same(args.opts.num_messages, 1);
    assert_same(args.opts.max_removed_msg_id, 1337);
});

run_test("user_status", ({override}) => {
    let event = event_fixtures.user_status__set_status_emoji;
    {
        const stub = make_stub();
        override(activity_ui, "redraw_user", stub.f);
        override(compose_pm_pill, "get_user_ids", () => [event.user_id]);
        override(pm_list, "update_private_messages", noop);
        override(compose_recipient, "update_compose_area_placeholder_text", noop);
        dispatch(event);
        assert.equal(stub.num_calls, 2);
        const args = stub.get_args("user_id");
        assert_same(args.user_id, test_user.user_id);
        const emoji_info = user_status.get_status_emoji(test_user.user_id);
        assert.deepEqual(emoji_info, {
            emoji_name: "smiley",
            emoji_code: "1f603",
            reaction_type: "unicode_emoji",
            // Extra parameters that were added by `emoji.get_emoji_details_by_name`
            emoji_alt_code: false,
        });
    }

    event = event_fixtures.user_status__set_status_text;
    {
        const stub = make_stub();
        override(activity_ui, "redraw_user", stub.f);
        override(compose_pm_pill, "get_user_ids", () => [event.user_id]);
        dispatch(event);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("user_id");
        assert_same(args.user_id, test_user.user_id);
        const status_text = user_status.get_status_text(test_user.user_id);
        assert.equal(status_text, "out to lunch");
    }
});

run_test("realm_export", ({override}) => {
    const event = event_fixtures.realm_export;
    const stub = make_stub();
    override(settings_exports, "populate_exports_table", stub.f);
    dispatch(event);

    assert.equal(stub.num_calls, 1);
    const args = stub.get_args("exports");
    assert.equal(args.exports, event.exports);
});

run_test("realm_export_consent", ({override}) => {
    const event = event_fixtures.realm_export_consent;
    const stub = make_stub();
    override(settings_exports, "update_export_consent_data_and_redraw", stub.f);
    dispatch(event);

    assert.equal(stub.num_calls, 1);
    const {export_consent} = stub.get_args("export_consent");
    assert.equal(export_consent.user_id, event.user_id);
    assert.equal(export_consent.consented, event.consented);
});

run_test("server_event_dispatch_op_errors", () => {
    blueslip.expect("error", "Unexpected event type subscription/other");
    server_events_dispatch.dispatch_normal_event({type: "subscription", op: "other"});
    blueslip.expect("error", "Unexpected event type reaction/other");
    server_events_dispatch.dispatch_normal_event({type: "reaction", op: "other"});
    blueslip.expect("error", "Unexpected event type realm/update_dict/other");
    server_events_dispatch.dispatch_normal_event({
        type: "realm",
        op: "update_dict",
        property: "other",
    });
    blueslip.expect("error", "Unexpected event type realm_bot/other");
    server_events_dispatch.dispatch_normal_event({type: "realm_bot", op: "other"});
    blueslip.expect("error", "Unexpected event type realm_domains/other");
    server_events_dispatch.dispatch_normal_event({type: "realm_domains", op: "other"});
    blueslip.expect("error", "Unexpected event type realm_user/other");
    server_events_dispatch.dispatch_normal_event({type: "realm_user", op: "other"});
    blueslip.expect("error", "Unexpected event type stream/other");
    server_events_dispatch.dispatch_normal_event({type: "stream", op: "other"});
    blueslip.expect("error", "Unexpected event type typing/other");
    server_events_dispatch.dispatch_normal_event({
        type: "typing",
        sender: {user_id: 5},
        op: "other",
    });
    blueslip.expect("error", "Unexpected event type typing_edit_message/other");
    server_events_dispatch.dispatch_normal_event({
        type: "typing_edit_message",
        sender_id: 5,
        op: "other",
    });
    blueslip.expect("error", "Unexpected event type user_group/other");
    server_events_dispatch.dispatch_normal_event({type: "user_group", op: "other"});
});

run_test("realm_user_settings_defaults", ({override}) => {
    let event = event_fixtures.realm_user_settings_defaults__emojiset;
    override(realm_user_settings_defaults, "emojiset", "text");
    override(settings_realm_user_settings_defaults, "update_page", noop);
    dispatch(event);
    assert_same(realm_user_settings_defaults.emojiset, "google");

    event = event_fixtures.realm_user_settings_defaults__notification_sound;
    override(realm_user_settings_defaults, "notification_sound", "zulip");
    let called = false;
    audible_notifications.update_notification_sound_source = () => {
        called = true;
    };
    dispatch(event);
    assert_same(realm_user_settings_defaults.notification_sound, "ding");
    assert_same(called, true);
});
