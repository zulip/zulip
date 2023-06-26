import $ from "jquery";

import * as compose_pm_pill from "./compose_pm_pill";
import * as compose_recipient from "./compose_recipient";
import * as sub_store from "./sub_store";

let message_type = false; // 'stream', 'private', or false-y
let recipient_edited_manually = false;

// We use this variable to keep track of whether user has viewed the topic resolved
// banner for the current compose session, for a narrow. This prevents the banner
// from popping up for every keystroke while composing.
// The variable is reset on sending a message, closing the compose box and changing
// the narrow and the user should still be able to see the banner once after
// performing these actions
let recipient_viewed_topic_resolved_banner = false;

export function set_recipient_edited_manually(flag) {
    recipient_edited_manually = flag;
}

export function is_recipient_edited_manually() {
    return recipient_edited_manually;
}

export function set_message_type(msg_type) {
    message_type = msg_type;
}

export function get_message_type() {
    return message_type;
}

export function set_recipient_viewed_topic_resolved_banner(flag) {
    recipient_viewed_topic_resolved_banner = flag;
}

export function has_recipient_viewed_topic_resolved_banner() {
    return recipient_viewed_topic_resolved_banner;
}

export function recipient_has_topics() {
    return message_type !== "stream";
}

export function composing() {
    // This is very similar to get_message_type(), but it returns
    // a boolean.
    return Boolean(message_type);
}

function get_or_set(fieldname, keep_leading_whitespace, no_trim) {
    // We can't hoist the assignment of '$elem' out of this lambda,
    // because the DOM element might not exist yet when get_or_set
    // is called.
    return function (newval) {
        const $elem = $(`#${CSS.escape(fieldname)}`);
        const oldval = $elem.val();
        if (newval !== undefined) {
            $elem.val(newval);
        }
        if (no_trim) {
            return oldval;
        } else if (keep_leading_whitespace) {
            return oldval.trimEnd();
        }
        return oldval.trim();
    };
}

// NOTE: See `selected_recipient_id` in compose_recipient to for
// documentation on the variable and how it is used.
export function stream_id() {
    const stream_id = compose_recipient.selected_recipient_id;
    if (typeof stream_id === "number") {
        return stream_id;
    }
    return "";
}

export function stream_name() {
    const stream_id = compose_recipient.selected_recipient_id;
    if (typeof stream_id === "number") {
        return sub_store.maybe_get_stream_name(stream_id) || "";
    }
    return "";
}

export function set_stream_id(stream_id) {
    compose_recipient.set_selected_recipient_id(stream_id);
}

export function set_compose_recipient_id(recipient_id) {
    if (typeof recipient_id !== "number") {
        recipient_id = compose_recipient.DIRECT_MESSAGE_ID;
    }
    compose_recipient.set_selected_recipient_id(recipient_id);
}

// TODO: Break out setter and getter into their own functions.
export const topic = get_or_set("stream_message_recipient_topic");

// We can't trim leading whitespace in `compose_textarea` because
// of the indented syntax for multi-line code blocks.
export const message_content = get_or_set("compose-textarea", true);

const untrimmed_message_content = get_or_set("compose-textarea", true, true);

function cursor_at_start_of_whitespace_in_compose() {
    const cursor_position = $("#compose-textarea").caret();
    return message_content() === "" && cursor_position === 0;
}

export function focus_in_empty_compose(consider_start_of_whitespace_message_empty = false) {
    // A user trying to press arrow keys in an empty compose is mostly
    // likely trying to navigate messages. This helper function
    // decides whether the compose box is empty for this purpose.
    if (!composing()) {
        return false;
    }

    // We treat the compose box as empty if it's completely empty, or
    // if the caller requested, if it contains only whitespace and we're
    // at the start of te compose box.
    const treat_compose_as_empty =
        untrimmed_message_content() === "" ||
        (consider_start_of_whitespace_message_empty && cursor_at_start_of_whitespace_in_compose());
    if (!treat_compose_as_empty) {
        return false;
    }

    const focused_element_id = document.activeElement.id;
    if (focused_element_id === "compose-textarea") {
        // Focus will be in the compose textarea after sending a
        // message; this is the most common situation.
        return true;
    }

    // If the current focus is in one of the recipient inputs, we need
    // to check whether the input is empty, to avoid accidentally
    // overriding the browser feature where the Up/Down arrow keys jump
    // you to the start/end of a non-empty text input.
    //
    // Check whether the current input element is empty for each input type.
    switch (focused_element_id) {
        case "private_message_recipient":
            return private_message_recipient().length === 0;
        case "stream_message_recipient_topic":
            return topic() === "";
        case "compose_select_recipient_widget_wrapper":
            return stream_id() === "";
    }

    return false;
}

export function private_message_recipient(value) {
    if (typeof value === "string") {
        compose_pm_pill.set_from_emails(value);
        return undefined;
    }
    return compose_pm_pill.get_emails();
}

export function has_message_content() {
    return message_content() !== "";
}

export function has_full_recipient() {
    if (message_type === "stream") {
        return stream_id() !== "" && topic() !== "";
    }
    return private_message_recipient() !== "";
}
