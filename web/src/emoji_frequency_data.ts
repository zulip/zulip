import assert from "minimalistic-assert";

import * as emoji from "./emoji.ts";
import type {Message} from "./message_store.ts";
import * as people from "./people.ts";
import {current_user} from "./state_data.ts";
import * as typeahead from "./typeahead.ts";

const EMOJI_PICKER_ROW_LENGTH = 6;
const MAX_FREQUENTLY_USED_EMOJIS = 5 * EMOJI_PICKER_ROW_LENGTH;
const CURRENT_USER_REACTION_WEIGHT = 1;

// The maximum ratio of importance given to others' reactions
// compared to yours.
const IMPORTANCE_RATIO = 1 / 5;
const OTHER_USER_REACTION_WEIGHT = CURRENT_USER_REACTION_WEIGHT * IMPORTANCE_RATIO;
const POPULAR_EMOJIS_BONUS_WEIGHT = 2.4 * CURRENT_USER_REACTION_WEIGHT;
const MY_RECENT_CUSTOM_EMOJI_BONUS = CURRENT_USER_REACTION_WEIGHT * 6;
const OTHER_USER_RECENT_CUSTOM_EMOJI_BONUS = CURRENT_USER_REACTION_WEIGHT * 2;

// The maximum score contribution by others' usage of an emoji.
const OTHERS_SCORE_CAP = 40 * CURRENT_USER_REACTION_WEIGHT;

// The emoji at the beginning of a new row must have this score
// for that new row to be displayed.
const MINIMUM_SCORE_TO_DISPLAY_ROW = 1.5 * CURRENT_USER_REACTION_WEIGHT;

// Emojis that are not creating a new row must have this score
// to be part of the existing last row.
const MINIMUM_SCORE_TO_BE_PART_OF_ROW = 0.5;

