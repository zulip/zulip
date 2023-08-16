import $ from "jquery";

import * as blueslip from "./blueslip";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
// We don't need an andSelf() here because we already know
// that our next element is *not* a message_row, so this
// isn't going to end up empty unless we're at the bottom or top.
export function next_visible($message_row) {
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
}

export function prev_visible($message_row) {
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
}

export function first_visible() {
    return $(".focused-message-list .selectable_row").first();
}

export function last_visible() {
    return $(".focused-message-list .selectable_row").last();
}

export function visible_range(start_id, end_id) {
    /*
        Get all visible rows between start_id
        and end_in, being inclusive on both ends.
    */

    const rows = [];

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
}

export function is_draft_row($row) {
    return $row.find("#drafts_table .restore-overlay-message").length >= 1;
}

export function id($message_row) {
    if (is_draft_row($message_row)) {
        blueslip.error("Drafts have no zid");
        return undefined;
    }

    /*
        For blueslip errors, don't return early, since
        we may have some code now that actually relies
        on the NaN behavior here.  We can try to clean
        that up in the future, but we mainly just want
        more data now.
    */

    if ($message_row.length !== 1) {
        blueslip.error("Caller should pass in a single row.");
    }

    const zid = $message_row.attr("zid");

    if (zid === undefined) {
        blueslip.error("Calling code passed rows.id a row with no zid attr.");
    }

    return Number.parseFloat(zid);
}

export function local_echo_id($message_row) {
    const zid = $message_row.attr("zid");

    if (zid === undefined) {
        blueslip.error("Calling code passed rows.local_id a row with no zid attr.");
        return undefined;
    }

    if (!zid.includes(".0")) {
        blueslip.error("Trying to get local_id from row that has reified message id", {zid});
    }

    return zid;
}

const valid_table_names = new Set(["zhome", "zfilt"]);

export function get_table(table_name) {
    if (!valid_table_names.has(table_name)) {
        return $();
    }

    return $(`#${CSS.escape(table_name)}`);
}

export function get_message_id(elem) {
    // Gets the message_id for elem, where elem is a DOM
    // element inside a message.  This is typically used
    // in click handlers for things like the reaction button.
    const $row = $(elem).closest(".message_row");
    const message_id = id($row);
    return message_id;
}

export function get_closest_group(element) {
    // This gets the closest message row to an element, whether it's
    // a recipient bar or message.  With our current markup,
    // this is the most reliable way to do it.
    return $(element).closest("div.recipient_row");
}

export function get_closest_row(element) {
    return $(element).closest("div.message_row");
}

export function first_message_in_group(message_group) {
    return $("div.message_row", message_group).first();
}

export function get_message_recipient_row($message_row) {
    return $message_row.parent(".recipient_row").expectOne();
}

export function get_message_recipient_header($message_row) {
    return $message_row.parent(".recipient_row").find(".message_header").expectOne();
}

export function recipient_from_group(message_group) {
    return message_store.get(id($(message_group).children(".message_row").first().expectOne()));
}

export function id_for_recipient_row($recipient_row) {
    // A recipient row can be either a normal recipient row, or
    // the FRB, which is a fake recipient row. If it's a FRB, it has
    // a 'zid' property that stores the message id it is directly over
    const $msg_row = first_message_in_group($recipient_row);
    if ($msg_row.length === 0) {
        // If we're narrowing from the FRB, take the msg id
        // directly from it
        return id($recipient_row);
    }
    return id($msg_row);
}
