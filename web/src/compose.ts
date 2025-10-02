/* Main compose box module for sending messages. */

import autosize from "autosize";
import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_success_message_scheduled_banner from "../templates/compose_banner/success_message_scheduled_banner.hbs";
import render_wildcard_mention_not_allowed_error from "../templates/compose_banner/wildcard_mention_not_allowed_error.hbs";

import * as channel from "./channel.ts";
import * as compose_banner from "./compose_banner.ts";
import * as compose_notifications from "./compose_notifications.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_ui from "./compose_ui.ts";
import * as compose_validate from "./compose_validate.ts";
import * as drafts from "./drafts.ts";
import * as echo from "./echo.ts";
import type {PostMessageAPIData} from "./echo.ts";
import * as message_events from "./message_events.ts";
import type {LocalMessage} from "./message_helper.ts";
import * as onboarding_steps from "./onboarding_steps.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import * as sent_messages from "./sent_messages.ts";
import * as server_events_state from "./server_events_state.ts";
import {current_user} from "./state_data.ts";
import * as transmit from "./transmit.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";
import * as zcommand from "./zcommand.ts";

// Docs: https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html

// This is similar to transmit.SendMessageData but not quite the same.
// We might want to try to consolidate them at some point.
export type SendMessageData = {
    sender_id: number;
    queue_id: string | null;
    to: string;
    content: string;
    resend?: boolean;
    locally_echoed?: boolean;
    draft_id: string;
} & (
    | {
          type: "stream";
          stream_id: number;
          topic: string;
      }
    | {
          type: "private";
          reply_to: string;
          private_message_recipient: string;
          to_user_ids: string | undefined;
          // TODO: It would be nice to only require stream_id and topic
          // on "stream" objects, but that requires some refactoring.
          stream_id: undefined;
          topic: "";
      }
);

export function clear_invites(): void {
    $(
        `#compose_banners .${CSS.escape(compose_banner.CLASSNAMES.recipient_not_subscribed)}`,
    ).remove();
}

export function clear_private_stream_alert(): void {
    $(`#compose_banners .${CSS.escape(compose_banner.CLASSNAMES.private_stream_warning)}`).remove();
}

export function clear_preview_area(): void {
    $("textarea#compose-textarea").trigger("focus");
    $("#compose .undo_markdown_preview").hide();
    $("#compose .preview_message_area").hide();
    $("#compose .preview_content").empty();
    $("#compose .markdown_preview").show();
    autosize.update($("textarea#compose-textarea"));

    // While in preview mode we disable unneeded compose_control_buttons,
    // so here we are re-enabling those compose_control_buttons
    $("#compose").removeClass("preview_mode");
    $("#compose .preview_mode_disabled .compose_control_button").attr("tabindex", 0);
}

export function show_preview_area(): void {
    // Disable unneeded compose_control_buttons as we don't
    // need them in preview mode.
    $("#compose").addClass("preview_mode");
    $("#compose .preview_mode_disabled .compose_control_button").attr("tabindex", -1);

    $("#compose .markdown_preview").hide();
    $("#compose .undo_markdown_preview").show();
    $("#compose .undo_markdown_preview").trigger("focus");

    render_preview_area();
}

export function render_preview_area(): void {
    const $compose_textarea = $<HTMLTextAreaElement>("textarea#compose-textarea");
    const content = compose_state.message_content();
    const $preview_message_area = $("#compose .preview_message_area");
    compose_ui.render_and_show_preview(
        $("#compose"),
        $("#compose .markdown_preview_spinner"),
        $("#compose .preview_content"),
        content,
    );
    const edit_height = $compose_textarea.height();
    $preview_message_area.css({"min-height": edit_height + "px"});
    $preview_message_area.show();
}

export function clear_compose_box(): void {
    /* Before clearing the compose box, we reset it to the
     * default/normal size. Note that for locally echoed messages, we
     * will have already done this action before echoing the message
     * to avoid the compose box triggering "new message out of view"
     * notifications incorrectly. */
    if (compose_ui.is_expanded()) {
        compose_ui.make_compose_box_original_size();
    }
    $("textarea#compose-textarea").val("").trigger("focus");
    compose_ui.compose_textarea_typeahead?.hide();
    compose_validate.check_overflow_text($("#send_message_form"));
    compose_validate.clear_topic_resolved_warning();
    drafts.set_compose_draft_id(undefined);
    compose_ui.autosize_textarea($("textarea#compose-textarea"));
    compose_banner.clear_errors();
    compose_banner.clear_warnings();
    compose_banner.clear_uploads();
    compose_ui.hide_compose_spinner();
    scheduled_messages.reset_selected_schedule_timestamp();
    $(".needs-empty-compose").removeClass("disabled-on-hover");
}

export type SentMessageData = SendMessageData & {
    local_id: string;
    locally_echoed: boolean;
    resend: boolean;
};

