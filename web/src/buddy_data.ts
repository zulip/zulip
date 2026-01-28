import assert from "minimalistic-assert";

import * as hash_util from "./hash_util.ts";
import {$t} from "./i18n.ts";
import * as message_lists from "./message_lists.ts";
import * as muted_users from "./muted_users.ts";
import * as narrow_state from "./narrow_state.ts";
import {page_params} from "./page_params.ts";
import * as peer_data from "./peer_data.ts";
import * as people from "./people.ts";
import * as presence from "./presence.ts";
import * as stream_data from "./stream_data.ts";
import * as timerender from "./timerender.ts";
import * as unread from "./unread.ts";
import {user_settings} from "./user_settings.ts";
import * as user_status from "./user_status.ts";
import * as util from "./util.ts";

/*
   This is the main model code for building the buddy list.
   We also rely on presence.js to compute the actual presence
   for users.  We glue in other "people" data and do
   filtering/sorting of the data that we'll send into the view.
*/

export let max_size_before_shrinking = 600;

export function rewire_max_size_before_shrinking(value: typeof max_size_before_shrinking): void {
    max_size_before_shrinking = value;
}

export let max_channel_size_to_show_all_subscribers = 75;

export function rewire_max_channel_size_to_show_all_subscribers(
    value: typeof max_channel_size_to_show_all_subscribers,
): void {
    max_channel_size_to_show_all_subscribers = value;
}

let is_searching_users = false;

export function get_is_searching_users(): boolean {
    return is_searching_users;
}

export function set_is_searching_users(val: boolean): void {
    is_searching_users = val;
}

export function get_user_circle_class(user_id: number, use_deactivated_circle = false): string {
    if (use_deactivated_circle) {
        return "user-circle-deactivated";
    }

    const status = presence.get_status(user_id);

    switch (status) {
        case "active":
            return "user-circle-active";
        case "idle":
            return "user-circle-idle";
        default:
            return "user-circle-offline";
    }
}

export function level(user_id: number): number {
    if (people.is_my_user_id(user_id) && !is_searching_users) {
        return 0;
    }

    const status = presence.get_status(user_id);

    switch (status) {
        case "active":
            return 1;
        case "idle":
            return 2;
        default:
            return 3;
    }
}

export let user_matches_narrow_using_loaded_data = (
    user_id: number,
    pm_ids: Set<number>,
    stream_id: number | undefined,
): boolean => {
    if (stream_id) {
        return stream_data.is_user_loaded_and_subscribed(stream_id, user_id);
    }
    if (pm_ids.size > 0) {
        return pm_ids.has(user_id) || people.is_my_user_id(user_id);
    }
    return false;
};

export function rewire_user_matches_narrow_using_loaded_data(
    value: typeof user_matches_narrow_using_loaded_data,
): void {
    user_matches_narrow_using_loaded_data = value;
}

function get_num_unread(user_id: number): number {
    return unread.num_unread_for_user_ids_string(user_id.toString());
}

export function compare_function(
    a: number,
    b: number,
    stream_id: number | undefined,
    pm_ids: Set<number>,
    conversation_participants: Set<number>,
): number {
    // 1. Unread messages priority (Highest)
    const a_unread = get_num_unread(a);
    const b_unread = get_num_unread(b);
    if (a_unread > 0 && b_unread === 0) {
        return -1;
    }
    if (a_unread === 0 && b_unread > 0) {
        return 1;
    }

    // 2. Conversation participants priority
    const a_is_participant = conversation_participants.has(a);
    const b_is_participant = conversation_participants.has(b);
    if (a_is_participant && !b_is_participant) {
        return -1;
    }
    if (!a_is_participant && b_is_participant) {
        return 1;
    }

    // 3. Relevance to view (Matches narrow)
    const a_matches = user_matches_narrow_using_loaded_data(a, pm_ids, stream_id);
    const b_matches = user_matches_narrow_using_loaded_data(b, pm_ids, stream_id);
    if (a_matches && !b_matches) {
        return -1;
    }
    if (!a_matches && b_matches) {
        return 1;
    }

    // 4. Presence Level (Active > Idle > Offline)
    const level_a = level(a);
    const level_b = level(b);
    const diff = level_a - level_b;
    if (diff !== 0) {
        return diff;
    }

    // 5. Alphabetical Fallback (Ensures stability and satisfies TypeScript)
    const person_a = people.maybe_get_user_by_id(a);
    const person_b = people.maybe_get_user_by_id(b);
    return util.strcmp(person_a?.full_name ?? "", person_b?.full_name ?? "");
}

