"use strict";

const util = zrequire("util");
set_global("$", global.make_zjquery());

zrequire("narrow_state");
set_global("resize", {
    resize_stream_filters_container: () => {},
});
zrequire("stream_data");
zrequire("Filter", "js/filter");
zrequire("FetchStatus", "js/fetch_status");
zrequire("MessageListData", "js/message_list_data");
zrequire("unread");
zrequire("narrow");
zrequire("search_pill");

set_global("channel", {});
set_global("compose", {});
set_global("compose_actions", {});
set_global("current_msg_list", {});
set_global("hashchange", {});
set_global("home_msg_list", {});
set_global("message_fetch", {});
set_global("message_list", {
    set_narrowed(value) {
        this.narrowed = value;
    },
});
set_global("message_scroll", {});
set_global("message_util", {});
set_global("notifications", {});
set_global("page_params", {});
set_global("search", {});
set_global("stream_list", {});
set_global("message_view_header", {});
set_global("top_left_corner", {});
set_global("typing_events", {});
set_global("ui_util", {});
set_global("unread_ops", {});
set_global("search_pill_widget", {
    widget: {
        clear() {
            return true;
        },
        appendValue() {
            return true;
        },
    },
});
set_global("recent_topics", {
    hide: () => {},
    is_visible: () => {},
});

//
// We have strange hacks in narrow.activate to sleep 0
// seconds.
global.patch_builtin("setTimeout", (f, t) => {
    assert.equal(t, 0);
    f();
});

set_global("muting", {
    is_topic_muted: () => false,
});

const denmark = {
    subscribed: false,
    color: "blue",
    name: "Denmark",
    stream_id: 1,
    is_muted: true,
};
stream_data.add_sub(denmark);

function test_helper() {
    let events = [];

    function stub(module_name, func_name) {
        global[module_name][func_name] = () => {
            events.push(module_name + "." + func_name);
        };
    }

    stub("compose_actions", "on_narrow");
    stub("hashchange", "save_narrow");
    stub("message_scroll", "hide_indicators");
    stub("message_scroll", "show_loading_older");
    stub("message_scroll", "hide_top_of_narrow_notices");
    stub("notifications", "clear_compose_notifications");
    stub("notifications", "redraw_title");
    stub("search", "update_button_visibility");
    stub("stream_list", "handle_narrow_activated");
    stub("message_view_header", "initialize");
    stub("top_left_corner", "handle_narrow_activated");
    stub("typing_events", "render_notifications_for_narrow");
    stub("ui_util", "change_tab_to");
    stub("unread_ops", "process_visible");
    stub("compose", "update_closed_compose_buttons_for_stream");
    stub("compose", "update_closed_compose_buttons_for_private");

    return {
        clear: () => {
            events = [];
        },
        push_event: (event) => {
            events.push(event);
        },
        assert_events: (expected_events) => {
            assert.deepEqual(expected_events, events);
        },
    };
}

function stub_message_list() {
    message_list.MessageList = function (opts) {
        const list = this;
        this.data = opts.data;
        this.view = {
            set_message_offset(offset) {
                list.view.offset = offset;
            },
        };

        return this;
    };

    message_list.MessageList.prototype = {
        get(msg_id) {
            return this.data.get(msg_id);
        },

        empty() {
            return this.data.empty();
        },

        select_id(msg_id) {
            this.selected_id = msg_id;
        },
    };
}

run_test("basics", () => {
    stub_message_list();

    const helper = test_helper();
    const terms = [{operator: "stream", operand: "Denmark"}];

    const selected_id = 1000;

    const selected_message = {
        id: selected_id,
        type: "stream",
        stream_id: denmark.stream_id,
        topic: "whatever",
    };

    const messages = [selected_message];

    const row = {
        length: 1,
        offset: () => ({top: 25}),
    };

    current_msg_list.selected_id = () => -1;
    current_msg_list.get_row = () => row;

    message_list.all = {
        all_messages: () => messages,
        get: (msg_id) => {
            assert.equal(msg_id, selected_id);
            return selected_message;
        },
        data: {
            fetch_status: {
                has_found_newest: () => true,
            },
        },
        empty: () => false,
        first: () => ({id: 900}),
        last: () => ({id: 1100}),
    };

    let cont;

    message_fetch.load_messages_for_narrow = (opts) => {
        cont = opts.cont;

        assert.deepEqual(opts, {
            cont: opts.cont,
            anchor: 1000,
        });
    };

    narrow.activate(terms, {
        then_select_id: selected_id,
    });

    assert.equal(message_list.narrowed.selected_id, selected_id);
    assert.equal(message_list.narrowed.view.offset, 25);
    assert.equal(narrow_state.narrowed_to_pms(), false);

    helper.assert_events([
        "notifications.clear_compose_notifications",
        "notifications.redraw_title",
        "message_scroll.hide_top_of_narrow_notices",
        "message_scroll.hide_indicators",
        "ui_util.change_tab_to",
        "unread_ops.process_visible",
        "hashchange.save_narrow",
        "compose.update_closed_compose_buttons_for_stream",
        "search.update_button_visibility",
        "compose_actions.on_narrow",
        "top_left_corner.handle_narrow_activated",
        "stream_list.handle_narrow_activated",
        "typing_events.render_notifications_for_narrow",
        "message_view_header.initialize",
    ]);

    current_msg_list.selected_id = () => -1;
    current_msg_list.get_row = () => row;
    util.sorted_ids = () => [];

    narrow.activate([{operator: "is", operand: "private"}], {
        then_select_id: selected_id,
    });

    assert.equal(narrow_state.narrowed_to_pms(), true);

    channel.post = (opts) => {
        assert.equal(opts.url, "/json/report/narrow_times");
        helper.push_event("report narrow times");
    };

    helper.clear();
    cont();
    helper.assert_events(["report narrow times"]);
});