export function send_message_success(
    sent_message: SentMessageData | LocalMessage,
    data: PostMessageAPIData,
): void {
    if (!sent_message.locally_echoed) {
        clear_compose_box();
    }

    echo.reify_message_id(sent_message.local_id, data.id);
    drafts.draft_model.deleteDrafts([sent_message.draft_id]);

    if (sent_message.type === "stream") {
        if (data.automatic_new_visibility_policy) {
            if (!onboarding_steps.ONE_TIME_NOTICES_TO_DISPLAY.has("visibility_policy_banner")) {
                return;
            }
            // topic has been automatically unmuted or followed. No need to
            // suggest the user to unmute. Show the banner and return.
            compose_notifications.notify_automatic_new_visibility_policy(sent_message, {
                ...data,
                automatic_new_visibility_policy: data.automatic_new_visibility_policy,
            });
            return;
        }

        const muted_narrow = compose_notifications.get_muted_narrow(sent_message);
        if (muted_narrow) {
            compose_notifications.notify_unmute(
                muted_narrow,
                sent_message.stream_id,
                sent_message.topic,
            );
        }
    }
}

export let send_message = (): void => {
    // Changes here must also be kept in sync with echo.try_deliver_locally
    compose_state.set_recipient_edited_manually(false);
    compose_state.set_is_content_unedited_restored_draft(false);

    // Silently save / update a draft to ensure the message is not lost in case send fails.
    // We delete the draft on successful send.
    const draft_id = drafts.update_draft({
        no_notify: true,
        update_count: false,
        is_sending_saving: true,
        // Even 2-character messages that you actually tried to send
        // should be saved as a draft, since it's confusing if a
        // message can just disappear into the void.
        force_save: true,
    });
    assert(draft_id !== undefined);

    const message_type = compose_state.get_message_type();
    assert(message_type !== undefined);
    let message_data: SendMessageData;
    if (message_type === "private") {
        const recipient_emails = compose_state.private_message_recipient_emails();
        const recipient_ids = compose_state.private_message_recipient_ids();
        message_data = {
            type: message_type,
            content: compose_state.message_content(),
            sender_id: current_user.user_id,
            queue_id: server_events_state.queue_id,
            topic: "",
            to: JSON.stringify(recipient_ids),
            reply_to: recipient_emails,
            private_message_recipient: recipient_emails,
            to_user_ids: util.sorted_ids(recipient_ids).join(","),
            draft_id,
            stream_id: undefined,
        };
    } else {
        const stream_id = compose_state.stream_id();
        assert(stream_id !== undefined);
        const topic = compose_state.topic();
        message_data = {
            type: message_type,
            content: compose_state.message_content(),
            sender_id: current_user.user_id,
            queue_id: server_events_state.queue_id,
            topic: util.is_topic_name_considered_empty(topic) ? "" : topic,
            stream_id,
            to: JSON.stringify([stream_id]),
            draft_id,
        };
    }

    let local_id: string;

    const message = echo.try_deliver_locally(message_data, message_events.insert_new_messages);
    const locally_echoed = Boolean(message);
    if (message) {
        // We are rendering this message locally with an id
        // like 92l99.01 that corresponds to a reasonable
        // approximation of the id we'll get from the server
        // in terms of sorting messages.
        assert(message.local_id !== undefined);
        local_id = message.local_id;
    } else {
        // We are not rendering this message locally, but we
        // track the message's life cycle with an id like
        // loc-1, loc-2, loc-3,etc.
        local_id = sent_messages.get_new_local_id();
    }

    function success(data: unknown): void {
        const parsed_data = z
            .object({
                id: z.number(),
                automatic_new_visibility_policy: z.optional(z.number()),
            })
            .parse(data);
        send_message_success(
            {
                ...message_data,
                local_id,
                locally_echoed,
                resend: false,
            },
            parsed_data,
        );
    }

    function error(response: string, server_error_code: string): void {
        // Error callback for failed message send attempts.
        if (!locally_echoed) {
            if (server_error_code === "TOPIC_WILDCARD_MENTION_NOT_ALLOWED") {
                // The topic wildcard mention permission code path has
                // a special error.
                const new_row_html = render_wildcard_mention_not_allowed_error({
                    banner_type: compose_banner.ERROR,
                    classname: compose_banner.CLASSNAMES.wildcards_not_allowed,
                });
                compose_banner.append_compose_banner_to_banner_list(
                    $(new_row_html),
                    $("#compose_banners"),
                );
            } else {
                compose_banner.show_error_message(
                    response,
                    compose_banner.CLASSNAMES.generic_compose_error,
                    $("#compose_banners"),
                    $("textarea#compose-textarea"),
                );
            }

            // For messages that were not locally echoed, we're
            // responsible for hiding the compose spinner to restore
            // the compose box so one can send a next message.
            //
            // (Restoring this state is handled by clear_compose_box
            // for locally echoed messages.)
            compose_ui.hide_compose_spinner();
            return;
        }

        assert(message !== undefined);
        echo.message_send_error(message.id, response);

        // We might not have updated the draft count because we assumed the
        // message would send. Ensure that the displayed count is correct.
        drafts.sync_count();

        assert(draft_id !== undefined);
        const draft = drafts.draft_model.getDraft(draft_id);
        assert(draft !== false);
        draft.is_sending_saving = false;
        drafts.draft_model.editDraft(draft_id, draft);
    }

    transmit.send_message(
        {...message_data, local_id, locally_echoed, resend: false},
        success,
        error,
    );
    server_events_state.assert_get_events_running(
        "Restarting get_events because it was not running during send",
    );

    if (locally_echoed) {
        clear_compose_box();
        assert(message !== undefined);
        // Schedule a timer to display a spinner when the message is
        // taking a longtime to send.
        setTimeout(() => {
            echo.display_slow_send_loading_spinner(message);
        }, 5000);
    }
};

