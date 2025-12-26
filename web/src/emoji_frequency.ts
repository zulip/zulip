import assert from "minimalistic-assert";

import * as all_messages_data from "./all_messages_data.ts";
import * as emoji_picker from "./emoji_picker.ts";
import * as message_store from "./message_store.ts";
import * as reactions from "./reactions.ts";
import {current_user} from "./state_data.ts";
import * as typeahead from "./typeahead.ts";

export type ReactionUsage = {
    score: number;
    emoji_code: string;
    emoji_type: string;
    message_ids: Set<number>;
    current_user_reacted_message_ids: Set<number>;
};

const EMOJI_PICKER_ROW_LENGTH = 6;
const MAX_FREQUENTLY_USED_EMOJIS = 5 * EMOJI_PICKER_ROW_LENGTH;
const CURRENT_USER_REACTION_WEIGHT = 5;
const POPULAR_EMOJIS_BONUS_WEIGHT = 18;
export const reaction_data = new Map<string, ReactionUsage>();

export function update_frequently_used_emojis_list(): void {
    const frequently_used_emojis = [...reaction_data.values()].toSorted(
        (a, b) => b.score - a.score,
    );

    const top_frequently_used_emojis = [];
    for (const emoji of frequently_used_emojis) {
        if (top_frequently_used_emojis.length === MAX_FREQUENTLY_USED_EMOJIS || emoji.score < 10) {
            break;
        }
        assert(emoji !== undefined);
        top_frequently_used_emojis.push({
            emoji_type: emoji.emoji_type,
            emoji_code: emoji.emoji_code,
        });
    }

    const num_frequently_used_emojis =
        Math.floor(top_frequently_used_emojis.length / EMOJI_PICKER_ROW_LENGTH) *
        EMOJI_PICKER_ROW_LENGTH;
    const final_frequently_used_emoji_list = top_frequently_used_emojis.slice(
        0,
        num_frequently_used_emojis,
    );
    typeahead.set_frequently_used_emojis(final_frequently_used_emoji_list);
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
            emoji_type: clean_reaction_object.reaction_type,
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
    const messages = message_data.all_messages_after_mute_filtering();

    //
    for (const {emoji_code, emoji_type} of typeahead.get_popular_emojis()) {
        const emoji_id = [emoji_type, emoji_code].join(",");
        if (!reaction_data.has(emoji_id)) {
            reaction_data.set(emoji_id, {
                score: POPULAR_EMOJIS_BONUS_WEIGHT,
                emoji_code,
                emoji_type,
                message_ids: new Set(),
                current_user_reacted_message_ids: new Set(),
            });
        }
        const reaction = reaction_data.get(emoji_id);
        assert(reaction !== undefined);
        reaction.score += POPULAR_EMOJIS_BONUS_WEIGHT;
    }

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
                    emoji_type: emoji.reaction_type,
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
