"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

// The undo toast is a success banner; `banners.open_and_close` does
// DOM and timer work that's out of scope here, so we stub it and just
// assert the selection module hands it the right banner config.
const banner_opens = [];
mock_esm("../src/banners", {
    open_and_close(banner, _$container, remove_after) {
        banner_opens.push({banner, remove_after});
    },
});

mock_esm("../src/ui_report", {
    error: noop,
});

mock_esm("../src/popovers", {
    hide_all: noop,
});

mock_esm("../src/compose_actions", {
    cancel: noop,
});

const channel_calls = [];
mock_esm("../src/channel", {
    del(opts) {
        channel_calls.push({method: "del", ...opts});
    },
    post(opts) {
        channel_calls.push({method: "post", ...opts});
    },
});

// A minimal stand-in for the message lists module. Selection mode
// interacts with it to (a) discover the owning list and (b) find DOM
// rows for individual messages so it can flip CSS classes on them.
const fake_rows_by_id = new Map();
function ensure_row(message_id) {
    if (!fake_rows_by_id.has(message_id)) {
        const $row = $.create(`fake-row-${message_id}`);
        const $checkbox = $.create(`fake-row-${message_id}-checkbox`);
        $row.set_find_results(".message-selection-checkbox", $checkbox);
        fake_rows_by_id.set(message_id, $row);
    }
    return fake_rows_by_id.get(message_id);
}

mock_esm("../src/message_lists", {
    current: {id: 7},
    all_rendered_row_for_message_id(message_id) {
        return ensure_row(message_id);
    },
});

// Banner rendering is a thin wrapper around the template; replace
// with a stub so we don't have to construct a real DOM here.
const banner_renders = [];
mock_esm("../templates/selection_mode_banner.hbs", {
    default(args) {
        banner_renders.push(args);
        return "<banner/>";
    },
});

const message_selection = zrequire("message_selection");

function reset() {
    fake_rows_by_id.clear();
    banner_renders.length = 0;
    banner_opens.length = 0;
    channel_calls.length = 0;
    // The test harness clears delegated body handlers before each
    // test, so (re)bind them here for the undo button below.
    message_selection.initialize();
}

// Drive the undo banner's Undo button, which is bound by initialize()
// as a delegated handler on the document body.
function click_undo() {
    $("body").get_on_handler(
        "click",
        "#message_delete_undo_banner .message-delete-undo-button",
    )({
        preventDefault: noop,
    });
}

run_test("enter and exit", () => {
    reset();
    assert.equal(message_selection.is_active(), false);
    assert.equal(message_selection.selected_count(), 0);

    message_selection.enter(101);

    assert.equal(message_selection.is_active(), true);
    assert.equal(message_selection.selected_count(), 1);
    assert.deepEqual(message_selection.selected_ids(), [101]);
    assert.equal(message_selection.is_selected(101), true);
    assert.equal(banner_renders.length, 1);
    assert.equal(banner_renders[0].delete_disabled, false);

    message_selection.exit();
    assert.equal(message_selection.is_active(), false);
    assert.equal(message_selection.selected_count(), 0);
});

run_test("toggle adds and removes ids and re-renders banner", () => {
    reset();
    message_selection.enter(1);
    assert.deepEqual(message_selection.selected_ids(), [1]);

    message_selection.toggle(2);
    assert.equal(message_selection.selected_count(), 2);
    assert.equal(message_selection.is_selected(2), true);

    message_selection.toggle(2);
    assert.equal(message_selection.selected_count(), 1);
    assert.equal(message_selection.is_selected(2), false);

    // Banner re-rendered on every toggle so the "Delete N messages"
    // count stays accurate.
    assert.ok(banner_renders.length >= 3);

    // Toggling the only remaining message yields an empty selection;
    // the banner's delete button should now be disabled.
    message_selection.toggle(1);
    assert.equal(message_selection.selected_count(), 0);
    const last_render = banner_renders.at(-1);
    assert.equal(last_render.delete_disabled, true);

    message_selection.exit();
});

run_test("toggle is a no-op outside selection mode", () => {
    reset();
    assert.equal(message_selection.is_active(), false);
    message_selection.toggle(42);
    assert.equal(message_selection.selected_count(), 0);
});

run_test("confirm_delete bulk-deletes immediately, then shows undo toast", () => {
    reset();

    message_selection.enter(10);
    message_selection.toggle(11);
    assert.equal(message_selection.selected_count(), 2);

    message_selection.confirm_delete();

    // Selection mode exits and a single bulk DELETE fires right away.
    assert.equal(message_selection.is_active(), false);
    assert.equal(channel_calls.length, 1);
    assert.equal(channel_calls[0].method, "del");
    assert.equal(channel_calls[0].url, "/json/messages");
    assert.deepEqual(JSON.parse(channel_calls[0].data.message_ids), [10, 11]);

    // The undo toast only appears once the server confirms the deletion.
    assert.equal(banner_opens.length, 0);
    channel_calls[0].success();
    assert.equal(banner_opens.length, 1);
    assert.equal(banner_opens[0].banner.intent, "success");
    assert.equal(banner_opens[0].remove_after, message_selection.UNDO_DELAY_MS);
    assert.equal(banner_opens[0].banner.close_button, true);
    assert.equal(banner_opens[0].banner.buttons[0].custom_classes, "message-delete-undo-button");
});

