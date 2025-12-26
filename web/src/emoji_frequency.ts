import assert from "minimalistic-assert";

import * as all_messages_data from "./all_messages_data.ts";
import * as emoji from "./emoji.ts";
import * as emoji_picker from "./emoji_picker.ts";
import * as message_store from "./message_store.ts";
import type {Message} from "./message_store.ts";
import * as reactions from "./reactions.ts";
import {current_user} from "./state_data.ts";
import * as typeahead from "./typeahead.ts";

/*
    Weighted Emoji Frequency Algorithm:
    
    Base scoring (per message):
    - 5 points for each message where you used that emoji
    - 1 point for each message where someone else used that emoji

    Bonuses:
    - 18-point bonus for the 6 built-in popular emoji (not guaranteed to show)
    - 30-point bonus for custom emoji you uploaded (first week only)
    - 10-point bonus for custom emoji uploaded by others (first week only)

    Display:
    - Show complete rows (6 emojis each) where the last emoji scores >= 10
    - Maximum of 5 rows (30 emojis)
*/

// Scoring constants
const CURRENT_USER_REACTION_WEIGHT = 5;
const OTHER_USER_REACTION_WEIGHT = 1;
const BUILTIN_EMOJI_BONUS = 18;
const CUSTOM_EMOJI_SELF_UPLOADED_BONUS = 30;
const CUSTOM_EMOJI_OTHER_UPLOADED_BONUS = 10;
const CUSTOM_EMOJI_BONUS_DURATION_MS = 7 * 24 * 60 * 60 * 1000; // 1 week

// Display constants
const EMOJIS_PER_ROW = 6;
const MAX_ROWS = 5;
const MIN_SCORE_THRESHOLD = 10;

export type ReactionUsage = {
    base_score: number;
    bonus_score: number;
    total_score: number;
    emoji_code: string;
    emoji_type: string;
    emoji_name?: string;
    message_ids: Set<number>;
    current_user_reacted_message_ids: Set<number>;
    author_id?: number;
    created_at?: number;
};

export const reaction_data = new Map<string, ReactionUsage>();

function get_builtin_emoji_bonus(emoji_code: string): number {
    if (typeahead.popular_emojis.includes(emoji_code)) {
        return BUILTIN_EMOJI_BONUS;
    }
    return 0;
}

function get_custom_emoji_bonus(
    emoji_type: string,
    author_id: number | undefined,
    created_at: number | undefined,
): number {
    if (emoji_type !== "realm_emoji") {
        return 0;
    }
    if (created_at === undefined) {
        return 0;
    }
    const now = Date.now();
    const age_ms = now - created_at;
    if (age_ms > CUSTOM_EMOJI_BONUS_DURATION_MS) {
        return 0;
    }
    if (author_id === current_user.user_id) {
        return CUSTOM_EMOJI_SELF_UPLOADED_BONUS;
    }
    return CUSTOM_EMOJI_OTHER_UPLOADED_BONUS;
}

function calculate_total_score(usage: ReactionUsage): number {
    const builtin_bonus = get_builtin_emoji_bonus(usage.emoji_code);
    const custom_bonus = get_custom_emoji_bonus(
        usage.emoji_type,
        usage.author_id,
        usage.created_at,
    );
    usage.bonus_score = builtin_bonus + custom_bonus;
    usage.total_score = usage.base_score + usage.bonus_score;
    return usage.total_score;
}

function calculate_rows_to_show(sorted_emojis: ReactionUsage[]): number {
    let rows_to_show = 0;
    for (let row = 1; row <= MAX_ROWS; row++) {
        const last_index_in_row = row * EMOJIS_PER_ROW - 1;
        if (last_index_in_row >= sorted_emojis.length) {
            break;
        }
        const last_emoji_in_row = sorted_emojis[last_index_in_row];
        if (last_emoji_in_row && last_emoji_in_row.total_score >= MIN_SCORE_THRESHOLD) {
            rows_to_show = row;
        } else {
            break;
        }
    }
    return rows_to_show;
}

function get_custom_emoji_metadata(
    emoji_code: string,
    emoji_type: string,
): {author_id?: number; created_at?: number} {
    if (emoji_type !== "realm_emoji") {
        return {};
    }
    const realm_emoji = emoji.active_realm_emojis.get(emoji_code);
    if (realm_emoji && "id" in realm_emoji) {
        const id_num = Number.parseInt(realm_emoji.id, 10);
        if (!Number.isNaN(id_num)) {
            return {created_at: id_num * 1000};
        }
    }
    return {};
}

