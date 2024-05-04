import assert from "minimalistic-assert";

import * as favicon from "./favicon";
import type {Filter} from "./filter";
import {$t} from "./i18n";
import * as inbox_util from "./inbox_util";
import * as people from "./people";
import * as recent_view_util from "./recent_view_util";
import {realm} from "./state_data";
import * as unread from "./unread";
import type {FullUnreadCountsData} from "./unread";

export let unread_count = 0;
let pm_count = 0;
export let narrow_title = "home";

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
        if (!filter._sub) {
            // The stream is not set because it does not currently
            // exist (possibly due to a stream name change), or it
            // is a private stream and the user is not subscribed.
            return filter_title;
        }
        if (filter.has_operator("topic")) {
            const topic_name = filter.operands("topic")[0];
            return "#" + filter_title + " > " + topic_name;
        }
        return "#" + filter_title;
    }

    if (filter.has_operator("dm")) {
        const emails = filter.operands("dm")[0];
        const user_ids = people.emails_strings_to_user_ids_string(emails);

        if (user_ids !== undefined) {
            return people.get_recipients(user_ids);
        }
        if (emails.includes(",")) {
            return $t({defaultMessage: "Invalid users"});
        }
        return $t({defaultMessage: "Invalid user"});
    }

    if (filter.has_operator("sender")) {
        const user = people.get_by_email(filter.operands("sender")[0]);
        if (user) {
            if (people.is_my_user_id(user.user_id)) {
                return $t({defaultMessage: "Messages sent by you"});
            }
            return $t(
                {defaultMessage: "Messages sent by {sender}"},
                {
                    sender: user.full_name,
                },
            );
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
    if (window.electron_bridge !== undefined) {
        window.electron_bridge.send_event("total_unread_count", unread_count);
    }

    // TODO: Add a `window.electron_bridge.updateDirectMessageCount(new_pm_count);` call?
    redraw_title();
}

export function update_narrow_title(filter?: Filter): void {
    narrow_title = compute_narrow_title(filter);
    redraw_title();
}
