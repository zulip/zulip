/* Main compose box module for sending messages. */

import autosize from "autosize";
import $ from "jquery";
import _ from "lodash";

import render_success_message_scheduled_banner from "../templates/compose_banner/success_message_scheduled_banner.hbs";

import * as channel from "./channel";
import * as compose_banner from "./compose_banner";
import * as compose_notifications from "./compose_notifications";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as compose_validate from "./compose_validate";
import * as drafts from "./drafts";
import * as echo from "./echo";
import {$t_html} from "./i18n";
import * as loading from "./loading";
import * as markdown from "./markdown";
import * as message_events from "./message_events";
import {page_params} from "./page_params";
import * as people from "./people";
import * as rendered_markdown from "./rendered_markdown";
import * as scheduled_messages from "./scheduled_messages";
import * as sent_messages from "./sent_messages";
import * as server_events from "./server_events";
import * as transmit from "./transmit";
import {user_settings} from "./user_settings";
import * as util from "./util";
import * as zcommand from "./zcommand";

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
    $("#compose-textarea").show();
    $("#compose-textarea").trigger("focus");
    $("#compose .undo_markdown_preview").hide();
    $("#compose .preview_message_area").hide();
    $("#compose .preview_content").empty();
    $("#compose .markdown_preview").show();
    autosize.update($("#compose-textarea"));

    // While in preview mode we disable unneeded compose_control_buttons,
    // so here we are re-enabling those compose_control_buttons
    $("#compose").removeClass("preview_mode");
    $("#compose .preview_mode_disabled .compose_control_button").attr("tabindex", 0);
}

