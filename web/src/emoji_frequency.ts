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

const CURRENT_USER_REACTION_WEIGHT = 5;
const BUILTIN_EMOJI_BONUS = 18;

const EMOJIS_PER_ROW = 6;
const MAX_ROWS = 5;
const MIN_SCORE_TO_SHOW = 10;

export const reaction_data = new Map<string, ReactionUsage>();

function is_builtin_emoji(emoji_code: string): boolean {
    return typeahead.get_popular_emojis().some((emoji) => emoji.emoji_code === emoji_code);
}

export function update_frequently_used_emojis_list(): void {
    const scored_emojis = [...reaction_data.values()].map((emoji_usage) => {
        let effective_score = emoji_usage.score;

        if (is_builtin_emoji(emoji_usage.emoji_code)) {
            effective_score += BUILTIN_EMOJI_BONUS;
        }

        return {
            ...emoji_usage,
            effective_score,
        };
    });

    scored_emojis.sort((a, b) => b.effective_score - a.effective_score);

    const selected: typeof scored_emojis = [];

    for (let i = 0; i < scored_emojis.length; i += EMOJIS_PER_ROW) {
        const row = scored_emojis.slice(i, i + EMOJIS_PER_ROW);

        if (row.length < EMOJIS_PER_ROW) {
            break;
        }

        const last_in_row = row.at(-1);
        if (!last_in_row || last_in_row.effective_score < MIN_SCORE_TO_SHOW) {
            break;
        }

        selected.push(...row);

        if (selected.length >= EMOJIS_PER_ROW * MAX_ROWS) {
            break;
        }
    }

    typeahead.set_frequently_used_emojis(
        selected.map((emoji_usage) => ({
            emoji_type: emoji_usage.emoji_type,
            emoji_code: emoji_usage.emoji_code,
        })),
    );

    emoji_picker.rebuild_catalog();
}

export function update_emoji_frequency_on_add_reaction_event(event: reactions.ReactionEvent): void {
    const message = message_store.get(event.message_id);
    if (!message) {
        return;
    }

    const emoji_id = reactions.get_local_reaction_id(event);
    const clean_reaction = message.clean_reactions.get(emoji_id);
    assert(clean_reaction !== undefined);

    if (!reaction_data.has(emoji_id)) {
        reaction_data.set(emoji_id, {
            score: 0,
            emoji_code: clean_reaction.emoji_code,
            emoji_type: clean_reaction.reaction_type,
            message_ids: new Set(),
            current_user_reacted_message_ids: new Set(),
        });
    }

    const usage = reaction_data.get(emoji_id);
    if (!usage) {
        return;
    }

    if (usage.message_ids.has(message.id)) {
        return;
    }

    usage.message_ids.add(message.id);

    if (event.user_id === current_user.user_id) {
        usage.score += CURRENT_USER_REACTION_WEIGHT;
        usage.current_user_reacted_message_ids.add(message.id);
    } else {
        usage.score += 1;
    }

    update_frequently_used_emojis_list();
}

export function update_emoji_frequency_on_remove_reaction_event(
    event: reactions.ReactionEvent,
): void {
    const message = message_store.get(event.message_id);
    if (!message) {
        return;
    }

    const emoji_id = reactions.get_local_reaction_id(event);
    const usage = reaction_data.get(emoji_id);

    if (!usage?.message_ids.has(message.id)) {
        return;
    }

    usage.message_ids.delete(message.id);

    if (event.user_id === current_user.user_id) {
        usage.score -= CURRENT_USER_REACTION_WEIGHT;
        usage.current_user_reacted_message_ids.delete(message.id);
    } else {
        usage.score -= 1;
    }

    update_frequently_used_emojis_list();
}

export function update_emoji_frequency_on_messages_deletion(message_ids: number[]): void {
    for (const message_id of message_ids) {
        const message = message_store.get(message_id);
        if (!message) {
            continue;
        }

        for (const emoji of message.clean_reactions.values()) {
            const usage = reaction_data.get(emoji.local_id);
            if (!usage) {
                continue;
            }

            if (usage.message_ids.delete(message_id)) {
                usage.score -= 1;
            }

            if (usage.current_user_reacted_message_ids.delete(message_id)) {
                usage.score -= CURRENT_USER_REACTION_WEIGHT - 1;
            }
        }
    }

    update_frequently_used_emojis_list();
}

export function initialize_frequently_used_emojis(): void {
    const messages = all_messages_data.all_messages_data.all_messages_after_mute_filtering();

    for (const message of messages) {
        for (const emoji_reaction of message.clean_reactions.values()) {
            if (!reaction_data.has(emoji_reaction.local_id)) {
                reaction_data.set(emoji_reaction.local_id, {
                    score: 0,
                    emoji_code: emoji_reaction.emoji_code,
                    emoji_type: emoji_reaction.reaction_type,
                    message_ids: new Set(),
                    current_user_reacted_message_ids: new Set(),
                });
            }

            const usage = reaction_data.get(emoji_reaction.local_id);
            if (!usage) {
                continue;
            }

            usage.score += 1;
            usage.message_ids.add(message.id);

            if (emoji_reaction.user_ids.includes(current_user.user_id)) {
                usage.score += CURRENT_USER_REACTION_WEIGHT - 1;
                usage.current_user_reacted_message_ids.add(message.id);
            }
        }
    }

    update_frequently_used_emojis_list();
}
