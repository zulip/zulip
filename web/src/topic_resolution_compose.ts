/**
 * This module handles the compose box flow for resolving topics when
 * the organization setting `topic_resolution_message_requirement` is
 * set to "required" or "optional".
 *
 * When resolving a topic in these modes, instead of resolving immediately,
 * the compose box is opened and the user can optionally enter a message
 * explaining why the topic was resolved. The message is sent as a normal
 * message with `then_resolve_topic=true`, which atomically sends the
 * message and resolves the topic.
 */

import $ from "jquery";

import * as channel from "./channel.ts";
import * as compose_actions from "./compose_actions.ts";
import * as compose_banner from "./compose_banner.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_validate from "./compose_validate.ts";
import {$t} from "./i18n.ts";
import * as resolved_topic from "./resolved_topic.ts";
import {realm} from "./state_data.ts";
import * as ui_report from "./ui_report.ts";

export const has_pending_resolution = compose_state.has_pending_resolution;
export const get_pending_resolution = compose_state.get_pending_resolution;

export const MIN_RESOLUTION_MESSAGE_LENGTH = compose_state.MIN_RESOLUTION_MESSAGE_LENGTH;
export const meets_minimum_length = compose_state.meets_minimum_resolution_length;

export function is_message_requirement_enabled(): boolean {
    const setting = realm.realm_topic_resolution_message_requirement;
    return setting === "required" || setting === "optional";
}

export function is_message_required(): boolean {
    return realm.realm_topic_resolution_message_requirement === "required";
}

export function is_message_optional(): boolean {
    return realm.realm_topic_resolution_message_requirement === "optional";
}

export function is_resolve_via_move_allowed(): boolean {
    return realm.realm_topic_resolution_message_requirement !== "required";
}

export function clear_pending_resolution(): void {
    compose_state.clear_pending_resolution_state();
    // Remove the resolution banner if present
    compose_banner.clear_topic_resolution_banners();
    // Re-enable recipient area
    enable_recipient_area();
}

/**
 * Opens the compose box for entering a topic resolution message.
 * This is called when the user clicks the resolve topic button and
 * the organization setting requires or allows a resolution message.
 */
export function start_resolution_compose(
    message_id: number,
    stream_id: number,
    topic: string,
    report_errors_in_global_banner: boolean,
): void {
    // Store the pending resolution state
    compose_state.set_pending_resolution({
        message_id,
        stream_id,
        topic,
        report_errors_in_global_banner,
    });

    // Open the compose box targeting the same stream and topic
    compose_actions.start({
        message_type: "stream",
        stream_id,
        topic,
        trigger: "topic_resolution",
        keep_composebox_empty: true,
    });

    // Disable recipient area - user cannot change stream/topic in resolution mode
    disable_recipient_area();

    // Show the resolution banner
    show_resolution_banner();

    // Update send button status - in Required mode, button should start disabled
    compose_validate.validate_and_update_send_button_status();
}

/**
 * Lock the compose recipient area in resolution mode.
 *
 * Uses the HTML `inert` attribute on the entire recipient box so that
 * all children (topic input, stream widget, clear-topic button, etc.)
 * become completely non-interactive — no clicks, no focus, no typeahead.
 * The area still looks normal (no opacity change) so it reads as
 * informational rather than disabled.
 */
function disable_recipient_area(): void {
    // `inert` makes the entire subtree non-interactive: no focus, no events,
    // no typeahead. It is the standard HTML mechanism for this purpose.
    $("#compose-recipient").prop("inert", true);
}

/**
 * Re-enable the compose recipient area after resolution mode ends.
 */
function enable_recipient_area(): void {
    $("#compose-recipient").prop("inert", false);
}

function show_resolution_banner(): void {
    const is_required = is_message_required();
    compose_banner.show_topic_resolution_banner(
        is_required,
        cancel_resolution, // on_cancel
        is_required ? undefined : resolve_without_message, // on_resolve_without_message (only for optional mode)
    );
}

/**
 * Cancel the resolution flow and return compose box to normal state.
 * Does NOT close compose - just removes resolution mode.
 */
export function cancel_resolution(): void {
    if (!has_pending_resolution()) {
        return;
    }
    compose_state.clear_pending_resolution_state();
    compose_banner.clear_topic_resolution_banners();
    // Re-enable recipient area (don't close compose)
    enable_recipient_area();
    // Re-validate send button (may now allow scheduling, etc.)
    compose_validate.validate_and_update_send_button_status();
}
/**
 * Resolve the topic without a message (only allowed in "optional" mode).
 * Uses the topic-move API directly since there's no message to send.
 */
export function resolve_without_message(): void {
    if (!is_message_optional() || !has_pending_resolution()) {
        return;
    }

    const pending = compose_state.get_pending_resolution()!;
    const {message_id, topic} = pending;

    // Resolve the topic via the topic-move API (no message)
    const new_topic_name = resolved_topic.resolve_name(topic);
    void channel.patch({
        url: "/json/messages/" + message_id,
        data: {
            propagate_mode: "change_all",
            topic: new_topic_name,
            send_notification_to_old_thread: false,
            send_notification_to_new_thread: true,
        },
        success() {
            // Close compose only after API success to avoid losing state on failure
            clear_pending_resolution();
            compose_actions.cancel();
        },
        error(xhr) {
            // Un-lock recipient area if the API call fails so user can recover
            enable_recipient_area();
            compose_validate.validate_and_update_send_button_status();
            const error_msg = channel.xhr_error_message(
                $t({defaultMessage: "Failed to resolve topic"}),
                xhr,
            );
            ui_report.generic_embed_error(error_msg, 3500);
        },
    });
}

export function get_resolution_blocked_error(): string {
    return $t({
        defaultMessage:
            "Your organization requires a message when resolving topics. Please use the resolve topic button instead.",
    });
}

/**
 * Check if a topic edit indicates that our pending resolution was resolved
 * by another user, and if so, silently cancel our resolution compose mode.
 *
 * This is called from message_events.ts when topic edits are processed.
 */
export function check_and_cancel_if_topic_resolved(
    stream_id: number,
    old_topic: string,
    new_topic: string,
): void {
    if (!has_pending_resolution()) {
        return;
    }

    const pending = get_pending_resolution()!;

    // Check if this is our pending resolution's topic being resolved by someone else
    if (
        pending.stream_id === stream_id &&
        pending.topic.toLowerCase() === old_topic.toLowerCase() &&
        resolved_topic.is_resolved(new_topic)
    ) {
        // Topic was resolved by another user - silently exit resolution mode.
        // No banner or warning needed since user will see the resolved state naturally.
        cancel_resolution();
    }
}

/**
 * Update the resolution banner if the setting changes while user is composing.
 *
 * This handles the case where the setting changes from "optional" to "required"
 * (or vice versa) during compose. The banner updates seamlessly without losing
 * the user's typed message.
 */
export function update_banner_if_needed(): void {
    if (!has_pending_resolution()) {
        return;
    }

    // If setting changed to "not_requested", don't update the banner.
    // The user started the resolution compose under a specific mode (required/optional),
    // and we should let them complete that flow even if the admin disables the feature.
    // Only update when switching between "required" and "optional".
    if (!is_message_requirement_enabled()) {
        return;
    }

    // Re-render banner with current setting (required vs optional).
    // This preserves compose content - only the banner UI updates.
    show_resolution_banner();

    // Re-validate send button since requirements may have changed
    compose_validate.validate_and_update_send_button_status();
}
