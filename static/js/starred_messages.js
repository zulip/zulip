import $ from "jquery";

import render_confirm_unstar_all_messages from "../templates/confirm_unstar_all_messages.hbs";
import render_confirm_unstar_all_messages_in_topic from "../templates/confirm_unstar_all_messages_in_topic.hbs";

import * as confirm_dialog from "./confirm_dialog";
import * as message_flags from "./message_flags";
import * as message_store from "./message_store";
import * as stream_popover from "./stream_popover";
import * as top_left_corner from "./top_left_corner";

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

export function get_starred_message_ids_in_topic(stream_id, topic) {
    if (stream_id === undefined || topic === undefined) {
        return [];
    }

    return Array.from(starred_ids).filter((id) => {
        const message = message_store.get(id);

        if (message === undefined) {
            // We know the `id` from the initial data fetch from page_params,
            // but the message itself hasn't been fetched from the server yet.
            // We ignore this message, since we can't check if it belongs to
            // the topic, but it could, meaning this implementation isn't
            // completely correct. The right way to do this would be to ask the
            // backend for starred IDs from the topic.
            return false;
        }

        return (
            message.type === "stream" &&
            message.stream_id === stream_id &&
            message.topic.toLowerCase() === topic.toLowerCase()
        );
    });
}

export function rerender_ui() {
    let count = get_count();

    if (!page_params.starred_message_counts) {
        // This essentially hides the count
        count = 0;
    }

    stream_popover.hide_topic_popover();
    top_left_corner.update_starred_count(count);
    stream_popover.hide_starred_messages_popover();
}

export function confirm_unstar_all_messages() {
    const modal_parent = $(".left-sidebar-modal-holder");
    const html_body = render_confirm_unstar_all_messages();

    confirm_dialog.launch({
        parent: modal_parent,
        html_heading: i18n.t("Unstar all messages"),
        html_body,
        html_yes_button: i18n.t("Unstar messages"),
        on_click: message_flags.unstar_all_messages,
    });
}

export function confirm_unstar_all_messages_in_topic(stream_id, topic) {
    function on_click() {
        message_flags.unstar_all_messages_in_topic(stream_id, topic);
    }

    const modal_parent = $(".left-sidebar-modal-holder");
    const html_body = render_confirm_unstar_all_messages_in_topic({
        topic,
    });

    confirm_dialog.launch({
        parent: modal_parent,
        html_heading: i18n.t("Unstar messages in topic"),
        html_body,
        html_yes_button: i18n.t("Unstar messages"),
        on_click,
    });
}
