"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const messages_overlay_ui = zrequire("messages_overlay_ui");

// A minimal stand-in for an HTMLElement, tracking just enough state
// (CSS classes and focus calls) for these tests to observe whether
// `activate_element`/`handle_row_focus` moved DOM focus. Only the
// classList methods `activate_element`/`handle_row_focus` actually call
// are stubbed here.
function make_element(initial_classes) {
    const classes = new Set(initial_classes);
    return {
        focus_call_count: 0,
        classList: {
            add: (name) => classes.add(name),
            contains: (name) => classes.has(name),
        },
        focus() {
            this.focus_call_count += 1;
        },
    };
}

// Only `box_item_selector` is read by `activate_element`/`handle_row_focus`;
// the rest of the `Context` type isn't needed for these tests.
const context = {
    box_item_selector: "overlay-message-info-box",
};

run_test("activate_element focuses and marks the given element active", () => {
    const row = make_element(["overlay-message-info-box"]);

    messages_overlay_ui.activate_element(row, context);

    assert.ok(row.classList.contains("active"));
    assert.equal(row.focus_call_count, 1);
});

run_test("handle_row_focus focuses the row when the row itself is the target", () => {
    const row = make_element(["overlay-message-info-box"]);

    // This is what happens when a row gains focus directly, e.g. the
    // user Tabs onto the row, or we programmatically select it.
    messages_overlay_ui.handle_row_focus(row, row, context);

    assert.ok(row.classList.contains("active"));
    assert.equal(row.focus_call_count, 1);
});

run_test("handle_row_focus does not steal focus from a nested control", () => {
    const row = make_element(["overlay-message-info-box"]);
    const action_button = make_element(["delete-overlay-message"]);

    // This is what happens when the user Tabs from the row onto one of
    // its action buttons (e.g. Copy/Delete/Select): the button is the
    // real event target, but it is still inside the row.
    messages_overlay_ui.handle_row_focus(action_button, row, context);

    // The row should keep its selection highlight for arrow-key
    // navigation to resume from...
    assert.ok(row.classList.contains("active"));
    // ...but DOM focus must be left alone. Regression test for the bug
    // where the row's `focus()` was called unconditionally, which
    // immediately snapped focus back to the row and made the action
    // buttons unreachable via Tab.
    assert.equal(row.focus_call_count, 0);
    assert.equal(action_button.focus_call_count, 0);
});
