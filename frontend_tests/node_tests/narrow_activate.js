"use strict";

const {strict: assert} = require("assert");

const {rewiremock, set_global, use} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

rewiremock("../../static/js/resize").with({
    resize_stream_filters_container: () => {},
});

const channel = rewiremock("../../static/js/channel").with({});
const compose = rewiremock("../../static/js/compose").with({});
const compose_actions = rewiremock("../../static/js/compose_actions").with({});
set_global("current_msg_list", {});
const hashchange = rewiremock("../../static/js/hashchange").with({});
set_global("home_msg_list", {});
const message_fetch = rewiremock("../../static/js/message_fetch").with({});
const message_list = rewiremock("../../static/js/message_list").with({
    set_narrowed(value) {
        message_list.narrowed = value;
    },
});
const message_scroll = rewiremock("../../static/js/message_scroll").with({});
const notifications = rewiremock("../../static/js/notifications").with({});
set_global("page_params", {});
const search = rewiremock("../../static/js/search").with({});
const stream_list = rewiremock("../../static/js/stream_list").with({});
const message_view_header = rewiremock("../../static/js/message_view_header").with({});
const top_left_corner = rewiremock("../../static/js/top_left_corner").with({});
const typing_events = rewiremock("../../static/js/typing_events").with({});
const ui_util = rewiremock("../../static/js/ui_util").with({});
const unread_ops = rewiremock("../../static/js/unread_ops").with({});
rewiremock("../../static/js/recent_topics").with({
    hide: () => {},
    is_visible: () => {},
});

//
// We have strange hacks in narrow.activate to sleep 0
// seconds.
set_global("setTimeout", (f, t) => {
    assert.equal(t, 0);
    f();
});

rewiremock("../../static/js/muting").with({
    is_topic_muted: () => false,
});

const {narrow, narrow_state, stream_data, util} = use(
    "fold_dict",
    "util",
    "stream_data",
    "filter",
    "fetch_status",
    "message_list_data",
    "narrow_state",
    "unread",
    "narrow",
);

const denmark = {
    subscribed: false,
    color: "blue",
    name: "Denmark",
    stream_id: 1,
    is_muted: true,
};
stream_data.add_sub(denmark);

function test_helper(override) {
    let events = [];

    function stub(module, func_name) {
        override(module, func_name, () => {
            events.push([module, func_name]);
        });
    }

    stub(compose_actions, "on_narrow");
    stub(hashchange, "save_narrow");
    stub(message_scroll, "hide_indicators");
    stub(message_scroll, "hide_top_of_narrow_notices");
    stub(notifications, "clear_compose_notifications");
    stub(notifications, "redraw_title");
    stub(search, "update_button_visibility");
    stub(stream_list, "handle_narrow_activated");
    stub(message_view_header, "initialize");
    stub(top_left_corner, "handle_narrow_activated");
    stub(typing_events, "render_notifications_for_narrow");
    stub(ui_util, "change_tab_to");
    stub(unread_ops, "process_visible");
    stub(compose, "update_closed_compose_buttons_for_stream");
    stub(compose, "update_closed_compose_buttons_for_private");

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
        this.data = opts.data;
        this.view = {
            set_message_offset(offset) {
                this.offset = offset;
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

run_test("basics", (override) => {
    stub_message_list();

    const helper = test_helper(override);
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
        [notifications, "clear_compose_notifications"],
        [notifications, "redraw_title"],
        [message_scroll, "hide_top_of_narrow_notices"],
        [message_scroll, "hide_indicators"],
        [ui_util, "change_tab_to"],
        [unread_ops, "process_visible"],
        [hashchange, "save_narrow"],
        [compose, "update_closed_compose_buttons_for_stream"],
        [search, "update_button_visibility"],
        [compose_actions, "on_narrow"],
        [top_left_corner, "handle_narrow_activated"],
        [stream_list, "handle_narrow_activated"],
        [typing_events, "render_notifications_for_narrow"],
        [message_view_header, "initialize"],
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
