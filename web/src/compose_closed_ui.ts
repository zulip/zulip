import $ from "jquery";
import assert from "minimalistic-assert";

import render_decorated_channel_name from "../templates/decorated_channel_name.hbs";
import render_reply_recipient_label from "../templates/reply_recipient_label.hbs";

import * as compose_actions from "./compose_actions.ts";
import {$t} from "./i18n.ts";
import * as inbox_util from "./inbox_util.ts";
import * as message_lists from "./message_lists.ts";
import * as message_store from "./message_store.ts";
import * as message_util from "./message_util.ts";
import * as narrow_state from "./narrow_state.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as recent_view_util from "./recent_view_util.ts";
import * as stream_color from "./stream_color.ts";
import * as stream_data from "./stream_data.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as util from "./util.ts";

// This is likely a temporary function for supporting both the
// new skinned compose box in conversation views and the legacy
// closed compose box in home views, etc.
export function update_closed_compose_box_class_by_narrow(is_conversation_narrow: boolean): void {
    if (is_conversation_narrow) {
        $("#compose").addClass("composing-to-conversation-narrow");
    } else {
        $("#compose").removeClass("composing-to-conversation-narrow");
    }
}

type RecipientLabel = {
    label_text?: string;
    has_empty_string_topic?: boolean;
    stream?: StreamSubscription;
    topic_display_name?: string;
    is_dm_with_self?: boolean;
    user_ids?: number[];
};

function get_stream_recipient_label(stream_id: number, topic: string): RecipientLabel | undefined {
    const stream = stream_data.get_sub_by_id(stream_id);
    const topic_display_name = util.get_final_topic_display_name(topic);
    if (stream) {
        const recipient_label: RecipientLabel = {
            has_empty_string_topic: topic === "",
            stream,
            topic_display_name,
        };
        return recipient_label;
    }
    return undefined;
}

function get_direct_message_recipient_label(user_ids: number[]): RecipientLabel {
    let label_text = "";
    let is_dm_with_self = false;
    if (people.is_direct_message_conversation_with_self(user_ids)) {
        is_dm_with_self = true;
    } else {
        label_text = message_store.get_pm_full_names(user_ids);
    }
    const recipient_label: RecipientLabel = {
        label_text,
        is_dm_with_self,
        user_ids,
    };
    return recipient_label;
}

export type ReplyRecipientInformation = {
    stream_id?: number | undefined;
    topic?: string | undefined;
    user_ids?: number[] | undefined;
    display_reply_to?: string | undefined;
};

export function get_recipient_label(
    recipient_information?: ReplyRecipientInformation,
): RecipientLabel | undefined {
    if (recipient_information !== undefined) {
        assert(recent_view_util.is_visible() || inbox_util.is_visible());
        // When we're in either the Inbox or Recent Conversations view,
        // we try to update the closed compose box button label with
        // information about the reply target from the focused row in
        // the view.
        if (
            recipient_information.stream_id !== undefined &&
            recipient_information.topic !== undefined
        ) {
            return get_stream_recipient_label(
                recipient_information.stream_id,
                recipient_information.topic,
            );
        }
        if (recipient_information.user_ids !== undefined) {
            return get_direct_message_recipient_label(recipient_information.user_ids);
        }
        if (recipient_information.display_reply_to !== undefined) {
            return {label_text: recipient_information.display_reply_to};
        }
    }

    // Otherwise, we check the current message list for information
    // about the reply target for the closed compose box button label.
    if (message_lists.current === undefined) {
        return undefined;
    }

    if (message_lists.current.visibly_empty()) {
        // For empty narrows where there's a clear reply target,
        // i.e. channel and topic or a direct message conversation,
        // we label the button as replying to the thread.
        const stream_id = narrow_state.stream_id(narrow_state.filter(), true);
        const topic = narrow_state.topic();
        const user_ids_string = narrow_state.pm_ids_string();
        if (stream_id !== undefined && topic !== undefined) {
            return get_stream_recipient_label(stream_id, topic);
        }
        if (user_ids_string !== undefined) {
            // Check for validity of user ids to avoid any errors in case user
            // narrowed to an incorrect URL.
            const user_ids = people.user_ids_string_to_ids_array(user_ids_string);
            if (!people.is_valid_user_ids(user_ids)) {
                return undefined;
            }
            return get_direct_message_recipient_label(user_ids);
        }
        // Show the standard button text for empty narrows without
        // a clear reply target, e.g., an empty search view.
        return undefined;
    }

    const selected_message = message_lists.current.selected_message();
    if (selected_message !== undefined) {
        if (selected_message?.is_stream) {
            return get_stream_recipient_label(selected_message.stream_id, selected_message.topic);
        }
        const user_ids = people.user_ids_string_to_ids_array(selected_message.to_user_ids);
        return get_direct_message_recipient_label(user_ids);
    }
    // Fall through to show the standard button text.
    return undefined;
}