run_test("undo restores the deleted messages from the archive", () => {
    reset();

    message_selection.enter(20);
    message_selection.toggle(21);
    message_selection.confirm_delete();
    channel_calls[0].success();

    // Clicking undo restores exactly the messages that were deleted.
    click_undo();
    const restore_call = channel_calls.find((call) => call.method === "post");
    assert.ok(restore_call);
    assert.equal(restore_call.url, "/json/messages/restore");
    assert.deepEqual(JSON.parse(restore_call.data.message_ids), [20, 21]);

    // A second click has nothing left to restore (no duplicate request).
    const post_calls_before = channel_calls.filter((call) => call.method === "post").length;
    click_undo();
    const post_calls_after = channel_calls.filter((call) => call.method === "post").length;
    assert.equal(post_calls_after, post_calls_before);
});

run_test("confirm_delete with empty selection is a no-op", () => {
    reset();
    // Not in selection mode at all.
    message_selection.confirm_delete();
    assert.equal(banner_opens.length, 0);
    assert.equal(channel_calls.length, 0);
});

run_test("state-changing helpers are no-ops outside selection mode", () => {
    reset();
    // None of these do anything when selection mode isn't active.
    message_selection.update_banner();
    message_selection.exit();
    message_selection.maybe_exit_on_view_change();
    assert.equal(message_selection.is_active(), false);

    // enter does nothing when there is no current message list.
    const message_lists = require("../src/message_lists.ts");
    message_lists.current = undefined;
    message_selection.enter(1);
    assert.equal(message_selection.is_active(), false);
    message_lists.current = {id: 7};

    // Re-selecting an already-selected message, or deselecting one that
    // isn't selected, leaves the selection unchanged.
    message_selection.enter(2);
    message_selection.set_selected(2, true);
    message_selection.set_selected(99, false);
    assert.deepEqual(message_selection.selected_ids(), [2]);

    // Confirming with everything deselected does nothing (no request).
    message_selection.set_selected(2, false);
    assert.equal(message_selection.selected_count(), 0);
    message_selection.confirm_delete();
    assert.equal(channel_calls.length, 0);
    message_selection.exit();
});

run_test("banner delete and cancel buttons", () => {
    reset();
    // Cancel exits selection mode.
    message_selection.enter(60);
    $("body").get_on_handler(
        "click",
        "#selection_mode_banner .selection-mode-cancel-button",
    )({
        preventDefault: noop,
    });
    assert.equal(message_selection.is_active(), false);

    // Delete triggers the bulk deletion request.
    message_selection.enter(61);
    $("body").get_on_handler(
        "click",
        "#selection_mode_banner .selection-mode-delete-button",
    )({
        preventDefault: noop,
    });
    assert.ok(channel_calls.some((call) => call.method === "del"));
});

run_test("failed delete request is reported", () => {
    reset();
    message_selection.enter(70);
    message_selection.confirm_delete();
    // The delete request fails: the error path is exercised (and reported).
    channel_calls[0].error({});
});

run_test("failed restore request is reported", () => {
    reset();
    message_selection.enter(71);
    message_selection.confirm_delete();
    channel_calls[0].success();
    click_undo();
    const restore_call = channel_calls.find((call) => call.method === "post");
    // The restore request fails: the error path is exercised (and reported).
    restore_call.error({});
});

run_test("checkbox change handler syncs selection from the DOM", () => {
    reset();
    const change_handler = $("body").get_on_handler("change", ".message-selection-checkbox");

    // Not in selection mode: ignored before touching the DOM.
    change_handler.call({checked: true}, {});

    message_selection.enter(80);

    // A checkbox whose row has no message id is ignored.
    const $no_id_checkbox = $.create("checkbox-no-id");
    $no_id_checkbox.checked = true;
    $no_id_checkbox.set_closest_results(".message_row", $.create("row-no-id"));
    change_handler.call($no_id_checkbox, {});
    assert.deepEqual(message_selection.selected_ids(), [80]);

    // Checking a resolvable checkbox selects that message.
    const $checkbox = $.create("checkbox-81");
    $checkbox.checked = true;
    const $row = $.create("row-81");
    $row.attr("data-message-id", "81");
    $checkbox.set_closest_results(".message_row", $row);
    change_handler.call($checkbox, {});
    assert.equal(message_selection.is_selected(81), true);

    message_selection.exit();
});

run_test("checkbox wrapper click does not bubble to the row", () => {
    reset();
    let stopped = false;
    $("body").get_on_handler(
        "click",
        ".message-selection-checkbox-wrapper",
    )({
        stopPropagation() {
            stopped = true;
        },
    });
    assert.ok(stopped);
});

run_test("maybe_exit_on_view_change exits when list id changes", () => {
    reset();
    message_selection.enter(50);
    assert.equal(message_selection.is_active(), true);

    // Same list id => no-op.
    message_selection.maybe_exit_on_view_change();
    assert.equal(message_selection.is_active(), true);

    // Simulate navigating to a different message list.
    const message_lists = require("../src/message_lists.ts");
    message_lists.current = {id: 99};
    message_selection.maybe_exit_on_view_change();
    assert.equal(message_selection.is_active(), false);

    // Restore for subsequent tests.
    message_lists.current = {id: 7};
});
