import assert from "minimalistic-assert";

import type {Message} from "./message_store.ts";
import {current_user} from "./state_data.ts";
import type * as typeahead from "./typeahead.ts";

const EMOJI_PICKER_ROW_LENGTH = 6;
const MAX_FREQUENTLY_USED_EMOJIS = 5 * EMOJI_PICKER_ROW_LENGTH;
const CURRENT_USER_REACTION_WEIGHT = 5;
const POPULAR_EMOJIS_BONUS_WEIGHT = 12;

type ReactionUsage = {
    emoji_code: string;
    emoji_type: string;
    message_ids: Set<number>;
    current_user_reacted_message_ids: Set<number>;
};

type ScoredEmoji = {
    score: number;
    emoji_code: string;
    emoji_type: string;
};

const popular_emoji_map = new Map<string, typeahead.EmojiItem>();

// Exported for testing.
export const reaction_data = new Map<string, ReactionUsage>();

function get_key_for_popular_emoji_map(info: {emoji_type: string; emoji_code: string}): string {
    const {emoji_type, emoji_code} = info;
    return [emoji_type, emoji_code].join(",");
}

function compute_score(info: {
    is_popular: boolean;
    others_count: number;
    my_count: number;
}): number {
    const {is_popular, others_count, my_count} = info;
    const popular_emoji_bonus = is_popular ? POPULAR_EMOJIS_BONUS_WEIGHT : 0;

    const score = my_count * CURRENT_USER_REACTION_WEIGHT + others_count + popular_emoji_bonus;
    return score;
}

function get_scored_emoji_for_usage(usage: ReactionUsage): ScoredEmoji {
    const {emoji_code, emoji_type} = usage;
    const emoji_id = get_key_for_popular_emoji_map({emoji_code, emoji_type});

    const is_popular = popular_emoji_map.has(emoji_id);
    const others_count = usage.message_ids.size - usage.current_user_reacted_message_ids.size;
    const my_count = usage.current_user_reacted_message_ids.size;

    const score = compute_score({is_popular, my_count, others_count});
    return {
        score,
        emoji_code,
        emoji_type,
    };
}

export function preferred_emoji_list(): typeahead.EmojiItem[] {
    const scored_emojis: ScoredEmoji[] = [...reaction_data.values()].map((emoji_usage) =>
        get_scored_emoji_for_usage(emoji_usage),
    );
    const sorted_scored_emojis = scored_emojis.toSorted((a, b) => b.score - a.score);

    const top_frequently_used_emojis = [];
    for (const scored_emoji of sorted_scored_emojis) {
        if (top_frequently_used_emojis.length === MAX_FREQUENTLY_USED_EMOJIS || scored_emoji.score < 10) {
            break;
        }
        assert(scored_emoji !== undefined);
        top_frequently_used_emojis.push({
            emoji_type: scored_emoji.emoji_type,
            emoji_code: scored_emoji.emoji_code,
        });
    }

    const num_frequently_used_emojis =
        Math.floor(top_frequently_used_emojis.length / EMOJI_PICKER_ROW_LENGTH) *
        EMOJI_PICKER_ROW_LENGTH;

    return top_frequently_used_emojis.slice(0, num_frequently_used_emojis);
}

export function handle_reaction_addition_on_message(info: {
    message_id: number;
    emoji_id: string;
    emoji_code: string;
    emoji_type: string;
    is_me: boolean;
}): void {
    const {message_id, emoji_id, emoji_code, emoji_type, is_me} = info;

    if (!reaction_data.has(emoji_id)) {
        reaction_data.set(emoji_id, {
            emoji_code,
            emoji_type,
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

    if (is_me) {
        reaction_usage.current_user_reacted_message_ids.add(message_id);
    }
}

export function handle_reaction_removal_on_message(info: {
    emoji_id: string;
    message_id: number;
    is_me: boolean;
}): void {
    const {emoji_id, message_id, is_me} = info;

    const reaction_usage = reaction_data.get(emoji_id);
    if (reaction_usage === undefined) {
        return;
    }

    if (!reaction_usage.message_ids.has(message_id)) {
        return;
    }
    reaction_usage.message_ids.delete(message_id);

    if (is_me) {
        reaction_usage.current_user_reacted_message_ids.delete(message_id);
    }
}

export function remove_message_reactions(info: {message_id: number; emoji_ids: string[]}): void {
    const {message_id, emoji_ids} = info;

    for (const emoji_id of emoji_ids) {
        const reaction_usage = reaction_data.get(emoji_id);
        if (reaction_usage === undefined) {
            // This seems like it should be a continue, but I only
            // am moving the code for now.  We may end up with a
            // completely different algorithm here anyway.
            return;
        }
        reaction_usage.message_ids.delete(message_id);
        reaction_usage.current_user_reacted_message_ids.delete(message_id);
    }
}

export function initialize_data(info: {
    messages: Message[];
    popular_emojis: typeahead.EmojiItem[];
}): void {
    const {messages, popular_emojis} = info;

    for (const popular_emoji of popular_emojis) {
        const {emoji_code, emoji_type} = popular_emoji;
        const emoji_id = get_key_for_popular_emoji_map({emoji_code, emoji_type});
        popular_emoji_map.set(emoji_id, popular_emoji);
    }

    for (let i = messages.length - 1; i >= 0; i -= 1) {
        const message = messages[i];
        assert(message !== undefined);
        const message_reactions = message.clean_reactions.values();
        for (const emoji of message_reactions) {
            const emoji_id = emoji.local_id;
            if (!reaction_data.has(emoji_id)) {
                reaction_data.set(emoji_id, {
                    emoji_code: emoji.emoji_code,
                    emoji_type: emoji.reaction_type,
                    message_ids: new Set(),
                    current_user_reacted_message_ids: new Set(),
                });
            }
            const reaction = reaction_data.get(emoji_id);
            assert(reaction !== undefined);
            reaction.message_ids.add(message.id);

            if (emoji.user_ids.includes(current_user.user_id)) {
                reaction.current_user_reacted_message_ids.add(message.id);
            }
        }
    }
}