export function rewire_send_message(value: typeof send_message): void {
    send_message = value;
}

export function handle_enter_key_with_preview_open(cmd_or_ctrl_pressed = false): void {
    if (
        (user_settings.enter_sends && !cmd_or_ctrl_pressed) ||
        (!user_settings.enter_sends && cmd_or_ctrl_pressed)
    ) {
        // If this enter should send, we attempt to send the message.
        finish();
    } else {
        // Otherwise, we return to the normal compose state.
        clear_preview_area();
    }
}

// Common entrypoint for asking the server to send the message
// currently drafted in the compose box, including for scheduled
// messages.
export let finish = (scheduling_message = false): boolean | undefined => {
    if (compose_ui.compose_spinner_visible) {
        // Avoid sending a message twice in parallel in races where
        // the user clicks the `Send` button very quickly twice or
        // presses enter and the send button simultaneously.
        return undefined;
    }

    clear_invites();
    clear_private_stream_alert();
    compose_banner.clear_message_sent_banners();

    const message_content = compose_state.message_content();

    // Skip normal validation for zcommands, since they aren't
    // actual messages with recipients; users only send them
    // from the compose box for convenience sake.
    if (zcommand.process(message_content)) {
        do_post_send_tasks();
        clear_compose_box();
        return undefined;
    }

    compose_ui.show_compose_spinner();

    if (!compose_validate.validate(scheduling_message)) {
        // If the message failed validation, hide compose spinner.
        compose_ui.hide_compose_spinner();
        return false;
    }

    if (scheduling_message) {
        schedule_message_to_custom_date();
    } else {
        send_message();
    }
    do_post_send_tasks();
    return true;
};

export function rewire_finish(value: typeof finish): void {
    finish = value;
}

export function do_post_send_tasks(): void {
    clear_preview_area();
    // TODO: Do we want to fire the event even if the send failed due
    // to a server-side error?
    $(document).trigger("compose_finished.zulip");
}

function schedule_message_to_custom_date(): void {
    const deliver_at = scheduled_messages.get_formatted_selected_send_later_time();
    const scheduled_delivery_timestamp = scheduled_messages.get_selected_send_later_timestamp();

    const message_type = compose_state.get_message_type();
    let req_type;

    if (message_type === "private") {
        req_type = "direct";
    } else {
        req_type = message_type;
    }

    let message_to;
    if (message_type === "private") {
        message_to = compose_state.private_message_recipient_ids();
    } else {
        message_to = compose_state.stream_id();
    }

    const scheduled_message_data = {
        type: req_type,
        to: JSON.stringify(message_to),
        topic: message_type === "stream" ? compose_state.topic() : "",
        content: compose_state.message_content(),
        scheduled_delivery_timestamp,
    };

    const draft_id = drafts.update_draft({
        no_notify: true,
        update_count: false,
        is_sending_saving: true,
    });
    assert(draft_id !== undefined);

    const $banner_container = $("#compose_banners");
    const success = function (data: unknown): void {
        drafts.draft_model.deleteDrafts([draft_id]);
        clear_compose_box();
        const {scheduled_message_id} = z.object({scheduled_message_id: z.number()}).parse(data);
        const new_row_html = render_success_message_scheduled_banner({
            scheduled_message_id,
            minimum_scheduled_message_delay_minutes:
                scheduled_messages.MINIMUM_SCHEDULED_MESSAGE_DELAY_SECONDS / 60,
            deliver_at,
            minimum_scheduled_message_delay_minutes_note:
                scheduled_messages.show_minimum_scheduled_message_delay_minutes_note,
        });
        compose_banner.clear_message_sent_banners();
        compose_banner.append_compose_banner_to_banner_list($(new_row_html), $banner_container);
    };

    const error = function (xhr: JQuery.jqXHR<unknown>): void {
        const response = channel.xhr_error_message("Error sending message", xhr);
        compose_ui.hide_compose_spinner();
        compose_banner.show_error_message(
            response,
            compose_banner.CLASSNAMES.generic_compose_error,
            $banner_container,
            $("textarea#compose-textarea"),
        );
        const draft = drafts.draft_model.getDraft(draft_id);
        assert(draft !== false);
        draft.is_sending_saving = false;
        drafts.draft_model.editDraft(draft_id, draft);
    };

    channel.post({
        url: "/json/scheduled_messages",
        data: scheduled_message_data,
        success,
        error,
    });
}

export function is_topic_input_focused(): boolean {
    return $("#stream_message_recipient_topic").is(":focus");
}
