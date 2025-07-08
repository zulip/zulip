"use strict";

const assert = require("node:assert/strict");

const example_settings = require("./lib/example_settings.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {make_stub} = require("./lib/stub.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const $ = require("./lib/zjquery.cjs");

const browser_history = mock_esm("../src/browser_history");
const color_data = mock_esm("../src/color_data");
const compose_recipient = mock_esm("../src/compose_recipient");
const dialog_widget = mock_esm("../src/dialog_widget");
const message_live_update = mock_esm("../src/message_live_update");
const settings_streams = mock_esm("../src/settings_streams");
const stream_color_events = mock_esm("../src/stream_color_events");
const stream_list = mock_esm("../src/stream_list");
const stream_muting = mock_esm("../src/stream_muting");
const stream_settings_api = mock_esm("../src/stream_settings_api");
const stream_settings_data = mock_esm("../src/stream_settings_data");
const onboarding_steps = mock_esm("../src/onboarding_steps");
const stream_settings_ui = mock_esm("../src/stream_settings_ui", {
    update_settings_for_subscribed: noop,
    update_empty_left_panel_message: noop,
});
const unread_ui = mock_esm("../src/unread_ui");
const message_lists = mock_esm("../src/message_lists", {
    current: undefined,
});
const message_view_header = mock_esm("../src/message_view_header", {
    maybe_rerender_title_area_for_stream() {},
});
mock_esm("../src/recent_view_ui", {
    complete_rerender() {},
});
mock_esm("../src/settings_notifications", {
    update_page() {},
    user_settings_panel: "stub", // Not used, but can't be undefined
});
mock_esm("../src/overlays", {
    streams_open: () => true,
});
const settings_config = zrequire("settings_config");
mock_esm("../src/user_settings", {
    user_settings: {
        web_channel_default_view: settings_config.web_channel_default_view_values.channel_feed.code,
    },
});

const user_group_edit = mock_esm("../src/user_group_edit");
const user_profile = mock_esm("../src/user_profile");

const {Filter} = zrequire("../src/filter");
const activity_ui = zrequire("activity_ui");
const {buddy_list} = zrequire("buddy_list");
const compose_state = zrequire("compose_state");
const narrow_state = zrequire("narrow_state");
const peer_data = zrequire("peer_data");
const people = zrequire("people");
const {set_current_user, set_realm} = zrequire("state_data");
const stream_create = zrequire("stream_create");
const stream_data = zrequire("stream_data");
const stream_events = zrequire("stream_events");

const realm = {};
set_current_user({});
set_realm(realm);

const george = {
    email: "george@zulip.com",
    full_name: "George",
    user_id: 103,
};
const me = {
    email: "me@zulip.com",
    full_name: "Me Myself",
    user_id: 104,
};
people.add_active_user(george);
people.add_active_user(me);
people.initialize_current_user(me.user_id);

const dev_help = {
    subscribed: true,
    color: "blue",
    name: "dev help",
    stream_id: 2,
    is_muted: true,
    invite_only: false,
    can_administer_channel_group: 1,
    can_remove_subscribers_group: 1,
};

const frontend = {
    subscribed: false,
    color: "yellow",
    name: "frontend",
    stream_id: 101,
    is_muted: true,
    invite_only: false,
    can_administer_channel_group: 1,
    can_remove_subscribers_group: 1,
};

function narrow_to_frontend() {
    const filter = new Filter([{operator: "stream", operand: frontend.stream_id.toString()}]);
    message_lists.current = {
        data: {
            filter,
        },
    };
}

function test(label, f) {
    run_test(label, (helpers) => {
        stream_data.clear_subscriptions();
        f(helpers);
    });
}

test("update_property", ({override}) => {
    override(compose_recipient, "possibly_update_stream_name_in_compose", noop);
    override(compose_recipient, "on_compose_select_recipient_update", noop);
    override(
        realm,
        "server_supported_permission_settings",
        example_settings.server_supported_permission_settings,
    );
    override(user_group_edit, "update_stream_setting_in_permissions_panel", noop);
    const sub = {...frontend};
    stream_data.add_sub(sub);

    const stream_id = sub.stream_id;

    // Invoke error for non-existent stream/property
    {
        blueslip.expect("warn", "Update for an unknown subscription");
        stream_events.update_property(99, "color", "blue");
        blueslip.reset();

        blueslip.expect("warn", "Unexpected subscription property type");
        stream_events.update_property(stream_id, "not_real", 42);
        blueslip.reset();
    }

    // Test update color
    {
        const stub = make_stub();
        override(stream_color_events, "update_stream_color", stub.f);
        stream_events.update_property(stream_id, "color", "blue");
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "val");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, "blue");
    }

    // Test in home view (code coverage; until event/property removed)
    {
        stream_events.update_property(stream_id, "in_home_view", false);
    }

    // Test is muted
    {
        const stub = make_stub();
        override(stream_muting, "update_is_muted", stub.f);
        override(stream_list, "refresh_muted_or_unmuted_stream", noop);
        stream_events.update_property(stream_id, "is_muted", true);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "val");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, true);
    }

    function checkbox_for(property) {
        return $(`#${CSS.escape(property)}_${CSS.escape(stream_id)}`);
    }

    // Test desktop notifications
    stream_events.update_property(stream_id, "desktop_notifications", true);
    assert.equal(sub.desktop_notifications, true);
    let $checkbox = checkbox_for("desktop_notifications");
    assert.equal($checkbox.prop("checked"), true);

    // Tests audible notifications
    stream_events.update_property(stream_id, "audible_notifications", true);
    assert.equal(sub.audible_notifications, true);
    $checkbox = checkbox_for("audible_notifications");
    assert.equal($checkbox.prop("checked"), true);

    // Tests push notifications
    stream_events.update_property(stream_id, "push_notifications", true);
    assert.equal(sub.push_notifications, true);
    $checkbox = checkbox_for("push_notifications");
    assert.equal($checkbox.prop("checked"), true);

    // Tests email notifications
    stream_events.update_property(stream_id, "email_notifications", true);
    assert.equal(sub.email_notifications, true);
    $checkbox = checkbox_for("email_notifications");
    assert.equal($checkbox.prop("checked"), true);

    // Tests wildcard_mentions_notify notifications
    stream_events.update_property(stream_id, "wildcard_mentions_notify", true);
    assert.equal(sub.wildcard_mentions_notify, true);
    $checkbox = checkbox_for("wildcard_mentions_notify");
    assert.equal($checkbox.prop("checked"), true);

    // Test name change
    {
        const stub = make_stub();
        override(stream_settings_ui, "update_stream_name", stub.f);
        stream_events.update_property(stream_id, "name", "the frontend");
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "val");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, "the frontend");
    }

    // Test description change
    {
        const stub = make_stub();
        override(stream_settings_ui, "update_stream_description", stub.f);
        stream_events.update_property(stream_id, "description", "we write code", {
            rendered_description: "we write code",
        });
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "val");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, "we write code");
    }

    // Test pin to top
    {
        override(stream_list, "refresh_pinned_or_unpinned_stream", noop);
        stream_events.update_property(stream_id, "pin_to_top", true);
        $checkbox = checkbox_for("pin_to_top");
        assert.equal($checkbox.prop("checked"), true);
    }

    // Test change in stream active status
    {
        let sidebar_updated_for_stream_active_status = false;
        override(stream_list, "update_streams_sidebar", () => {
            sidebar_updated_for_stream_active_status = true;
        });
        stream_events.update_property(stream_id, "is_recently_active", false);
        assert.equal(sidebar_updated_for_stream_active_status, true);
    }

    // Test stream privacy change event
    {
        const stub = make_stub();
        override(stream_settings_ui, "update_stream_privacy", stub.f);
        stream_events.update_property(stream_id, "invite_only", true, {
            history_public_to_subscribers: true,
            is_web_public: false,
        });
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "val");
        assert.equal(args.sub.stream_id, stream_id);
        assert.deepEqual(args.val, {
            invite_only: true,
            history_public_to_subscribers: true,
            is_web_public: false,
        });
    }

    // Test stream message_retention_days change event
    {
        const stub = make_stub();
        override(stream_settings_ui, "update_message_retention_setting", stub.f);
        stream_events.update_property(stream_id, "message_retention_days", 20);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "val");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, 20);
    }

    // Test stream topics_policy change event
    {
        const stub = make_stub();
        override(stream_settings_ui, "update_topics_policy_setting", stub.f);
        override(compose_recipient, "update_topic_inputbox_on_topics_policy_change", noop);
        override(compose_recipient, "update_compose_area_placeholder_text", noop);
        stream_events.update_property(stream_id, "topics_policy", "allow_topics_policy");
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "val");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, "allow_topics_policy");
    }

    // Test stream can_remove_subscribers_group change event
    {
        const stub = make_stub();
        override(stream_settings_ui, "update_stream_permission_group_setting", stub.f);
        stream_events.update_property(stream_id, "can_remove_subscribers_group", 3);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("setting_name", "sub", "val");
        assert.equal(args.setting_name, "can_remove_subscribers_group");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, 3);
    }

    // Test stream can_administer_channel_group change event
    {
        const stub = make_stub();
        override(stream_settings_ui, "update_stream_permission_group_setting", stub.f);
        override(stream_settings_data, "get_sub_for_settings", () => ({
            can_add_subscribers: false,
            ...sub,
        }));
        stream_events.update_property(stream_id, "can_administer_channel_group", 3);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("setting_name", "sub", "val");
        assert.equal(args.setting_name, "can_administer_channel_group");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, 3);
    }

    // Test stream can_resolve_topics_group change event
    {
        const stub = make_stub();
        override(stream_settings_ui, "update_stream_permission_group_setting", stub.f);
        override(message_live_update, "rerender_messages_view", noop);
        stream_events.update_property(stream_id, "can_resolve_topics_group", 3);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("setting_name", "sub", "val");
        assert.equal(args.setting_name, "can_resolve_topics_group");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, 3);
    }

    // Test stream can_subscribe_group change event
    {
        const stub = make_stub();
        override(stream_settings_ui, "update_stream_permission_group_setting", stub.f);
        const update_subscription_elements_stub = make_stub();
        override(
            stream_settings_ui,
            "update_subscription_elements",
            update_subscription_elements_stub.f,
        );
        stream_events.update_property(stream_id, "can_subscribe_group", 3);
        assert.equal(stub.num_calls, 1);
        assert.equal(update_subscription_elements_stub.num_calls, 1);
        let args = stub.get_args("setting_name", "sub", "val");
        assert.equal(args.setting_name, "can_subscribe_group");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, 3);
        args = update_subscription_elements_stub.get_args("sub");
        assert.equal(args.sub, sub);
    }

    // Update channel folder
    {
        const stub = make_stub();
        override(stream_settings_ui, "update_channel_folder", stub.f);
        stream_events.update_property(stream_id, "folder_id", 3);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "value");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.value, 3);
    }

    // Test archiving stream
    {
        stream_data.subscribe_myself(sub);

        const stub = make_stub();
        override(stream_settings_ui, "update_settings_for_archived_and_unarchived", stub.f);
        override(settings_streams, "update_default_streams_table", noop);
        override(message_live_update, "rerender_messages_view", noop);

        narrow_to_frontend();
        let bookend_updates = 0;
        override(message_lists.current, "update_trailing_bookend", () => {
            bookend_updates += 1;
        });

        let removed_sidebar_rows = 0;
        override(stream_list, "remove_sidebar_row", () => {
            removed_sidebar_rows += 1;
        });

        compose_state.set_stream_id(stream_id);

        stream_events.update_property(stream_id, "is_archived", true);

        assert.ok(stream_data.is_stream_archived(stream_id));
        assert.ok(stream_data.is_subscribed(stream_id));

        const args = stub.get_args("sub");
        assert.equal(args.sub.stream_id, stream_id);

        assert.equal(bookend_updates, 1);
        assert.equal(removed_sidebar_rows, 1);
    }

    // Test unarchiving stream
    {
        const stub = make_stub();
        override(stream_settings_ui, "update_settings_for_archived_and_unarchived", stub.f);
        override(message_live_update, "rerender_messages_view", noop);

        let bookend_updates = 0;
        override(message_lists.current, "update_trailing_bookend", () => {
            bookend_updates += 1;
        });

        let added_sidebar_rows = 0;
        override(stream_list, "add_sidebar_row", () => {
            added_sidebar_rows += 1;
        });

        compose_state.set_stream_id(stream_id);

        // Unarchive the stream
        stream_events.update_property(stream_id, "is_archived", false);
        assert.ok(!stream_data.is_stream_archived(stream_id));
        assert.ok(stream_data.is_subscribed(stream_id));

        const args = stub.get_args("sub");
        assert.equal(args.sub.stream_id, stream_id);

        assert.equal(bookend_updates, 1);
        assert.equal(added_sidebar_rows, 1);
    }

    // Test deprecated properties for coverage.
    {
        stream_events.update_property(stream_id, "stream_post_policy", 2);
        stream_events.update_property(stream_id, "is_announcement_only", false);
    }
});

