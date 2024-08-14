import $ from "jquery";
import assert from "minimalistic-assert";

import * as inbox_util from "./inbox_util";
import * as message_lists from "./message_lists";
import type {Message} from "./message_store";
import * as narrow_state from "./narrow_state";
import * as overlays from "./overlays";
import * as popover_menus from "./popover_menus";
import * as recent_view_ui from "./recent_view_ui";
import * as settings_user_topics from "./settings_user_topics";
import * as stream_data from "./stream_data";
import * as stream_list from "./stream_list";
import * as sub_store from "./sub_store";
import * as unread_ui from "./unread_ui";
import * as user_topics from "./user_topics";
import type {ServerUserTopic} from "./user_topics";

function should_add_topic_update_delay(visibility_policy: number): boolean | undefined {
    // If topic visibility related popovers are active, add a delay to all methods that
    // hide the topic on mute. This allows the switching animations to complete before the
    // popover is force closed due to the reference element being removed from view.
    const is_topic_muted = visibility_policy === user_topics.all_visibility_policies.MUTED;
    const is_relevant_popover_open =
        popover_menus.is_topic_menu_popover_displayed() ??
        popover_menus.is_visibility_policy_popover_displayed();

    // Don't add delay if the user is in inbox view or topics narrow, since
    // the popover's reference element is always visible in these cases.
    const is_inbox_view = inbox_util.is_visible();
    const is_topic_narrow = narrow_state.narrowed_by_topic_reply();

    return is_topic_muted && is_relevant_popover_open && !is_inbox_view && !is_topic_narrow;
}

export function handle_topic_updates(user_topic_event: ServerUserTopic): void {
    // Update the UI after changes in topic visibility policies.
    user_topics.set_user_topic(user_topic_event);

    setTimeout(
        () => {
            stream_list.update_streams_sidebar();
            unread_ui.update_unread_counts();
            message_lists.current?.update_muting_and_rerender();
            recent_view_ui.update_topic_visibility_policy(
                user_topic_event.stream_id,
                user_topic_event.topic_name,
            );
        },
        should_add_topic_update_delay(user_topic_event.visibility_policy) ? 500 : 0,
    );

    if (overlays.settings_open() && settings_user_topics.loaded) {
        const stream_id = user_topic_event.stream_id;
        const topic_name = user_topic_event.topic_name;
        const visibility_policy = user_topic_event.visibility_policy;

        // Find the row with the specified stream_id and topic_name
        const $row = $('tr[data-stream-id="' + stream_id + '"][data-topic="' + topic_name + '"]');

        if ($row.length) {
            // If the row exists, update the status only.
            // We don't call 'populate_list' in this case as it re-creates the panel (re-sorts by date updated +
            // removes topics with status set to 'Default for channel'), making it hard to review the changes
            // and undo if needed.
            const $status = $row.find("select.settings_user_topic_visibility_policy");
            $status.val(visibility_policy);
        } else {
            // If the row doesn't exist, the user must have set the visibility policy
            // via another tab. We call 'populate_list' to re-create the panel, hence
            // including the new row.
            settings_user_topics.populate_list();
        }
    }

    setTimeout(() => {
        // Defer updates for any background-rendered messages lists until the visible one has been updated.
        for (const list of message_lists.all_rendered_message_lists()) {
            if (list.preserve_rendered_state && message_lists.current !== list) {
                list.update_muting_and_rerender();
            }
        }
    }, 0);
}

export function toggle_topic_visibility_policy(message: Message): void {
    if (message.type !== "stream") {
        return;
    }

    const stream_id = message.stream_id;
    const topic = message.topic;

    if (!stream_data.is_subscribed(stream_id)) {
        return;
    }

    const sub = sub_store.get(stream_id);
    assert(sub !== undefined);

    if (sub.is_muted) {
        if (user_topics.is_topic_unmuted_or_followed(stream_id, topic)) {
            user_topics.set_user_topic_visibility_policy(
                stream_id,
                topic,
                user_topics.all_visibility_policies.INHERIT,
                true,
            );
        } else {
            user_topics.set_user_topic_visibility_policy(
                stream_id,
                topic,
                user_topics.all_visibility_policies.UNMUTED,
                true,
            );
        }
    } else {
        if (user_topics.is_topic_muted(stream_id, topic)) {
            user_topics.set_user_topic_visibility_policy(
                stream_id,
                topic,
                user_topics.all_visibility_policies.INHERIT,
                true,
            );
        } else {
            user_topics.set_user_topic_visibility_policy(
                stream_id,
                topic,
                user_topics.all_visibility_policies.MUTED,
                true,
            );
        }
    }
}
