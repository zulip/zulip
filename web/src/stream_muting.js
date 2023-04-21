import * as message_lists from "./message_lists";
import * as settings_notifications from "./settings_notifications";
import * as stream_edit from "./stream_edit";
import * as stream_list from "./stream_list";
import * as unread_ui from "./unread_ui";

export function update_is_muted(sub, value) {
    sub.is_muted = value;

    // TODO: In theory, other message lists whose behavior depends on
    // stream muting might need to be live-updated as well, but the
    // current _all_items design doesn't have a way to support that.
    message_lists.home.update_muting_and_rerender();

    // Since muted streams aren't counted in visible unread
    // counts, we need to update the rendering of them.
    unread_ui.update_unread_counts();

    settings_notifications.update_muted_stream_state(sub);
    stream_edit.update_muting_rendering(sub);
    stream_list.set_in_home_view(sub.stream_id, !sub.is_muted);
}
