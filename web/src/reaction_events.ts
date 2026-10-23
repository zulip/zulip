import * as blueslip from "./blueslip.ts";
import * as emoji_frequency from "./emoji_frequency.ts";
import * as message_events from "./message_events.ts";
import * as message_store from "./message_store.ts";
import type {Message} from "./message_store.ts";
import * as muted_users from "./muted_users.ts";
import * as reaction_notifications from "./reaction_notifications.ts";
import * as reactions from "./reactions.ts";
import type {ReactionEvent} from "./reactions.ts";
import {current_user} from "./state_data.ts";

// Server events are not validated before they reach us, so op may be
// something other than "add" or "remove".
export type ServerReactionEvent = ReactionEvent & {op: string};

function apply_reaction_event(event: ServerReactionEvent): void {
    switch (event.op) {
        case "add":
            reactions.add_reaction(event);
            emoji_frequency.update_emoji_frequency_on_add_reaction_event(event);
            break;
        case "remove":
            reactions.remove_reaction(event);
            emoji_frequency.update_emoji_frequency_on_remove_reaction_event(event);
            break;
        default:
            blueslip.error("Unexpected event type reaction/" + event.op);
            return;
    }
    message_events.update_views_filtered_on_message_property(
        [event.message_id],
        "has-reaction",
        event.op === "add",
    );
}

function is_reaction_event_meaningful(event: ReactionEvent): boolean {
    // Whether a reaction event is activity to point the current user at,
    // decided from the event alone.

    // A reaction by the current user is never meaningful.
    if (event.user_id === current_user.user_id) {
        return false;
    }

    // Nor is one by a user they have muted.
    if (muted_users.is_user_muted(event.user_id)) {
        return false;
    }

    // Only reactions to the current user's own messages are meaningful.
    return event.message_sender_id === current_user.user_id;
}

function process_reactions_to_message(message: Message, message_reactions: ReactionEvent[]): void {
    // A failure to act on one message's reactions should not keep the
    // rest of the batch from being acted on.
    try {
        reaction_notifications.send_reaction_notifications(message, message_reactions);
    } catch (error) {
        blueslip.error("Failed to process reactions to a message", {message_id: message.id}, error);
    }
}

function get_pending_reactions(events: ServerReactionEvent[]): ServerReactionEvent[] {
    // The reactions worth acting on that still stand, in arrival order
    // with a re-added one last, as the notification title credits the
    // newest reactor first. One retracted later is dropped, since reacting
    // and unreacting while the user is away is not worth a notification.
    if (!reaction_notifications.reaction_notifications_enabled()) {
        return [];
    }
    const pending_reactions = new Map<string, ServerReactionEvent>();
    for (const event of events) {
        // A failure to process one reaction should not keep the rest from
        // being processed.
        try {
            const key = reactions.get_reaction_event_key(event);
            pending_reactions.delete(key);
            if (event.op === "add" && is_reaction_event_meaningful(event)) {
                pending_reactions.set(key, event);
            }
        } catch (error) {
            blueslip.error(
                "Failed to process a reaction event",
                {message_id: event.message_id, op: event.op},
                error,
            );
        }
    }
    return pending_reactions.values().toArray();
}

export function received_reactions(events: ServerReactionEvent[]): void {
    // Apply every reaction to its message first, so that the rest of this
    // batch sees the message as it now is.
    for (const event of events) {
        // A failure to apply one reaction should not keep the rest of
        // the batch from being applied.
        try {
            apply_reaction_event(event);
        } catch (error) {
            blueslip.error(
                "Failed to apply a reaction event",
                {message_id: event.message_id, op: event.op},
                error,
            );
        }
    }

    for (const event of events) {
        if (event.op !== "remove") {
            continue;
        }
        // Handled even when we would not notify, since a removal dismisses
        // an earlier notification.
        try {
            reaction_notifications.remove_reaction_notification(event);
        } catch (error) {
            blueslip.error(
                "Failed to process a reaction event",
                {message_id: event.message_id, op: event.op},
                error,
            );
        }
    }

    // Reaction events are delivered to everyone who can see the message,
    // so filter out events that cannot notify using the event alone. The
    // checks that need the message, such as whether the user is viewing
    // it, come later. Grouped by message, in arrival order, so that each
    // message gets one notification for the batch.
    const reactions_by_message_id = Map.groupBy(
        get_pending_reactions(events),
        (event) => event.message_id,
    );

    for (const [message_id, message_reactions] of reactions_by_message_id) {
        // A message this client has not cached leaves nothing to build a
        // notification from.
        const message = message_store.get(message_id);
        if (message !== undefined) {
            process_reactions_to_message(message, message_reactions);
        }
    }
}
