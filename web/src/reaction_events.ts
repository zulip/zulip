import * as blueslip from "./blueslip.ts";
import * as emoji_frequency from "./emoji_frequency.ts";
import * as message_events from "./message_events.ts";
import * as reactions from "./reactions.ts";
import type {ReactionEvent} from "./reactions.ts";

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

export function received_reactions(events: ServerReactionEvent[]): void {
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
}
