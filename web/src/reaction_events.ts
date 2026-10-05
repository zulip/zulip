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

// The reactions we still intend to act on, as one set of reaction event
// keys per batch of events -- held while the batch is being processed,
// and then for as long as a request it started is fetching messages. A
// reaction that is retracted before we act on it is dropped from
// whichever batches are holding it, so that we do not go on to notify
// about or count a reaction that no longer exists.
const pending_reactions_by_batch = new Map<number, Set<string>>();
let next_reaction_batch_id = 0;

// How many requests are fetching each message, and the reaction events
// that arrived for it in the meantime. Those reactions find no message
// to apply to, and the server may have built its response before they
// existed; once a message is cached, a fresher copy of it from a later
// response is ignored. So we apply them again when the message arrives.
const message_fetches_in_flight = new Map<number, number>();
const reaction_events_during_message_fetch = new Map<number, ServerReactionEvent[]>();

function apply_reaction_event(event: ServerReactionEvent): void {
    if (message_store.get(event.message_id) !== undefined) {
        // Another request may have cached the message while ours is still
        // fetching it. The reactions held for our request happened before
        // this one, so they must be applied first.
        apply_reactions_received_during_fetch(event.message_id);
    }
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
    if (
        message_fetches_in_flight.has(event.message_id) &&
        message_store.get(event.message_id) === undefined
    ) {
        const message_events_so_far =
            reaction_events_during_message_fetch.get(event.message_id) ?? [];
        message_events_so_far.push(event);
        reaction_events_during_message_fetch.set(event.message_id, message_events_so_far);
    }
    message_events.update_views_filtered_on_message_property(
        [event.message_id],
        "has-reaction",
        event.op === "add",
    );
}

function discard_pending_reaction(event: ReactionEvent): void {
    // Cancels whatever we still intended to do for a retracted reaction,
    // in the batch still being processed and in any request already
    // fetching its message.
    const key = reactions.get_reaction_event_key(event);
    for (const pending_keys of pending_reactions_by_batch.values()) {
        pending_keys.delete(key);
    }
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
    // What a reaction to your own message gets inside the app: an animation
    // on a message the user is looking at, or a count on the left sidebar's
    // Reactions row for one they have no other way to find. Both are
    // independent of the reaction notification settings: neither is an
    // interruption, so a user who declined notifications still gets them.
    if (message_viewport.is_message_on_screen(message)) {
        // The user is watching the reaction land, so it needs no
        // notification; the animation is what points at it.
        reactions.animate_reaction_arrival(event);
        return;
    }

    // Muted channels and topics are excluded from the count, as they are
    // from notifications.
    if (
        message.type === "stream" &&
        !user_topics.is_topic_visible_in_home(message.stream_id, message.topic)
    ) {
        return;
    }

    if (
        message_viewport.viewport_is_visible_and_focused() &&
        message_lists.current?.get(message.id) !== undefined
    ) {
        // In the conversation the user is reading, but scrolled out of
        // sight, and the notification just shown takes them to it, so
        // there is nothing left for the count to tell them.
        return;
    }

    reactions.increment_new_reaction_count(event);
}

function process_reactions_to_message(message: Message, message_reactions: ReactionEvent[]): void {
    // A failure to act on one message's reactions should not keep the
    // rest of the batch from being acted on.
    try {
        reaction_notifications.send_reaction_notifications(message, message_reactions);
        for (const event of message_reactions) {
            show_reaction_in_app(message, event);
        }
    } catch (error) {
        blueslip.error("Failed to process reactions to a message", {message_id: message.id}, error);
    }
}

function apply_reactions_received_during_fetch(message_id: number): void {
    // add_reaction and remove_reaction leave a message alone when it
    // already reflects the event, so this is safe even when the fetched
    // message already included these reactions.
    const events_during_fetch = reaction_events_during_message_fetch.get(message_id) ?? [];
    for (const event of events_during_fetch) {
        // As when they first arrived, a failure to apply one should not
        // keep the rest from being applied.
        try {
            if (event.op === "add") {
                reactions.add_reaction(event);
            } else {
                reactions.remove_reaction(event);
            }
        } catch (error) {
            blueslip.error(
                "Failed to apply a reaction event",
                {message_id: event.message_id, op: event.op},
                error,
            );
        }
    }
    reaction_events_during_message_fetch.delete(message_id);
}

function end_message_fetch(message_ids: number[]): void {
    for (const message_id of message_ids) {
        const remaining_fetches = message_fetches_in_flight.get(message_id)! - 1;
        if (remaining_fetches > 0) {
            message_fetches_in_flight.set(message_id, remaining_fetches);
        } else {
            message_fetches_in_flight.delete(message_id);
            reaction_events_during_message_fetch.delete(message_id);
        }
    }
}