export function sort_users(user_ids: number[], conversation_participants: Set<number>): number[] {
    const stream_id = narrow_state.stream_id(narrow_state.filter(), true);
    const pm_ids_set = narrow_state.pm_ids_set();
    user_ids.sort((a, b) =>
        compare_function(a, b, stream_id, pm_ids_set, conversation_participants),
    );
    return user_ids;
}

export function user_last_seen_time_status(
    user_id: number,
    missing_data_callback?: (user_id: number) => void,
): string {
    const status = presence.get_status(user_id);
    if (status === "active") {
        return $t({defaultMessage: "Active now"});
    }

    if (status === "idle") {
        return $t({defaultMessage: "Idle"});
    }

    const last_active_date = presence.last_active_date(user_id);
    if (last_active_date === undefined) {
        assert(page_params.presence_history_limit_days_for_web_app === 365);

        if (missing_data_callback !== undefined) {
            missing_data_callback(user_id);
            return "";
        }
        return $t({defaultMessage: "Not active in the last year"});
    }
    return timerender.last_seen_status_from_date(last_active_date);
}

export type BuddyUserInfo = {
    href: string;
    name: string;
    user_id: number;
    profile_picture: string;
    status_emoji_info: user_status.UserStatusEmojiInfo | undefined;
    is_current_user: boolean;
    num_unread: number;
    user_circle_class: string;
    status_text: string | undefined;
    has_status_text: boolean;
    user_list_style: {
        COMPACT: boolean;
        WITH_STATUS: boolean;
        WITH_AVATAR: boolean;
    };
    should_add_guest_user_indicator: boolean;
    faded?: boolean;
};

export function info_for(user_id: number, direct_message_recipients: Set<number>): BuddyUserInfo {
    const is_deactivated = !people.is_person_active(user_id);
    const is_dm = direct_message_recipients.has(user_id);

    const user_circle_class = get_user_circle_class(user_id, is_deactivated && is_dm);
    const person = people.get_by_user_id(user_id);

    const status_emoji_info = user_status.get_status_emoji(user_id);
    const status_text = user_status.get_status_text(user_id);
    const user_list_style_value = user_settings.user_list_style;
    const user_list_style = {
        COMPACT: user_list_style_value === 1,
        WITH_STATUS: user_list_style_value === 2,
        WITH_AVATAR: user_list_style_value === 3,
    };

    return {
        href: hash_util.pm_with_url(person.user_id.toString()),
        name: person.full_name,
        user_id,
        status_emoji_info,
        profile_picture: people.small_avatar_url_for_person(person),
        is_current_user: people.is_my_user_id(user_id),
        num_unread: get_num_unread(user_id),
        user_circle_class,
        status_text,
        has_status_text: Boolean(status_text),
        user_list_style,
        should_add_guest_user_indicator: people.should_add_guest_user_indicator(user_id),
    };
}

export type TitleData = {
    first_line: string;
    second_line: string | undefined;
    third_line: string;
    show_you?: boolean;
    is_deactivated?: boolean;
};

export function get_title_data(
    user_ids_string: string,
    is_group: boolean,
    should_show_status: boolean,
): TitleData {
    if (is_group) {
        return {
            first_line: people.format_recipients(user_ids_string, "long"),
            second_line: "",
            third_line: "",
        };
    }

    const user_id = Number.parseInt(user_ids_string, 10);
    const person = people.get_by_user_id(user_id);
    const is_deactivated = !people.is_person_active(user_id);

    if (person.is_bot) {
        const bot_owner = people.get_bot_owner_user(person);

        if (bot_owner) {
            const bot_owner_name = $t(
                {defaultMessage: "Owner: {name}"},
                {name: bot_owner.full_name},
            );

            return {
                first_line: person.full_name,
                second_line: bot_owner_name,
                third_line: is_deactivated
                    ? $t({defaultMessage: "This bot has been deactivated."})
                    : "",
                is_deactivated,
            };
        }

        return {
            first_line: person.full_name,
            second_line: "",
            third_line: "",
        };
    }

    const last_seen = user_last_seen_time_status(user_id);
    const is_my_user = people.is_my_user_id(user_id);

    if (is_deactivated) {
        return {
            first_line: person.full_name,
            second_line: $t({defaultMessage: "This user has been deactivated."}),
            third_line: "",
            show_you: is_my_user,
            is_deactivated,
        };
    }

    if (user_status.get_status_text(user_id)) {
        return {
            first_line: person.full_name,
            second_line: should_show_status ? user_status.get_status_text(user_id) : "",
            third_line: last_seen,
            show_you: is_my_user,
        };
    }

    return {
        first_line: person.full_name,
        second_line: last_seen,
        third_line: "",
        show_you: is_my_user,
    };
}

