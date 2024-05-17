"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {make_stub} = require("./lib/stub");
const {run_test, noop} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");

const color_data = mock_esm("../src/color_data");
const compose_recipient = mock_esm("../src/compose_recipient");
const stream_color_events = mock_esm("../src/stream_color_events");
const stream_list = mock_esm("../src/stream_list");
const stream_muting = mock_esm("../src/stream_muting");
const stream_settings_api = mock_esm("../src/stream_settings_api");
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
});
mock_esm("../src/overlays", {
    streams_open: () => true,
});
const user_profile = mock_esm("../src/user_profile");

const {Filter} = zrequire("../src/filter");
const activity_ui = zrequire("activity_ui");
const {buddy_list} = zrequire("buddy_list");
const narrow_state = zrequire("narrow_state");
const peer_data = zrequire("peer_data");
const people = zrequire("people");
const settings_config = zrequire("settings_config");
const stream_data = zrequire("stream_data");
const stream_events = zrequire("stream_events");

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
};

const frontend = {
    subscribed: false,
    color: "yellow",
    name: "frontend",
    stream_id: 101,
    is_muted: true,
    invite_only: false,
};

function narrow_to_frontend() {
    const filter = new Filter([{operator: "stream", operand: "frontend"}]);
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

    // Test email address change
    stream_events.update_property(stream_id, "email_address", "zooly@zulip.com");
    assert.equal(sub.email_address, "zooly@zulip.com");

    // Test pin to top
    {
        override(stream_list, "refresh_pinned_or_unpinned_stream", noop);
        stream_events.update_property(stream_id, "pin_to_top", true);
        $checkbox = checkbox_for("pin_to_top");
        assert.equal($checkbox.prop("checked"), true);
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

    // Test stream stream_post_policy change event
    {
        const stub = make_stub();
        override(stream_settings_ui, "update_stream_post_policy", stub.f);
        stream_events.update_property(
            stream_id,
            "stream_post_policy",
            settings_config.stream_post_policy_values.admins.code,
        );
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "val");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, settings_config.stream_post_policy_values.admins.code);
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

    // Test stream can_remove_subscribers_group change event
    {
        const stub = make_stub();
        override(stream_settings_ui, "update_can_remove_subscribers_group_id", stub.f);
        stream_events.update_property(stream_id, "can_remove_subscribers_group", 3);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "val");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, 3);
    }
});

test("marked_unsubscribed (code coverage)", () => {
    // We don't error for unsubscribed streams for some reason.
    stream_events.mark_unsubscribed(undefined);
});

test("marked_(un)subscribed (early return)", () => {
    // The early-return prevents us from exploding or needing
    // to override functions with side effects
    stream_events.mark_subscribed({subscribed: true});
    stream_events.mark_unsubscribed({subscribed: false});
});

test("marked_subscribed (error)", () => {
    // Test undefined error
    blueslip.expect("error", "Undefined sub passed to mark_subscribed");
    stream_events.mark_subscribed(undefined, [], "yellow");
    blueslip.reset();
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

    assert.ok(!stream_data.is_subscribed_by_name(sub.name));

    const user_ids = [15, 20, 25, me.user_id];
    stream_events.mark_subscribed(sub, user_ids, "");
    assert.deepEqual(new Set(peer_data.get_subscribers(sub.stream_id)), new Set(user_ids));
    assert.ok(stream_data.is_subscribed_by_name(sub.name));

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
