"use strict";

const assert = require("node:assert/strict");

const {$t} = require("./lib/i18n.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const bootstrap_typeahead = mock_esm("../src/bootstrap_typeahead");
const input_pill = mock_esm("../src/input_pill");
const state = {
    narrowed_stream_id: undefined,
    is_subscribed: false,
    has_resolved_topics: false,
    clear_called_with: undefined,
    append_called_with: undefined,
    hide_called: false,
    captured_input: undefined,
    captured_config: undefined,
};
mock_esm("../src/narrow_state", {
    filter: () => ({}),
    stream_id: () => state.narrowed_stream_id,
});
mock_esm("../src/stream_data", {
    is_subscribed: () => state.is_subscribed,
});

mock_esm("../src/stream_topic_history", {
    stream_has_locally_available_resolved_topics: () => state.has_resolved_topics,
});

const blueslip = zrequire("blueslip");
const topic_filter_pill = zrequire("topic_filter_pill");
const filter_options = topic_filter_pill.filter_options;
const left_sidebar_filter = zrequire("left_sidebar_filter");
const filter_placeholder = $t({defaultMessage: "Filter"});
const default_placeholder = $t({defaultMessage: "Filter left sidebar"});

function set_up(
    {override},
    {narrowed_stream_id = undefined, is_subscribed = true, has_resolved_topics = true} = {},
) {
    $.reset_selector("#left-sidebar-filter-query");
    $.reset_selector("#left-sidebar-filter-input");
    const $input = $("#left-sidebar-filter-query");
    const $pill_container = $("#left-sidebar-filter-input");
    $input.text("");

    Object.assign(state, {
        narrowed_stream_id,
        is_subscribed,
        has_resolved_topics,
        clear_called_with: undefined,
        append_called_with: undefined,
        hide_called: false,
        captured_input: undefined,
        captured_config: undefined,
    });
    const pill_items = [];
    const handlers = {
        on_pill_create: noop,
        on_pill_remove: noop,
        on_text_input: noop,
    };
    const pill_widget = {
        items() {
            return pill_items;
        },
        clear(suppress) {
            state.clear_called_with = suppress;
            pill_items.length = 0;
        },
        appendValue(syntax) {
            state.append_called_with = syntax;
            pill_items.push({syntax});
            handlers.on_pill_create();
        },
        onPillCreate(callback) {
            handlers.on_pill_create = callback;
        },
        onPillRemove(callback) {
            handlers.on_pill_remove = callback;
        },
        onTextInputHook(callback) {
            handlers.on_text_input = callback;
        },
        createPillonPaste: noop,
    };

    override(input_pill, "create", (opts) => {
        assert.equal(opts.$container.selector, "#left-sidebar-filter-input");
        return pill_widget;
    });

    function FakeTypeahead(input_element, config) {
        state.captured_input = input_element;
        state.captured_config = config;
        return {
            hide() {
                state.hide_called = true;
            },
            unlisten: noop,
        };
    }
    override(bootstrap_typeahead, "Typeahead", FakeTypeahead);

    left_sidebar_filter.setup_left_sidebar_filter_typeahead();

    return {
        $input,
        $pill_container,
        pill_items,
        state,
        handlers,
    };
}

run_test("get_raw_topics_state", ({override}) => {
    const {pill_items} = set_up({override});
    assert.equal(left_sidebar_filter.get_raw_topics_state(), "");

    pill_items.push({syntax: "is:resolved"});
    assert.equal(left_sidebar_filter.get_raw_topics_state(), "is:resolved");

    let warning_message;
    override(blueslip, "warn", (message) => {
        warning_message = message;
    });
    pill_items.push({syntax: "is:followed"});
    assert.equal(left_sidebar_filter.get_raw_topics_state(), "is:resolved");
    assert.equal(warning_message, "Multiple pills found in left sidebar filter input.");
});

run_test("clear_left_sidebar_filter", ({override}) => {
    const info = set_up({override});
    const {$input, $pill_container, state} = info;
    $input.html("filter");

    const input_events = [];
    $input.on("blur", () => {
        input_events.push("blur");
    });

    const container_events = [];
    $pill_container.on("input", () => {
        container_events.push("input");
    });

    let stop_called = false;
    const event = {
        stopPropagation() {
            stop_called = true;
        },
    };

    left_sidebar_filter.clear_left_sidebar_filter(event);
    assert.ok(stop_called);
    assert.ok(state.hide_called);
    assert.equal(state.clear_called_with, true);
    assert.equal($input.html(), "");
    assert.deepEqual(container_events, ["input"]);
    assert.deepEqual(input_events, ["blur"]);
});

run_test("effective_topics_state_for_search", ({override}) => {
    const info = set_up({override}, {is_subscribed: false});
    assert.equal(left_sidebar_filter.get_effective_topics_state_for_search(), "");

    info.pill_items.push({syntax: "is:followed"});
    info.state.narrowed_stream_id = 5;
    assert.equal(left_sidebar_filter.get_effective_topics_state_for_search(), "");

    info.state.is_subscribed = true;
    assert.equal(left_sidebar_filter.get_effective_topics_state_for_search(), "is:followed");
});

run_test("query_helpers", ({override}) => {
    const info = set_up({override});
    const {$input, $pill_container, pill_items} = info;

    assert.equal(left_sidebar_filter.has_left_sidebar_filter_value(), false);

    pill_items.push({syntax: "is:resolved"});
    assert.equal(left_sidebar_filter.has_left_sidebar_filter_value(), true);

    const container_events = [];
    $pill_container.on("input", () => {
        container_events.push("input");
    });
    $input.html("devel");
    left_sidebar_filter.clear_query();
    assert.equal($input.html(), "");
    assert.deepEqual(container_events, ["input"]);
});

run_test("setup_left_sidebar_filter_typeahead", ({override}) => {
    assert.equal(left_sidebar_filter.is_typeahead_shown(), false);

    $.set_results("#left-sidebar-filter-query", []);
    $.set_results("#left-sidebar-filter-input", []);
    left_sidebar_filter.setup_left_sidebar_filter_typeahead();
    assert.equal(left_sidebar_filter.is_typeahead_shown(), false);

    const info = set_up({override});
    const {$input, $pill_container, pill_items, state, handlers} = info;
    assert.equal(left_sidebar_filter.is_typeahead_shown(), false);

    const input_events = [];
    $input.on("focus", () => {
        input_events.push("focus");
    });

    const container_events = [];
    $pill_container.on("input", () => {
        container_events.push("input");
    });

    $input.text("");
    assert.equal($input.attr("data-placeholder"), default_placeholder);
    assert.equal(state.captured_input.$element.selector, $input.selector);

    $input.text("has-text");
    handlers.on_text_input();
    assert.equal($input.attr("data-placeholder"), "");

    $input.text("");
    pill_items.push({syntax: "is:followed"});
    container_events.length = 0;
    handlers.on_pill_create();
    assert.equal($input.attr("data-placeholder"), filter_placeholder);
    assert.deepEqual(container_events, ["input"]);

    $input.text("is:");
    state.narrowed_stream_id = undefined;
    assert.deepEqual(state.captured_config.source(), []);

    state.narrowed_stream_id = 5;
    pill_items.length = 0;
    assert.ok(state.captured_config.source().some((option) => option.syntax === "is:resolved"));

    state.has_resolved_topics = false;
    assert.ok(state.captured_config.source().every((option) => option.syntax !== "is:resolved"));

    $input.text("is:");
    const result = state.captured_config.updater(filter_options[1]);
    assert.equal(state.clear_called_with, true);
    assert.equal(state.append_called_with, "is:resolved");
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
    handlers.on_pill_remove();
    assert.deepEqual(container_events, ["input"]);
    assert.equal($input.attr("data-placeholder"), default_placeholder);
});
