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

export function rerender_ui() {
    let count = get_count();

    if (!page_params.starred_message_counts) {
        // This essentially hides the count
        count = 0;
    }

    top_left_corner.update_starred_count(count);
}
