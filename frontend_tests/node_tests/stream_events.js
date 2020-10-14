"use strict";

const noop = function () {};
const return_true = function () {
    return true;
};
set_global("$", global.make_zjquery());
const _settings_notifications = {
    update_page: () => {},
};
set_global("settings_notifications", _settings_notifications);

set_global("color_data", {});
set_global("current_msg_list", {});
set_global("message_util", {});
set_global("stream_color", {});
set_global("stream_list", {});
set_global("stream_muting", {});
set_global("subs", {});

const people = zrequire("people");
zrequire("stream_data");
zrequire("stream_events");
zrequire("Filter", "js/filter");
zrequire("narrow_state");
zrequire("message_view_header");

const george = {
    email: "george@zulip.com",
    full_name: "George",
    user_id: 103,
};
people.add_active_user(george);

const frontend = {
    subscribed: false,
    color: "yellow",
    name: "frontend",
    stream_id: 1,
    is_muted: true,
    invite_only: false,
};

stream_data.add_sub(frontend);

const frontend_filter_terms = [{operator: "stream", operand: "frontend"}];

const frontend_filter = new Filter(frontend_filter_terms);

run_test("update_property", (override) => {
    // Invoke error for non-existent stream/property
    {
        let errors = 0;
        override("blueslip.warn", () => {
            errors += 1;
        });

        stream_events.update_property(99, "color", "blue");
        assert.equal(errors, 1);

        stream_events.update_property(1, "not_real", 42);
        assert.equal(errors, 2);
    }

    // Test update color
    {
        global.with_stub((stub) => {
            override("stream_color.update_stream_color", stub.f);
            stream_events.update_property(1, "color", "blue");
            const args = stub.get_args("sub", "val");
            assert.equal(args.sub.stream_id, 1);
            assert.equal(args.val, "blue");
        });
    }

    // Test in home view
    {
        global.with_stub((stub) => {
            override("stream_muting.update_is_muted", stub.f);
            stream_events.update_property(1, "in_home_view", false);
            const args = stub.get_args("sub", "val");
            assert.equal(args.sub.stream_id, 1);
            assert.equal(args.val, true);
        });
    }

    // Test desktop notifications
    stream_events.update_property(1, "desktop_notifications", true);
    assert.equal(frontend.desktop_notifications, true);
    let checkbox = $("#desktop_notifications_1");
    assert.equal(checkbox.prop("checked"), true);

    // Tests audible notifications
    stream_events.update_property(1, "audible_notifications", true);
    assert.equal(frontend.audible_notifications, true);
    checkbox = $("#audible_notifications_1");
    assert.equal(checkbox.prop("checked"), true);

    // Tests push notifications
    stream_events.update_property(1, "push_notifications", true);
    assert.equal(frontend.push_notifications, true);
    checkbox = $("#push_notifications_1");
    assert.equal(checkbox.prop("checked"), true);

    // Tests email notifications
    stream_events.update_property(1, "email_notifications", true);
    assert.equal(frontend.email_notifications, true);
    checkbox = $("#email_notifications_1");
    assert.equal(checkbox.prop("checked"), true);

    // Tests wildcard_mentions_notify notifications
    stream_events.update_property(1, "wildcard_mentions_notify", true);
    assert.equal(frontend.wildcard_mentions_notify, true);
    checkbox = $("#wildcard_mentions_notify_1");
    assert.equal(checkbox.prop("checked"), true);

    // Test name change
    {
        global.with_stub((stub) => {
            override("subs.update_stream_name", stub.f);
            stream_events.update_property(1, "name", "the frontend");
            const args = stub.get_args("sub", "val");
            assert.equal(args.sub.stream_id, 1);
            assert.equal(args.val, "the frontend");
        });
    }

    // Test description change
    {
        global.with_stub((stub) => {
            override("subs.update_stream_description", stub.f);
            stream_events.update_property(1, "description", "we write code", {
                rendered_description: "we write code",
            });
            const args = stub.get_args("sub", "val");
            assert.equal(args.sub.stream_id, 1);
            assert.equal(args.val, "we write code");
        });
    }

    // Test email address change
    stream_events.update_property(1, "email_address", "zooly@zulip.com");
    assert.equal(frontend.email_address, "zooly@zulip.com");

    // Test pin to top
    {
        override("stream_list.refresh_pinned_or_unpinned_stream", noop);
        stream_events.update_property(1, "pin_to_top", true);
        checkbox = $("#pin_to_top_1");
        assert.equal(checkbox.prop("checked"), true);
    }

    // Test stream privacy change event
    {
        global.with_stub((stub) => {
            override("subs.update_stream_privacy", stub.f);
            stream_events.update_property(1, "invite_only", true, {
                history_public_to_subscribers: true,
            });
            const args = stub.get_args("sub", "val");
            assert.equal(args.sub.stream_id, 1);
            assert.deepEqual(args.val, {
                invite_only: true,
                history_public_to_subscribers: true,
            });
        });
    }

    // Test stream stream_post_policy change event
    {
        global.with_stub((stub) => {
            override("subs.update_stream_post_policy", stub.f);
            stream_events.update_property(
                1,
                "stream_post_policy",
                stream_data.stream_post_policy_values.admins.code,
            );
            const args = stub.get_args("sub", "val");
            assert.equal(args.sub.stream_id, 1);
            assert.equal(args.val, stream_data.stream_post_policy_values.admins.code);
        });
    }

    // Test stream message_retention_days change event
    {
        global.with_stub((stub) => {
            override("subs.update_message_retention_setting", stub.f);
            stream_events.update_property(1, "message_retention_days", 20);
            const args = stub.get_args("sub", "val");
            assert.equal(args.sub.stream_id, 1);
            assert.equal(args.val, 20);
        });
    }
});

