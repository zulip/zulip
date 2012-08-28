import assert from "minimalistic-assert";

import * as emoji_frequency_data from "./emoji_frequency_data.ts";
import * as emoji_picker from "./emoji_picker.ts";
import * as message_store from "./message_store.ts";
import * as muted_users from "./muted_users.ts";
import * as reactions from "./reactions.ts";
import * as recent_view_messages_data from "./recent_view_messages_data.ts";
import {current_user} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as typeahead from "./typeahead.ts";
import * as user_topics from "./user_topics.ts";

// Returns true if the reaction is from:
// - A muted sender.
// - A muted channel.
// - A muted topic.
function should_ignore_reaction(
    message: message_store.Message,
    reaction_sender_id?: number,
): boolean {
    if (message.type === "stream") {
        if (user_topics.is_topic_muted(message.stream_id, message.topic)) {
            return true;
        }
        if (stream_data.is_muted(message.stream_id)) {
            return true;
        }
    }
    if (reaction_sender_id && muted_users.is_user_muted(reaction_sender_id)) {
        return true;
    }
    return false;
}

export function update_frequently_used_emojis_list(): void {
    const emojis = emoji_frequency_data.preferred_emoji_list();
    typeahead.set_frequently_used_emojis(emojis);
    emoji_picker.rebuild_catalog();
}

/*
    This function assumes reactions.add_reaction has already been called.
    TODO: Split reactions.ts into data and UI modules, so that this can
    be called from directly from reactions.add_reaction without creating
    an import cycle.
*/
export function update_emoji_frequency_on_add_reaction_event(event: reactions.ReactionEvent): void {
    const message_id = event.message_id;
    const message = message_store.get(message_id);
    if (message === undefined) {
        return;
    }
    if (should_ignore_reaction(message, event.user_id)) {
        return;
    }
    const emoji_id = reactions.get_local_reaction_id(event);
    const clean_reaction_object = message.clean_reactions.get(emoji_id);

    assert(clean_reaction_object !== undefined);
    const emoji_code = clean_reaction_object.emoji_code;
    const emoji_type = clean_reaction_object.reaction_type;
    const is_me = event.user_id === current_user.user_id;

    emoji_frequency_data.handle_reaction_addition_on_message({
        message_id,
        emoji_id,
        emoji_code,
        emoji_type,
        is_me,
    });

    update_frequently_used_emojis_list();
}

export function update_emoji_frequency_on_remove_reaction_event(
    event: reactions.ReactionEvent,
): void {
    const message_id = event.message_id;
    const message = message_store.get(message_id);
    if (message === undefined) {
        return;
    }
    if (should_ignore_reaction(message, event.user_id)) {
        return;
    }

    const emoji_id = reactions.get_local_reaction_id(event);
    const is_me = event.user_id === current_user.user_id;

    emoji_frequency_data.handle_reaction_removal_on_message({
        emoji_id,
        message_id,
        is_me,
    });

    update_frequently_used_emojis_list();
}

export function update_emoji_frequency_on_messages_deletion(message_ids: number[]): void {
    for (const message_id of message_ids) {
        const message = message_store.get(message_id);
        // It's normal to receive events about the deletion of
        // messages that this client doesn't have locally cached. No
        // action is required, since only messages that are locally
        // cached are represented in our emoji frequency data.
        if (message === undefined) {
            continue;
        }
        if (should_ignore_reaction(message)) {
            continue;
        }
        assert(message !== undefined);
        const message_reactions = [...message.clean_reactions.values()];
        const emoji_ids = message_reactions.map((reaction) => reaction.local_id);

        emoji_frequency_data.remove_message_reactions({
            message_id,
            emoji_ids,
        });
    }
    update_frequently_used_emojis_list();
}

export function initialize_frequently_used_emojis(): void {
    const message_data = recent_view_messages_data.recent_view_messages_data;
    const messages = message_data.all_messages_after_mute_filtering();
    const popular_emojis = typeahead.get_popular_emojis();

    emoji_frequency_data.initialize_data({
        messages,
        popular_emojis,
    });
    update_frequently_used_emojis_list();
}
