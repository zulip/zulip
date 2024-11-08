import $ from "jquery";

import * as compose_actions from "./compose_actions";
import {$t} from "./i18n";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import * as message_util from "./message_util";
import * as narrow_state from "./narrow_state";
import * as people from "./people";
import * as stream_data from "./stream_data";

function format_stream_recipient_label(stream_id: number, topic: string): string {
    const stream = stream_data.get_sub_by_id(stream_id);
    if (stream) {
        return "#" + stream.name + " > " + topic;
    }
    return "";
}

type ComposeClosedMessage = {
    stream_id?: number | undefined;
    topic?: string;
    display_reply_to?: string | undefined;
};

export function get_recipient_label(message?: ComposeClosedMessage): string {
    // TODO: This code path is bit of a type-checking disaster; we mix
    // actual message objects with fake objects containing just a
    // couple fields, both those constructed here and potentially
    // passed in.
    if (message_lists.current === undefined) {
        return "";
    }

    if (message === undefined) {
        if (message_lists.current.visibly_empty()) {
            // For empty narrows where there's a clear reply target,
            // i.e. stream+topic or a single direct message conversation,
            // we label the button as replying to the thread.
            const stream_id = narrow_state.stream_sub()?.stream_id;
            const topic = narrow_state.topic();
            if (stream_id !== undefined && topic !== undefined) {
                return format_stream_recipient_label(stream_id, topic);
            } else if (narrow_state.pm_ids_string()) {
                const user_ids = people.user_ids_string_to_ids_array(narrow_state.pm_ids_string()!);
                return message_store.get_pm_full_names(user_ids);
            }
        } else {
            message = message_lists.current.selected_message();
        }
    }

    if (message) {
        if (message.stream_id && message.topic) {
            return format_stream_recipient_label(message.stream_id, message.topic);
        } else if (message.display_reply_to) {
            return message.display_reply_to;
        }
    }
    return "";
}

// Exported for tests
export let update_reply_button_state = (disable = false): void => {
    $(".compose_reply_button").attr("disabled", disable ? "disabled" : null);
    if (disable) {
        $("#compose_buttons .compose-reply-button-wrapper").attr(
            "data-reply-button-type",
            "direct_disabled",
        );
        return;
    }
    if (narrow_state.is_message_feed_visible()) {
        $("#compose_buttons .compose-reply-button-wrapper").attr(
            "data-reply-button-type",
            "selected_message",
        );
    } else {
        $("#compose_buttons .compose-reply-button-wrapper").attr(
            "data-reply-button-type",
            "selected_conversation",
        );
    }
};

export function rewire_update_reply_button_state(value: typeof update_reply_button_state): void {
    update_reply_button_state = value;
}

function update_buttons(disable_reply?: boolean): void {
    update_reply_button_state(disable_reply);
}

export function update_buttons_for_private(): void {
    const pm_ids_string = narrow_state.pm_ids_string();

    let disable_reply;

    if (!pm_ids_string || message_util.user_can_send_direct_message(pm_ids_string)) {
        disable_reply = false;
    } else {
        // disable the [Message X] button when in a private narrow
        // if the user cannot dm the current recipient
        disable_reply = true;
    }

    $("#new_conversation_button").attr("data-conversation-type", "direct");
    update_buttons(disable_reply);
}

export function update_buttons_for_stream_views(): void {
    $("#new_conversation_button").attr("data-conversation-type", "stream");
    update_buttons();
}

export function update_buttons_for_non_specific_views(): void {
    $("#new_conversation_button").attr("data-conversation-type", "non-specific");
    update_buttons();
}

function set_reply_button_label(label: string): void {
    $("#left_bar_compose_reply_button_big").text(label);
}

export function set_standard_text_for_reply_button(): void {
    set_reply_button_label($t({defaultMessage: "Compose message"}));
}

export function update_reply_recipient_label(message?: ComposeClosedMessage): void {
    const recipient_label = get_recipient_label(message);
    if (recipient_label) {
        set_reply_button_label(
            $t({defaultMessage: "Message {recipient_label}"}, {recipient_label}),
        );
    } else {
        set_standard_text_for_reply_button();
    }
}

export function initialize(): void {
    // When the message selection changes, change the label on the Reply button.
    $(document).on("message_selected.zulip", () => {
        if (narrow_state.is_message_feed_visible()) {
            // message_selected events can occur with Recent Conversations
            // open due to the combined feed view loading in the background,
            // so we only update if message feed is visible.
            update_reply_recipient_label();
        }
    });

    // Click handlers for buttons in the compose box.
    $("body").on("click", ".compose_new_conversation_button", () => {
        compose_actions.start({
            message_type: "stream",
            trigger: "clear topic button",
            keep_composebox_empty: true,
        });
    });

    $("body").on("click", ".compose_mobile_button", () => {
        // Remove the channel and topic context, since on mobile widths,
        // the "+" button should open the compose box with the channel
        // picker open (even if the user is in a topic or channel view).
        compose_actions.start({
            message_type: "stream",
            stream_id: undefined,
            topic: "",
            keep_composebox_empty: true,
        });
    });

    $("body").on("click", ".compose_new_direct_message_button", () => {
        compose_actions.start({
            message_type: "private",
            trigger: "new direct message",
            keep_composebox_empty: true,
        });
    });
}
