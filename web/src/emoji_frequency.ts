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

const MAX_FREQUENTLY_USED_EMOJIS = 12;
const CURRENT_USER_REACTION_WEIGHT = 5;
export const reaction_data = new Map<string, ReactionUsage>();

export function update_frequently_used_emojis_list(): void {
    // 1. Get the list of special emojis
    const built_in_emojis = new Set(typeahead.popular_emojis);

    const frequently_used_emojis = [...reaction_data.values()].sort((a, b) => {
        let score_a = a.score;
        let score_b = b.score;

        // 2. Give +18 Bonus points if it is a built-in emoji
        if (built_in_emojis.has(a.emoji_code)) {
            score_a += 18;
        }
        if (built_in_emojis.has(b.emoji_code)) {
            score_b += 18;
        }

        // 3. Compare the new scores
        return score_b - score_a;
    });

    const top_frequently_used_emojis = [];
    const popular_emojis = typeahead.get_popular_emojis();

    for (const emoji of frequently_used_emojis) {
        if (
            top_frequently_used_emojis.length + popular_emojis.length ===
            MAX_FREQUENTLY_USED_EMOJIS
        ) {
            break;
        }
        if (emoji === undefined) {
            continue;
        }
        top_frequently_used_emojis.push({
            emoji_code: emoji.emoji_code,
            emoji_type: emoji.emoji_type,
        });
    }

    // Filter out duplicates
    const final_frequently_used_emoji_list = top_frequently_used_emojis.filter((emoji) => {
        const is_duplicate = popular_emojis.some(
            (popular_emoji) => popular_emoji.emoji_code === emoji.emoji_code,
        );
        return !is_duplicate;
    });

    typeahead.set_frequently_used_emojis(final_frequently_used_emoji_list);
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

    if (clean_reaction_object === undefined) {
        return;
    }

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
    if (reaction_usage === undefined) {
        return;
    }

    if (reaction_usage.message_ids.has(message_id)) {
        return;
    }
    reaction_usage.message_ids.add(message_id);

    if (event.user_id === current_user.user_id) {
        reaction_usage.score += CURRENT_USER_REACTION_WEIGHT;
        reaction_usage.current_user_reacted_message_ids.add(message_id);
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
        reaction_usage.current_user_reacted_message_ids.delete(message_id);
    } else {
        reaction_usage.score -= 1;
    }
    update_frequently_used_emojis_list();
}

export function update_emoji_frequency_on_messages_deletion(message_ids: number[]): void {
    for (const message_id of message_ids) {
        const message = message_store.get(message_id);
        if (message === undefined) {
            continue;
        }
        const message_reactions = message.clean_reactions.values();
        for (const emoji of message_reactions) {
            const emoji_id = emoji.local_id;
            const reaction_usage = reaction_data.get(emoji_id);
            if (reaction_usage === undefined) {
                continue;
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

    for (let i = messages.length - 1; i >= 0; i -= 1) {
        const message = messages[i];
        if (message === undefined) {
            continue;
        }
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
            if (reaction === undefined) {
                continue;
            }
            reaction.score += 1;
            // FIX: Use brackets ["id"] to satisfy TS4111 strict index signature
            reaction.message_ids.add(message["id"]);

            if (emoji.user_ids.includes(current_user.user_id)) {
                reaction.score += CURRENT_USER_REACTION_WEIGHT - 1;
                reaction.current_user_reacted_message_ids.add(message["id"]);
            }
        }
    }
    update_frequently_used_emojis_list();
}