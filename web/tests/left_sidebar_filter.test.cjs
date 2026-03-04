"use strict";

const assert = require("node:assert/strict");

const {$t} = require("./lib/i18n.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const bootstrap_typeahead = mock_esm("../src/bootstrap_typeahead");
const input_pill = mock_esm("../src/input_pill");
const narrow_state = mock_esm("../src/narrow_state", {
    filter: () => ({}),
    stream_id: () => undefined,
});
const stream_data = mock_esm("../src/stream_data", {
    is_subscribed: () => false,
});

const stream_topic_history = mock_esm("../src/stream_topic_history", {
    stream_has_locally_available_resolved_topics: () => false,
});

const topic_filter_pill = zrequire("topic_filter_pill");
const filter_options = topic_filter_pill.filter_options;
const left_sidebar_filter = zrequire("left_sidebar_filter");
const filter_placeholder = $t({defaultMessage: "Filter"});
const default_placeholder = $t({defaultMessage: "Filter left sidebar"});

run_test("get_topics_state_and_clear_without_updating", ({override_rewire}) => {
    assert.equal(stream_topic_history.stream_has_locally_available_resolved_topics(), false);
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

    const $input = $("#left-sidebar-filter-query");
    $input.html("filter");

    override_rewire(left_sidebar_filter, "left_sidebar_filter_pill_widget", pill_widget);
    assert.equal(left_sidebar_filter.get_topics_state(), "is:resolved");

    left_sidebar_filter.clear_without_updating();
    assert.equal(clear_called_with, true);
    assert.equal($input.html(), "");
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
    assert.ok(hide_called);
    assert.equal(clear_called_with, true);
    assert.equal($input.html(), "");
    assert.deepEqual(container_events, ["input"]);
    assert.deepEqual(input_events, ["blur"]);
});

run_test(
    "typeahead_visibility_and_topic_state_filter_applicability",
    ({override, override_rewire}) => {
        assert.equal(left_sidebar_filter.is_typeahead_shown(), false);

        override_rewire(left_sidebar_filter, "left_sidebar_filter_typeahead", {shown: true});
        assert.equal(left_sidebar_filter.is_typeahead_shown(), true);

        override_rewire(left_sidebar_filter, "left_sidebar_filter_typeahead", {shown: false});
        assert.equal(left_sidebar_filter.is_typeahead_shown(), false);
        assert.equal(left_sidebar_filter.topic_state_filter_applies(), false);
        assert.equal(left_sidebar_filter.get_effective_topics_state_for_search(), "");

        override_rewire(left_sidebar_filter, "left_sidebar_filter_pill_widget", {
            items: () => [{syntax: "is:followed"}],
        });
        override(narrow_state, "stream_id", () => 5);
        assert.equal(left_sidebar_filter.topic_state_filter_applies(), false);
        assert.equal(left_sidebar_filter.get_effective_topics_state_for_search(), "");

        override(stream_data, "is_subscribed", () => false);
        assert.equal(left_sidebar_filter.topic_state_filter_applies(), false);
        assert.equal(left_sidebar_filter.get_effective_topics_state_for_search(), "");

        override(stream_data, "is_subscribed", () => true);
        assert.equal(left_sidebar_filter.topic_state_filter_applies(), true);
        assert.equal(left_sidebar_filter.get_effective_topics_state_for_search(), "is:followed");
    },
);

run_test("setup_left_sidebar_filter_typeahead_returns_if_missing_elements", () => {
    $.set_results("#left-sidebar-filter-query", []);
    $.set_results("#left-sidebar-filter-input", []);

    left_sidebar_filter.setup_left_sidebar_filter_typeahead();
    assert.equal(left_sidebar_filter.get_topics_state(), "");
    $.reset_selector("#left-sidebar-filter-query");
    $.reset_selector("#left-sidebar-filter-input");
});

run_test("setup_left_sidebar_filter_typeahead", ({override}) => {
    const $input = $("#left-sidebar-filter-query");
    const $pill_container = $("#left-sidebar-filter-input");

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
            on_pill_create?.();
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
        createPillonPaste: noop,
    };

    override(input_pill, "create", (opts) => {
        assert.equal(opts.$container.selector, "#left-sidebar-filter-input");
        return pill_widget;
    });

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
    $input.on("focus", () => {
        input_events.push("focus");
    });

    const container_events = [];
    $pill_container.on("input", () => {
        container_events.push("input");
    });

    $input.text("");
    left_sidebar_filter.setup_left_sidebar_filter_typeahead();

    assert.equal($input.attr("data-placeholder"), default_placeholder);

    $input.text("has-text");
    on_text_input();
    assert.equal($input.attr("data-placeholder"), "");

    $input.text("");
    pill_items.push({syntax: "is:resolved"});
    container_events.length = 0;
    on_pill_create();
    assert.equal($input.attr("data-placeholder"), filter_placeholder);
    assert.deepEqual(container_events, ["input"]);
    assert.equal(captured_input.$element.selector, $input.selector);

    pill_items.length = 0;
    $input.text("is:");
    narrowed_stream_id = undefined;
    assert.deepEqual(captured_config.source(), []);

    narrowed_stream_id = 5;
    has_resolved_topics = false;
    assert.deepEqual(
        captured_config.source().map((option) => option.syntax),
        ["is:followed"],
    );
    has_resolved_topics = true;
    assert.deepEqual(
        captured_config.source().map((option) => option.syntax),
        ["-is:resolved", "is:resolved", "is:followed"],
    );

    narrowed_stream_id = 5;
    is_subscribed = true;
    has_resolved_topics = true;
    $input.text("-is");
    assert.deepEqual(
        captured_config.source().map((option) => option.syntax),
        ["-is:resolved", "is:resolved", "is:followed", "-is:followed"],
    );

    $input.text("is:");
    pill_items.push({syntax: "is:resolved"});
    assert.deepEqual(
        captured_config.source().map((option) => option.syntax),
        ["-is:resolved", "is:followed"],
    );
    pill_items.length = 0;

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
