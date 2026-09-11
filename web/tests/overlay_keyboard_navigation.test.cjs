"use strict";

const assert = require("node:assert/strict");

const {JSDOM} = require("jsdom");

// These are the real (unmocked) templates for the rows rendered inside
// the Drafts, Scheduled messages, and Message reminders overlays. We
// render them directly and inspect the resulting markup to verify that
// every action button is a real, natively-focusable `<button>` element
// that participates in the browser's normal Tab order -- rather than a
// non-focusable `<span>`/`<div>` with only a decorative `role="button"`,
// which the browser silently skips when tabbing.
const render_draft = require("../templates/draft.hbs");
const render_reminder_list = require("../templates/reminder_list.hbs");
const render_scheduled_message = require("../templates/scheduled_message.hbs");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const overlay_util = zrequire("overlay_util");

function parse(html) {
    return new JSDOM(html).window.document;
}

function assert_is_focusable_button(button, description) {
    assert.equal(button.tagName, "BUTTON", `${description} should be a real <button> element`);
    assert.notEqual(
        button.getAttribute("tabindex"),
        "-1",
        `${description} must not be removed from the Tab order`,
    );
    assert.ok(!button.hasAttribute("disabled"), `${description} must not be disabled`);
    assert.ok(
        button.matches(overlay_util.OVERLAY_FOCUSABLE_SELECTOR),
        `${description} should match OVERLAY_FOCUSABLE_SELECTOR, the selector Zulip's ` +
            "overlays use to compute Tab order",
    );
}

run_test("draft action buttons are keyboard-focusable", () => {
    const html = render_draft({
        draft_id: "1",
        is_stream: false,
        is_dm_with_self: true,
        time_stamp: "12:00 PM",
        content: "hello",
    });
    const document = parse(html);
    const controls = document.querySelector(".overlay_message_controls");
    const buttons = [...controls.children];

    // Copy, Delete, and Select.
    assert.equal(buttons.length, 3);
    for (const button of buttons) {
        assert_is_focusable_button(button, `.${button.className.split(" ", 1)[0]}`);
    }

    const copy_button = controls.querySelector(".copy-overlay-message");
    assert_is_focusable_button(copy_button, "the Copy draft button");
    // A native <button> is already exposed to assistive tech as a
    // button; a redundant `role="button"` is unnecessary and was the
    // remnant of the old `<span role="button">` markup.
    assert.ok(!copy_button.hasAttribute("role"));

    const select_button = controls.querySelector(".draft-selection-tooltip");
    assert_is_focusable_button(select_button, "the Select draft button");
    assert.equal(select_button.getAttribute("role"), "checkbox");
    assert.equal(select_button.getAttribute("aria-checked"), "false");

    const delete_button = controls.querySelector(".delete-overlay-message");
    assert_is_focusable_button(delete_button, "the Delete draft button");
});

run_test("scheduled message action buttons are keyboard-focusable", () => {
    const html = render_scheduled_message({
        scheduled_messages_data: [
            {
                scheduled_message_id: 1,
                is_stream: false,
                is_dm_with_self: true,
                formatted_send_at_time: "12:00 PM",
                rendered_content: "hello",
            },
        ],
    });
    const document = parse(html);
    const delete_button = document.querySelector(
        ".overlay_message_controls .delete-overlay-message",
    );
    assert_is_focusable_button(delete_button, "the Delete scheduled message button");
});

run_test("reminder action buttons are keyboard-focusable", () => {
    const html = render_reminder_list({
        reminders_data: [
            {
                reminder_id: 1,
                formatted_send_at_time: "12:00 PM",
                rendered_content: "hello",
            },
        ],
    });
    const document = parse(html);
    const delete_button = document.querySelector(
        ".overlay_message_controls .delete-overlay-message",
    );
    assert_is_focusable_button(delete_button, "the Delete reminder button");
});
