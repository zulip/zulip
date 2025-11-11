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

const MAX_FREQUENTLY_USED_EMOJI = 12;
const CURRENT_USER_REACTION_WEIGHT = 5;
export const reaction_data = new Map<string, ReactionData>();

export function update_frequently_used_emojis_list(): void {
    const frequently_used_emojis = [...reaction_data.values()].toSorted(
        (a, b) => b.score - a.score,
    );

    const top_frequently_used_emoji_codes = [];
    let popular_emojis = [...typeahead.popular_emojis];
    for (const emoji of frequently_used_emojis) {
        if (
            top_frequently_used_emoji_codes.length + popular_emojis.length ===
            MAX_FREQUENTLY_USED_EMOJI
        ) {
            break;
        }
        assert(emoji !== undefined);
        top_frequently_used_emoji_codes.push(emoji.emoji_code);
        if (popular_emojis.includes(emoji.emoji_code)) {
            popular_emojis = popular_emojis.filter((emoji_code) => emoji_code !== emoji.emoji_code);
        }
    }

    typeahead.set_frequently_used_emojis([...top_frequently_used_emoji_codes, ...popular_emojis]);
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

    if (event.user_id === current_user.user_id) {
        reaction_usage.score += CURRENT_USER_REACTION_WEIGHT;
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
        return;
    }

    const emoji_id = reactions.get_local_reaction_id(event);
    const reaction_usage = reaction_data.get(emoji_id);
    if (reaction_usage === undefined) {
        return;
    }

    if (!reaction_usage.message_ids.has(message_id)) {
        return;
    }
    reaction_usage.message_ids.delete(message_id);

    if (event.user_id === current_user.user_id) {
        reaction_usage.score -= CURRENT_USER_REACTION_WEIGHT;
        reaction_usage.current_user_reacted_message_ids.delete(message.id);
    } else {
        reaction_usage.score -= 1;
    }
    update_frequently_used_emojis_list();
}

export function update_emoji_frequency_on_messages_deletion(message_ids: number[]): void {
    for (const message_id of message_ids) {
        const message = message_store.get(message_id);
        assert(message !== undefined);
        const message_reactions = message.clean_reactions.values();
        for (const emoji of message_reactions) {
            const emoji_id = emoji.local_id;
            const reaction_usage = reaction_data.get(emoji_id);
            if (reaction_usage === undefined) {
                return;
            }
            if (reaction_usage.message_ids.delete(message_id)) {
                reaction_usage.score -= 1;
            }
            if (reaction_usage.current_user_reacted_message_ids.delete(message_id)) {
                reaction_usage.score -= CURRENT_USER_REACTION_WEIGHT - 1;
            }
        }
    }
    update_frequently_used_emojis_list();
}

export function initialize_frequently_used_emojis(): void {
    const message_data = all_messages_data.all_messages_data;
    const messages = message_data.all_messages();

    for (let i = messages.length - 1; i >= 0; i -= 1) {
        const message = messages[i];
        assert(message !== undefined);
        const message_reactions = message.clean_reactions.values();
        for (const emoji of message_reactions) {
            const emoji_id = emoji.local_id;
            if (!reaction_data.has(emoji_id)) {
                reaction_data.set(emoji_id, {
                    score: 0,
                    emoji_code: emoji.emoji_code,
                    message_ids: new Set(),
                    current_user_reacted_message_ids: new Set(),
                });
            }
            const reaction = reaction_data.get(emoji_id);
            assert(reaction !== undefined);
            reaction.score += 1;
            reaction.message_ids.add(message.id);
                        if (emoji.user_ids.includes(current_user.user_id)) {
                reaction.score += CURRENT_USER_REACTION_WEIGHT - 1;
                reaction.current_user_reacted_message_ids.add(message.id);
            }
        }
    }
    update_frequently_used_emojis_list();
}