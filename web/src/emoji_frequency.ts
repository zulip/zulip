import assert from "minimalistic-assert";

import * as typeahead from "../shared/src/typeahead.ts";

import * as all_messages_data from "./all_messages_data.ts";
import * as emoji_picker from "./emoji_picker.ts";
import * as message_store from "./message_store.ts";
import * as reactions from "./reactions.ts";
import {current_user} from "./state_data.ts";

export type ReactionData = {
    score: number;
    emoji_code: string;
    message_ids: Set<number>;
    current_user_reacted_message_ids: Set<number>;
};

const reaction_data = new Map<string, ReactionData>();

function update_frequently_used_emojis_list(): void {
    const frequently_used_emoji_codes = [...reaction_data.values()]
        .sort((a, b) => b.score - a.score)
        .slice(0, 6)
        .map((r) => r.emoji_code);
    typeahead.set_frequently_used_emojis([
        ...frequently_used_emoji_codes,
        ...typeahead.popular_emojis,
    ]);
    emoji_picker.rebuild_catalog();
}

export function update_emoji_frequency_on_add_reaction_event(event: reactions.ReactionEvent): void {
    const message_id = event.message_id;
    const message = message_store.get(message_id);

    if (message === undefined) {
        // If we don't have the message in cache, do nothing; if we
        // ever fetch it from the server, it'll come with the
        // latest reactions attached
        return;
    }

    const user_id = event.user_id;
    const emoji_id = reactions.get_local_reaction_id(event);
    const clean_reaction_object = message.clean_reactions.get(emoji_id);

    assert(clean_reaction_object !== undefined);

    if (!reaction_data.has(emoji_id)) {
        reaction_data.set(emoji_id, {
            score: 0,
            emoji_code: clean_reaction_object.emoji_code,
            message_ids: new Set(),
            current_user_reacted_message_ids: new Set(),
        });
    }

    const reaction_usage = reaction_data.get(emoji_id);
    assert(reaction_usage !== undefined);

    if (reaction_usage.message_ids.has(message_id)) {
        return;
    }
    reaction_usage.message_ids.add(message_id);

    if (user_id === current_user.user_id) {
        reaction_usage.score += 5;
        reaction_usage.current_user_reacted_message_ids.add(message.id);
    } else {
        reaction_usage.score += 1;
    }
    update_frequently_used_emojis_list();
}

export function update_emoji_frequency_on_remove_reaction_event(
    event: reactions.ReactionEvent,
): void {
    const message_id = event.message_id;
    const message = message_store.get(message_id);

    if (message === undefined) {
        // If we don't have the message in cache, do nothing; if we
        // ever fetch it from the server, it'll come with the
        // latest reactions attached
        return;
    }

    const user_id = event.user_id;
    const emoji_id = reactions.get_local_reaction_id(event);

    const reaction_usage = reaction_data.get(emoji_id);
    if (reaction_usage === undefined) {
        return;
    }

    if (!reaction_usage.message_ids.has(message_id)) {
        return;
    }
    reaction_usage.message_ids.delete(message_id);

    if (user_id === current_user.user_id) {
        reaction_usage.score -= 5;
        reaction_usage.current_user_reacted_message_ids.delete(message.id);
    } else {
        reaction_usage.score -= 1;
    }
    update_frequently_used_emojis_list();
}

export function initialize_frequently_used_emojis(): void {
    const message_data = all_messages_data.all_messages_data;
    const messages = message_data.all_messages();

    for (let i = messages.length - 1; i >= 0; i -= 1) {
        const message = messages[i];
        assert(message !== undefined);
        const message_reactions = reactions.get_message_reactions(message);
        for (const emoji of message_reactions) {
            const emoji_id = emoji.local_id;
            if (!reaction_data.has(emoji_id)) {
                reaction_data.set(emoji_id, {
                    score: emoji.count,
                    emoji_code: emoji.emoji_code,
                    message_ids: new Set(),
                    current_user_reacted_message_ids: new Set(),
                });
            }
            const reaction = reaction_data.get(emoji_id);
            assert(reaction !== undefined);
            reaction.message_ids.add(message.id);

            if (emoji.user_ids.includes(current_user.user_id)) {
                reaction.score += 5;
                reaction.current_user_reacted_message_ids.add(message.id);
            }
        }
    }
    update_frequently_used_emojis_list();
}
