"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {make_stub} = require("../zjsunit/stub");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const noop = function () {};
const return_true = function () {
    return true;
};
const _settings_notifications = {
    update_page: () => {},
};
set_global("settings_notifications", _settings_notifications);

const color_data = set_global("color_data", {});
set_global("current_msg_list", {});
const message_util = set_global("message_util", {});
const stream_color = set_global("stream_color", {});
const stream_list = set_global("stream_list", {});
const stream_muting = set_global("stream_muting", {});
let subs = set_global("subs", {});

const peer_data = zrequire("peer_data");
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const stream_events = zrequire("stream_events");
const Filter = zrequire("Filter", "js/filter");
const narrow_state = zrequire("narrow_state");
const message_view_header = zrequire("message_view_header");

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

const frontend = {
    subscribed: false,
    color: "yellow",
    name: "frontend",
    stream_id: 101,
    is_muted: true,
    invite_only: false,
};

set_global("message_list", {
    all: {
        all_messages() {
            return ["msg"];
        },
    },
});

stream_data.add_sub(frontend);

const frontend_filter_terms = [{operator: "stream", operand: "frontend"}];

const frontend_filter = new Filter(frontend_filter_terms);

run_test("update_property", (override) => {
    const stream_id = frontend.stream_id;

    // Invoke error for non-existent stream/property
    {
        let errors = 0;
        override(blueslip, "warn", () => {
            errors += 1;
        });

        stream_events.update_property(99, "color", "blue");
        assert.equal(errors, 1);

        stream_events.update_property(stream_id, "not_real", 42);
        assert.equal(errors, 2);
    }

    // Test update color
    {
        const stub = make_stub();
        override(stream_color, "update_stream_color", stub.f);
        stream_events.update_property(stream_id, "color", "blue");
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "val");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, "blue");
    }

    // Test in home view
    {
        const stub = make_stub();
        override(stream_muting, "update_is_muted", stub.f);
        stream_events.update_property(stream_id, "in_home_view", false);
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
    assert.equal(frontend.desktop_notifications, true);
    let checkbox = checkbox_for("desktop_notifications");
    assert.equal(checkbox.prop("checked"), true);

    // Tests audible notifications
    stream_events.update_property(stream_id, "audible_notifications", true);
    assert.equal(frontend.audible_notifications, true);
    checkbox = checkbox_for("audible_notifications");
    assert.equal(checkbox.prop("checked"), true);

    // Tests push notifications
    stream_events.update_property(stream_id, "push_notifications", true);
    assert.equal(frontend.push_notifications, true);
    checkbox = checkbox_for("push_notifications");
    assert.equal(checkbox.prop("checked"), true);

    // Tests email notifications
    stream_events.update_property(stream_id, "email_notifications", true);
    assert.equal(frontend.email_notifications, true);
    checkbox = checkbox_for("email_notifications");
    assert.equal(checkbox.prop("checked"), true);

    // Tests wildcard_mentions_notify notifications
    stream_events.update_property(stream_id, "wildcard_mentions_notify", true);
    assert.equal(frontend.wildcard_mentions_notify, true);
    checkbox = checkbox_for("wildcard_mentions_notify");
    assert.equal(checkbox.prop("checked"), true);

    // Test name change
    {
        const stub = make_stub();
        override(subs, "update_stream_name", stub.f);
        stream_events.update_property(stream_id, "name", "the frontend");
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "val");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, "the frontend");
    }

    // Test description change
    {
        const stub = make_stub();
        override(subs, "update_stream_description", stub.f);
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
    assert.equal(frontend.email_address, "zooly@zulip.com");

    // Test pin to top
    {
        override(stream_list, "refresh_pinned_or_unpinned_stream", noop);
        stream_events.update_property(stream_id, "pin_to_top", true);
        checkbox = checkbox_for("pin_to_top");
        assert.equal(checkbox.prop("checked"), true);
    }

    // Test stream privacy change event
    {
        const stub = make_stub();
        override(subs, "update_stream_privacy", stub.f);
        stream_events.update_property(stream_id, "invite_only", true, {
            history_public_to_subscribers: true,
        });
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "val");
        assert.equal(args.sub.stream_id, stream_id);
        assert.deepEqual(args.val, {
            invite_only: true,
            history_public_to_subscribers: true,
        });
    }

    // Test stream stream_post_policy change event
    {
        const stub = make_stub();
        override(subs, "update_stream_post_policy", stub.f);
        stream_events.update_property(
            stream_id,
            "stream_post_policy",
            stream_data.stream_post_policy_values.admins.code,
        );
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "val");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, stream_data.stream_post_policy_values.admins.code);
    }

    // Test stream message_retention_days change event
    {
        const stub = make_stub();
        override(subs, "update_message_retention_setting", stub.f);
        stream_events.update_property(stream_id, "message_retention_days", 20);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("sub", "val");
        assert.equal(args.sub.stream_id, stream_id);
        assert.equal(args.val, 20);
    }
});

run_test("marked_unsubscribed (code coverage)", () => {
    // We don't error for unsubscribed streams for some reason.
    stream_events.mark_unsubscribed(undefined);
});

run_test("marked_(un)subscribed (early return)", () => {
    // The early-return prevents us from exploding or needing
    // to override functions with side effects
    stream_events.mark_subscribed({subscribed: true});
    stream_events.mark_unsubscribed({subscribed: false});
});

