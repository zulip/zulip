/* Main compose box module for sending messages. */

import autosize from "autosize";
import $ from "jquery";

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
import * as message_events from "./message_events.ts";
import * as onboarding_steps from "./onboarding_steps.ts";
import * as people from "./people.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import * as sent_messages from "./sent_messages.ts";
import * as server_events_state from "./server_events_state.ts";
import {current_user} from "./state_data.ts";
import * as transmit from "./transmit.js";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";
import * as zcommand from "./zcommand.ts";

// Docs: https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html

export function clear_invites() {
    $(
        `#compose_banners .${CSS.escape(compose_banner.CLASSNAMES.recipient_not_subscribed)}`,
    ).remove();
}

export function clear_private_stream_alert() {
    $(`#compose_banners .${CSS.escape(compose_banner.CLASSNAMES.private_stream_warning)}`).remove();
}

export function clear_preview_area() {
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

export function show_preview_area() {
    // Disable unneeded compose_control_buttons as we don't
    // need them in preview mode.
    $("#compose").addClass("preview_mode");
    $("#compose .preview_mode_disabled .compose_control_button").attr("tabindex", -1);

    $("#compose .markdown_preview").hide();
    $("#compose .undo_markdown_preview").show();
    $("#compose .undo_markdown_preview").trigger("focus");

    render_preview_area();
}

export function render_preview_area() {
    const $compose_textarea = $("textarea#compose-textarea");
    const content = $compose_textarea.val();
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

export function create_message_object(message_content = compose_state.message_content()) {
    // Changes here must also be kept in sync with echo.try_deliver_locally
    const message = {
        type: compose_state.get_message_type(),
        content: message_content,
        sender_id: current_user.user_id,
        queue_id: server_events_state.queue_id,
        stream_id: undefined,
    };
    message.topic = "";

    if (message.type === "private") {
        // TODO: this should be collapsed with the code in composebox_typeahead.ts
        const recipient = compose_state.private_message_recipient_emails();
        const emails = util.extract_pm_recipients(recipient);
        message.to = emails;
        message.reply_to = recipient;
        message.private_message_recipient = recipient;
        message.to_user_ids = people.email_list_to_user_ids_string(emails);

        // Note: The `undefined` case is for situations like
        // the is_zephyr_mirror_realm case where users may
        // be automatically created when you try to send a
        // direct message to their email address.
        if (message.to_user_ids !== undefined) {
            message.to = people.user_ids_string_to_ids_array(message.to_user_ids);
        }
    } else {
        const topic = compose_state.topic();
        message.topic = util.is_topic_name_considered_empty(topic) ? "" : topic;
        const stream_id = compose_state.stream_id();
        message.stream_id = stream_id;
        message.to = stream_id;
    }
    return message;
}

export function clear_compose_box() {
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

export function send_message_success(request, data) {
    if (!request.locally_echoed) {
        clear_compose_box();
    }

    echo.reify_message_id(request.local_id, data.id);
    drafts.draft_model.deleteDrafts([request.draft_id]);

    if (request.type === "stream") {
        if (data.automatic_new_visibility_policy) {
            if (!onboarding_steps.ONE_TIME_NOTICES_TO_DISPLAY.has("visibility_policy_banner")) {
                return;
            }
            // topic has been automatically unmuted or followed. No need to
            // suggest the user to unmute. Show the banner and return.
            compose_notifications.notify_automatic_new_visibility_policy(request, data);
            return;
        }

        const muted_narrow = compose_notifications.get_muted_narrow(request);
        if (muted_narrow) {
            compose_notifications.notify_unmute(muted_narrow, request.stream_id, request.topic);
        }
    }
}

export let send_message = (request = create_message_object()) => {
    compose_state.set_recipient_edited_manually(false);
    compose_state.set_is_content_unedited_restored_draft(false);
    if (request.type === "private") {
        request.to = JSON.stringify(request.to);
    } else {
        request.to = JSON.stringify([request.to]);
    }

    // Silently save / update a draft to ensure the message is not lost in case send fails.
    // We delete the draft on successful send.
    request.draft_id = drafts.update_draft({
        no_notify: true,
        update_count: false,
        is_sending_saving: true,
    });

    let local_id;
    let locally_echoed;

    const message = echo.try_deliver_locally(request, message_events.insert_new_messages);
    if (message) {
        // We are rendering this message locally with an id
        // like 92l99.01 that corresponds to a reasonable
        // approximation of the id we'll get from the server
        // in terms of sorting messages.
        local_id = message.local_id;
        locally_echoed = true;
    } else {
        // We are not rendering this message locally, but we
        // track the message's life cycle with an id like
        // loc-1, loc-2, loc-3,etc.
        locally_echoed = false;
        local_id = sent_messages.get_new_local_id();
    }

    request.local_id = local_id;
    request.locally_echoed = locally_echoed;
    request.resend = false;

    function success(data) {
        send_message_success(request, data);
    }

    function error(response, server_error_code) {
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

        echo.message_send_error(message.id, response);

        // We might not have updated the draft count because we assumed the
        // message would send. Ensure that the displayed count is correct.
        drafts.sync_count();

        const draft = drafts.draft_model.getDraft(request.draft_id);
        draft.is_sending_saving = false;
        drafts.draft_model.editDraft(request.draft_id, draft);
    }

    transmit.send_message(request, success, error);
    server_events_state.assert_get_events_running(
        "Restarting get_events because it was not running during send",
    );

    if (locally_echoed) {
        clear_compose_box();
        // Schedule a timer to display a spinner when the message is
        // taking a longtime to send.
        setTimeout(() => echo.display_slow_send_loading_spinner(message), 5000);
    }
};

export function rewire_send_message(value) {
    send_message = value;
}

export function handle_enter_key_with_preview_open(cmd_or_ctrl_pressed = false) {
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
export let finish = (scheduling_message = false) => {
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

export function rewire_finish(value) {
    finish = value;
}

export function do_post_send_tasks() {
    clear_preview_area();
    // TODO: Do we want to fire the event even if the send failed due
    // to a server-side error?
    $(document).trigger("compose_finished.zulip");
}

function schedule_message_to_custom_date() {
    const compose_message_object = create_message_object();

    const deliver_at = scheduled_messages.get_formatted_selected_send_later_time();
    const scheduled_delivery_timestamp = scheduled_messages.get_selected_send_later_timestamp();

    const message_type = compose_message_object.type;
    let req_type;

    if (message_type === "private") {
        req_type = "direct";
    } else {
        req_type = message_type;
    }

    const scheduled_message_data = {
        type: req_type,
        to: JSON.stringify(compose_message_object.to),
        topic: compose_message_object.topic,
        content: compose_message_object.content,
        scheduled_delivery_timestamp,
    };

    const draft_id = drafts.update_draft({
        no_notify: true,
        update_count: false,
        is_sending_saving: true,
    });

    const $banner_container = $("#compose_banners");
    const success = function (data) {
        drafts.draft_model.deleteDrafts([draft_id]);
        clear_compose_box();
        const new_row_html = render_success_message_scheduled_banner({
            scheduled_message_id: data.scheduled_message_id,
            minimum_scheduled_message_delay_minutes:
                scheduled_messages.MINIMUM_SCHEDULED_MESSAGE_DELAY_SECONDS / 60,
            deliver_at,
            minimum_scheduled_message_delay_minutes_note:
                scheduled_messages.show_minimum_scheduled_message_delay_minutes_note,
        });
        compose_banner.clear_message_sent_banners();
        compose_banner.append_compose_banner_to_banner_list($(new_row_html), $banner_container);
    };

    const error = function (xhr) {
        const response = channel.xhr_error_message("Error sending message", xhr);
        compose_ui.hide_compose_spinner();
        compose_banner.show_error_message(
            response,
            compose_banner.CLASSNAMES.generic_compose_error,
            $banner_container,
            $("textarea#compose-textarea"),
        );
        const draft = drafts.draft_model.getDraft(draft_id);
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

export function is_topic_input_focused() {
    return $("#stream_message_recipient_topic").is(":focus");
}
