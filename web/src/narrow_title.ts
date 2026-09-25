import assert from "minimalistic-assert";

import {electron_bridge} from "./electron_bridge.ts";
import * as favicon from "./favicon.ts";
import type {Filter} from "./filter.ts";
import * as hash_parser from "./hash_parser.ts";
import {$t} from "./i18n.ts";
import * as inbox_util from "./inbox_util.ts";
import * as people from "./people.ts";
import * as recent_view_util from "./recent_view_util.ts";
import {current_user, realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as unread from "./unread.ts";
import type {FullUnreadCountsData} from "./unread.ts";

export let unread_count = 0;
let pm_count = 0;
export let narrow_title = "home";

export function compute_overlay_title(hash: string): string | undefined {
    switch (hash_parser.get_hash_category(hash)) {
        case "drafts":
            return $t({defaultMessage: "Drafts"});
        case "groups":
            return current_user.is_guest ? undefined : $t({defaultMessage: "User groups"});
        case "settings":
            return $t({defaultMessage: "Personal settings"});
        case "organization":
            return $t({defaultMessage: "Organization settings"});
        case "channels":
        case "streams":
            return $t({defaultMessage: "Channels"});
        case "invite":
            // The invite modal opens without changing the hash.
            return undefined;
        case "keyboard-shortcuts":
            return $t({defaultMessage: "Keyboard shortcuts"});
        case "message-formatting":
            return $t({defaultMessage: "Message formatting"});
        case "search-operators":
            return $t({defaultMessage: "Search filters"});
        case "about-zulip":
            return $t({defaultMessage: "About Zulip"});
        case "scheduled":
            return $t({defaultMessage: "Scheduled messages"});
        case "reminders":
            return $t({defaultMessage: "Scheduled reminders"});
        case "user": {
            const user_id = Number.parseInt(hash_parser.get_hash_section(hash), 10);
            return people.is_known_user_id(user_id)
                ? people.get_full_name(user_id)
                : $t({defaultMessage: "No user found"});
        }
        default:
            return undefined;
    }
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
    const overlay_title = compute_overlay_title(window.location.hash);
    const new_title =
        (overlay_title === undefined && unread_count ? "(" + unread_count + ") " : "") +
        (overlay_title ?? narrow_title) +
        " - " +
        realm.realm_name +
        " - " +
        "Zulip";

    document.title = new_title;
}

export function update_unread_counts(counts: FullUnreadCountsData): void {
    const new_unread_count = unread.calculate_notifiable_count(counts);
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
    redraw_title();
}
