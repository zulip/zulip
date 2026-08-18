"use strict";

const assert = require("node:assert/strict");

const {$t} = require("./lib/i18n.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

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

run_test("effective_topics_state_for_search", ({override}) => {
    const info = set_up({override}, {is_subscribed: false});
    assert.equal(left_sidebar_filter.get_effective_topics_state_for_search(), "");

    info.pill_items.push({syntax: "is:followed"});
    info.state.narrowed_stream_id = 5;
    assert.equal(left_sidebar_filter.get_effective_topics_state_for_search(), "");

    info.state.is_subscribed = true;
    assert.equal(left_sidebar_filter.get_effective_topics_state_for_search(), "is:followed");
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

    left_sidebar_filter.handle_clear_left_sidebar_filter_click(event);
    assert.ok(stop_called);
    assert.ok(state.hide_called);
    assert.equal(state.clear_called_with, true);
    assert.equal($input.html(), "");
    assert.deepEqual(container_events, ["input"]);
    assert.deepEqual(input_events, ["blur"]);
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

run_test("typeahead_source_options", ({override}) => {
    const info = set_up({override});
    const {$input, state} = info;
    const source = state.captured_config.source;

    assert.deepEqual(source(), []);

    state.narrowed_stream_id = 42;
    state.is_subscribed = false;
    assert.deepEqual(source(), []);

    state.is_subscribed = true;
    state.has_resolved_topics = false;
    $input.text("is:");
    assert.deepEqual(source(), [filter_options[2]]);

    state.has_resolved_topics = true;
    assert.deepEqual(source(), [filter_options[0], filter_options[1], filter_options[2]]);
});

run_test("typeahead_updater", ({override}) => {
    const info = set_up({override});
    const {$input, state} = info;
    $input.text("is:res");

    const focus_events = [];
    $input.on("focus", () => {
        focus_events.push("focus");
    });

    const result = state.captured_config.updater(filter_options[1]);
    assert.equal(result, "");
    assert.equal(state.clear_called_with, true);
    assert.equal(state.append_called_with, "is:resolved");
    assert.deepEqual(focus_events, ["focus"]);
    assert.equal($input.text(), "");
});

run_test("typeahead_keydown", ({override}) => {
    const info = set_up({override});
    const {$input} = info;
    const keydown_handler = $input.get_on_handler("keydown");

    for (const key of ["Enter", ","]) {
        let stop_called = false;
        let prevent_called = false;
        keydown_handler({
            key,
            stopPropagation() {
                stop_called = true;
            },
            preventDefault() {
                prevent_called = true;
            },
        });
        assert.ok(stop_called);
        assert.equal(prevent_called, key === "Enter");
    }
});

run_test("placeholder_updates", ({override}) => {
    const info = set_up({override});
    const {$input, pill_items, handlers} = info;

    assert.equal($input.attr("data-placeholder"), default_placeholder);

    $input.text("search");
    handlers.on_text_input();
    assert.equal($input.attr("data-placeholder"), "");

    $input.text("");
    handlers.on_text_input();
    assert.equal($input.attr("data-placeholder"), default_placeholder);

    pill_items.push({syntax: "is:resolved"});
    handlers.on_pill_create();
    assert.equal($input.attr("data-placeholder"), filter_placeholder);

    pill_items.pop();
    handlers.on_pill_remove();
    assert.equal($input.attr("data-placeholder"), default_placeholder);
});
