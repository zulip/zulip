"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const $ = require("./lib/zjquery");

mock_esm("../src/resize", {
    resize_stream_filters_container() {},
});
const {Filter} = zrequire("../src/filter");
const all_messages_data = mock_esm("../src/all_messages_data");
const browser_history = mock_esm("../src/browser_history", {
    state: {changing_hash: false},
});
const compose_actions = mock_esm("../src/compose_actions");
const compose_banner = mock_esm("../src/compose_banner");
const compose_closed_ui = mock_esm("../src/compose_closed_ui");
const compose_recipient = mock_esm("../src/compose_recipient");
const message_fetch = mock_esm("../src/message_fetch");
const message_list = mock_esm("../src/message_list");
const message_lists = mock_esm("../src/message_lists", {
    current: {
        view: {
            $list: {
                remove: noop,
                removeClass: noop,
                addClass: noop,
            },
        },
        data: {
            filter: new Filter([{operator: "in", operand: "all"}]),
        },
    },
    update_current_message_list(msg_list) {
        message_lists.current = msg_list;
    },
    all_rendered_message_lists() {
        return [message_lists.current];
    },
});
const message_feed_top_notices = mock_esm("../src/message_feed_top_notices");
const message_feed_loading = mock_esm("../src/message_feed_loading");
const message_view_header = mock_esm("../src/message_view_header");
const message_viewport = mock_esm("../src/message_viewport");
const narrow_history = mock_esm("../src/narrow_history");
const narrow_title = mock_esm("../src/narrow_title");
const stream_list = mock_esm("../src/stream_list");
const left_sidebar_navigation_area = mock_esm("../src/left_sidebar_navigation_area");
const typing_events = mock_esm("../src/typing_events");
const unread_ops = mock_esm("../src/unread_ops");
mock_esm("../src/pm_list", {
    handle_narrow_activated() {},
});
mock_esm("../src/unread_ui", {
    reset_unread_banner() {},
    update_unread_banner() {},
});

//
// We have strange hacks in narrow.activate to sleep 0
// seconds.
set_global("setTimeout", (f, t) => {
    assert.equal(t, 0);
    f();
});

mock_esm("../src/user_topics", {
    is_topic_muted: () => false,
});

const {buddy_list} = zrequire("buddy_list");
const activity_ui = zrequire("activity_ui");
const narrow_state = zrequire("narrow_state");
const stream_data = zrequire("stream_data");
const narrow = zrequire("narrow");
const people = zrequire("people");

const denmark = {
    subscribed: false,
    color: "blue",
    name: "Denmark",
    stream_id: 1,
    is_muted: true,
};
stream_data.add_sub(denmark);

function test_helper({override}) {
    const events = [];

    function stub(module, func_name) {
        override(module, func_name, () => {
            events.push([module, func_name]);
        });
    }

    stub(browser_history, "set_hash");
    stub(compose_banner, "clear_message_sent_banners");
    stub(compose_actions, "on_narrow");
    stub(compose_closed_ui, "update_reply_recipient_label");
    stub(compose_recipient, "handle_middle_pane_transition");
    stub(narrow_history, "save_narrow_state_and_flush");
    stub(message_feed_loading, "hide_indicators");
    stub(message_feed_top_notices, "hide_top_of_narrow_notices");
    stub(narrow_title, "update_narrow_title");
    stub(stream_list, "handle_narrow_activated");
    stub(message_view_header, "render_title_area");
    stub(message_viewport, "stop_auto_scrolling");
    stub(left_sidebar_navigation_area, "handle_narrow_activated");
    stub(typing_events, "render_notifications_for_narrow");
    stub(unread_ops, "process_visible");
    stub(compose_closed_ui, "update_buttons_for_stream_views");
    stub(compose_closed_ui, "update_buttons_for_private");
    // We don't test the css calls; we just skip over them.
    $("#mark_read_on_scroll_state_banner").toggleClass = noop;

    return {
        assert_events(expected_events) {
            assert.deepEqual(events, expected_events);
        },
    };
}