test("marked_(un)subscribed (early return)", () => {
    // The early-return prevents us from exploding or needing
    // to override functions with side effects
    stream_events.mark_subscribed({subscribed: true});
    stream_events.mark_unsubscribed({subscribed: false});
});

test("marked_subscribed (normal)", ({override}) => {
    const sub = {...frontend};
    stream_data.add_sub(sub);
    override(stream_color_events, "update_stream_color", noop);
    override(buddy_list, "populate", noop);
    activity_ui.set_cursor_and_filter();

    narrow_to_frontend();

    let list_updated = false;

    const stream_list_stub = make_stub();
    const message_view_header_stub = make_stub();

    override(stream_list, "add_sidebar_row", stream_list_stub.f);
    override(stream_list, "update_subscribe_to_more_streams_link", noop);
    override(unread_ui, "update_unread_counts", noop);
    override(
        message_view_header,
        "maybe_rerender_title_area_for_stream",
        message_view_header_stub.f,
    );
    override(message_lists.current, "update_trailing_bookend", () => {
        list_updated = true;
    });
    override(user_profile, "update_user_profile_streams_list_for_users", noop);

    $("#channels_overlay_container .stream-row:not(.notdisplayed)").length = 0;

    stream_events.mark_subscribed(sub, [], "blue");

    const args = stream_list_stub.get_args("sub");
    assert.equal(args.sub.stream_id, sub.stream_id);
    assert.equal(message_view_header_stub.num_calls, 1);

    assert.equal(list_updated, true);

    assert.equal(sub.color, "blue");
    message_lists.current = undefined;
});

