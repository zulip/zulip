"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const $ = require("./lib/zjquery.cjs");

const sample_events = [
    {
        data: {
            option: "First option",
            idx: 1,
            type: "new_option",
        },
        sender_id: 101,
    },
    {
        data: {
            option: "Second option",
            idx: 1,
            type: "new_option",
        },
        sender_id: 102,
    },
    {
        data: {
            option: "Third option",
            idx: 1,
            type: "new_option",
        },
        sender_id: 102,
    },
];

let events;
let $widget_elem;
let handle_events;
let is_event_handled;
let is_widget_activated;

const fake_poll_widget = {
    activate(data) {
        is_widget_activated = true;
        $widget_elem = data.$elem;
        assert.ok($widget_elem.hasClass("widget-content"));
        handle_events = (e) => {
            is_event_handled = true;
            assert.deepStrictEqual(e, events);
        };
        data.callback("test_data");
        return handle_events;
    },
};

const message_lists = mock_esm("../src/message_lists", {current: {id: 2}, home: {id: 1}});
mock_esm("../src/poll_widget", fake_poll_widget);

set_global("document", "document-stub");

const widgetize = zrequire("widgetize");
const widgets = zrequire("widgets");

widgets.initialize();

function test(label, f) {
    run_test(label, ({override}) => {
        events = [...sample_events];
        $widget_elem = undefined;
        handle_events = undefined;
        is_event_handled = false;
        is_widget_activated = false;
        widgetize.clear_for_testing();
        f({override});
    });
}

test("activate", ({override}) => {
    // Both widgetize.activate and widgetize.handle_event are tested
    // here to use the "caching" of widget event handlers.
    const $row = $.create("<stub message row>");
    $row.length = 1;
    $row.attr("id", `message-row-${message_lists.current.id}-2909`);
    const $message_content = $.create(`#message-row-${message_lists.current.id}-2909`);
    $row.set_find_results(".message_content", $message_content);

    const opts = {
        events: [...events],
        extra_data: "",
        message: {
            id: 2001,
        },
        post_to_server(data) {
            assert.equal(data.msg_type, "widget");
            assert.equal(data.data, "test_data");
        },
        $row,
        widget_type: "poll",
    };

    let is_widget_elem_inserted;

    $message_content.append = ($elem) => {
        is_widget_elem_inserted = true;
        assert.equal($elem, $widget_elem);
        assert.ok($elem.hasClass("widget-content"));
    };

    is_widget_elem_inserted = false;
    is_widget_activated = false;
    is_event_handled = false;
    assert.ok(!widgetize.widget_event_handlers.has(opts.message.id));

    widgetize.activate(opts);

    assert.ok(is_widget_elem_inserted);
    assert.ok(is_widget_activated);
    assert.ok(is_event_handled);
    assert.equal(widgetize.widget_event_handlers.get(opts.message.id), handle_events);

    message_lists.current = undefined;
    is_widget_elem_inserted = false;
    is_widget_activated = false;
    is_event_handled = false;

    widgetize.activate(opts);

    assert.ok(!is_widget_elem_inserted);
    assert.ok(!is_widget_activated);
    assert.ok(!is_event_handled);

    blueslip.expect("warn", "unknown widget_type");
    is_widget_elem_inserted = false;
    is_widget_activated = false;
    is_event_handled = false;
    opts.widget_type = "invalid_widget";

    widgetize.activate(opts);
    assert.ok(!is_widget_elem_inserted);
    assert.ok(!is_widget_activated);
    assert.ok(!is_event_handled);
    assert.deepEqual(blueslip.get_test_logs("warn")[0].more_info, {widget_type: "invalid_widget"});

    opts.widget_type = "tictactoe";

    widgetize.activate(opts);
    assert.ok(!is_widget_elem_inserted);
    assert.ok(!is_widget_activated);
    assert.ok(!is_event_handled);

    /* Testing widgetize.handle_events */
    message_lists.current = {id: 2};
    const post_activate_event = {
        data: {
            idx: 1,
            type: "new_option",
        },
        message_id: 2001,
        sender_id: 102,
    };
    handle_events = (e) => {
        is_event_handled = true;
        assert.deepEqual(e, [post_activate_event]);
    };
    widgetize.widget_event_handlers.set(2001, handle_events);
    override(message_lists.current, "get_row", (idx) => {
        assert.equal(idx, 2001);
        return $row;
    });
    is_event_handled = false;
    widgetize.handle_event(post_activate_event);
    assert.ok(is_event_handled);

    is_event_handled = false;
    post_activate_event.message_id = 1000;
    widgetize.handle_event(post_activate_event);
    assert.ok(!is_event_handled);
});
