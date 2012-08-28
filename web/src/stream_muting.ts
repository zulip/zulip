import type {MessageList} from "./message_list.ts";
import * as message_lists from "./message_lists.ts";
import * as settings_notifications from "./settings_notifications.ts";
import * as stream_edit from "./stream_edit.ts";
import * as stream_list from "./stream_list.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as unread_ui from "./unread_ui.ts";

export function update_is_muted(
    sub: StreamSubscription,
    value: boolean,
    rerender_combined_feed_callback: (combined_feed_msg_list: MessageList) => void,
): void {
    sub.is_muted = value;

    for (const msg_list of message_lists.all_rendered_message_lists()) {
        // TODO: In theory, other message lists whose behavior depends on
        // stream muting might need to be live-updated as well, but the
        // current _all_items design doesn't have a way to support that.
        if (msg_list.data.filter.is_in_home()) {
            if (!value) {
                rerender_combined_feed_callback(msg_list);
            } else {
                msg_list.update_muting_and_rerender();
            }
        }
    }

    // Since muted streams aren't counted in visible unread
    // counts, we need to update the rendering of them.
    unread_ui.update_unread_counts();

    settings_notifications.update_muted_stream_state(sub);
    stream_edit.update_muting_rendering(sub);
    stream_list.set_in_home_view(sub.stream_id, !sub.is_muted);
}