test("marked_subscribed (color)", ({override}) => {
    override(stream_list, "add_sidebar_row", noop);
    override(stream_list, "update_subscribe_to_more_streams_link", noop);
    override(unread_ui, "update_unread_counts", noop);

    const sub = {
        subscribed: false,
        name: "production help",
        stream_id: 201,
        is_muted: true,
        invite_only: false,
    };
    stream_data.add_sub(sub);

    override(color_data, "pick_color", () => "green");
    override(user_profile, "update_user_profile_streams_list_for_users", noop);

    $("#channels_overlay_container .stream-row:not(.notdisplayed)").length = 0;

    // narrow state is undefined
    {
        const stub = make_stub();
        override(stream_settings_api, "set_color", stub.f);
        blueslip.expect("warn", "Frontend needed to pick a color in mark_subscribed");
        stream_events.mark_subscribed(sub, [], undefined);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("id", "color");
        assert.equal(args.id, sub.stream_id);
        assert.equal(args.color, "green");
        blueslip.reset();
    }
});

test("marked_subscribed (emails)", ({override}) => {
    const sub = {...frontend};
    stream_data.add_sub(sub);
    override(stream_color_events, "update_stream_color", noop);

    // Test assigning subscriber emails
    // narrow state is undefined
    override(stream_list, "add_sidebar_row", noop);
    override(stream_list, "update_subscribe_to_more_streams_link", noop);
    override(unread_ui, "update_unread_counts", noop);

    const subs_stub = make_stub();
    override(stream_settings_ui, "update_settings_for_subscribed", subs_stub.f);
    override(user_profile, "update_user_profile_streams_list_for_users", noop);

    $("#channels_overlay_container .stream-row:not(.notdisplayed)").length = 0;

    assert.ok(!stream_data.is_subscribed(sub.stream_id));

    const user_ids = [15, 20, 25, me.user_id];
    stream_events.mark_subscribed(sub, user_ids, "");
    assert.deepEqual(new Set(peer_data.get_subscribers(sub.stream_id)), new Set(user_ids));
    assert.ok(stream_data.is_subscribed(sub.stream_id));

    const args = subs_stub.get_args("sub");
    assert.deepEqual(sub, args.sub);
});