run_test("marked_subscribed", (override) => {
    override("stream_data.subscribe_myself", noop);
    override("stream_data.set_subscribers", noop);
    override("stream_data.update_calculated_fields", noop);

    // Test undefined error
    {
        let errors = 0;
        override("blueslip.error", () => {
            errors += 1;
        });
        stream_events.mark_subscribed(undefined, [], "yellow");
        assert.equal(errors, 1);
    }

    // Test early return if subscribed
    {
        let completed = false;
        override("message_util.do_unread_count_updates", () => {
            completed = true; // This gets run if we continue and don't early return
        });
        const subscribed = {subscribed: true};
        stream_events.mark_subscribed(subscribed, [], "yellow");
        assert.equal(completed, false);

        // prevent warning about spurious override
        message_util.do_unread_count_updates();
    }

    set_global("message_list", {
        all: {
            all_messages() {
                return ["msg"];
            },
        },
    });

    set_global("subs", {update_settings_for_subscribed: noop});
    set_global("overlays", {streams_open: return_true});

    // Test basic dispatching and updating stream color
    narrow_state.set_current_filter(frontend_filter);
    {
        let args;
        let list_updated = false;

        const stream_list_stub = global.make_stub();
        const message_view_header_stub = global.make_stub();
        const message_util_stub = global.make_stub();

        override("stream_color.update_stream_color", noop);
        override("stream_list.add_sidebar_row", stream_list_stub.f);
        override("message_util.do_unread_count_updates", message_util_stub.f);
        override("message_view_header.render_title_area", message_view_header_stub.f);
        override("current_msg_list.update_trailing_bookend", () => {
            list_updated = true;
        });

        stream_events.mark_subscribed(frontend, [], "blue");

        args = message_util_stub.get_args("messages");
        assert.deepEqual(args.messages, ["msg"]);

        args = stream_list_stub.get_args("sub");
        assert.equal(args.sub.stream_id, 1);
        assert.equal(message_view_header_stub.num_calls, 1);

        assert.equal(list_updated, true);

        assert.equal(frontend.color, "blue");
    }
    narrow_state.reset_current_filter();

    // Test assigning generated color
    {
        frontend.color = undefined;
        override("color_data.pick_color", () => "green");
        let warnings = 0;
        override("blueslip.warn", () => {
            warnings += 1;
        });

        // narrow state is undefined
        global.with_stub((stub) => {
            override("message_util.do_unread_count_updates", noop);
            override("stream_list.add_sidebar_row", noop);
            override("subs.set_color", stub.f);
            stream_events.mark_subscribed(frontend, [], undefined);
            const args = stub.get_args("id", "color");
            assert.equal(args.id, 1);
            assert.equal(args.color, "green");
            assert.equal(warnings, 1);
        });
    }

    // Test assigning subscriber emails
    // narrow state is undefined
    {
        override("stream_color.update_stream_color", noop);
        override("message_util.do_unread_count_updates", noop);
        override("stream_list.add_sidebar_row", noop);

        global.with_stub((stub) => {
            override("stream_data.set_subscribers", stub.f);
            const user_ids = [15, 20, 25];
            stream_events.mark_subscribed(frontend, user_ids, "");
            const args = stub.get_args("sub", "subscribers");
            assert.deepEqual(frontend, args.sub);
            assert.deepEqual(user_ids, args.subscribers);
        });

        // assign self as well
        global.with_stub((stub) => {
            override("stream_data.subscribe_myself", stub.f);
            stream_events.mark_subscribed(frontend, [], "");
            const args = stub.get_args("sub");
            assert.deepEqual(frontend, args.sub);
        });

        // and finally update subscriber settings
        global.with_stub((stub) => {
            override("subs.update_settings_for_subscribed", stub.f);
            stream_events.mark_subscribed(frontend, [], "");
            const args = stub.get_args("sub");
            assert.deepEqual(frontend, args.sub);
        });
    }
});

