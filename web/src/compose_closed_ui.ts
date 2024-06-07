import $ from "jquery";

import * as compose_actions from "./compose_actions";
import {$t} from "./i18n";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import * as narrow_state from "./narrow_state";
import * as people from "./people";
import * as stream_data from "./stream_data";

const format_stream_recipient_label = (stream_id: number, topic: string): string => {
    const stream = stream_data.get_sub_by_id(stream_id);
    if (stream) {
        return "#" + stream.name + " > " + topic;
    }
    return "";
};

type ComposeClosedMessage = {
    stream_id?: number | undefined;
    topic?: string;
    display_reply_to?: string | undefined;
};

export const get_recipient_label = (message?: ComposeClosedMessage): string => {
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
};

const update_reply_button_state = (disable = false): void => {
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

const update_new_conversation_button = (
    btn_text: string,
    is_direct_message_narrow?: boolean,
): void => {
    const $new_conversation_button = $("#new_conversation_button");
    $new_conversation_button.text(btn_text);
    // In a direct-message narrow, the new conversation button should act
    // like a new direct message button
    if (is_direct_message_narrow) {
        $new_conversation_button.addClass("compose_new_direct_message_button");
        $new_conversation_button.removeClass("compose_new_conversation_button");
    } else {
        // Restore the usual new conversation button class, if it was
        // changed after a previous direct-message narrow visit
        $new_conversation_button.addClass("compose_new_conversation_button");
        $new_conversation_button.removeClass("compose_new_direct_message_button");
    }
};

const update_new_direct_message_button = (btn_text: string): void => {
    $("#new_direct_message_button").text(btn_text);
};

const toggle_direct_message_button_visibility = (is_direct_message_narrow?: boolean): void => {
    const $new_direct_message_button_container = $(".new_direct_message_button_container");
    if (is_direct_message_narrow) {
        $new_direct_message_button_container.hide();
    } else {
        $new_direct_message_button_container.show();
    }
};

const update_buttons = (
    text_stream: string,
    is_direct_message_narrow?: boolean,
    disable_reply?: boolean,
): void => {
    const text_conversation = $t({defaultMessage: "New direct message"});
    update_new_conversation_button(text_stream, is_direct_message_narrow);
    update_new_direct_message_button(text_conversation);
    update_reply_button_state(disable_reply);
    toggle_direct_message_button_visibility(is_direct_message_narrow);
};

export const update_buttons_for_private = (): void => {
    const text_stream = $t({defaultMessage: "Start new conversation"});
    const is_direct_message_narrow = true;
    const pm_ids_string = narrow_state.pm_ids_string();
    if (!pm_ids_string || people.user_can_direct_message(pm_ids_string)) {
        $("#new_conversation_button").attr("data-conversation-type", "direct");
        update_buttons(text_stream, is_direct_message_narrow);
        return;
    }
    // disable the [Message X] button when in a private narrow
    // if the user cannot dm the current recipient
    const disable_reply = true;
    update_buttons(text_stream, is_direct_message_narrow, disable_reply);
};

export const update_buttons_for_stream_views = (): void => {
    const text_stream = $t({defaultMessage: "Start new conversation"});
    $("#new_conversation_button").attr("data-conversation-type", "stream");
    update_buttons(text_stream);
};

export const update_buttons_for_non_specific_views = (): void => {
    const text_stream = $t({defaultMessage: "Start new conversation"});
    $("#new_conversation_button").attr("data-conversation-type", "non-specific");
    update_buttons(text_stream);
};

const set_reply_button_label = (label: string): void => {
    $("#left_bar_compose_reply_button_big").text(label);
};

export const set_standard_text_for_reply_button = (): void => {
    set_reply_button_label($t({defaultMessage: "Compose message"}));
};

export const update_reply_recipient_label = (message?: ComposeClosedMessage): void => {
    const recipient_label = get_recipient_label(message);
    if (recipient_label) {
        set_reply_button_label(
            $t({defaultMessage: "Message {recipient_label}"}, {recipient_label}),
        );
    } else {
        set_standard_text_for_reply_button();
    }
};

export const initialize = (): void => {
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

    $("body").on("click", ".compose_new_direct_message_button", () => {
        compose_actions.start({
            message_type: "private",
            trigger: "new direct message",
            keep_composebox_empty: true,
        });
    });
};
