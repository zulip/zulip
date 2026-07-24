"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const messages_overlay_ui = mock_esm("../src/messages_overlay_ui");

const reminders_overlay_ui = zrequire("reminders_overlay_ui");
const scheduled_messages_overlay_ui = zrequire("scheduled_messages_overlay_ui");

function assert_focus_handler_ignores_child_controls({handler_selector, initialize, override}) {
    initialize();

    let activated_element;
    override(messages_overlay_ui, "activate_element", (element) => {
        activated_element = element;
    });

    const $row = $.create(`${handler_selector}-row`);
    const $child_control = $.create(`${handler_selector}-child-control`);
    const focus_handler = $("body").get_on_handler("focus", handler_selector);

    focus_handler.call($row[0], {target: $child_control[0]});
    assert.equal(activated_element, undefined);

    focus_handler.call($row[0], {target: $row[0]});
    assert.equal(activated_element, $row[0]);
}

run_test("scheduled message row focus ignores child controls", ({override}) => {
    assert_focus_handler_ignores_child_controls({
        handler_selector: ".scheduled-message-info-box",
        initialize: scheduled_messages_overlay_ui.initialize,
        override,
    });
});

run_test("reminder row focus ignores child controls", ({override}) => {
    assert_focus_handler_ignores_child_controls({
        handler_selector: ".reminder-info-box",
        initialize: reminders_overlay_ui.initialize,
        override,
    });
});
