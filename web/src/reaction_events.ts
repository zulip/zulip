import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as emoji_frequency from "./emoji_frequency.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as message_events from "./message_events.ts";
import * as message_helper from "./message_helper.ts";
import * as message_lists from "./message_lists.ts";
import * as message_store from "./message_store.ts";
import {raw_message_schema} from "./message_store.ts";
import type {Message} from "./message_store.ts";
import * as message_viewport from "./message_viewport.ts";
import * as muted_users from "./muted_users.ts";
import * as reaction_notifications from "./reaction_notifications.ts";
import * as reactions from "./reactions.ts";
import type {ReactionEvent} from "./reactions.ts";
import {current_user} from "./state_data.ts";
import * as user_topics from "./user_topics.ts";

const fetch_messages_response_schema = z.object({
    messages: z.array(raw_message_schema),
});

// Server events are not validated before they reach us, so op may be
// something other than "add" or "remove".
export type ServerReactionEvent = ReactionEvent & {op: string};

// Messages being fetched to act on reactions to them, each by one
// request, mapped to the reaction events for the message since then, in
// arrival order: first the reactions that prompted the request, then
// every event that arrives. Once the message is cached, replaying them
// brings it up to date however old our copy is, and they say which
// reactions still stand; see settle_message_fetch.
const message_fetches = new Map<number, ServerReactionEvent[]>();

export function clear_for_testing(): void {
    message_fetches.clear();
}

function apply_reaction_event(event: ServerReactionEvent): void {
    if (event.op !== "add" && event.op !== "remove") {
        blueslip.error("Unexpected event type reaction/" + event.op);
        return;
    }
    const held_events = message_fetches.get(event.message_id);
    if (held_events === undefined) {
        apply_reaction_to_message(event);
    } else {
        // Applied when the fetch settles, after the events held before
        // it, so that each event is applied once and in order.
        held_events.push(event);
    }
}

function apply_reaction_to_message(event: ServerReactionEvent): void {
    // Emoji frequency and the views filtered on has:reaction read the
    // message's reactions, so they are updated after the reaction is
    // applied to the message.
    if (event.op === "add") {
        reactions.add_reaction(event);
        emoji_frequency.update_emoji_frequency_on_add_reaction_event(event);
    } else {
        reactions.remove_reaction(event);
        emoji_frequency.update_emoji_frequency_on_remove_reaction_event(event);
    }
    message_events.update_views_filtered_on_message_property(
        [event.message_id],
        "has-reaction",
        event.op === "add",
    );
}

