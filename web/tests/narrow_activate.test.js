"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

mock_esm("../src/resize", {
    resize_stream_filters_container() {},
});

const all_messages_data = mock_esm("../src/all_messages_data");
const channel = mock_esm("../src/channel");
const compose_actions = mock_esm("../src/compose_actions");
const compose_banner = mock_esm("../src/compose_banner");
const compose_closed_ui = mock_esm("../src/compose_closed_ui");
const hashchange = mock_esm("../src/hashchange");
const message_fetch = mock_esm("../src/message_fetch");
const message_list = mock_esm("../src/message_list");
const message_lists = mock_esm("../src/message_lists", {
    home: {},
    current: {},
    set_current(msg_list) {
        message_lists.current = msg_list;
    },
});
const message_scroll = mock_esm("../src/message_scroll");
const message_view_header = mock_esm("../src/message_view_header");
const notifications = mock_esm("../src/notifications");
const search = mock_esm("../src/search");
const stream_list = mock_esm("../src/stream_list");
const top_left_corner = mock_esm("../src/top_left_corner");
const typing_events = mock_esm("../src/typing_events");
const unread_ops = mock_esm("../src/unread_ops");
mock_esm("../src/recent_topics_util", {
    is_visible() {},
});
mock_esm("../src/pm_list", {
    handle_narrow_activated() {},
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

const util = zrequire("util");
const narrow_state = zrequire("narrow_state");
const stream_data = zrequire("stream_data");
const narrow = zrequire("narrow");

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

    function stub(module, func_name) {
        module[func_name] = () => {
            events.push([module, func_name]);
        };
    }

    stub(compose_banner, "clear_message_sent_banners");
    stub(compose_actions, "on_narrow");
    stub(compose_closed_ui, "update_reply_recipient_label");
    stub(hashchange, "save_narrow");
    stub(message_scroll, "hide_indicators");
    stub(message_scroll, "show_loading_older");
    stub(message_scroll, "hide_top_of_narrow_notices");
    stub(notifications, "redraw_title");
    stub(search, "update_button_visibility");
    stub(stream_list, "handle_narrow_activated");
    stub(message_view_header, "initialize");
    stub(top_left_corner, "handle_narrow_activated");
    stub(typing_events, "render_notifications_for_narrow");
    stub(compose_actions, "update_narrow_to_recipient_visibility");
    stub(unread_ops, "process_visible");
    stub(compose_closed_ui, "update_buttons_for_stream");
    stub(compose_closed_ui, "update_buttons_for_private");
    // We don't test the css calls; we just skip over them.
    $("#mark_as_read_turned_off_banner").toggleClass = () => {};

    return {
        clear() {
            events = [];
        },
        push_event(event) {
            events.push(event);
        },
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
        };

        get(msg_id) {
            return this.data.get(msg_id);
        }

        empty() {
            return this.data.empty();
        }

        select_id(msg_id) {
            this.selected_id = msg_id;
        }
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

    message_lists.current.selected_id = () => -1;
    message_lists.current.get_row = () => row;

    all_messages_data.all_messages_data = {
        all_messages: () => messages,
        empty: () => false,
        first: () => ({id: 900}),
        last: () => ({id: 1100}),
    };

    let cont;

    message_fetch.load_messages_for_narrow = (opts) => {
        // Only validates the anchor and set of fields
        cont = opts.cont;

        assert.deepEqual(opts, {
            cont: opts.cont,
            msg_list: opts.msg_list,
            anchor: 1000,
        });
    };

    narrow.activate(terms, {
        then_select_id: selected_id,
    });

    assert.equal(message_lists.current.selected_id, selected_id);
    assert.equal(message_lists.current.view.offset, 25);
    assert.equal(narrow_state.narrowed_to_pms(), false);

    helper.assert_events([
        [message_scroll, "hide_top_of_narrow_notices"],
        [message_scroll, "hide_indicators"],
        [compose_banner, "clear_message_sent_banners"],
        [notifications, "redraw_title"],
        [unread_ops, "process_visible"],
        [hashchange, "save_narrow"],
        [compose_closed_ui, "update_buttons_for_stream"],
        [compose_closed_ui, "update_reply_recipient_label"],
        [search, "update_button_visibility"],
        [compose_actions, "on_narrow"],
        [top_left_corner, "handle_narrow_activated"],
        [stream_list, "handle_narrow_activated"],
        [typing_events, "render_notifications_for_narrow"],
        [message_view_header, "initialize"],
        [compose_actions, "update_narrow_to_recipient_visibility"],
    ]);

    message_lists.current.selected_id = () => -1;
    message_lists.current.get_row = () => row;
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
