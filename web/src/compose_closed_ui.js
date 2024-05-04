import $ from "jquery";

import * as compose_actions from "./compose_actions";
import {$t} from "./i18n";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import * as narrow_state from "./narrow_state";
import * as people from "./people";
import * as stream_data from "./stream_data";

export function get_recipient_label(message) {
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
            if (narrow_state.narrowed_to_topic()) {
                const stream = narrow_state.stream_sub();
                const stream_id = stream?.stream_id;
                message = {
                    stream_id,
                    topic: narrow_state.topic(),
                };
            } else if (narrow_state.pm_ids_string()) {
                // TODO: This is a total hack.  Ideally, we'd rework
                // this to not duplicate the actual compose_actions.ts
                // logic for what happens when you click the button,
                // and not call into random modules with hacky fake
                // "message" objects.
                const user_ids = people.user_ids_string_to_ids_array(narrow_state.pm_ids_string());
                const user_ids_dicts = user_ids.map((user_id) => ({id: user_id}));
                message = {
                    display_reply_to: message_store.get_pm_full_names({
                        type: "private",
                        display_recipient: user_ids_dicts,
                    }),
                };
            }
        } else {
            message = message_lists.current.selected_message();
        }
    }

    if (message) {
        if (message.stream_id && message.topic) {
            const stream = stream_data.get_sub_by_id(message.stream_id);
            if (stream) {
                return "#" + stream.name + " > " + message.topic;
            }
        } else if (message.display_reply_to) {
            return message.display_reply_to;
        }
    }
    return "";
}

function update_reply_button_state(disable = false) {
    $(".compose_reply_button").attr("disabled", disable);
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
}

function update_new_conversation_button(btn_text, is_direct_message_narrow) {
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
}

function update_new_direct_message_button(btn_text) {
    $("#new_direct_message_button").text(btn_text);
}

function toggle_direct_message_button_visibility(is_direct_message_narrow) {
    const $new_direct_message_button_container = $(".new_direct_message_button_container");
    if (is_direct_message_narrow) {
        $new_direct_message_button_container.hide();
    } else {
        $new_direct_message_button_container.show();
    }
}

function update_buttons(text_stream, is_direct_message_narrow, disable_reply) {
    const text_conversation = $t({defaultMessage: "New direct message"});
    update_new_conversation_button(text_stream, is_direct_message_narrow);
    update_new_direct_message_button(text_conversation);
    update_reply_button_state(disable_reply);
    toggle_direct_message_button_visibility(is_direct_message_narrow);
}

export function update_buttons_for_private() {
    const text_stream = $t({defaultMessage: "Start new conversation"});
    const is_direct_message_narrow = true;
    if (
        !narrow_state.pm_ids_string() ||
        people.user_can_direct_message(narrow_state.pm_ids_string())
    ) {
        $("#new_conversation_button").attr("data-conversation-type", "direct");
        update_buttons(text_stream, is_direct_message_narrow);
        return;
    }
    // disable the [Message X] button when in a private narrow
    // if the user cannot dm the current recipient
    const disable_reply = true;
    update_buttons(text_stream, is_direct_message_narrow, disable_reply);
}

export function update_buttons_for_stream_views() {
    const text_stream = $t({defaultMessage: "Start new conversation"});
    $("#new_conversation_button").attr("data-conversation-type", "stream");
    update_buttons(text_stream);
}

export function update_buttons_for_non_specific_views() {
    const text_stream = $t({defaultMessage: "Start new conversation"});
    $("#new_conversation_button").attr("data-conversation-type", "non-specific");
    update_buttons(text_stream);
}

function set_reply_button_label(label) {
    $("#left_bar_compose_reply_button_big").text(label);
}

export function set_standard_text_for_reply_button() {
    set_reply_button_label($t({defaultMessage: "Compose message"}));
}

export function update_reply_recipient_label(message) {
    const recipient_label = get_recipient_label(message);
    if (recipient_label) {
        set_reply_button_label(
            $t({defaultMessage: "Message {recipient_label}"}, {recipient_label}),
        );
    } else {
        set_standard_text_for_reply_button();
    }
}

export function initialize() {
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
}
