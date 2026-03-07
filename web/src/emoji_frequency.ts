import assert from "minimalistic-assert";

import * as all_messages_data from "./all_messages_data.ts";
import * as emoji from "./emoji.ts";
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
    /**
     * Records the exact weight applied when each message was first scored.
     * This ensures symmetric removal even if the emoji's bonus window has
     * expired since the reaction was added (new → old transition).
     */
    message_add_weights: Map<number, number>;
};

const MAX_FREQUENTLY_USED_EMOJIS = 12;
const CURRENT_USER_REACTION_WEIGHT = 5;
const BONUS_PERIOD_DAYS = 7;
const NEW_EMOJI_AUTHOR_BONUS_WEIGHT = 30;
const NEW_EMOJI_OTHER_BONUS_WEIGHT = 10;
export const reaction_data = new Map<string, ReactionUsage>();

/**
 * Returns the reaction weight for an emoji, applying new-emoji bonuses for realm
 * emoji uploaded within the last 7 days. Bonus weights replace (not augment) the
 * normal 5/1 weights. The tier (30 vs 10) is determined by who uploaded the emoji,
 * not by who is reacting: 30 if the current user uploaded it, 10 otherwise.
 */
function get_emoji_reaction_weight(
    emoji_code: string,
    emoji_type: string,
    is_current_user_reaction: boolean,
): number {
    if (emoji_type !== "realm_emoji") {
        return is_current_user_reaction ? CURRENT_USER_REACTION_WEIGHT : 1;
    }

    const server_emoji_data = emoji.get_server_realm_emoji_data();
    const emoji_data = server_emoji_data[emoji_code];
    // Use === undefined, not !created_at: the epoch sentinel is 0 (falsy), so
    // a truthiness check would mishandle pre-migration emoji.
    if (emoji_data === undefined || emoji_data.created_at === undefined) {
        return is_current_user_reaction ? CURRENT_USER_REACTION_WEIGHT : 1;
    }

    // Deactivated emoji are hidden from the picker; don't boost them.
    if (emoji_data.deactivated) {
        return is_current_user_reaction ? CURRENT_USER_REACTION_WEIGHT : 1;
    }

    // Guard against clock skew: treat negative ages as 0.
    const emoji_age_ms = Math.max(0, Date.now() - emoji_data.created_at);
    const emoji_age_days = emoji_age_ms / (1000 * 60 * 60 * 24);

    if (emoji_age_days > BONUS_PERIOD_DAYS) {
        return is_current_user_reaction ? CURRENT_USER_REACTION_WEIGHT : 1;
    }

    // Bonus tier is by authorship. null author_id (pre-author-tracking emoji)
    // always fails the comparison, falling through to the 10-point path.
    if (emoji_data.author_id === current_user.user_id) {
        return NEW_EMOJI_AUTHOR_BONUS_WEIGHT;
    }
    return NEW_EMOJI_OTHER_BONUS_WEIGHT;
}

export function update_frequently_used_emojis_list(): void {
    const frequently_used_emojis = [...reaction_data.values()].toSorted(
        (a, b) => b.score - a.score,
    );

    const top_frequently_used_emojis = [];
    let popular_emojis = typeahead.get_popular_emojis();
    for (const emoji of frequently_used_emojis) {
        if (
            top_frequently_used_emojis.length + popular_emojis.length ===
            MAX_FREQUENTLY_USED_EMOJIS
        ) {
            break;
        }
        assert(emoji !== undefined);
        top_frequently_used_emojis.push({
            emoji_type: emoji.emoji_type,
            emoji_code: emoji.emoji_code,
        });
        popular_emojis = popular_emojis.filter(
            (popular_emoji) => popular_emoji.emoji_code !== emoji.emoji_code,
        );
    }

    const final_frequently_used_emoji_list = [...top_frequently_used_emojis, ...popular_emojis];
    typeahead.set_frequently_used_emojis(
        final_frequently_used_emoji_list.slice(0, MAX_FREQUENTLY_USED_EMOJIS),
    );
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
            message_add_weights: new Map(),
        });
    }

    const reaction_usage = reaction_data.get(emoji_id);
    assert(reaction_usage !== undefined);

    if (reaction_usage.message_ids.has(message_id)) {
        return;
    }
    reaction_usage.message_ids.add(message_id);

    const is_current_user = event.user_id === current_user.user_id;
    const weight = get_emoji_reaction_weight(
        clean_reaction_object.emoji_code,
        clean_reaction_object.reaction_type,
        is_current_user,
    );
    // Store the add-time weight so removal is symmetric even if the emoji ages out.
    reaction_usage.message_add_weights.set(message_id, weight);
    reaction_usage.score += weight;

    if (is_current_user) {
        reaction_usage.current_user_reacted_message_ids.add(message.id);
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

    const is_current_user = event.user_id === current_user.user_id;
    // Use the stored add-time weight for symmetric removal. The ?? fallback
    // handles the rare race where the add event predates module initialization.
    const weight =
        reaction_usage.message_add_weights.get(message_id) ??
        get_emoji_reaction_weight(reaction_usage.emoji_code, reaction_usage.emoji_type, is_current_user);
    reaction_usage.message_add_weights.delete(message_id);
    reaction_usage.score -= weight;

    if (is_current_user) {
        reaction_usage.current_user_reacted_message_ids.delete(message.id);
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
                // Same symmetric-removal logic as the remove handler.
                const was_current_user =
                    reaction_usage.current_user_reacted_message_ids.has(message_id);
                const weight =
                    reaction_usage.message_add_weights.get(message_id) ??
                    get_emoji_reaction_weight(
                        reaction_usage.emoji_code,
                        reaction_usage.emoji_type,
                        was_current_user,
                    );
                reaction_usage.message_add_weights.delete(message_id);
                reaction_usage.current_user_reacted_message_ids.delete(message_id);
                reaction_usage.score -= weight;
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
        for (const emoji of message_reactions) {
            const emoji_id = emoji.local_id;
            if (!reaction_data.has(emoji_id)) {
                reaction_data.set(emoji_id, {
                    score: 0,
                    emoji_code: emoji.emoji_code,
                    emoji_type: emoji.reaction_type,
                    message_ids: new Set(),
                    current_user_reacted_message_ids: new Set(),
                    message_add_weights: new Map(),
                });
            }
            const reaction = reaction_data.get(emoji_id);
            assert(reaction !== undefined);

            const is_current_user = emoji.user_ids.includes(current_user.user_id);
            const weight = get_emoji_reaction_weight(
                emoji.emoji_code,
                emoji.reaction_type,
                is_current_user,
            );
            reaction.score += weight;
            reaction.message_ids.add(message.id);
            reaction.message_add_weights.set(message.id, weight);

            if (is_current_user) {
                reaction.current_user_reacted_message_ids.add(message.id);
            }
        }
    }
    update_frequently_used_emojis_list();
}
