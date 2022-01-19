import * as message_store from "./message_store";
import {page_params} from "./page_params";
import * as stream_popover from "./stream_popover";
import * as top_left_corner from "./top_left_corner";
import {user_settings} from "./user_settings";

export const starred_ids = new Set();

export function initialize() {
    starred_ids.clear();

    for (const id of page_params.starred_messages) {
        starred_ids.add(id);
    }

    rerender_ui();
}

export function add(ids) {
    for (const id of ids) {
        starred_ids.add(id);
    }

    rerender_ui();
}

export function remove(ids) {
    for (const id of ids) {
        starred_ids.delete(id);
    }

    rerender_ui();
}

export function get_count() {
    return starred_ids.size;
}

export function get_starred_msg_ids() {
    return Array.from(starred_ids);
}

export function get_count_in_topic(stream_id, topic) {
    if (stream_id === undefined || topic === undefined) {
        return 0;
    }

    const messages = Array.from(starred_ids).filter((id) => {
        const message = message_store.get(id);

        if (message === undefined) {
            // We know the `id` from the initial data fetch from page_params,
            // but the message itself hasn't been fetched from the server yet.
            // We ignore this message, since we can't check if it belongs to
            // the topic, but it could, meaning this implementation isn't
            // completely correct.
            // Since this function is used only when opening the topic popover,
            // and not for actually unstarring messages, this discrepancy is
            // probably acceptable. The worst it could manifest as is the topic
            // popover not having the "Unstar all messages in topic" option, when
            // it should have had.
            return false;
        }

        return (
            message.type === "stream" &&
            message.stream_id === stream_id &&
            message.topic.toLowerCase() === topic.toLowerCase()
        );
    });

    return messages.length;
}

export function rerender_ui() {
    let count = get_count();

    if (!user_settings.starred_message_counts) {
        // This essentially hides the count
        count = 0;
    }

    stream_popover.hide_topic_popover();
    top_left_corner.update_starred_count(count);
    stream_popover.hide_starred_messages_popover();
}
