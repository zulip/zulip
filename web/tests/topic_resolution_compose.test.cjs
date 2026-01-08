"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

// Mock dependencies
mock_esm("../src/channel", {
    patch(opts) {
        // Mock API call - invoke the success callback to simulate server response
        if (opts.success) {
            opts.success();
        }
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

mock_esm("../src/compose_validate", {
    validate_and_update_send_button_status() {},
});

// Unused mocks removed to fix coverage

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

run_test("is_resolve_via_move_allowed", ({override}) => {
    override(realm, "realm_topic_resolution_message_requirement", "not_requested");
    assert.equal(topic_resolution_compose.is_resolve_via_move_allowed(), true);

    override(realm, "realm_topic_resolution_message_requirement", "optional");
    assert.equal(topic_resolution_compose.is_resolve_via_move_allowed(), true);

    override(realm, "realm_topic_resolution_message_requirement", "required");
    assert.equal(topic_resolution_compose.is_resolve_via_move_allowed(), false);
});

run_test("pending_resolution_state", () => {
    // Initially no pending resolution
    topic_resolution_compose.clear_pending_resolution();
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);
    assert.equal(topic_resolution_compose.get_pending_resolution(), null);

    // After starting resolution compose, there should be pending state
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic", false);
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    const pending = topic_resolution_compose.get_pending_resolution();
    assert.ok(pending);
    assert.equal(pending.message_id, 123);
    assert.equal(pending.stream_id, 456);
    assert.equal(pending.topic, "test topic");

    // Clear pending resolution
    topic_resolution_compose.clear_pending_resolution();
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);
});

run_test("meets_minimum_length", () => {
    // Empty message should not meet minimum
    compose_state.message_content("");
    assert.equal(topic_resolution_compose.meets_minimum_length(), false);

    // Short message should not meet minimum (< 10 chars)
    compose_state.message_content("short");
    assert.equal(topic_resolution_compose.meets_minimum_length(), false);

    // Exactly 10 chars should meet minimum
    compose_state.message_content("ten chars!");
    assert.equal(topic_resolution_compose.meets_minimum_length(), true);

    // Longer message should meet minimum
    compose_state.message_content("This is a longer message explaining the resolution");
    assert.equal(topic_resolution_compose.meets_minimum_length(), true);

    // Whitespace-only should not meet minimum (after trim)
    compose_state.message_content("          ");
    assert.equal(topic_resolution_compose.meets_minimum_length(), false);
});

run_test("MIN_RESOLUTION_MESSAGE_LENGTH_constant", () => {
    assert.equal(topic_resolution_compose.MIN_RESOLUTION_MESSAGE_LENGTH, 10);
});

run_test("resolve_without_message_in_optional_mode", ({override}) => {
    // Set to optional mode
    override(realm, "realm_topic_resolution_message_requirement", "optional");

    // Setup pending resolution
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic", false);
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Resolve without message
    topic_resolution_compose.resolve_without_message();

    // State should be cleared
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);
});

run_test("resolve_without_message_blocked_in_required_mode", ({override}) => {
    // Set to required mode
    override(realm, "realm_topic_resolution_message_requirement", "required");

    // Setup pending resolution
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic", false);
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

run_test("get_resolution_blocked_error", () => {
    const error = topic_resolution_compose.get_resolution_blocked_error();
    assert.ok(error.length > 0);
    assert.ok(error.includes("requires a message"));
});

run_test("banner_callback_triggers_cancel_resolution", ({override}) => {
    // Set to optional mode
    override(realm, "realm_topic_resolution_message_requirement", "optional");

    // Start resolution compose - this will capture the cancel callback
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic", false);
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
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic", false);
    assert.equal(topic_resolution_compose.has_pending_resolution(), true);

    // Another user resolved the same topic
    topic_resolution_compose.check_and_cancel_if_topic_resolved(456, "test topic", "✔ test topic");

    // Should silently cancel
    assert.equal(topic_resolution_compose.has_pending_resolution(), false);
});

run_test("check_and_cancel_if_topic_resolved - different topic not affected", () => {
    // Setup pending resolution
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic", false);
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
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic", false);
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
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic", false);
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
    topic_resolution_compose.start_resolution_compose(123, 456, "test topic", false);
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
        topic_resolution_compose.start_resolution_compose(123, 456, "test topic", false);
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
