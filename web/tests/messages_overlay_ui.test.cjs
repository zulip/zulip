"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const messages_overlay_ui = zrequire("messages_overlay_ui");

const context = {
    box_item_selector: "overlay-message-info-box",
};

function make_row() {
    const classes = new Set();
    return {
        classes,
        is_focused: false,
        classList: {
            add(name) {
                classes.add(name);
            },
        },
        focus() {
            this.is_focused = true;
        },
    };
}

run_test("handle_row_focus focuses the row when the row itself gets focus", () => {
    const row = make_row();
    messages_overlay_ui.handle_row_focus(row, true, context);
    assert.ok(row.classes.has("active"));
    assert.ok(row.is_focused);
});

run_test("handle_row_focus leaves focus on a control inside the row", () => {
    const row = make_row();
    messages_overlay_ui.handle_row_focus(row, false, context);
    assert.ok(row.classes.has("active"));
    assert.ok(!row.is_focused);
});
