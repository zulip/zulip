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
let is_event_handled;
let is_widget_activated;
let is_widget_rendered;

const fake_poll_widget = {
    activate(data) {
        is_widget_activated = true;
        const inbound_events_handler = (e) => {
            is_event_handled = true;
            assert.deepStrictEqual(e, events);
        };
        const widget_data = {
            widget_type: "poll",
            extra_data: data.any_data.extra_data,
        };
        return {inbound_events_handler, widget_data};
    },
    render(data) {
        is_widget_rendered = true;
        $widget_elem = data.$elem;
        assert.ok($widget_elem.hasClass("widget-content"));
        data.callback("test_data");
    },
};

const message_lists = mock_esm("../src/message_lists", {current: {id: 2}, home: {id: 1}});
mock_esm("../src/poll_widget", fake_poll_widget);

set_global("document", "document-stub");

const {GenericWidget} = zrequire("generic_widget");
const widgetize = zrequire("widgetize");
const widgets = zrequire("widgets");

widgets.initialize();

function test(label, f) {
    run_test(label, ({override}) => {
        events = [...sample_events];
        $widget_elem = undefined;
        is_event_handled = false;
        is_widget_activated = false;
        is_widget_rendered = false;
        widgetize.clear_for_testing();
        f({override});
    });
}

test("activate", ({override}) => {
    // Both widgetize.render and widgetize.handle_event are tested
    // here to use the "caching" of widgets.
    const $row = $.create("<stub message row>");
    $row.length = 1;
    $row.attr("id", `message-row-${message_lists.current.id}-2909`);
    const $message_content = $.create(`#message-row-${message_lists.current.id}-2909`);
    $row.set_find_results(".message_content", $message_content);

    const $widget_content = $.create(".widget-content");
    $widget_content.addClass("widget-content");
    $row.set_find_results(".widget-content", $widget_content);

    let is_widget_elem_inserted = false;
    let $inserted_elem;

    $message_content.append = ($elem) => {
        is_widget_elem_inserted = true;
        $inserted_elem = $elem;
        assert.ok($elem.hasClass("widget-content"));
    };

    const activate_opts = {
        events: [...events],
        any_data: {
            widget_type: "poll",
            extra_data: "",
        },
        message: {
            id: 2001,
        },
    };

    // Test widget initialization

    is_widget_elem_inserted = false;
    is_widget_activated = false;
    is_widget_rendered = false;
    assert.deepEqual(widgetize.get_message_ids(), []);

    widgetize.activate(activate_opts);

    // activate() should create widget and handle events, but NOT render
    assert.ok(is_widget_activated);
    assert.ok(!is_widget_rendered);
    assert.ok(!is_widget_elem_inserted);
    assert.deepEqual(widgetize.get_message_ids(), [activate_opts.message.id]);

    // Activate with invalid widget type
    blueslip.expect("warn", "unknown widget_type");
    is_widget_activated = false;
    activate_opts.any_data.widget_type = "invalid_widget";
    activate_opts.message.id = 2002;

    widgetize.activate(activate_opts);

    assert.ok(!is_widget_activated);
    assert.deepEqual(blueslip.get_test_logs("warn")[0].more_info, {widget_type: "invalid_widget"});

    // Activate with tictactoe (legacy widget) should silently fail
    is_widget_activated = false;
    activate_opts.any_data.widget_type = "tictactoe";
    activate_opts.message.id = 2003;

    widgetize.activate(activate_opts);

    assert.ok(!is_widget_activated);

    // Test widget UI rendering

    widgetize.clear_for_testing();
    is_widget_elem_inserted = false;
    is_widget_activated = false;
    is_widget_rendered = false;
    events = [...sample_events];
    activate_opts.any_data.widget_type = "poll";
    activate_opts.events = [...events];
    activate_opts.message.id = 2005;

    widgetize.activate(activate_opts);

    assert.ok(is_widget_activated);
    assert.ok(!is_widget_rendered);
    assert.ok(!is_widget_elem_inserted);

    const render_opts = {
        post_to_server(data) {
            assert.equal(data.msg_type, "widget");
            assert.equal(data.data, "test_data");
        },
        $row,
        message: {
            id: 2005,
        },
    };

    widgetize.render(render_opts);

    assert.ok(is_widget_rendered);
    assert.ok(is_widget_elem_inserted);
    assert.equal($inserted_elem, $widget_elem);

    // Test render without a widget should return early
    is_widget_rendered = false;
    is_widget_elem_inserted = false;
    render_opts.message.id = 9999;

    widgetize.render(render_opts);

    assert.ok(!is_widget_rendered);
    assert.ok(!is_widget_elem_inserted);

    // Test incoming widget events

    const $empty_row = $.create("<empty row>");
    $empty_row.length = 0;

    let expected_message_id;

    const post_activate_event = {
        data: {
            idx: 1,
            type: "new_option",
        },
        message: {
            id: 2001,
        },
        post_to_server(data) {
            assert.equal(data.msg_type, "widget");
            assert.equal(data.data, "test_data");
        },
        sender_id: 102,
    };
    const handle_events = (e) => {
        is_event_handled = true;
        assert.deepEqual(e, [post_activate_event]);
    };

    // handle_event on message not in view should only update the state
    message_lists.current = undefined;

    is_event_handled = false;
    is_widget_rendered = false;
    expected_message_id = 2001;

    const widget_data = {widget_type: "poll", extra_data: ""};
    widgetize.set_widget_for_tests(2001, new GenericWidget(handle_events, widget_data));

    widgetize.handle_event(post_activate_event);

    assert.ok(is_event_handled);
    assert.ok(!is_widget_rendered);

    message_lists.current = {id: 2};

    override(message_lists.current, "get_row", (idx) => {
        assert.equal(idx, expected_message_id);
        if (idx === 2001) {
            return $row;
        }

        return $empty_row;
    });

    // Test handle_event for ui update
    widgetize.set_widget_for_tests(2001, new GenericWidget(handle_events, widget_data));

    is_event_handled = false;
    is_widget_rendered = false;
    expected_message_id = 2001;

    widgetize.handle_event(post_activate_event);

    assert.ok(is_event_handled);
    assert.ok(is_widget_rendered);

    // Test handle_event for nonexistent widget
    is_event_handled = false;
    is_widget_rendered = false;
    expected_message_id = 1000;

    const nonexistent_event = {
        data: {
            idx: 1,
            type: "new_option",
        },
        sender_id: 102,
        post_to_server() {},
        message: {
            id: 1000,
        },
    };

    widgetize.handle_event(nonexistent_event);

    assert.ok(!is_event_handled);
    assert.ok(!is_widget_rendered);
});