export function get_items_for_users(user_ids: number[]): BuddyUserInfo[] {
    const direct_message_recipients = narrow_state.pm_ids_set();
    return user_ids.map((user_id) => info_for(user_id, direct_message_recipients));
}

function user_is_recently_active(user_id: number): boolean {
    return level(user_id) <= 2;
}

function maybe_shrink_list(
    user_ids: number[],
    user_filter_text: string,
    conversation_participants: Set<number>,
): number[] {
    if (user_ids.length <= max_size_before_shrinking) {
        return user_ids;
    }

    if (user_filter_text) {
        return user_ids;
    }

    const pm_ids_set = narrow_state.pm_ids_set();
    const stream_id = narrow_state.stream_id(narrow_state.filter(), true);
    const filter_by_stream_id =
        stream_id &&
        peer_data.get_subscriber_count(stream_id) <= max_channel_size_to_show_all_subscribers;

    return user_ids.filter(
        (user_id) =>
            user_is_recently_active(user_id) ||
            user_matches_narrow_using_loaded_data(
                user_id,
                pm_ids_set,
                filter_by_stream_id ? stream_id : undefined,
            ) ||
            conversation_participants.has(user_id),
    );
}

function filter_user_ids(user_filter_text: string, user_ids: number[]): number[] {
    const direct_message_recipients = narrow_state.pm_ids_set();
    user_ids = user_ids.filter((user_id) => {
        const person = people.maybe_get_user_by_id(user_id, true);

        if (!person) {
            return false;
        }

        if (person.is_bot) {
            return false;
        }

        const is_dm = direct_message_recipients.has(user_id);
        if (!people.is_person_active(user_id) && !is_dm) {
            return false;
        }

        if (muted_users.is_user_muted(user_id)) {
            return false;
        }

        return true;
    });

    if (!user_filter_text) {
        return user_ids;
    }

    const persons = user_ids.map((user_id) => people.get_by_user_id(user_id));
    return [...people.filter_people_by_search_terms(persons, user_filter_text)];
}

function get_filtered_user_id_list(
    user_filter_text: string,
    conversation_participants: Set<number>,
): number[] {
    let base_user_id_list = [];

    if (user_filter_text) {
        base_user_id_list = people.get_active_user_ids();
    } else {
        base_user_id_list = presence.get_user_ids();

        const my_user_id = people.my_current_user_id();
        if (!base_user_id_list.includes(my_user_id)) {
            base_user_id_list = [my_user_id, ...base_user_id_list];
        }

        const pm_ids_set = narrow_state.pm_ids_set();
        if (pm_ids_set.size > 0) {
            const base_user_id_set = new Set([...base_user_id_list, ...pm_ids_set]);
            base_user_id_list = [...base_user_id_set];
        }

        const stream_id = narrow_state.stream_id(narrow_state.filter(), true);
        if (stream_id) {
            const subscriber_count = peer_data.get_subscriber_count(stream_id);
            if (subscriber_count <= max_channel_size_to_show_all_subscribers) {
                const subscribers = peer_data.get_subscriber_ids_assert_loaded(stream_id);
                const base_user_id_set = new Set([...base_user_id_list, ...subscribers]);
                base_user_id_list = [...base_user_id_set];
            }
        }
    }

    const user_ids_set = new Set([...base_user_id_list, ...conversation_participants]);
    return filter_user_ids(user_filter_text, [...user_ids_set]);
}

export function get_conversation_participants_callback(): () => Set<number> {
    return () => {
        if (
            !narrow_state.stream_id() ||
            narrow_state.topic() === undefined ||
            !message_lists.current
        ) {
            return new Set<number>();
        }
        return message_lists.current.data.participants.visible();
    };
}

export function get_filtered_and_sorted_user_ids(user_filter_text: string): number[] {
    const conversation_participants = get_conversation_participants_callback()();
    let user_ids = get_filtered_user_id_list(user_filter_text, conversation_participants);
    user_ids = maybe_shrink_list(user_ids, user_filter_text, conversation_participants);
    return sort_users(user_ids, conversation_participants);
}

export function matches_filter(user_filter_text: string, user_id: number): boolean {
    return filter_user_ids(user_filter_text, [user_id]).length === 1;
}