test("mark_unsubscribed (update_settings_for_unsubscribed)", ({override}) => {
    // Test unsubscribe
    const sub = {...dev_help};
    stream_data.add_sub(sub);
    stream_data.subscribe_myself(sub);

    const stub = make_stub();

    override(stream_settings_ui, "update_settings_for_unsubscribed", stub.f);
    override(stream_list, "remove_sidebar_row", noop);
    override(stream_list, "update_subscribe_to_more_streams_link", noop);
    override(unread_ui, "update_unread_counts", noop);
    override(user_profile, "update_user_profile_streams_list_for_users", noop);

    $("#channels_overlay_container .stream-row:not(.notdisplayed)").length = 0;

    stream_events.mark_unsubscribed(sub);
    const args = stub.get_args("sub");
    assert.deepEqual(args.sub, sub);
});

test("mark_unsubscribed (render_title_area)", ({override}) => {
    const sub = {...frontend, subscribed: true};
    stream_data.add_sub(sub);

    // Test update bookend and remove done event
    narrow_to_frontend();
    const message_view_header_stub = make_stub();
    override(
        message_view_header,
        "maybe_rerender_title_area_for_stream",
        message_view_header_stub.f,
    );
    override(stream_settings_ui, "update_settings_for_unsubscribed", noop);
    override(message_lists.current, "update_trailing_bookend", noop);
    override(stream_list, "remove_sidebar_row", noop);
    override(stream_list, "update_subscribe_to_more_streams_link", noop);
    override(unread_ui, "update_unread_counts", noop);
    override(unread_ui, "hide_unread_banner", noop);
    override(user_profile, "update_user_profile_streams_list_for_users", noop);
    override(buddy_list, "populate", noop);

    $("#channels_overlay_container .stream-row:not(.notdisplayed)").length = 0;

    stream_events.mark_unsubscribed(sub);

    assert.equal(message_view_header_stub.num_calls, 1);

    message_lists.current = undefined;
});