function is_reaction_event_meaningful(event: ReactionEvent): boolean {
    // Whether a reaction event is activity to point the current user at,
    // decided from the event alone so that a reaction we would ignore
    // costs nothing for a message this client does not have cached.

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

function show_reaction_in_app(message: Message, event: ReactionEvent): void {
    // A count on the left sidebar's Reactions row, for a reaction the user
    // has no other way to find.

    // Muted channels and topics are excluded from the count, as they are
    // from notifications.
    if (!user_topics.is_message_visible_in_home(message)) {
        return;
    }

    if (
        message_viewport.viewport_is_visible_and_focused() &&
        message_lists.current?.get(message.id) !== undefined
    ) {
        // On screen, or scrolled out of sight in the list the user is
        // reading, so the count has nothing to point them to.
        return;
    }

    reactions.increment_new_reaction_count(event);
}

function process_reactions_to_message(message: Message, message_reactions: ReactionEvent[]): void {
    // A failure to act on one message's reactions should not keep the
    // rest of the batch from being acted on.
    try {
        reaction_notifications.send_reaction_notifications(message, message_reactions);
    } catch (error) {
        blueslip.error("Failed to process reactions to a message", {message_id: message.id}, error);
    }

    // Nor should a failure to notify keep the reactions from being shown
    // in the app.
    try {
        for (const event of message_reactions) {
            show_reaction_in_app(message, event);
        }
    } catch (error) {
        blueslip.error(
            "Failed to show reactions to a message in the app",
            {message_id: message.id},
            error,
        );
    }
}

function get_pending_reactions(events: ServerReactionEvent[]): ServerReactionEvent[] {
    // The reactions worth acting on that still stand, in arrival order
    // with a re-added one last, as the notification title credits the
    // newest reactor first. One retracted later is dropped, since reacting
    // and unreacting while the user is away is not worth a notification.
    // Checked when called, so that muting a held reaction's reactor
    // meanwhile keeps it out.
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

function settle_message_fetch(message: Message): void {
    // Called once the message is cached, by our request or anything else.
    const message_events = message_fetches.get(message.id)!;
    message_fetches.delete(message.id);
    // Applying a reaction ignores an event the message already reflects,
    // such as the reactions that prompted the fetch.
    for (const event of message_events) {
        // A failure to apply one should not stop the rest.
        try {
            apply_reaction_to_message(event);
        } catch (error) {
            blueslip.error(
                "Failed to apply a reaction event",
                {message_id: event.message_id, op: event.op},
                error,
            );
        }
    }
    // A failure here should not keep the other messages of the batch or
    // the request from settling.
    let pending_reactions: ReactionEvent[];
    try {
        pending_reactions = get_pending_reactions(message_events);
    } catch (error) {
        blueslip.error("Failed to process reactions to a message", {message_id: message.id}, error);
        return;
    }
    if (pending_reactions.length > 0) {
        process_reactions_to_message(message, pending_reactions);
    }
}

function settle_message_fetches(message_ids: number[]): void {
    // Called once a request finishes, whether or not it succeeded. A
    // message still not cached, because the request failed or the user
    // can no longer access it, has nothing to apply its reactions to.
    for (const message_id of message_ids) {
        if (!message_fetches.has(message_id)) {
            // Settled earlier, when something else cached it.
            continue;
        }
        const message = message_store.get(message_id);
        if (message === undefined) {
            message_fetches.delete(message_id);
        } else {
            settle_message_fetch(message);
        }
    }
    left_sidebar_navigation_area.update_my_reactions_row();
}

function fetch_messages_for_reactions(
    reactions_by_message_id: Map<number, ServerReactionEvent[]>,
): void {
    // One request for all of a batch's uncached messages, of which a user
    // returning to an idle Zulip can have many.
    const message_ids = reactions_by_message_id.keys().toArray();
    for (const [message_id, message_reactions] of reactions_by_message_id) {
        message_fetches.set(message_id, [...message_reactions]);
    }
    void channel.get({
        url: "/json/messages",
        data: {
            message_ids: JSON.stringify(message_ids),
            allow_empty_topic_name: true,
        },
        success(raw_data) {
            try {
                const data = fetch_messages_response_schema.parse(raw_data);
                // Cache every message, even one with no reactions left to
                // act on, so that later reactions to it need no fetch.
                for (const raw_message of data.messages) {
                    // A message we fail to process only loses its own
                    // reactions, not those of the rest of the response.
                    try {
                        message_helper.process_new_server_message(raw_message);
                    } catch (error) {
                        blueslip.error(
                            "Failed to process a message fetched for reactions",
                            {message_id: raw_message.id},
                            error,
                        );
                    }
                }
            } finally {
                settle_message_fetches(message_ids);
            }
        },
        error() {
            blueslip.info("Failed to fetch messages for reaction events");
            // A message something else cached meanwhile can still settle.
            settle_message_fetches(message_ids);
        },
    });
}

export function received_reactions(events: ServerReactionEvent[]): void {
    // Apply every reaction to its message first, so that the rest of this
    // batch sees the message as it now is. Reactions to a message being
    // fetched are held instead, and applied when the fetch settles.
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
        // an earlier notification. A fetch of the message holds the
        // removal too, and drops the reaction when it settles.
        try {
            reactions.decrement_new_reaction_count(event);
            reaction_notifications.remove_reaction_notification(event);
        } catch (error) {
            blueslip.error(
                "Failed to process a reaction event",
                {message_id: event.message_id, op: event.op},
                error,
            );
        }
    }

    // Reaction events reach everyone who can see the message, so drop what
    // cannot notify before fetching anything. Checks that need the message
    // come later. Grouped by message, in arrival order, so that each
    // message gets one notification for the batch, and the messages we
    // need to fetch share one request.
    const reactions_by_message_id = Map.groupBy(
        get_pending_reactions(events),
        (event) => event.message_id,
    );

    // Every message the batch touched, since any event for a message can
    // settle its fetch.
    const message_ids = new Set(events.map((event) => event.message_id));
    const uncached_reactions_by_message_id = new Map<number, ServerReactionEvent[]>();
    for (const message_id of message_ids) {
        const message = message_store.get(message_id);
        const message_reactions = reactions_by_message_id.get(message_id) ?? [];
        if (message_fetches.has(message_id)) {
            // This batch's events are held with the fetch's. Once
            // something else has cached the message, there is no need to
            // wait for our request.
            if (message !== undefined) {
                settle_message_fetch(message);
            }
        } else if (message_reactions.length > 0) {
            if (message === undefined) {
                uncached_reactions_by_message_id.set(message_id, message_reactions);
            } else {
                process_reactions_to_message(message, message_reactions);
            }
        }
    }

    if (uncached_reactions_by_message_id.size > 0) {
        fetch_messages_for_reactions(uncached_reactions_by_message_id);
    }

    // Update the count in the reactions row.
    left_sidebar_navigation_area.update_my_reactions_row();
}
