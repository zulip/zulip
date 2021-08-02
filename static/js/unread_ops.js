import * as channel from "./channel";
import * as message_flags from "./message_flags";
import * as message_list from "./message_list";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import * as message_viewport from "./message_viewport";
import * as notifications from "./notifications";
import * as recent_topics_ui from "./recent_topics_ui";
import * as reload from "./reload";
import * as unread from "./unread";
import * as unread_ui from "./unread_ui";

export function mark_all_as_read() {
    unread.declare_bankruptcy();
    unread_ui.update_unread_counts();

    channel.post({
        url: "/json/mark_all_as_read",
        idempotent: true,
        success: () => {
            // After marking all messages as read, we reload the browser.
            // This is useful to avoid leaving ourselves deep in the past.
            reload.initiate({
                immediate: true,
                save_pointer: false,
                save_narrow: true,
                save_compose: true,
            });
        },
    });
}

function process_newly_read_message(message, options) {
    message_lists.home.show_message_as_read(message, options);
    if (message_list.narrowed) {
        message_list.narrowed.show_message_as_read(message, options);
    }
    notifications.close_notification(message);
    recent_topics_ui.update_topic_unread_count(message);
}

export function process_read_messages_event(message_ids) {
    /*
        This code has a lot in common with notify_server_messages_read,
        but there are subtle differences due to the fact that the
        server can tell us about unread messages that we didn't
        actually read locally (and which we may not have even
        loaded locally).
    */
    const options = {from: "server"};

    message_ids = unread.get_unread_message_ids(message_ids);
    if (message_ids.length === 0) {
        return;
    }

    for (const message_id of message_ids) {
        if (message_lists.current === message_list.narrowed) {
            // I'm not sure this entirely makes sense for all server
            // notifications.
            unread.set_messages_read_in_narrow(true);
        }

        unread.mark_as_read(message_id);

        const message = message_store.get(message_id);

        if (message) {
            process_newly_read_message(message, options);
        }
    }

    unread_ui.update_unread_counts();
}

// Takes a list of messages and marks them as read.
// Skips any messages that are already marked as read.
export function notify_server_messages_read(messages, options = {}) {
    messages = unread.get_unread_messages(messages);
    if (messages.length === 0) {
        return;
    }

    message_flags.send_read(messages);

    for (const message of messages) {
        if (message_lists.current === message_list.narrowed) {
            unread.set_messages_read_in_narrow(true);
        }

        unread.mark_as_read(message.id);
        process_newly_read_message(message, options);
    }

    unread_ui.update_unread_counts();
}

export function notify_server_message_read(message, options) {
    notify_server_messages_read([message], options);
}

export function process_scrolled_to_bottom() {
    if (message_lists.current.can_mark_messages_read()) {
        mark_current_list_as_read();
        return;
    }

    // For message lists that don't support marking messages as read
    // automatically, we display a banner offering to let you mark
    // them as read manually, only if there are unreads present.
    if (message_lists.current.has_unread_messages()) {
        unread_ui.notify_messages_remain_unread();
    }
}

// If we ever materially change the algorithm for this function, we
// may need to update notifications.received_messages as well.
export function process_visible() {
    if (message_viewport.is_visible_and_focused() && message_viewport.bottom_message_visible()) {
        process_scrolled_to_bottom();
    }
}

export function mark_current_list_as_read(options) {
    notify_server_messages_read(message_lists.current.all_messages(), options);
}

export function mark_stream_as_read(stream_id, cont) {
    channel.post({
        url: "/json/mark_stream_as_read",
        idempotent: true,
        data: {stream_id},
        success: cont,
    });
}

export function mark_topic_as_read(stream_id, topic, cont) {
    channel.post({
        url: "/json/mark_topic_as_read",
        idempotent: true,
        data: {stream_id, topic_name: topic},
        success: cont,
    });
}
