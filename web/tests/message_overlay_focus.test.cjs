"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const messages_overlay_ui = mock_esm("../src/messages_overlay_ui");

const reminders_overlay_ui = zrequire("reminders_overlay_ui");
const scheduled_messages_overlay_ui = zrequire("scheduled_messages_overlay_ui");

function assert_focus_handler_updates_row_selection({
    box_item_selector,
    handle_keyboard_events,
    handler_selector,
    initialize,
    override,
}) {
    initialize();

    let activated_element;
    override(messages_overlay_ui, "activate_element", (element) => {
        activated_element = element;
    });

    const $row = $.create(`${handler_selector}-row`);
    const $active_row = $.create(`${handler_selector}-active-row`);
    $active_row.addClass("active");
    $.set_results(handler_selector, [$active_row[0]]);

    const keyboard_focused_child = Object.create(window.HTMLElement.prototype);
    keyboard_focused_child.matches = (selector) => {
        assert.equal(selector, ":focus-visible");
        return true;
    };
    const focus_handler = $("body").get_on_handler("focus", handler_selector);

    focus_handler.call($row[0], {target: keyboard_focused_child});
    assert.equal(activated_element, undefined);
    assert.equal($active_row.hasClass("active"), false);

    const pointer_focused_child = Object.create(window.HTMLElement.prototype);
    pointer_focused_child.matches = (selector) => {
        assert.equal(selector, ":focus-visible");
        return false;
    };
    $active_row.addClass("active");
    focus_handler.call($row[0], {target: pointer_focused_child});
    assert.equal(activated_element, undefined);
    assert.equal($active_row.hasClass("active"), true);

    focus_handler.call($row[0], {target: $row[0]});
    assert.equal(activated_element, $row[0]);

    let handled_event;
    override(messages_overlay_ui, "modals_handle_events", (key, context, event_target) => {
        handled_event = {key, box_item_selector: context.box_item_selector, event_target};
    });
    handle_keyboard_events("up_arrow", keyboard_focused_child);
    assert.deepEqual(handled_event, {
        key: "up_arrow",
        box_item_selector,
        event_target: keyboard_focused_child,
    });
}

run_test("scheduled message row focus updates row selection", ({override}) => {
    assert_focus_handler_updates_row_selection({
        box_item_selector: "scheduled-message-info-box",
        handle_keyboard_events: scheduled_messages_overlay_ui.handle_keyboard_events,
        handler_selector: ".scheduled-message-info-box",
        initialize: scheduled_messages_overlay_ui.initialize,
        override,
    });
});

run_test("reminder row focus updates row selection", ({override}) => {
    assert_focus_handler_updates_row_selection({
        box_item_selector: "reminder-info-box",
        handle_keyboard_events: reminders_overlay_ui.handle_keyboard_events,
        handler_selector: ".reminder-info-box",
        initialize: reminders_overlay_ui.initialize,
        override,
    });
});
