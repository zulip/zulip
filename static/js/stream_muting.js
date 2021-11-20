import {all_messages_data} from "./all_messages_data";
import * as message_lists from "./message_lists";
import * as message_scroll from "./message_scroll";
import * as message_util from "./message_util";
import * as message_viewport from "./message_viewport";
import * as navigate from "./navigate";
import * as overlays from "./overlays";
import * as settings_notifications from "./settings_notifications";
import * as stream_edit from "./stream_edit";
import * as stream_list from "./stream_list";

export function update_is_muted(sub, value) {
    sub.is_muted = value;

    setTimeout(() => {
        let msg_offset;
        let saved_ypos;
        // Save our current scroll position
        if (overlays.is_active()) {
            saved_ypos = message_viewport.scrollTop();
        } else if (
            message_lists.home === message_lists.current &&
            message_lists.current.selected_row().offset() !== null
        ) {
            msg_offset = message_lists.current.selected_row().offset().top;
        }

        message_lists.home.clear({clear_selected_id: false});

        // Recreate the message_lists.home with the newly filtered all_messages_data
        message_util.add_old_messages(all_messages_data.all_messages(), message_lists.home);

        // Ensure we're still at the same scroll position
        if (overlays.is_active()) {
            message_viewport.scrollTop(saved_ypos);
        } else if (message_lists.home === message_lists.current) {
            // We pass use_closest to handle the case where the
            // currently selected message is being hidden from the
            // home view
            message_lists.home.select_id(message_lists.home.selected_id(), {
                use_closest: true,
                empty_ok: true,
            });
            if (message_lists.current.selected_id() !== -1) {
                message_lists.current.view.set_message_offset(msg_offset);
            }
        }

        // In case we added messages to what's visible in the home
        // view, we need to re-scroll to make sure the pointer is
        // still visible. We don't want the auto-scroll handler to
        // move our pointer to the old scroll location before we have
        // a chance to update it.
        navigate.plan_scroll_to_selected();
        message_scroll.suppress_selection_update_on_next_scroll();

        if (!message_lists.home.empty()) {
            message_util.do_unread_count_updates(message_lists.home.all_messages());
        }
    }, 0);

    settings_notifications.update_muted_stream_state(sub);
    stream_edit.update_muting_rendering(sub);
    stream_list.set_in_home_view(sub.stream_id, !sub.is_muted);
}
