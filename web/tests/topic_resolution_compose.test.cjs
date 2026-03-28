"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

// Mock dependencies
const channel = mock_esm("../src/channel", {
    patch(opts) {
        // Mock API call - invoke the success callback to simulate server response
        if (opts.success) {
            opts.success();
        }
    },
    xhr_error_message(message, _xhr) {
        return message;
    },
});

mock_esm("../src/compose_actions", {
    cancel() {},
    start(_opts) {},
});

mock_esm("../src/compose_banner", {
    show_topic_resolution_banner(_is_required, _on_cancel, _on_resolve) {},
    clear_topic_resolution_banners() {},
});

const compose_validate = mock_esm("../src/compose_validate", {
    validate_and_update_send_button_status() {},
});

const drafts = mock_esm("../src/drafts", {
    update_draft() {},
});

mock_esm("../src/ui_report", {
    generic_embed_error() {},
});

const compose_state = zrequire("compose_state");
const {set_realm} = zrequire("state_data");
const topic_resolution_compose = zrequire("topic_resolution_compose");

// Set up realm with default settings
const realm = make_realm({
    realm_topic_resolution_message_requirement: "not_requested",
});
set_realm(realm);

run_test("is_message_requirement_enabled", ({override}) => {
    override(realm, "realm_topic_resolution_message_requirement", "not_requested");
    assert.equal(topic_resolution_compose.is_message_requirement_enabled(), false);

    override(realm, "realm_topic_resolution_message_requirement", "optional");
    assert.equal(topic_resolution_compose.is_message_requirement_enabled(), true);

    override(realm, "realm_topic_resolution_message_requirement", "required");
    assert.equal(topic_resolution_compose.is_message_requirement_enabled(), true);
});

run_test("is_message_required", ({override}) => {
    override(realm, "realm_topic_resolution_message_requirement", "not_requested");
    assert.equal(topic_resolution_compose.is_message_required(), false);

    override(realm, "realm_topic_resolution_message_requirement", "optional");
    assert.equal(topic_resolution_compose.is_message_required(), false);

    override(realm, "realm_topic_resolution_message_requirement", "required");
    assert.equal(topic_resolution_compose.is_message_required(), true);
});

run_test("is_message_optional", ({override}) => {
    override(realm, "realm_topic_resolution_message_requirement", "not_requested");
    assert.equal(topic_resolution_compose.is_message_optional(), false);

    override(realm, "realm_topic_resolution_message_requirement", "optional");
    assert.equal(topic_resolution_compose.is_message_optional(), true);

    override(realm, "realm_topic_resolution_message_requirement", "required");
    assert.equal(topic_resolution_compose.is_message_optional(), false);
});

run_test("start_resolution_compose saves existing draft", ({override}) => {
    topic_resolution_compose.clear_pending_resolution();
    compose_state.set_message_type("stream");
    compose_state.message_content("draft I was already typing");

    let update_draft_called = false;
    override(drafts, "update_draft", () => {
        update_draft_called = true;
    });

    topic_resolution_compose.start_resolution_compose(123, 456, "test topic");

    assert.ok(update_draft_called);
    assert.equal(compose_state.message_content(), "");

    topic_resolution_compose.clear_pending_resolution();
    compose_state.set_message_type(undefined);
});

run_test("pending_resolution_state", () => {
    // Initially no pending resolution
    topic_resolution_compose.clear_pending_resolution();
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);
    assert.equal(compose_state.get_pending_resolution(), null);

    // After starting resolution compose, there should be pending state
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic");
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    const pending = compose_state.get_pending_resolution();
    assert.ok(pending);
    assert.equal(pending.message_id, 123);
    assert.equal(pending.stream_id, 456);
    assert.equal(pending.topic, "test topic");

    // Clear pending resolution
    topic_resolution_compose.clear_pending_resolution();
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);
});

run_test("resolve_without_message_in_optional_mode", ({override}) => {
    // Set to optional mode
    override(realm, "realm_topic_resolution_message_requirement", "optional");

    // Setup pending resolution
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic");
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Resolve without message
    topic_resolution_compose.resolve_without_message();

    // State should be cleared
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);
});

run_test("resolve_without_message_handles_api_error", ({override}) => {
    // Set to optional mode
    override(realm, "realm_topic_resolution_message_requirement", "optional");

    const $recipient_row = $("#compose-recipient");

    // Setup pending resolution (this calls disable_recipient_area → sets inert)
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic");
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Verify recipient row was made inert
    assert.ok($recipient_row.prop("inert"));

    // Mock channel.patch to trigger error
    let error_triggered = false;
    override(channel, "patch", (opts) => {
        opts.error({});
        error_triggered = true;
    });

    let send_button_status_updated = false;
    override(compose_validate, "validate_and_update_send_button_status", () => {
        send_button_status_updated = true;
    });

    // Resolve without message (triggers error callback)
    topic_resolution_compose.resolve_without_message();

    // Verify error was triggered
    assert.ok(error_triggered);

    // Recipient row stays locked while resolution state is still pending.
    assert.ok($recipient_row.prop("inert"));
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    assert.ok(send_button_status_updated);

    // Clean up pending resolution
    topic_resolution_compose.clear_pending_resolution();
});

