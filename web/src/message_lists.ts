import $ from "jquery";

import * as inbox_util from "./inbox_util";
import type {MessageListData} from "./message_list_data";
import type {Message} from "./message_store";
import * as ui_util from "./ui_util";

// TODO(typescript): Move this to message_list_view when it's
// converted to TypeScript.
export type MessageContainer = {
    msg: Message;
    is_hidden: boolean;
    url: string;
};

// TODO(typescript): Move this to message_list_view when it's
// converted to typescript.
type MessageListView = {
    update_recipient_bar_background_color: () => void;
    rerender_messages: (messages: Message[], message_content_edited?: boolean) => void;
    is_fetched_end_rendered: () => boolean;
    is_fetched_start_rendered: () => boolean;
    first_rendered_message: () => Message | undefined;
    last_rendered_message: () => Message | undefined;
    show_message_as_read: (message: Message, options: {from?: "pointer" | "server"}) => void;
    show_messages_as_unread: (message_ids: number[]) => void;
    change_message_id: (old_id: number, new_id: number) => void;
    message_containers: Map<number, MessageContainer>;
    _render_win_start: number;
    _render_win_end: number;
    sticky_recipient_message_id: number | undefined;
    $list: JQuery;
};

export type RenderInfo = {need_user_to_scroll: boolean};

export type SelectIdOpts = {
    then_scroll?: boolean;
    target_scroll_offset?: number;
    use_closest?: boolean;
    empty_ok?: boolean;
    mark_read?: boolean;
    force_rerender?: boolean;
    from_scroll?: boolean;
};

export type MessageList = {
    id: number;
    preserve_rendered_state: boolean;
    view: MessageListView;
    is_combined_feed_view: boolean;
    selected_id: () => number;
    selected_row: () => JQuery;
    selected_idx: () => number;
    all_messages: () => Message[];
    get: (id: number) => Message | undefined;
    has_unread_messages: () => boolean;
    can_mark_messages_read: () => boolean;
    can_mark_messages_read_without_setting: () => boolean;
    change_message_id: (old_id: number, new_id: number) => boolean;
    remove_and_rerender: (id: number[]) => void;
    rerender_view: () => void;
    update_muting_and_rerender: () => void;
    prev: () => number | undefined;
    next: () => number | undefined;
    is_at_end: () => boolean;
    prevent_reading: () => void;
    resume_reading: () => void;
    data: MessageListData;
    select_id: (message_id: number, opts?: SelectIdOpts) => void;
    get_row: (message_id: number) => JQuery;
    add_messages: (
        messages: Message[],
        append_opts: {messages_are_new: boolean},
    ) => RenderInfo | undefined;
    first: () => Message | undefined;
    last: () => Message | undefined;
    visibly_empty: () => boolean;
    selected_message: () => Message;
    should_preserve_current_rendered_state: () => boolean;
    show_edit_message: ($row: JQuery, $form: JQuery) => void;
    show_edit_topic_on_recipient_row: ($recipient_row: JQuery, $form: JQuery) => void;
    hide_edit_topic_on_recipient_row: ($recipient_row: JQuery) => void;
    hide_edit_message: ($row: JQuery) => void;
    get_last_message_sent_by_me: () => Message | undefined;
};

export let current: MessageList | undefined;
export const rendered_message_lists = new Map<number, MessageList>();

export function set_current(msg_list: MessageList | undefined): void {
    // NOTE: Strictly used for mocking in node tests.
    // Use `update_current_message_list` instead in production.
    current = msg_list;
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
        current.view.$list.remove();
        rendered_message_lists.delete(current.id);
    } else {
        // We plan to keep the current message list cached.
        current?.view.$list.removeClass("focused-message-list");
        // Remove any existing message lists that we have with the same filter.
        // TODO: If we start supporting more messages lists than just Combined feed,
        // make this a proper filter comparison between the lists.
        if (current?.data.filter.is_in_home()) {
            for (const [id, msg_list] of rendered_message_lists) {
                if (id !== current.id && msg_list.data.filter.is_in_home()) {
                    msg_list.view.$list.remove();
                    rendered_message_lists.delete(id);
                    // We only expect to have one instance of a message list filter cached.
                    break;
                }
            }
        }
    }

    current = msg_list;
    if (current !== undefined) {
        rendered_message_lists.set(current.id, current);
        current.view.$list.addClass("focused-message-list");
    }
}

export function all_rendered_message_lists(): MessageList[] {
    return [...rendered_message_lists.values()];
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