run_test("mark_unsubscribed", (override) => {
    override("stream_data.update_calculated_fields", noop);

    {
        let removed_sub = false;
        override("stream_list.remove_sidebar_row", () => {
            removed_sub = true;
        });

        // take no action if no sub specified
        stream_events.mark_unsubscribed();
        assert.equal(removed_sub, false);

        // take no action if already unsubscribed
        frontend.subscribed = false;
        stream_events.mark_unsubscribed(frontend);
        assert.equal(removed_sub, false);

        // prevent warning about spurious mock
        stream_list.remove_sidebar_row();
    }

    // Test unsubscribe
    frontend.subscribed = true;
    {
        global.with_stub((stub) => {
            override("stream_data.unsubscribe_myself", stub.f);
            override("subs.update_settings_for_unsubscribed", noop);
            override("stream_list.remove_sidebar_row", noop);
            stream_events.mark_unsubscribed(frontend);
            const args = stub.get_args("sub");
            assert.deepEqual(args.sub, frontend);
        });
    }

    // Test update settings after unsubscribe
    {
        global.with_stub((stub) => {
            override("subs.update_settings_for_unsubscribed", stub.f);
            override("stream_data.unsubscribe_myself", noop);
            override("stream_list.remove_sidebar_row", noop);
            stream_events.mark_unsubscribed(frontend);
            const args = stub.get_args("sub");
            assert.deepEqual(args.sub, frontend);
        });
    }

    // Test update bookend and remove done event
    narrow_state.set_current_filter(frontend_filter);
    {
        const message_view_header_stub = global.make_stub();
        override("message_view_header.render_title_area", message_view_header_stub.f);
        override("stream_data.unsubscribe_myself", noop);
        override("subs.update_settings_for_unsubscribed", noop);

        let updated = false;
        override("current_msg_list.update_trailing_bookend", () => {
            updated = true;
        });

        let event_triggered = false;
        override("stream_list.remove_sidebar_row", (stream_id) => {
            assert.equal(stream_id, frontend.stream_id);
            event_triggered = true;
        });

        stream_events.mark_unsubscribed(frontend);

        assert.equal(message_view_header_stub.num_calls, 1);
        assert.equal(updated, true);
        assert.equal(event_triggered, true);
    }
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
    const subs_stub = global.make_stub();
    subs.update_subscribers_ui = subs_stub.f;

    dev_help.can_access_subscribers = true;

    // verify that deactivating user should unsubscribe user from all streams
    assert(stream_data.add_subscriber(dev_help.stream_id, george.user_id));
    assert(dev_help.subscribers.has(george.user_id));

    stream_events.remove_deactivated_user_from_all_streams(george.user_id);

    // verify that we issue a call to update subscriber count/list UI
    assert.equal(subs_stub.num_calls, 1);
});