function stub_message_list() {
    message_list.MessageList = class MessageList {
        constructor(opts) {
            this.data = opts.data;
        }

        view = {
            set_message_offset(offset) {
                this.offset = offset;
            },

            $list: {
                remove: noop,
                removeClass: noop,
                addClass: noop,
            },
        };

        get(msg_id) {
            return this.data.get(msg_id);
        }

        visibly_empty() {
            return this.data.visibly_empty();
        }

        select_id(msg_id) {
            this.selected_id = msg_id;
        }
    };
}

run_test("basics", ({override}) => {
    stub_message_list();
    activity_ui.set_cursor_and_filter();

    const me = {
        email: "me@zulip.com",
        user_id: 999,
        full_name: "Me Myself",
    };
    people.add_active_user(me);
    people.initialize_current_user(me.user_id);
    override(buddy_list, "populate", noop);

    const helper = test_helper({override});
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
        get_offset_to_window: () => ({top: 25}),
    };

    message_lists.current.selected_id = () => -1;
    message_lists.current.get_row = () => row;

    all_messages_data.all_messages_data = {
        all_messages: () => messages,
        visibly_empty: () => false,
        first: () => ({id: 900}),
        last: () => ({id: 1100}),
    };

    $("#navbar-fixed-container").set_height(40);
    $("#compose").get_offset_to_window = () => ({top: 200});

    message_fetch.load_messages_for_narrow = (opts) => {
        // Only validates the anchor and set of fields
        assert.deepEqual(opts, {
            cont: opts.cont,
            msg_list: opts.msg_list,
            anchor: 1000,
        });

        opts.cont();
    };

    narrow.activate(terms, {
        then_select_id: selected_id,
    });

    assert.equal(message_lists.current.selected_id, selected_id);
    // 25 was the offset of the selected message but it is low for the
    // message top to be visible, so we use set offset to navbar height + header height.
    assert.equal(message_lists.current.view.offset, 80);
    assert.equal(narrow_state.narrowed_to_pms(), false);

    helper.assert_events([
        [message_feed_top_notices, "hide_top_of_narrow_notices"],
        [message_feed_loading, "hide_indicators"],
        [compose_banner, "clear_message_sent_banners"],
        [compose_actions, "on_narrow"],
        [unread_ops, "process_visible"],
        [narrow_history, "save_narrow_state_and_flush"],
        [message_viewport, "stop_auto_scrolling"],
        [browser_history, "set_hash"],
        [typing_events, "render_notifications_for_narrow"],
        [compose_closed_ui, "update_buttons_for_stream_views"],
        [compose_closed_ui, "update_reply_recipient_label"],
        [message_view_header, "render_title_area"],
        [narrow_title, "update_narrow_title"],
        [left_sidebar_navigation_area, "handle_narrow_activated"],
        [stream_list, "handle_narrow_activated"],
        [compose_recipient, "handle_middle_pane_transition"],
    ]);

    message_lists.current.selected_id = () => -1;
    message_lists.current.get_row = () => row;

    narrow.activate([{operator: "is", operand: "private"}], {
        then_select_id: selected_id,
    });

    assert.equal(narrow_state.narrowed_to_pms(), true);

    message_lists.current.selected_id = () => -1;
    // Row offset is between navbar and compose, so we keep it in the same position.
    row.get_offset_to_window = () => ({top: 100, bottom: 150});
    message_lists.current.get_row = () => row;

    narrow.activate(terms, {
        then_select_id: selected_id,
    });

    assert.equal(message_lists.current.view.offset, 100);

    message_lists.current.selected_id = () => -1;
    // Row is below navbar and row bottom is below compose but since the message is
    // visible enough, we don't scroll the message to a new position.
    row.get_offset_to_window = () => ({top: 150, bottom: 250});
    message_lists.current.get_row = () => row;

    narrow.activate(terms, {
        then_select_id: selected_id,
    });

    assert.equal(message_lists.current.view.offset, 150);
});