function fetch_messages_for_reactions(
    reactions_by_message_id: Map<number, ReactionEvent[]>,
    batch_id: number,
    pending_keys: Set<string>,
): void {
    // A batch of events can carry reactions to several messages we do
    // not have cached, which is typical when a user returns to an idle
    // Zulip. We fetch all of those messages in a single request, rather
    // than one per reaction.
    const message_ids = reactions_by_message_id.keys().toArray();
    for (const message_id of message_ids) {
        message_fetches_in_flight.set(
            message_id,
            (message_fetches_in_flight.get(message_id) ?? 0) + 1,
        );
    }
    void channel.get({
        url: "/json/messages",
        data: {
            message_ids: JSON.stringify(message_ids),
            allow_empty_topic_name: true,
        },
        success(raw_data) {
            pending_reactions_by_batch.delete(batch_id);
            let fetched_messages: Map<number, Message>;
            try {
                const data = fetch_messages_response_schema.parse(raw_data);
                // Cache the messages regardless of whether we still want
                // to act on their reactions, so later reactions to them
                // skip this fetch.
                fetched_messages = new Map();
                for (const raw_message of data.messages) {
                    // A message we fail to process only loses its own
                    // reactions, not those of the rest of the response.
                    try {
                        fetched_messages.set(
                            raw_message.id,
                            message_helper.process_new_server_message(raw_message),
                        );
                    } catch (error) {
                        blueslip.error(
                            "Failed to process a message fetched for reactions",
                            {message_id: raw_message.id},
                            error,
                        );
                    }
                }
                for (const message_id of fetched_messages.keys()) {
                    apply_reactions_received_during_fetch(message_id);
                }
            } finally {
                end_message_fetch(message_ids);
            }

            for (const [message_id, reaction_events] of reactions_by_message_id) {
                // A reaction no longer pending was retracted while we were
                // fetching its message. A removal is not new activity, so
                // there is nothing to act on.
                const still_pending = reaction_events.filter((event) =>
                    pending_keys.delete(reactions.get_reaction_event_key(event)),
                );
                // A message the current user can no longer access --
                // deleted, or moved somewhere they cannot see it -- is
                // simply absent from the response.
                const message = fetched_messages.get(message_id);
                if (message !== undefined && still_pending.length > 0) {
                    process_reactions_to_message(message, still_pending);
                }
            }
            left_sidebar_navigation_area.update_my_reactions_row();
        },
        error() {
            pending_reactions_by_batch.delete(batch_id);
            end_message_fetch(message_ids);
            blueslip.info("Failed to fetch messages for reaction events");
        },
    });
}

export function received_reactions(events: ServerReactionEvent[]): void {
    // Apply every reaction to its message first, so that the rest of this
    // batch sees the message as it now is; the animation, for one, looks
    // for the reaction in the message's rendered reactions.
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

    // Reaction events are delivered to everyone who can see the message,
    // so filter out events that cannot notify before fetching uncached
    // messages. Whether the user is viewing the message is checked later,
    // once we have the message; uncached messages cannot be in the
    // visible feed.
    const can_notify = reaction_notifications.reaction_notifications_enabled();

    // This batch's pending reactions. We register every reaction we might
    // act on before acting on any of them, so that a reaction retracted by
    // a later event in the same batch is dropped from the batch: reacting
    // and unreacting while the user is away is not activity worth a
    // notification, a sound, or a count, whether or not we happen to have
    // the message cached.
    const pending_keys = new Set<string>();
    const batch_id = next_reaction_batch_id;
    next_reaction_batch_id += 1;
    pending_reactions_by_batch.set(batch_id, pending_keys);
    let fetch_owns_pending_keys = false;

    try {
        // The reactions this batch might act on, one entry per reaction,
        // keyed by reaction event key. For add → retract → add, the first
        // add is discarded and only the latest add is kept.
        const candidate_events = new Map<string, ReactionEvent>();
        for (const event of events) {
            if (event.op === "remove") {
                // Removals are processed even when we would not notify,
                // since they dismiss notifications shown for earlier
                // reactions, and drop retracted reactions from any batch
                // still holding them.
                discard_pending_reaction(event);
                reactions.decrement_new_reaction_count(event);
                reaction_notifications.remove_reaction_notification(event);
                continue;
            }

            if (event.op !== "add" || !can_notify || !is_reaction_event_meaningful(event)) {
                continue;
            }

            const key = reactions.get_reaction_event_key(event);
            pending_keys.add(key);
            // Delete before setting so that re-adding a reaction moves it
            // to the end of the map's iteration order, rather than keeping
            // the position of the add that was retracted. The notification
            // title credits reactors in arrival order, so the newest add
            // must sort last.
            candidate_events.delete(key);
            candidate_events.set(key, event);
        }

        // The whole batch has now been seen, so pending_keys holds exactly
        // the reactions that survived it. They are grouped by message, in
        // arrival order, so that each message gets one notification for
        // the batch, and the messages we need to fetch share one request.
        const reactions_by_message_id = new Map<number, ReactionEvent[]>();
        for (const [key, event] of candidate_events) {
            if (!pending_keys.has(key)) {
                // Retracted by a later event in this same batch.
                continue;
            }
            const message_reactions = reactions_by_message_id.get(event.message_id) ?? [];
            message_reactions.push(event);
            reactions_by_message_id.set(event.message_id, message_reactions);
        }

        const uncached_reactions_by_message_id = new Map<number, ReactionEvent[]>();
        for (const [message_id, message_reactions] of reactions_by_message_id) {
            const message = message_store.get(message_id);
            if (message === undefined) {
                uncached_reactions_by_message_id.set(message_id, message_reactions);
            } else {
                process_reactions_to_message(message, message_reactions);
            }
        }

        if (uncached_reactions_by_message_id.size > 0) {
            fetch_messages_for_reactions(uncached_reactions_by_message_id, batch_id, pending_keys);
            fetch_owns_pending_keys = true;
        }

        // Update the count in the reactions row.
        left_sidebar_navigation_area.update_my_reactions_row();
    } finally {
        // Once a request is on its way, it owns these keys and unregisters
        // them when it settles. Otherwise -- including if we threw partway
        // through the batch -- nothing else will, so we do it here.
        if (!fetch_owns_pending_keys) {
            pending_reactions_by_batch.delete(batch_id);
        }
    }
}
