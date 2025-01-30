import $ from "jquery";

import * as inbox_util from "./inbox_util.ts";
import type {MessageList} from "./message_list.ts";
import type {MessageListData} from "./message_list_data.ts";
import * as message_list_data_cache from "./message_list_data_cache.ts";
import * as ui_util from "./ui_util.ts";

export let current: MessageList | undefined;
export const rendered_message_lists = new Map<number, MessageList>();

export function set_current(msg_list: MessageList | undefined): void {
    // NOTE: Strictly used for mocking in node tests.
    // Use `update_current_message_list` instead in production.
    current = msg_list;
}

export function delete_message_list(message_list: MessageList): void {
    message_list.view.$list.remove();
    rendered_message_lists.delete(message_list.id);
    message_list.data.set_rendered_message_list_id(undefined);
}

export function update_current_message_list(msg_list: MessageList | undefined): void {
    // Since we change `current` message list in the function, we need to decide if the
    // current message list needs to be cached or discarded.
    //
    // If we are caching the current message list, we need to remove any other message lists
    // that we have cached with the same filter.
    //
    // If we are discarding the current message list, we need to remove the
    // current message list from the DOM.
    if (current && !current.should_preserve_current_rendered_state()) {
        // Remove the current message list from the DOM.
        delete_message_list(current);
    } else {
        // We plan to keep the current message list cached.
        current?.view.$list.removeClass("focused-message-list");
        // Remove any existing message lists that we have with the same filter.
        // TODO: If we start supporting more messages lists than just Combined feed,
        // make this a proper filter comparison between the lists.
        if (current?.data.filter.is_in_home()) {
            for (const [id, msg_list] of rendered_message_lists) {
                if (id !== current.id && msg_list.data.filter.is_in_home()) {
                    delete_message_list(msg_list);
                    // We only expect to have one instance of a message list filter cached.
                    break;
                }
            }
        }
    }

    current = msg_list;
    if (current !== undefined) {
        rendered_message_lists.set(current.id, current);
        message_list_data_cache.add(current.data);
        current.view.$list.addClass("focused-message-list");
    }

    if (
        current?.data.filter.is_conversation_view() ||
        current?.data.filter.is_conversation_view_with_near()
    ) {
        $(".focused-message-list").addClass("is-conversation-view");
    } else {
        $(".focused-message-list").removeClass("is-conversation-view");
    }
}

export function all_rendered_message_lists(): MessageList[] {
    return [...rendered_message_lists.values()];
}

export function non_rendered_data(): MessageListData[] {
    const rendered_data = new Set(rendered_message_lists.keys());
    return message_list_data_cache.all().filter((data) => {
        if (data.rendered_message_list_id === undefined) {
            return true;
        }
        return !rendered_data.has(data.rendered_message_list_id);
    });
}

export function add_rendered_message_list(msg_list: MessageList): void {
    rendered_message_lists.set(msg_list.id, msg_list);
}

export function all_rendered_row_for_message_id(message_id: number): JQuery {
    let $rows = $();
    for (const msg_list of all_rendered_message_lists()) {
        const $row = msg_list.get_row(message_id);
        $rows = $rows.add($row);
    }
    return $rows;
}

export function all_current_message_rows(): JQuery {
    if (current === undefined) {
        return $();
    }

    return current.view.$list.find(".message_row");
}

export function update_recipient_bar_background_color(): void {
    for (const msg_list of all_rendered_message_lists()) {
        msg_list.view.update_recipient_bar_background_color();
    }
    inbox_util.update_stream_colors();
}

export function initialize(): void {
    // For users with automatic color scheme, we need to detect change
    // in `prefers-color-scheme` as it changes based on time.
    ui_util.listener_for_preferred_color_scheme_change(update_recipient_bar_background_color);
}
