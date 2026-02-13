"use strict";

const assert = require("node:assert/strict");

const {$t} = require("./lib/i18n.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const $ = require("./lib/zjquery.cjs");

const filter_options = [
    {type: "topic_filter", label: "unresolved", syntax: "-is:resolved"},
    {type: "topic_filter", label: "resolved", syntax: "is:resolved"},
];

const bootstrap_typeahead = mock_esm("../src/bootstrap_typeahead");
const narrow_state = mock_esm("../src/narrow_state", {
    filter: () => ({}),
    stream_id: () => undefined,
});
const stream_data = mock_esm("../src/stream_data", {
    is_subscribed: () => false,
});
const topic_filter_pill = mock_esm("../src/topic_filter_pill", {
    filter_options,
    get_typeahead_base_options() {
        return {
            item_html(item) {
                return `rendered:${item.label}`;
            },
            matcher(item, query) {
                return (
                    query.includes(":") &&
                    (item.syntax.toLowerCase().startsWith(query.toLowerCase()) ||
                        (item.syntax.startsWith("-") &&
                            item.syntax.slice(1).toLowerCase().startsWith(query.toLowerCase())))
                );
            },
            sorter(items) {
                return items;
            },
            stopAdvance: true,
            dropup: true,
        };
    },
    create_pills() {
        throw new Error("create_pills should be overridden in tests");
    },
});

const stream_topic_history = mock_esm("../src/stream_topic_history", {
    stream_has_locally_available_resolved_topics: () => false,
});

const left_sidebar_filter = zrequire("left_sidebar_filter");
const default_placeholder = $t({defaultMessage: "Filter left sidebar"});

run_test("default_mock_functions", () => {
    assert.equal(narrow_state.stream_id(), undefined);
    assert.equal(stream_data.is_subscribed(), false);
    assert.equal(stream_topic_history.stream_has_locally_available_resolved_topics(), false);
});

run_test("mocked_create_pills_guard", () => {
    assert.throws(() => topic_filter_pill.create_pills());
});

run_test("get_topics_state_and_clear_without_updating", ({override_rewire}) => {
    override_rewire(left_sidebar_filter, "left_sidebar_filter_pill_widget", null);
    assert.equal(left_sidebar_filter.get_topics_state(), "");

    const pill_items = [{syntax: "is:resolved"}];
    let clear_called_with;
    const pill_widget = {
        items() {
            return pill_items;
        },
        clear(suppress) {
            clear_called_with = suppress;
            pill_items.length = 0;
        },
        appendValue: noop,
        onPillRemove: noop,
    };

    let empty_called = false;
    const $input = $("#left-sidebar-filter-query");
    $input.empty = () => {
        empty_called = true;
        $input.text("");
        return $input;
    };

    override_rewire(left_sidebar_filter, "left_sidebar_filter_pill_widget", pill_widget);
    assert.equal(left_sidebar_filter.get_topics_state(), "is:resolved");

    pill_items.push({syntax: "-is:resolved"});
    blueslip.expect("warn", "Multiple pills found in left sidebar filter input.");
    assert.equal(left_sidebar_filter.get_topics_state(), "is:resolved");

    left_sidebar_filter.clear_without_updating();
    assert.equal(clear_called_with, true);
    assert.ok(empty_called);
});

run_test("clear_left_sidebar_filter", ({override_rewire}) => {
    const $input = $("#left-sidebar-filter-query");
    const $pill_container = $("#left-sidebar-filter-input");

    let hide_called = false;
    override_rewire(left_sidebar_filter, "left_sidebar_filter_typeahead", {
        hide() {
            hide_called = true;
        },
    });

    let clear_called_with;
    const clear_pill_widget = {
        clear(suppress) {
            clear_called_with = suppress;
        },
        items() {
            return [];
        },
        appendValue: noop,
        onPillRemove: noop,
    };
    override_rewire(left_sidebar_filter, "left_sidebar_filter_pill_widget", clear_pill_widget);
    clear_pill_widget.items();

    let empty_called = false;
    $input.empty = () => {
        empty_called = true;
        $input.text("");
        return $input;
    };

    const input_events = [];
    $input.trigger = (event_name) => {
        input_events.push(event_name);
    };

    const container_events = [];
    $pill_container.trigger = (event_name) => {
        container_events.push(event_name);
    };

    let stop_called = false;
    const event = {
        stopPropagation() {
            stop_called = true;
        },
    };

    left_sidebar_filter.clear_left_sidebar_filter(event);
    assert.ok(stop_called);
    assert.ok(hide_called);
    assert.equal(clear_called_with, true);
    assert.ok(empty_called);
    assert.equal($input.attr("data-placeholder"), default_placeholder);
    assert.deepEqual(container_events, ["input"]);
    assert.deepEqual(input_events, ["blur"]);
});

run_test(
    "setup_left_sidebar_filter_typeahead_returns_if_missing",
    ({disallow, override_rewire}) => {
        const $input = $("#left-sidebar-filter-query");
        const $pill_container = $("#left-sidebar-filter-input");
        $input.length = 0;
        $pill_container.length = 1;

        let unlisten_called = false;
        override_rewire(left_sidebar_filter, "left_sidebar_filter_typeahead", {
            unlisten() {
                unlisten_called = true;
            },
        });
        const inactive_pill_widget = {
            items() {
                return [];
            },
        };
        override_rewire(
            left_sidebar_filter,
            "left_sidebar_filter_pill_widget",
            inactive_pill_widget,
        );
        inactive_pill_widget.items();

        disallow(topic_filter_pill, "create_pills");

        left_sidebar_filter.setup_left_sidebar_filter_typeahead();
        assert.ok(unlisten_called);
        assert.equal(left_sidebar_filter.left_sidebar_filter_typeahead, undefined);
        assert.equal(left_sidebar_filter.left_sidebar_filter_pill_widget, null);
    },
);

run_test("setup_left_sidebar_filter_typeahead", ({override, override_rewire}) => {
    const $input = $("#left-sidebar-filter-query");
    const $pill_container = $("#left-sidebar-filter-input");
    const $pill_selector = $("#left-sidebar-filter-input .pill");
    $pill_selector.length = 0;

    let has_resolved_topics = true;
    let narrowed_stream_id;
    let is_subscribed = true;
    override(narrow_state, "stream_id", () => narrowed_stream_id);
    override(stream_data, "is_subscribed", () => is_subscribed);
    override(
        stream_topic_history,
        "stream_has_locally_available_resolved_topics",
        () => has_resolved_topics,
    );

    let old_unlisten_called = false;
    override_rewire(left_sidebar_filter, "left_sidebar_filter_typeahead", {
        unlisten() {
            old_unlisten_called = true;
        },
    });

    const pill_items = [];
    let clear_called_with;
    let append_called_with;
    let on_pill_remove;
    let on_pill_create;
    let on_text_input;
    const pill_widget = {
        items() {
            return pill_items;
        },
        clear(suppress) {
            clear_called_with = suppress;
            pill_items.length = 0;
        },
        appendValue(syntax) {
            append_called_with = syntax;
            pill_items.push({syntax});
        },
        onPillCreate(callback) {
            on_pill_create = callback;
        },
        onPillRemove(callback) {
            on_pill_remove = callback;
        },
        onTextInputHook(callback) {
            on_text_input = callback;
        },
    };

    override(topic_filter_pill, "create_pills", ($container) => {
        assert.equal($container.selector, "#left-sidebar-filter-input");
        return pill_widget;
    });
    pill_widget.items();

    let captured_input;
    let captured_config;
    let created_typeahead;
    function FakeTypeahead(input_element, config) {
        captured_input = input_element;
        captured_config = config;
        created_typeahead = {
            hide: noop,
            unlisten: noop,
        };
        return created_typeahead;
    }
    override(bootstrap_typeahead, "Typeahead", FakeTypeahead);

    const input_events = [];
    $input.trigger = (event_name) => {
        input_events.push(event_name);
    };

    const container_events = [];
    $pill_container.trigger = (event_name) => {
        container_events.push(event_name);
    };

    $input.text("");
    left_sidebar_filter.setup_left_sidebar_filter_typeahead();

    const filter_placeholder = $t({defaultMessage: "Filter"});
    const default_placeholder = $t({defaultMessage: "Filter left sidebar"});
    assert.equal($input.attr("data-placeholder"), default_placeholder);

    $input.text("has-text");
    on_text_input();
    assert.equal($input.attr("data-placeholder"), "");

    $input.text("");
    pill_items.push({syntax: "is:resolved"});
    on_pill_create();
    assert.equal($input.attr("data-placeholder"), filter_placeholder);

    assert.ok(old_unlisten_called);
    assert.equal(left_sidebar_filter.left_sidebar_filter_pill_widget, pill_widget);
    assert.equal(left_sidebar_filter.left_sidebar_filter_typeahead, created_typeahead);
    assert.equal(captured_input.$element, $input);
    assert.equal(captured_input.type, "contenteditable");
    assert.equal(captured_config.dropup, true);
    assert.equal(captured_config.stopAdvance, true);

    narrowed_stream_id = 5;
    is_subscribed = false;
    assert.deepEqual(captured_config.source(), []);
    is_subscribed = true;
    has_resolved_topics = false;
    assert.deepEqual(captured_config.source(), []);
    has_resolved_topics = true;
    assert.deepEqual(captured_config.source(), filter_options);

    narrowed_stream_id = undefined;
    assert.deepEqual(captured_config.source(), []);

    narrowed_stream_id = 5;
    is_subscribed = true;
    has_resolved_topics = true;
    $pill_selector.length = 1;
    assert.deepEqual(captured_config.source(), []);
    $pill_selector.length = 0;

    assert.equal(captured_config.item_html(filter_options[0]), "rendered:unresolved");

    assert.ok(captured_config.matcher(filter_options[1], "is:"));
    assert.ok(captured_config.matcher(filter_options[0], "is:"));
    assert.ok(!captured_config.matcher(filter_options[0], "resolved"));

    const items = [filter_options[0], filter_options[1]];
    assert.equal(captured_config.sorter(items), items);

    $input.text("is:");
    const result = captured_config.updater(filter_options[1]);
    assert.equal(clear_called_with, true);
    assert.equal(append_called_with, "is:resolved");
    assert.equal($input.text(), "");
    assert.equal(result, "");
    assert.ok(input_events.includes("focus"));
    assert.ok(container_events.includes("input"));
    assert.equal(pill_items.length, 1);

    const keydown_handler = $input.get_on_handler("keydown");
    let prevent_called = false;
    let stop_called = false;
    keydown_handler({
        key: "Enter",
        preventDefault() {
            prevent_called = true;
        },
        stopPropagation() {
            stop_called = true;
        },
    });
    assert.ok(prevent_called);
    assert.ok(stop_called);

    let comma_stop_called = false;
    keydown_handler({
        key: ",",
        stopPropagation() {
            comma_stop_called = true;
        },
    });
    assert.ok(comma_stop_called);

    container_events.length = 0;
    $input.text("");
    pill_items.length = 0;
    on_pill_remove();
    assert.deepEqual(container_events, ["input"]);
    assert.equal($input.attr("data-placeholder"), default_placeholder);
});
