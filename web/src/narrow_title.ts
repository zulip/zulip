import assert from "minimalistic-assert";

import {electron_bridge} from "./electron_bridge.ts";
import * as favicon from "./favicon.ts";
import type {Filter} from "./filter.ts";
import {$t} from "./i18n.ts";
import * as inbox_util from "./inbox_util.ts";
import * as narrow_state from "./narrow_state.ts";
import * as people from "./people.ts";
import * as recent_view_util from "./recent_view_util.ts";
import {desktop_icon_count_display_values} from "./settings_config.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as unread from "./unread.ts";
import type {FullUnreadCountsData} from "./unread.ts";
import {user_settings} from "./user_settings.ts";

export let unread_count = 0;
let pm_count = 0;
export let narrow_title = "home";

function is_current_conversation_mode(): boolean {
    return (
        user_settings.desktop_icon_count_display ===
        desktop_icon_count_display_values.current_conversation.code
    );
}

// Compute the unread count scoped to the currently active narrow.
// Falls back to the global home unread count when no specific narrow
// is active (e.g., Recent Conversations or Inbox).
function calculate_current_conversation_count(): number {
    const filter = narrow_state.filter();
    if (filter === undefined) {
        // Recent Conversations view returns undefined from narrow_state.filter().
        // Fall back to the global unread count.
        return unread.get_counts().home_unread_messages;
    }

    if (filter.has_operator("channel")) {
        const stream_operand = filter.terms_with_operator("channel")[0]!.operand;
        const sub = stream_data.get_sub_by_id_string(stream_operand);
        if (!sub) {
            return 0;
        }
        if (filter.has_operator("topic")) {
            const topic_name = filter.terms_with_operator("topic")[0]!.operand;
            return unread.num_unread_for_topic(sub.stream_id, topic_name);
        }
        return unread.unread_count_info_for_stream(sub.stream_id).unmuted_count;
    }

    if (filter.has_operator("dm")) {
        const user_ids = filter.terms_with_operator("dm")[0]!.operand;
        return unread.num_unread_for_user_ids_string(String(user_ids));
    }

    // For search results, combined feed, or other views, show 0.
    return 0;
}

export function compute_narrow_title(filter?: Filter): string {
    if (filter === undefined) {
        // Views without a message feed in the center pane.
        if (recent_view_util.is_visible()) {
            return $t({defaultMessage: "Recent conversations"});
        }

        assert(inbox_util.is_visible());
        return $t({defaultMessage: "Inbox"});
    }

    const filter_title = filter.get_title();

    if (filter_title === undefined) {
        // Default result for uncommon narrow/search views.
        return $t({defaultMessage: "Search results"});
    }

    if (filter.has_operator("channel")) {
        const sub = stream_data.get_sub_by_id_string(
            filter.terms_with_operator("channel")[0]!.operand,
        );
        if (!sub) {
            // The stream is not set because it does not currently
            // exist, or it is a private stream and the user is not
            // subscribed.
            return filter_title;
        }
        if (filter.has_operator("topic")) {
            const topic_name = filter.terms_with_operator("topic")[0]!.operand;
            return "#" + filter_title + " > " + topic_name;
        }
        return "#" + filter_title;
    }

    if (filter.has_operator("dm")) {
        const user_ids = filter.terms_with_operator("dm")[0]!.operand;

        if (people.is_valid_user_ids(user_ids)) {
            return people.format_recipients(String(user_ids), "long");
        }

        if (user_ids.length > 1) {
            return $t({defaultMessage: "Invalid users"});
        }
        return $t({defaultMessage: "Invalid user"});
    }

    return filter_title;
}

export function redraw_title(): void {
    // Update window title to reflect unread messages in current view
    const new_title =
        (unread_count ? "(" + unread_count + ") " : "") +
        narrow_title +
        " - " +
        realm.realm_name +
        " - " +
        "Zulip";

    document.title = new_title;
}

export function update_unread_counts(counts: FullUnreadCountsData): void {
    let new_unread_count = unread.calculate_notifiable_count(counts);

    // When "Current conversation" is selected, override the global
    // notifiable count (which is 0) with the narrow-scoped count.
    if (is_current_conversation_mode()) {
        new_unread_count = calculate_current_conversation_count();
    }

    const new_pm_count = counts.direct_message_count;
    if (new_unread_count === unread_count && new_pm_count === pm_count) {
        return;
    }

    unread_count = new_unread_count;
    pm_count = new_pm_count;

    // Indicate the message count in the favicon
    favicon.update_favicon(unread_count, pm_count);

    // Notify the current desktop app's UI about the new unread count.
    electron_bridge?.send_event("total_unread_count", unread_count);

    // TODO: Add a `electron_bridge.updateDirectMessageCount(new_pm_count);` call?
    redraw_title();
}

export function update_narrow_title(filter?: Filter): void {
    narrow_title = compute_narrow_title(filter);

    // When "Current conversation" is selected, the unread count depends
    // on the active narrow, so we must recompute it on every narrow change.
    if (is_current_conversation_mode()) {
        const new_count = calculate_current_conversation_count();
        if (new_count !== unread_count) {
            unread_count = new_count;
            favicon.update_favicon(unread_count, pm_count);
            electron_bridge?.send_event("total_unread_count", unread_count);
        }
    }

    redraw_title();
}