run_test("resolve_without_message_blocked_in_required_mode", ({override}) => {
    // Set to required mode
    override(realm, "realm_topic_resolution_message_requirement", "required");

    // Setup pending resolution
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic");
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Try to resolve without message - should be blocked
    topic_resolution_compose.resolve_without_message();

    // State should still be pending (not cleared)
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Cleanup
    topic_resolution_compose.clear_pending_resolution();
});

run_test("resolve_without_message_early_return_when_no_pending", ({override}) => {
    // Set to optional mode
    override(realm, "realm_topic_resolution_message_requirement", "optional");

    // Clear any pending resolution
    topic_resolution_compose.clear_pending_resolution();
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);

    // This should return early without error
    topic_resolution_compose.resolve_without_message();

    // State should still be clear
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);
});

run_test("banner_callback_triggers_cancel_resolution", ({override}) => {
    // Set to optional mode
    override(realm, "realm_topic_resolution_message_requirement", "optional");

    // Start resolution compose - this will capture the cancel callback
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic");
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Cancel should clear state
    topic_resolution_compose.cancel_resolution();
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);
});

run_test("cancel_resolution - early return when no pending resolution", () => {
    // Ensure no pending resolution
    topic_resolution_compose.clear_pending_resolution();
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);

    // Should return early without error
    topic_resolution_compose.cancel_resolution();
});

// Edge case tests

run_test("check_and_cancel_if_topic_resolved - no pending resolution", () => {
    // Ensure no pending resolution
    topic_resolution_compose.clear_pending_resolution();
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);

    // Should return early without error
    topic_resolution_compose.check_and_cancel_if_topic_resolved(456, "test topic", "✔ test topic");

    // Still no pending (nothing to clear)
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);
});

run_test("check_and_cancel_if_topic_resolved - matching topic resolved externally", () => {
    // Setup pending resolution
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic");
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Another user resolved the same topic
    topic_resolution_compose.check_and_cancel_if_topic_resolved(456, "test topic", "✔ test topic");

    // Should silently cancel
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);
});

run_test("check_and_cancel_if_topic_resolved - different topic not affected", () => {
    // Setup pending resolution
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic");
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // A different topic is resolved
    topic_resolution_compose.check_and_cancel_if_topic_resolved(
        456,
        "other topic",
        "✔ other topic",
    );

    // Should NOT cancel since it's a different topic
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Cleanup
    topic_resolution_compose.clear_pending_resolution();
});

run_test("check_and_cancel_if_topic_resolved - different stream not affected", () => {
    // Setup pending resolution
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic");
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Same topic name but different stream
    topic_resolution_compose.check_and_cancel_if_topic_resolved(999, "test topic", "✔ test topic");

    // Should NOT cancel since it's a different stream
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Cleanup
    topic_resolution_compose.clear_pending_resolution();
});

run_test("check_and_cancel_if_topic_resolved - topic edit not resolving", () => {
    // Setup pending resolution
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic");
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Topic renamed but not resolved (no ✔ prefix)
    topic_resolution_compose.check_and_cancel_if_topic_resolved(456, "test topic", "renamed topic");

    // Should NOT cancel since topic wasn't resolved
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Cleanup
    topic_resolution_compose.clear_pending_resolution();
});

run_test("update_banner_if_needed - early return when no pending resolution", () => {
    // Ensure no pending resolution
    topic_resolution_compose.clear_pending_resolution();
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);

    // Should return early without error and without calling any UI updates
    // (We verified no UI updates via mocks not throwing errors if called unexpectedly)
    topic_resolution_compose.update_banner_if_needed();
});

run_test("update_banner_if_needed - with pending resolution", ({override}) => {
    // Set to optional mode
    override(realm, "realm_topic_resolution_message_requirement", "optional");

    // Setup pending resolution
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic");
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Change setting to required
    override(realm, "realm_topic_resolution_message_requirement", "required");

    // Update banner - should not clear pending state
    topic_resolution_compose.update_banner_if_needed();

    // Still has pending (only banner updates, not state)
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Cleanup
    topic_resolution_compose.clear_pending_resolution();
});

run_test(
    "update_banner_if_needed - setting changed to not_requested keeps current mode",
    ({override}) => {
        // Start in required mode
        override(realm, "realm_topic_resolution_message_requirement", "required");

        // Setup pending resolution in required mode
        topic_resolution_compose.start_resolution_compose(123, 456, "test topic");
        assert.equal(topic_resolution_compose.has_pending_resolution(), true);

        // Admin changes setting to not_requested
        override(realm, "realm_topic_resolution_message_requirement", "not_requested");

        // Update banner - should NOT change the banner (early return)
        // The banner should stay in required mode, not switch to optional
        topic_resolution_compose.update_banner_if_needed();

        // Still has pending (unchanged)
        assert.equal(topic_resolution_compose.has_pending_resolution(), true);

        // Cleanup
        topic_resolution_compose.clear_pending_resolution();
    },
);