// Exported for tests
export let update_reply_button_state = (): void => {
    const $compose_reply_button_wrapper = $(
        "#legacy-closed-compose-box .compose-reply-button-wrapper",
    );
    const stream_id_str = $compose_reply_button_wrapper.attr("data-stream-id");
    const user_ids_string = $compose_reply_button_wrapper.attr("data-user-ids-string");

    let disable = false;
    if (stream_id_str !== undefined) {
        disable = should_disable_compose_reply_button_for_stream(
            Number.parseInt(stream_id_str, 10),
        );
    } else if (user_ids_string !== undefined) {
        disable = should_disable_compose_reply_button_for_direct_message(user_ids_string);
    }

    $(".compose_reply_button").attr("disabled", disable ? "disabled" : null);
    if (disable) {
        if (stream_id_str !== undefined) {
            $compose_reply_button_wrapper.attr("data-reply-button-type", "stream_disabled");
        } else {
            $compose_reply_button_wrapper.attr("data-reply-button-type", "direct_disabled");
        }
        return;
    }
    if (narrow_state.is_message_feed_visible()) {
        $compose_reply_button_wrapper.attr("data-reply-button-type", "selected_message");
    } else {
        $compose_reply_button_wrapper.attr("data-reply-button-type", "selected_conversation");
    }
};

export function rewire_update_reply_button_state(value: typeof update_reply_button_state): void {
    update_reply_button_state = value;
}

function update_new_conversation_button(data_attribute_string: "stream" | "non-specific"): void {
    $("#new_conversation_button").attr("data-conversation-type", data_attribute_string);
}

function should_disable_compose_reply_button_for_stream(stream_id: number): boolean {
    if (page_params.is_spectator) {
        return false;
    }
    const stream = stream_data.get_sub_by_id(stream_id);
    return stream !== undefined && !stream_data.can_post_messages_in_stream(stream);
}

// Exported for tests
export function should_disable_compose_reply_button_for_direct_message(
    user_ids_string: string,
): boolean {
    return !message_util.user_can_send_direct_message(user_ids_string);
}

export function update_buttons(update_type?: string): void {
    update_new_conversation_button(update_type === "stream" ? "stream" : "non-specific");
    // We omit recipient_information here, so update_reply_button derives
    // the reply target from the current message list: the selected
    // message, or the narrowed conversation in an empty view. (The Inbox
    // and Recent Conversations views instead pass the reply target from
    // their focused row.)
    update_reply_button();
}

export function maybe_update_buttons_for_dm_recipient(): void {
    const filter = narrow_state.filter();
    if (filter?.contains_only_private_messages()) {
        update_buttons("direct");
    }
}

function set_reply_button_label(label: string): void {
    $("#left_bar_compose_reply_button_big").text(label);
}

export function set_standard_text_for_reply_button(): void {
    set_reply_button_label($t({defaultMessage: "Compose message"}));
    const $compose_reply_button_wrapper = $(
        "#legacy-closed-compose-box .compose-reply-button-wrapper",
    );
    // Clear any stale recipient context from a previous reply target.
    $compose_reply_button_wrapper.removeAttr("data-stream-id");
    $compose_reply_button_wrapper.removeAttr("data-user-ids-string");
    $compose_reply_button_wrapper.removeAttr("data-reply-button-type");
    // Reset the stale disabled state if the reply button was
    // previously disabled.
    $(".compose_reply_button").attr("disabled", null);
}

export function update_recipient_row_on_skinned_compose(
    recipient_information?: ReplyRecipientInformation,
): void {
    // We're not currently working with ReplyRecipientInformation in the skinned
    // compose box, as that isn't used inside of conversation views, but these
    // lines make it so that we can cut over to that use in the future.
    const stream_id =
        recipient_information?.stream_id ?? narrow_state.stream_id(narrow_state.filter(), true);
    const topic = recipient_information?.topic ?? narrow_state.topic();

    const user_ids_string = narrow_state.pm_ids_string();
    let user_ids: number[] = [];
    let has_valid_user_ids = false;

    if (recipient_information?.user_ids) {
        user_ids = recipient_information?.user_ids;
    } else if (typeof user_ids_string === "string") {
        user_ids = people.user_ids_string_to_ids_array(user_ids_string);
    }

    has_valid_user_ids = people.is_valid_user_ids(user_ids);

    if (stream_id !== undefined && topic !== undefined) {
        // Update recipient row for stream/topic.
        const stream = stream_data.get_sub_by_id(stream_id);
        const has_empty_string_topic = topic === "";
        const topic_display_name = util.get_final_topic_display_name(topic);

        $("#skinned-channel-picker").html(
            render_decorated_channel_name({stream, show_colored_icon: true}),
        );
        $("#skinned-topic-box-label").text(topic_display_name);

        // Properly display *general chat*
        if (has_empty_string_topic) {
            $("#skinned-topic-box-label").addClass("empty-topic-display");
        } else {
            $("#skinned-topic-box-label").removeClass("empty-topic-display");
        }

        // Show adjusted colors as in the low-attention recipient row
        // of the open compose box.
        stream_color.adjust_stream_privacy_icon_colors(
            stream_id,
            "#skinned-channel-picker .channel-privacy-type-icon",
        );
    } else if (has_valid_user_ids) {
        // Update recipient row for DMs.
        const direct_message_label = $t({defaultMessage: "DM"});
        const dm_label = get_direct_message_recipient_label(user_ids);

        $("#skinned-channel-picker").html(
            `<i class="zulip-icon zulip-icon-users channel-privacy-type-icon"></i>
            <span class="decorated-channel-name">${direct_message_label}</span>`,
        );
        if (dm_label.label_text) {
            $("#skinned-topic-box-label").text(dm_label.label_text);
        }
    } else {
        // We had neither a stream_id or a valid set of user_ids, so we will
        // fall back to displaying the legacy closed compose.
        $("#compose").removeClass("composing-to-conversation-narrow");
    }
}