test("remove_deactivated_user_from_all_streams", () => {
    stream_data.add_sub(dev_help);
    const subs_stub = make_stub();
    stream_settings_ui.update_subscribers_ui = subs_stub.f;

    // assert starting state
    assert.ok(!stream_data.is_user_subscribed(dev_help.stream_id, george.user_id));

    // verify that deactivating user should unsubscribe user from all streams
    peer_data.add_subscriber(dev_help.stream_id, george.user_id);
    assert.ok(stream_data.is_user_subscribed(dev_help.stream_id, george.user_id));

    stream_events.remove_deactivated_user_from_all_streams(george.user_id);

    // verify that we issue a call to update subscriber count/list UI
    assert.equal(subs_stub.num_calls, 1);
});

test("process_subscriber_update", ({override, override_rewire}) => {
    const subsStub = make_stub();
    stream_settings_ui.update_subscribers_ui = subsStub.f;

    let build_user_sidebar_called = false;
    override_rewire(activity_ui, "build_user_sidebar", () => {
        build_user_sidebar_called = true;
    });
    override(user_profile, "update_user_profile_streams_list_for_users", noop);
    // Sample user IDs
    const userIds = [104, 2, 3];
    // Sample stream IDs
    const streamIds = [1, 2, 3];
    stream_data.add_sub({
        stream_id: 1,
        name: "Rome",
    });
    stream_data.add_sub({
        stream_id: 2,
        name: "Denmark",
    });
    stream_data.add_sub({
        stream_id: 3,
        name: "Paris",
    });
    // Call the function being tested
    stream_events.process_subscriber_update(userIds, streamIds);

    // Assert that update_subscribers_ui is called for each stream ID
    assert.equal(subsStub.num_calls, streamIds.length);

    assert.ok(!build_user_sidebar_called);

    // For a stream the user is currently viewing, we rebuild the user sidebar
    // when someone subscribes to that stream.
    override_rewire(narrow_state, "stream_id", () => 1);
    stream_events.process_subscriber_update(userIds, streamIds);
    assert.ok(build_user_sidebar_called);
});

test("marked_subscribed (new channel creation)", ({override}) => {
    stream_create.set_name(frontend.name);
    const sub = {...frontend};
    stream_data.add_sub(sub);

    const go_to_location_stub = make_stub();
    override(browser_history, "go_to_location", go_to_location_stub.f);
    override(unread_ui, "update_unread_counts", noop);
    override(stream_list, "add_sidebar_row", noop);
    override(stream_list, "update_subscribe_to_more_streams_link", noop);
    override(user_profile, "update_user_profile_streams_list_for_users", noop);
    override(
        onboarding_steps,
        "ONE_TIME_NOTICES_TO_DISPLAY",
        new Set(["first_stream_created_banner"]),
    );
    override(onboarding_steps, "post_onboarding_step_as_read", noop);

    // We're stubbing 'dialog_widget.launch()' instead of
    // 'stream_events.show_first_stream_created_modal()'
    // as it helps in test coverage.
    const dialog_widget_stub = make_stub();
    override(dialog_widget, "launch", dialog_widget_stub.f);

    stream_events.mark_subscribed(sub, [], "yellow");

    // Verify that the creator is redirected to channel view
    // and the first_stream_created modal is displayed.
    assert.equal(go_to_location_stub.num_calls, 1);
    assert.equal(dialog_widget_stub.num_calls, 1);
    assert.equal(stream_create.get_name(), undefined);
});
