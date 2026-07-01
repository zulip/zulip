import * as blueslip from "./blueslip.ts";
import * as buddy_data from "./buddy_data.ts";
import * as hash_util from "./hash_util.ts";
import * as narrow_state from "./narrow_state.ts";
import * as people from "./people.ts";
import * as pm_conversations from "./pm_conversations.ts";
import * as unread from "./unread.ts";
import * as user_status from "./user_status.ts";
import type {UserStatusEmojiInfo} from "./user_status.ts";

// Maximum number of conversation threads to show in default view.
const max_conversations_to_show = 8;

// Maximum number of conversation threads to show in default view with unreads.
const max_conversations_to_show_with_unreads = 15;

export function get_active_user_ids_string(): string | undefined {
    const filter = narrow_state.filter();

    if (!filter) {
        return undefined;
    }

    const user_ids = filter.terms_with_operator("dm")[0]?.operand;

    if (!user_ids || user_ids.length === 0) {
        return undefined;
    }

    if (!people.is_valid_user_ids(user_ids)) {
        blueslip.warn("Invalid user_ids", {user_ids});
        return undefined;
    }

    return people.sorted_other_user_ids(user_ids).join(",");
}

export type PMListConversation = {
    user_ids_string: string;
};

export type DisplayObject = {
    recipients: string;
    user_ids_string: string;
    is_current_user: boolean;
    unread: number;
    is_zero: boolean;
    is_active: boolean;
    url: string;
    status_emoji_info: UserStatusEmojiInfo | undefined;
    user_circle_class: string | undefined;
    is_group: boolean;
    is_bot: boolean;
    has_unread_mention: boolean;
    includes_deactivated_user: boolean;
    pinned: boolean;
};

export function get_conversations(search_string = ""): DisplayObject[] {
    const conversations = pm_conversations.recent.get();
    const display_objects: DisplayObject[] = [];

    // The user_ids_string for the current view, if any.
    const active_user_ids_string = get_active_user_ids_string();

    if (
        active_user_ids_string !== undefined &&
        !conversations
            .map((conversation) => conversation.user_ids_string)
            .includes(active_user_ids_string)
    ) {
        conversations.unshift({
            user_ids_string: active_user_ids_string,
            max_message_id: -1,
            pinned: false,
        });
    }

    for (const conversation of conversations) {
        const user_ids_string = conversation.user_ids_string;

        const user_ids = people.user_ids_string_to_ids_array(user_ids_string);
        const users = people.get_users_from_ids(user_ids);
        if (!people.dm_matches_search_string(users, search_string)) {
            // Skip adding the conversation to the display_objects array if it does
            // not match the search_term.
            continue;
        }

        const recipients_string = people.format_recipients(user_ids_string, "narrow");

        const num_unread = unread.num_unread_for_user_ids_string(user_ids_string);
        const has_unread_mention =
            unread.num_unread_mentions_for_user_ids_strings(user_ids_string) > 0;
        const is_group = user_ids_string.includes(",");
        const is_active = user_ids_string === active_user_ids_string;
        const includes_deactivated_user = user_ids.some(
            (id) => !people.is_active_user_or_system_bot(id),
        );

        let user_circle_class: string | undefined;
        let status_emoji_info: UserStatusEmojiInfo | undefined;
        let is_bot = false;
        let is_current_user = false;

        if (!is_group) {
            const user_id = Number.parseInt(user_ids_string, 10);
            user_circle_class = buddy_data.get_user_circle_class(
                user_id,
                includes_deactivated_user,
            );
            const recipient_user_obj = people.get_by_user_id(user_id);

            if (recipient_user_obj.is_bot) {
                is_bot = true;
            } else {
                is_current_user = people.is_my_user_id(user_id);
                status_emoji_info = user_status.get_status_emoji(user_id);
            }
        }

        const display_object: DisplayObject = {
            recipients: recipients_string,
            user_ids_string,
            unread: num_unread,
            is_zero: num_unread === 0,
            is_active,
            url: hash_util.pm_with_url(user_ids_string),
            status_emoji_info,
            user_circle_class,
            is_group,
            is_bot,
            has_unread_mention,
            includes_deactivated_user,
            is_current_user,
            pinned: conversation.pinned,
        };
        display_objects.push(display_object);
    }

    return display_objects;
}

// Designed to closely match topic_list_data.get_list_info().
export function get_list_info(
    zoomed: boolean,
    search_term = "",
): {
    conversations_to_be_shown: DisplayObject[];
    more_conversations_unread_count: number;
    pinned_count: number;
} {
    const conversations = get_conversations(search_term);
    // Pinned conversations are shown first, in recency order. Pinning is
    // additive, but the combined list is still capped (below) at
    // max_conversations_to_show_with_unreads.
    const pinned_conversations = conversations.filter((conversation) => conversation.pinned);
    const unpinned_conversations = conversations.filter((conversation) => !conversation.pinned);

    if (zoomed) {
        return {
            conversations_to_be_shown: [...pinned_conversations, ...unpinned_conversations],
            more_conversations_unread_count: 0,
            pinned_count: pinned_conversations.length,
        };
    }

    const pinned_count = pinned_conversations.length;
    const conversations_to_be_shown = [...pinned_conversations];
    let more_conversations_unread_count = 0;
    let unpinned_shown_count = 0;

    function should_show_unpinned_conversation(conversation: DisplayObject): boolean {
        // We always show the active conversation; see the similar
        // comment in topic_list_data.ts.
        if (conversation.is_active) {
            return true;
        }

        // We don't need to filter muted users here, because
        // pm_conversations.ts takes care of this for us.

        // Conversations that include any deactivated users are
        // hidden from the unzoomed view to declutter the sidebar,
        // unless they have unread messages since that's still worth
        // showing.
        if (conversation.includes_deactivated_user && conversation.unread === 0) {
            return false;
        }

        // Stop once the combined pinned + unpinned list hits the cap.
        if (pinned_count + unpinned_shown_count >= max_conversations_to_show_with_unreads) {
            return false;
        }

        // We include the most recent max_conversations_to_show
        // unpinned conversations, regardless of whether they have
        // unread messages.
        if (unpinned_shown_count < max_conversations_to_show) {
            return true;
        }

        // We include older unpinned conversations with unread messages
        // until the combined list reaches the cap above.
        if (conversation.unread > 0) {
            return true;
        }

        // Otherwise, this conversation should only be visible in
        // the unzoomed view.
        return false;
    }

    for (const conversation of unpinned_conversations) {
        if (should_show_unpinned_conversation(conversation)) {
            conversations_to_be_shown.push(conversation);
            unpinned_shown_count += 1;
        } else {
            more_conversations_unread_count += conversation.unread;
        }
    }

    return {
        conversations_to_be_shown,
        more_conversations_unread_count,
        pinned_count,
    };
}