export function update_reply_button_with_recipient_context(
    recipient_information?: ReplyRecipientInformation,
): void {
    const recipient_label = get_recipient_label(recipient_information);
    const $compose_reply_button_wrapper = $(
        "#legacy-closed-compose-box .compose-reply-button-wrapper",
    );
    if (recipient_label !== undefined) {
        const empty_string_topic_display_name = util.get_final_topic_display_name("");
        const rendered_recipient_label = render_reply_recipient_label({
            has_empty_string_topic: recipient_label.has_empty_string_topic,
            stream: recipient_label.stream,
            topic_display_name: recipient_label.topic_display_name,
            is_dm_with_self: recipient_label.is_dm_with_self,
            empty_string_topic_display_name,
            label_text: recipient_label.label_text,
        });
        // We store the recipient state so that update_reply_button_state
        // can use that information without re-examining the message list
        // or narrow state. The state is reset/unset by
        // set_standard_text_for_reply_button().
        if (recipient_label.stream) {
            // Channel message recipient.
            $compose_reply_button_wrapper.removeAttr("data-user-ids-string");
            $compose_reply_button_wrapper.attr(
                "data-stream-id",
                recipient_label.stream.stream_id.toString(),
            );
        } else if (recipient_label.user_ids) {
            // Direct message recipient.
            $compose_reply_button_wrapper.removeAttr("data-stream-id");
            $compose_reply_button_wrapper.attr(
                "data-user-ids-string",
                recipient_label.user_ids.join(","),
            );
        } else {
            // Fallback case: recipient label from display_reply_to
            // text when we couldn't decode user IDs from the narrow
            // URL. We can't check permissions, so we leave the
            // button enabled.
            $compose_reply_button_wrapper.removeAttr("data-stream-id");
            $compose_reply_button_wrapper.removeAttr("data-user-ids-string");
        }
        $("#left_bar_compose_reply_button_big").html(rendered_recipient_label);
    } else {
        set_standard_text_for_reply_button();
    }
}

// This should be called when updating the reply button so that
// update_reply_button_with_recipient_context() runs before
// update_reply_button_state(), ensuring that the button wrapper
// contains the relevant recipient metadata.
export function update_reply_button(recipient_information?: ReplyRecipientInformation): void {
    update_reply_button_with_recipient_context(recipient_information);
    update_reply_button_state();
}

// Wrapper function to more gracefully handle updates across
// the skinned and legacy closed compose boxes.
export function update_skinned_or_closed_compose_recipient_display(
    recipient_information?: ReplyRecipientInformation,
): void {
    const stream_id =
        recipient_information?.stream_id ?? narrow_state.stream_id(narrow_state.filter(), true);
    let user_can_post = true;

    if (stream_id !== undefined) {
        const stream = stream_data.get_sub_by_id(stream_id);
        if (stream !== undefined) {
            user_can_post = stream_data.can_post_messages_in_stream(stream);
        }
    }
    // The skinned compose box doesn't yet support a state where
    // we don't have a stream/topic or DM recipients.
    if ($("#compose").hasClass("composing-to-conversation-narrow") && user_can_post) {
        update_recipient_row_on_skinned_compose(recipient_information);
    } else {
        // If a user cannot post, then we want to fall back to displaying
        // the legacy closed compose box
        $("#compose").removeClass("composing-to-conversation-narrow");
    }

    // Follow the usual code path for the legacy closed compose
    // without recipient information.
    update_reply_button(recipient_information);
}

export function initialize(): void {
    update_closed_compose_box_class_by_narrow(narrow_state.is_message_feed_visible());

    // When the message selection changes, change the label on the Reply button.
    $(document).on("message_selected.zulip", () => {
        if (narrow_state.is_message_feed_visible()) {
            // message_selected events can occur with Recent Conversations
            // open due to the combined feed view loading in the background,
            // so we only update if message feed is visible.
            update_skinned_or_closed_compose_recipient_display();
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