export function create_message_object() {
    // Topics are optional, and we provide a placeholder if one isn't given.
    let topic = compose_state.topic();
    if (topic === "") {
        topic = compose_state.empty_topic_placeholder();
    }

    // Changes here must also be kept in sync with echo.try_deliver_locally
    const message = {
        type: compose_state.get_message_type(),
        content: compose_state.message_content(),
        sender_id: page_params.user_id,
        queue_id: page_params.queue_id,
        stream_id: undefined,
    };
    message.topic = "";

    if (message.type === "private") {
        // TODO: this should be collapsed with the code in composebox_typeahead.js
        const recipient = compose_state.private_message_recipient();
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
        message.topic = topic;
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
    if (compose_ui.is_full_size()) {
        compose_ui.make_compose_box_original_size();
    }
    $("#compose-textarea").val("").trigger("focus");
    compose_validate.check_overflow_text();
    compose_validate.clear_topic_resolved_warning();
    $("#compose-textarea").removeData("draft-id");
    compose_ui.autosize_textarea($("#compose-textarea"));
    compose_banner.clear_errors();
    compose_banner.clear_warnings();
    compose_banner.clear_uploads();
    compose_ui.hide_compose_spinner();
    scheduled_messages.reset_selected_schedule_timestamp();
    $(".compose_control_button_container:has(.add-poll)").removeClass("disabled");
}

export function send_message_success(request, data) {
    if (!request.locally_echoed) {
        if ($("#compose-textarea").data("draft-id")) {
            drafts.draft_model.deleteDraft($("#compose-textarea").data("draft-id"));
        }
        clear_compose_box();
    }

    echo.reify_message_id(request.local_id, data.id);

    if (request.type === "stream") {
        if (data.automatic_new_visibility_policy) {
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

export function send_message(request = create_message_object()) {
    compose_state.set_recipient_edited_manually(false);
    if (request.type === "private") {
        request.to = JSON.stringify(request.to);
    } else {
        request.to = JSON.stringify([request.to]);
    }

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

    function error(response) {
        // If we're not local echo'ing messages, or if this message was not
        // locally echoed, show error in compose box
        if (!locally_echoed) {
            compose_banner.show_error_message(
                response,
                compose_banner.CLASSNAMES.generic_compose_error,
                $("#compose_banners"),
                $("#compose-textarea"),
            );
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
    }

    transmit.send_message(request, success, error);
    server_events.assert_get_events_running(
        "Restarting get_events because it was not running during send",
    );

    if (locally_echoed) {
        clear_compose_box();
        // Schedule a timer to display a spinner when the message is
        // taking a longtime to send.
        setTimeout(() => echo.display_slow_send_loading_spinner(message), 5000);
    }
}

export function enter_with_preview_open(ctrl_pressed = false) {
    if (
        (user_settings.enter_sends && !ctrl_pressed) ||
        (!user_settings.enter_sends && ctrl_pressed)
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
export function finish(scheduling_message = false) {
    if (compose_ui.compose_spinner_visible) {
        // Avoid sending a message twice in parallel in races where
        // the user clicks the `Send` button very quickly twice or
        // presses enter and the send button simultaneously.
        return undefined;
    }

    clear_preview_area();
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
}

export function do_post_send_tasks() {
    clear_preview_area();
    // TODO: Do we want to fire the event even if the send failed due
    // to a server-side error?
    $(document).trigger("compose_finished.zulip");
}

export function render_and_show_preview($preview_spinner, $preview_content_box, content) {
    function show_preview(rendered_content, raw_content) {
        // content is passed to check for status messages ("/me ...")
        // and will be undefined in case of errors
        let rendered_preview_html;
        if (raw_content !== undefined && markdown.is_status_message(raw_content)) {
            // Handle previews of /me messages
            rendered_preview_html =
                "<p><strong>" +
                _.escape(page_params.full_name) +
                "</strong>" +
                rendered_content.slice("<p>/me".length);
        } else {
            rendered_preview_html = rendered_content;
        }

        $preview_content_box.html(util.clean_user_content_links(rendered_preview_html));
        rendered_markdown.update_elements($preview_content_box);
    }

    if (content.length === 0) {
        show_preview($t_html({defaultMessage: "Nothing to preview"}));
    } else {
        if (markdown.contains_backend_only_syntax(content)) {
            const $spinner = $preview_spinner.expectOne();
            loading.make_indicator($spinner);
        } else {
            // For messages that don't appear to contain syntax that
            // is only supported by our backend Markdown processor, we
            // render using the frontend Markdown processor (but still
            // render server-side to ensure the preview is accurate;
            // if the `markdown.contains_backend_only_syntax` logic is
            // wrong, users will see a brief flicker of the locally
            // echoed frontend rendering before receiving the
            // authoritative backend rendering from the server).
            const message_obj = {
                raw_content: content,
            };
            markdown.apply_markdown(message_obj);
        }
        channel.post({
            url: "/json/messages/render",
            data: {content},
            success(response_data) {
                if (markdown.contains_backend_only_syntax(content)) {
                    loading.destroy_indicator($preview_spinner);
                }
                show_preview(response_data.rendered, content);
            },
            error() {
                if (markdown.contains_backend_only_syntax(content)) {
                    loading.destroy_indicator($preview_spinner);
                }
                show_preview($t_html({defaultMessage: "Failed to generate preview"}));
            },
        });
    }
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

    const $banner_container = $("#compose_banners");
    const success = function (data) {
        drafts.draft_model.deleteDraft($("#compose-textarea").data("draft-id"));
        clear_compose_box();
        const new_row = render_success_message_scheduled_banner({
            scheduled_message_id: data.scheduled_message_id,
            deliver_at,
        });
        compose_banner.clear_message_sent_banners();
        compose_banner.append_compose_banner_to_banner_list(new_row, $banner_container);
    };

    const error = function (xhr) {
        const response = channel.xhr_error_message("Error sending message", xhr);
        compose_ui.hide_compose_spinner();
        compose_banner.show_error_message(
            response,
            compose_banner.CLASSNAMES.generic_compose_error,
            $banner_container,
            $("#compose-textarea"),
        );
    };

    channel.post({
        url: "/json/scheduled_messages",
        data: scheduled_message_data,
        success,
        error,
    });
}