run_test("marked_subscribed (error)", (override) => {
    // Test undefined error
    let errors = 0;
    override(blueslip, "error", () => {
        errors += 1;
    });
    stream_events.mark_subscribed(undefined, [], "yellow");
    assert.equal(errors, 1);
});

run_test("marked_subscribed (normal)", (override) => {
    override(stream_data, "subscribe_myself", noop);
    override(stream_data, "update_calculated_fields", noop);

    subs = set_global("subs", {update_settings_for_subscribed: noop});
    set_global("overlays", {streams_open: return_true});

    override(stream_color, "update_stream_color", noop);

    narrow_state.set_current_filter(frontend_filter);

    let args;
    let list_updated = false;

    const stream_list_stub = make_stub();
    const message_view_header_stub = make_stub();
    const message_util_stub = make_stub();

    override(stream_list, "add_sidebar_row", stream_list_stub.f);
    override(message_util, "do_unread_count_updates", message_util_stub.f);
    override(message_view_header, "render_title_area", message_view_header_stub.f);
    override(current_msg_list, "update_trailing_bookend", () => {
        list_updated = true;
    });

    stream_events.mark_subscribed(frontend, [], "blue");

    args = message_util_stub.get_args("messages");
    assert.deepEqual(args.messages, ["msg"]);

    args = stream_list_stub.get_args("sub");
    assert.equal(args.sub.stream_id, frontend.stream_id);
    assert.equal(message_view_header_stub.num_calls, 1);

    assert.equal(list_updated, true);

    assert.equal(frontend.color, "blue");
    narrow_state.reset_current_filter();
});

run_test("marked_subscribed (color)", (override) => {
    override(stream_data, "subscribe_myself", noop);
    override(stream_data, "update_calculated_fields", noop);
    override(message_util, "do_unread_count_updates", noop);
    override(stream_list, "add_sidebar_row", noop);

    frontend.color = undefined;
    override(color_data, "pick_color", () => "green");
    let warnings = 0;
    override(blueslip, "warn", () => {
        warnings += 1;
    });

    // narrow state is undefined
    {
        const stub = make_stub();
        override(subs, "set_color", stub.f);
        stream_events.mark_subscribed(frontend, [], undefined);
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("id", "color");
        assert.equal(args.id, frontend.stream_id);
        assert.equal(args.color, "green");
        assert.equal(warnings, 1);
    }
});

run_test("marked_subscribed (emails)", (override) => {
    override(stream_data, "update_calculated_fields", noop);
    override(stream_color, "update_stream_color", noop);

    // Test assigning subscriber emails
    // narrow state is undefined
    override(message_util, "do_unread_count_updates", noop);
    override(stream_list, "add_sidebar_row", noop);

    const subs_stub = make_stub();
    override(subs, "update_settings_for_subscribed", subs_stub.f);

    assert(!stream_data.is_subscribed(frontend.name));

    const user_ids = [15, 20, 25, me.user_id];
    stream_events.mark_subscribed(frontend, user_ids, "");
    assert.deepEqual(new Set(peer_data.get_subscribers(frontend.stream_id)), new Set(user_ids));
    assert(stream_data.is_subscribed(frontend.name));

    const args = subs_stub.get_args("sub");
    assert.deepEqual(frontend, args.sub);
});

run_test("mark_unsubscribed (update_settings_for_unsubscribed)", (override) => {
    override(stream_data, "update_calculated_fields", noop);

    // Test unsubscribe
    frontend.subscribed = true;

    const stub = make_stub();

    override(subs, "update_settings_for_unsubscribed", stub.f);
    override(stream_list, "remove_sidebar_row", noop);
    override(stream_data, "unsubscribe_myself", noop);

    stream_events.mark_unsubscribed(frontend);
    const args = stub.get_args("sub");
    assert.deepEqual(args.sub, frontend);
});

run_test("mark_unsubscribed (render_title_area)", (override) => {
    override(stream_data, "update_calculated_fields", noop);

    // Test update bookend and remove done event
    narrow_state.set_current_filter(frontend_filter);
    const message_view_header_stub = make_stub();
    override(message_view_header, "render_title_area", message_view_header_stub.f);
    override(stream_data, "unsubscribe_myself", noop);
    override(subs, "update_settings_for_unsubscribed", noop);
    override(current_msg_list, "update_trailing_bookend", noop);
    override(stream_list, "remove_sidebar_row", noop);

    stream_events.mark_unsubscribed(frontend);

    assert.equal(message_view_header_stub.num_calls, 1);

    narrow_state.reset_current_filter();
});

stream_data.clear_subscriptions();
const dev_help = {
    subscribed: true,
    color: "blue",
    name: "dev help",
    stream_id: 2,
    is_muted: true,
    invite_only: false,
};
stream_data.add_sub(dev_help);

run_test("remove_deactivated_user_from_all_streams", () => {
    const subs_stub = make_stub();
    subs.update_subscribers_ui = subs_stub.f;

    dev_help.can_access_subscribers = true;

    // assert starting state
    assert(!stream_data.is_user_subscribed(dev_help.stream_id, george.user_id));

    // verify that deactivating user should unsubscribe user from all streams
    peer_data.add_subscriber(dev_help.stream_id, george.user_id);
    assert(stream_data.is_user_subscribed(dev_help.stream_id, george.user_id));

    stream_events.remove_deactivated_user_from_all_streams(george.user_id);

    // verify that we issue a call to update subscriber count/list UI
    assert.equal(subs_stub.num_calls, 1);
});
