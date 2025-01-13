import $ from "jquery";

import * as compose_actions from "./compose_actions.ts";
import {$t, $t_html} from "./i18n.ts";
import * as message_lists from "./message_lists.ts";
import * as message_store from "./message_store.ts";
import * as message_util from "./message_util.ts";
import * as narrow_state from "./narrow_state.ts";
import * as people from "./people.ts";
import * as stream_data from "./stream_data.ts";
import * as util from "./util.ts";

type RecipientLabel = {
    label_text: string;
    has_empty_string_topic?: boolean;
    stream_name?: string;
};

function get_stream_recipient_label(stream_id: number, topic: string): RecipientLabel | undefined {
    const stream = stream_data.get_sub_by_id(stream_id);
    const topic_display_name = util.get_final_topic_display_name(topic);
    if (stream) {
        const recipient_label: RecipientLabel = {
            label_text: "#" + stream.name + " > " + topic_display_name,
            has_empty_string_topic: topic === "",
            stream_name: stream.name,
        };
        return recipient_label;
    }
    return undefined;
}

type ComposeClosedMessage = {
    stream_id?: number | undefined;
    topic?: string;
    display_reply_to?: string | undefined;
};

export function get_recipient_label(message?: ComposeClosedMessage): RecipientLabel | undefined {
    // TODO: This code path is bit of a type-checking disaster; we mix
    // actual message objects with fake objects containing just a
    // couple fields, both those constructed here and potentially
    // passed in.
    if (message_lists.current === undefined) {
        return undefined;
    }

    if (message === undefined) {
        if (message_lists.current.visibly_empty()) {
            // For empty narrows where there's a clear reply target,
            // i.e. stream+topic or a single direct message conversation,
            // we label the button as replying to the thread.
            const stream_id = narrow_state.stream_sub()?.stream_id;
            const topic = narrow_state.topic();
            if (stream_id !== undefined && topic !== undefined) {
                return get_stream_recipient_label(stream_id, topic);
            } else if (narrow_state.pm_ids_string()) {
                const user_ids = people.user_ids_string_to_ids_array(narrow_state.pm_ids_string()!);
                return {label_text: message_store.get_pm_full_names(user_ids)};
            }
        } else {
            message = message_lists.current.selected_message();
        }
    }

    if (message) {
        if (message.stream_id !== undefined && message.topic !== undefined) {
            return get_stream_recipient_label(message.stream_id, message.topic);
        } else if (message.display_reply_to) {
            return {label_text: message.display_reply_to};
        }
    }
    return undefined;
}

// Exported for tests
export let update_reply_button_state = (disable = false): void => {
    $(".compose_reply_button").attr("disabled", disable ? "disabled" : null);
    if (disable) {
        if (maybe_get_selected_message_stream_id() !== undefined) {
            $("#compose_buttons .compose-reply-button-wrapper").attr(
                "data-reply-button-type",
                "stream_disabled",
            );
        } else {
            $("#compose_buttons .compose-reply-button-wrapper").attr(
                "data-reply-button-type",
                "direct_disabled",
            );
        }
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

function maybe_get_selected_message_stream_id(): number | undefined {
    if (message_lists.current?.visibly_empty()) {
        return undefined;
    }
    const selected_message = message_lists.current?.selected_message();
    if (!selected_message?.is_stream) {
        return undefined;
    }
    return selected_message.stream_id;
}

function should_disable_compose_reply_button_for_stream(): boolean {
    const stream_id = maybe_get_selected_message_stream_id();
    if (stream_id !== undefined) {
        const stream = stream_data.get_sub_by_id(stream_id);
        if (stream && !stream_data.can_post_messages_in_stream(stream)) {
            return true;
        }
    }
    return false;
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
    update_buttons(should_disable_compose_reply_button_for_stream());
}

export function update_buttons_for_non_specific_views(): void {
    $("#new_conversation_button").attr("data-conversation-type", "non-specific");
    update_buttons(should_disable_compose_reply_button_for_stream());
}

function set_reply_button_label(label: string): void {
    $("#left_bar_compose_reply_button_big").text(label);
}

export function set_standard_text_for_reply_button(): void {
    set_reply_button_label($t({defaultMessage: "Compose message"}));
}

export function update_reply_recipient_label(message?: ComposeClosedMessage): void {
    const recipient_label = get_recipient_label(message);
    if (recipient_label !== undefined) {
        if (!recipient_label.has_empty_string_topic) {
            const recipient_label_text = recipient_label.label_text;
            set_reply_button_label(
                $t({defaultMessage: "Message {recipient_label_text}"}, {recipient_label_text}),
            );
        } else {
            const topic_display_name = util.get_final_topic_display_name("");
            const recipient_label_html = $t_html(
                {
                    defaultMessage: "Message <z-recipient-label></z-recipient-label>",
                },
                {
                    "z-recipient-label": () =>
                        `#${recipient_label.stream_name} > <span class="empty-topic-display">${topic_display_name}</span>`,
                },
            );
            $("#left_bar_compose_reply_button_big").html(recipient_label_html);
        }
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

            // Disable compose reply button if the selected message is a stream
            // message and the user is not allowed to post in the stream the message
            // belongs to.
            if (maybe_get_selected_message_stream_id() !== undefined) {
                update_buttons_for_stream_views();
                update_buttons_for_non_specific_views();
            }
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