export function update_frequently_used_emojis_list(): void {
    for (const usage of reaction_data.values()) {
        calculate_total_score(usage);
    }

    const sorted_emojis = [...reaction_data.values()].toSorted(
        (a, b) => b.total_score - a.total_score,
    );

    const rows_to_show = calculate_rows_to_show(sorted_emojis);
    const emojis_to_show = rows_to_show * EMOJIS_PER_ROW;

    const frequently_used_emojis = sorted_emojis.slice(0, emojis_to_show).map((usage) => ({
        emoji_type: usage.emoji_type,
        emoji_code: usage.emoji_code,
    }));

    typeahead.set_frequently_used_emojis(frequently_used_emojis);
    emoji_picker.rebuild_catalog();
}

export function update_emoji_frequency_on_add_reaction_event(
    event: reactions.ReactionEvent,
): void {
    const message_id = event.message_id;
    const message = message_store.get(message_id);
    if (message === undefined) {
        return;
    }

    const emoji_id = reactions.get_local_reaction_id(event);
    const clean_reaction_object = message.clean_reactions.get(emoji_id);

    assert(clean_reaction_object !== undefined);

    if (!reaction_data.has(emoji_id)) {
        const metadata = get_custom_emoji_metadata(
            clean_reaction_object.emoji_code,
            clean_reaction_object.reaction_type,
        );

        reaction_data.set(emoji_id, {
            base_score: 0,
            bonus_score: 0,
            total_score: 0,
            emoji_code: clean_reaction_object.emoji_code,
            emoji_type: clean_reaction_object.reaction_type,
            emoji_name: clean_reaction_object.emoji_name,
            message_ids: new Set(),
            current_user_reacted_message_ids: new Set(),
            ...metadata,
        });
    }

    const usage = reaction_data.get(emoji_id);
    assert(usage !== undefined);

    if (usage.message_ids.has(message_id)) {
        return;
    }
    usage.message_ids.add(message_id);

    if (event.user_id === current_user.user_id) {
        usage.base_score += CURRENT_USER_REACTION_WEIGHT;
        usage.current_user_reacted_message_ids.add((message as Message).id);
    } else {
        usage.base_score += OTHER_USER_REACTION_WEIGHT;
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
    const usage = reaction_data.get(emoji_id);
    if (usage === undefined) {
        return;
    }

    if (!usage.message_ids.has(message_id)) {
        return;
    }
    usage.message_ids.delete(message_id);

    if (event.user_id === current_user.user_id) {
        usage.base_score -= CURRENT_USER_REACTION_WEIGHT;
        usage.current_user_reacted_message_ids.delete((message as Message).id);
    } else {
        usage.base_score -= OTHER_USER_REACTION_WEIGHT;
    }

    update_frequently_used_emojis_list();
}

export function update_emoji_frequency_on_messages_deletion(message_ids: number[]): void {
    for (const message_id of message_ids) {
        const message = message_store.get(message_id);
        assert(message !== undefined);

        const message_reactions = message.clean_reactions.values();
        for (const reaction of message_reactions) {
            const emoji_id = reaction.local_id;
            const usage = reaction_data.get(emoji_id);
            if (usage === undefined) {
                continue;
            }

            if (usage.message_ids.delete(message_id)) {
                usage.base_score -= OTHER_USER_REACTION_WEIGHT;
            }
            if (usage.current_user_reacted_message_ids.delete(message_id)) {
                usage.base_score -= CURRENT_USER_REACTION_WEIGHT - OTHER_USER_REACTION_WEIGHT;
            }
        }
    }

    update_frequently_used_emojis_list();
}

export function initialize_frequently_used_emojis(): void {
    const message_data = all_messages_data.all_messages_data;
    const messages = message_data.all_messages_after_mute_filtering();

    for (let i = messages.length - 1; i >= 0; i -= 1) {
        const message = messages[i];
        assert(message !== undefined);

        const message_reactions = message.clean_reactions.values();
        for (const reaction of message_reactions) {
            const emoji_id = reaction.local_id;

            if (!reaction_data.has(emoji_id)) {
                const metadata = get_custom_emoji_metadata(
                    reaction.emoji_code,
                    reaction.reaction_type,
                );

                reaction_data.set(emoji_id, {
                    base_score: 0,
                    bonus_score: 0,
                    total_score: 0,
                    emoji_code: reaction.emoji_code,
                    emoji_type: reaction.reaction_type,
                    emoji_name: reaction.emoji_name,
                    message_ids: new Set(),
                    current_user_reacted_message_ids: new Set(),
                    ...metadata,
                });
            }

            const usage = reaction_data.get(emoji_id);
            assert(usage !== undefined);

            usage.base_score += OTHER_USER_REACTION_WEIGHT;
            usage.message_ids.add((message as Message).id);

            if (reaction.user_ids.includes(current_user.user_id)) {
                usage.base_score += CURRENT_USER_REACTION_WEIGHT - OTHER_USER_REACTION_WEIGHT;
                usage.current_user_reacted_message_ids.add((message as Message).id);
            }
        }
    }

    update_frequently_used_emojis_list();
}