type ReactionUsage = {
    // local_id is the ID reaction event handlers in emoji_frequency
    // send us to update our reactions_data data structure.

    // In case of emoji_type==="realm_emoji", it is a string
    // which looks like "realm_emoji,<database id of realm emoji>".
    // The reaction event object contains this as `emoji_code`.
    // Ref: https://zulip.com/api/get-events#reaction-add

    // Whereas in case of emoji_type==="unicode_emoji",
    // it is a string that looks like:
    // "unicode_emoji,<emoji_code>"

    local_id: string;
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

function get_local_id_for_unicode_emoji(info: {emoji_type: string; emoji_code: string}): string {
    const {emoji_type, emoji_code} = info;
    assert(emoji_type === "unicode_emoji");
    return [emoji_type, emoji_code].join(",");
}

function get_other_users_total_emoji_usage(): number {
    let count = 0;
    for (const usage of reaction_data.values()) {
        count += usage.message_ids.size - usage.current_user_reacted_message_ids.size;
    }
    return count;
}

export function show_reaction_data(): (ScoredEmoji & {
    my_count: number;
    others_count: number;
})[] {
    const others_count_for_all_emoji = get_other_users_total_emoji_usage();
    const data_for_emojis = [...reaction_data.values()].map((emoji_usage) => ({
        ...get_scored_emoji_for_usage(emoji_usage, others_count_for_all_emoji),
        my_count: emoji_usage.current_user_reacted_message_ids.size,
        others_count:
            emoji_usage.message_ids.size - emoji_usage.current_user_reacted_message_ids.size,
    }));
    return data_for_emojis.toSorted((a, b) => b.score - a.score);
}

// Here emoji_id denotes the id of the realm_emoji in the database.
// Ref: https://zulip.com/api/get-events#reaction-add
function calculate_recently_uploaded_custom_emoji_bonus(emoji_id: string): number {
    const data = emoji.get_server_realm_emoji_data();
    assert(data !== undefined);
    const current_custom_emoji = data[emoji_id];
    if (current_custom_emoji === undefined) {
        return 0;
    }

    const date_created_timestamp_in_seconds = current_custom_emoji.date_created;
    const seconds_till_now = Date.now() / 1000;
    const one_week_seconds_span = 60 * 60 * 24 * 7;
    if (seconds_till_now - date_created_timestamp_in_seconds > one_week_seconds_span) {
        return 0;
    }
    if (people.is_my_user_id(current_custom_emoji.author_id)) {
        return MY_RECENT_CUSTOM_EMOJI_BONUS;
    }
    return OTHER_USER_RECENT_CUSTOM_EMOJI_BONUS;
}

function compute_score(info: {
    usage: ReactionUsage;
    is_popular: boolean;
    others_count_for_current_emoji: number;
    my_count_for_current_emoji: number;
    others_count_for_all_emoji: number;
}): number {
    const {
        is_popular,
        others_count_for_current_emoji,
        my_count_for_current_emoji,
        others_count_for_all_emoji,
        usage,
    } = info;
    const popular_emoji_bonus = is_popular ? POPULAR_EMOJIS_BONUS_WEIGHT : 0;
    const custom_emoji_bonus = calculate_recently_uploaded_custom_emoji_bonus(usage.emoji_code);

    // We limit the total score contribution from other users so it asymptotically
    // approaches OTHERS_SCORE_CAP. For example, if the cap is 40, a user
    // reacting ~41 times (weighted at 1.0) is mathematically guaranteed to
    // outscore an infinite number of reactions from other users.
    const score =
        CURRENT_USER_REACTION_WEIGHT * Math.max(my_count_for_current_emoji - 0.5, 0) +
        Math.min(OTHER_USER_REACTION_WEIGHT, OTHERS_SCORE_CAP / others_count_for_all_emoji) *
            Math.max(others_count_for_current_emoji - 0.5, 0) +
        popular_emoji_bonus +
        custom_emoji_bonus;

    return score;
}

function get_scored_emoji_for_usage(
    usage: ReactionUsage,
    others_count_for_all_emoji: number,
): ScoredEmoji {
    const {emoji_code, emoji_type} = usage;
    const local_id = usage.local_id;

    const is_popular = popular_emoji_map.has(local_id);
    // This counts messages where only other users reacted with this emoji.
    const others_count_for_current_emoji =
        usage.message_ids.size - usage.current_user_reacted_message_ids.size;
    const my_count_for_current_emoji = usage.current_user_reacted_message_ids.size;

    const score = compute_score({
        usage,
        is_popular,
        my_count_for_current_emoji,
        others_count_for_current_emoji,
        others_count_for_all_emoji,
    });
    return {
        score,
        emoji_code,
        emoji_type,
    };
}

export function preferred_emoji_list(): typeahead.EmojiItem[] {
    const others_count_for_all_emoji = get_other_users_total_emoji_usage();
    const scored_emojis: ScoredEmoji[] = [...reaction_data.values()].map((emoji_usage) =>
        get_scored_emoji_for_usage(emoji_usage, others_count_for_all_emoji),
    );
    const sorted_scored_emojis = scored_emojis.toSorted((a, b) => b.score - a.score);

    const top_frequently_used_emojis = [];
    for (const [index, scored_emoji] of sorted_scored_emojis.entries()) {
        if (top_frequently_used_emojis.length === MAX_FREQUENTLY_USED_EMOJIS) {
            break;
        }

        const threshold =
            index % EMOJI_PICKER_ROW_LENGTH === 0
                ? MINIMUM_SCORE_TO_DISPLAY_ROW
                : MINIMUM_SCORE_TO_BE_PART_OF_ROW;
        if (scored_emoji.score < threshold) {
            break;
        }

        assert(scored_emoji !== undefined);
        top_frequently_used_emojis.push({
            emoji_type: scored_emoji.emoji_type,
            emoji_code: scored_emoji.emoji_code,
        });
    }

    return top_frequently_used_emojis;
}

export function handle_reaction_addition_on_message(info: {
    message_id: number;
    local_id: string;
    emoji_code: string;
    emoji_type: string;
    is_me: boolean;
}): void {
    const {message_id, local_id, emoji_code, emoji_type, is_me} = info;

    if (!reaction_data.has(local_id)) {
        reaction_data.set(local_id, {
            local_id,
            emoji_code,
            emoji_type,
            message_ids: new Set(),
            current_user_reacted_message_ids: new Set(),
        });
    }

    const reaction_usage = reaction_data.get(local_id);
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
    local_id: string;
    message_id: number;
    is_me: boolean;
}): void {
    const {local_id, message_id, is_me} = info;

    const reaction_usage = reaction_data.get(local_id);
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

export function remove_message_reactions(info: {message_id: number; local_ids: string[]}): void {
    const {message_id, local_ids} = info;

    for (const local_id of local_ids) {
        const reaction_usage = reaction_data.get(local_id);
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

function do_setup_for_popular_emojis(): void {
    const popular_emojis = typeahead.get_popular_emojis();
    for (const popular_emoji of popular_emojis) {
        const {emoji_code, emoji_type} = popular_emoji;
        const local_id = get_local_id_for_unicode_emoji({emoji_code, emoji_type});

        // Populate reaction_data with popular emojis, even if they have no usage
        // so that they are accounted for when preferred_emoji_list is called.
        reaction_data.set(local_id, {
            local_id,
            message_ids: new Set(),
            current_user_reacted_message_ids: new Set(),
            emoji_code,
            emoji_type,
        });
        popular_emoji_map.set(local_id, popular_emoji);
    }
}

function do_setup_for_realm_emojis(): void {
    const active_realm_emojis = emoji.active_realm_emojis;
    for (const realm_emoji of active_realm_emojis.values()) {
        const {id} = realm_emoji;
        // Same as reactions.
        const local_id = ["realm_emoji", id].join(",");
        // Populate reaction_data with custom emojis, even if they have no usage
        // so that they are accounted for when preferred_emoji_list is called.
        reaction_data.set(local_id, {
            local_id,
            message_ids: new Set(),
            current_user_reacted_message_ids: new Set(),
            // We follow the same convention used by the
            // reaction event response for realm emojis.
            emoji_code: id,
            emoji_type: "realm_emoji",
        });
    }
}

export function initialize_data(info: {messages: Message[]}): void {
    const {messages} = info;
    do_setup_for_popular_emojis();
    do_setup_for_realm_emojis();

    for (let i = messages.length - 1; i >= 0; i -= 1) {
        const message = messages[i];
        assert(message !== undefined);
        const message_reactions = message.clean_reactions.values();
        for (const emoji of message_reactions) {
            const local_id = emoji.local_id;
            if (!reaction_data.has(local_id)) {
                reaction_data.set(emoji.local_id, {
                    local_id: emoji.local_id,
                    emoji_code: emoji.emoji_code,
                    emoji_type: emoji.reaction_type,
                    message_ids: new Set(),
                    current_user_reacted_message_ids: new Set(),
                });
            }
            const reaction = reaction_data.get(local_id);
            assert(reaction !== undefined);
            reaction.message_ids.add(message.id);

            if (emoji.user_ids.includes(current_user.user_id)) {
                reaction.current_user_reacted_message_ids.add(message.id);
            }
        }
    }
}
