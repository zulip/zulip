import $ from "jquery";
import assert from "minimalistic-assert";

import * as blueslip from "./blueslip";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import type {Message} from "./message_store";

// We don't need an andSelf() here because we already know
// that our next element is *not* a message_row, so this
// isn't going to end up empty unless we're at the bottom or top.
export const next_visible = ($message_row: JQuery): JQuery => {
    if ($message_row === undefined || $message_row.length === 0) {
        return $();
    }
    const $row = $message_row.next(".selectable_row");
    if ($row.length !== 0) {
        return $row;
    }
    const $recipient_row = get_message_recipient_row($message_row);
    const $next_recipient_rows = $recipient_row.nextAll(".recipient_row");
    if ($next_recipient_rows.length === 0) {
        return $();
    }
    return $(".selectable_row", $next_recipient_rows[0]).first();
};

export const prev_visible = ($message_row: JQuery): JQuery => {
    if ($message_row === undefined || $message_row.length === 0) {
        return $();
    }
    const $row = $message_row.prev(".selectable_row");
    if ($row.length !== 0) {
        return $row;
    }
    const $recipient_row = get_message_recipient_row($message_row);
    const $prev_recipient_rows = $recipient_row.prevAll(".recipient_row");
    if ($prev_recipient_rows.length === 0) {
        return $();
    }
    return $(".selectable_row", $prev_recipient_rows[0]).last();
};

export const first_visible = (): JQuery => $(".focused-message-list .selectable_row").first();

export const last_visible = (): JQuery => $(".focused-message-list .selectable_row").last();

export const visible_range = (start_id: number, end_id: number): JQuery[] => {
    /*
        Get all visible rows between start_id
        and end_in, being inclusive on both ends.
    */

    const rows = [];

    assert(message_lists.current);
    let $row = message_lists.current.get_row(start_id);
    let msg_id = id($row);

    while (msg_id <= end_id) {
        rows.push($row);

        if (msg_id >= end_id) {
            break;
        }
        $row = next_visible($row);
        msg_id = id($row);
    }

    return rows;
};

export const is_overlay_row = ($row: JQuery): boolean =>
    $row.closest(".overlay-message-row").length >= 1;

export const id = ($message_row: JQuery): number => {
    if (is_overlay_row($message_row)) {
        throw new Error("Drafts and scheduled messages have no message id.");
    }

    if ($message_row.length !== 1) {
        throw new Error("Caller should pass in a single row.");
    }

    const message_id = $message_row.attr("data-message-id");

    if (message_id === undefined) {
        throw new Error("Calling code passed rows.id a row with no `data-message-id` attr.");
    }

    return Number.parseFloat(message_id);
};

export const local_echo_id = ($message_row: JQuery): string => {
    const message_id = $message_row.attr("data-message-id");

    if (message_id === undefined) {
        throw new Error("Calling code passed rows.local_id a row with no `data-message-id` attr.");
    }

    if (!message_id.includes(".0")) {
        blueslip.error("Trying to get local_id from row that has reified message id", {message_id});
    }

    return message_id;
};

export const get_message_id = (elem: HTMLElement): number => {
    // Gets the message_id for elem, where elem is a DOM
    // element inside a message.  This is typically used
    // in click handlers for things like the reaction button.
    const $row = $(elem).closest(".message_row");
    const message_id = id($row);
    return message_id;
};

export const get_closest_group = (element: string): JQuery =>
    $(element).closest("div.recipient_row");

export const get_closest_row = (element: string): JQuery => $(element).closest("div.message_row");

export const first_message_in_group = ($message_group: JQuery): JQuery =>
    $("div.message_row", $message_group).first();

export const last_message_in_group = ($message_group: JQuery): JQuery =>
    $("div.message_row", $message_group).last();

export const get_message_recipient_row = ($message_row: JQuery): JQuery =>
    $message_row.parent(".recipient_row").expectOne();

export const get_message_recipient_header = ($message_row: JQuery): JQuery =>
    $message_row.parent(".recipient_row").find(".message_header").expectOne();

export const recipient_from_group = ($message_group: JQuery): Message | undefined => {
    const message_id = id($message_group.children(".message_row").first().expectOne());
    return message_store.get(message_id);
};

export const is_header_of_row_sticky = ($recipient_row: JQuery): boolean =>
    $recipient_row.find(".message_header").hasClass("sticky_header");

export const id_for_recipient_row = ($recipient_row: JQuery): number => {
    if (is_header_of_row_sticky($recipient_row)) {
        const msg_id = message_lists.current?.view.sticky_recipient_message_id;
        if (msg_id !== undefined) {
            return msg_id;
        }
    }

    const $msg_row = first_message_in_group($recipient_row);
    return id($msg_row);
};
