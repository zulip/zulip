/* Main compose box module for sending messages. */

import autosize from "autosize";
import $ from "jquery";
import _ from "lodash";

import render_success_message_scheduled_banner from "../templates/compose_banner/success_message_scheduled_banner.hbs";

import * as channel from "./channel";
import * as compose_actions from "./compose_actions";
import * as compose_banner from "./compose_banner";
import {get_recipient_label} from "./compose_closed_ui";
import * as compose_recipient from "./compose_recipient";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as compose_validate from "./compose_validate";
import * as drafts from "./drafts";
import * as echo from "./echo";
import * as flatpickr from "./flatpickr";
import {$t, $t_html} from "./i18n";
import * as loading from "./loading";
import * as markdown from "./markdown";
import * as message_edit from "./message_edit";
import * as message_events from "./message_events";
import * as narrow from "./narrow";
import {page_params} from "./page_params";
import * as people from "./people";
import * as popover_menus from "./popover_menus";
import * as rendered_markdown from "./rendered_markdown";
import * as resize from "./resize";
import * as rows from "./rows";
import * as sent_messages from "./sent_messages";
import * as server_events from "./server_events";
import * as stream_data from "./stream_data";
import * as stream_settings_ui from "./stream_settings_ui";
import * as sub_store from "./sub_store";
import * as subscriber_api from "./subscriber_api";
import {get_timestamp_for_flatpickr} from "./timerender";
import * as transmit from "./transmit";
import * as ui_report from "./ui_report";
import * as upload from "./upload";
import {user_settings} from "./user_settings";
import * as user_topics from "./user_topics";
import * as util from "./util";
import * as zcommand from "./zcommand";

// Docs: https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html

/* Track the state of the @all warning. The user must acknowledge that they are spamming the entire
   stream before the warning will go away. If they try to send before explicitly dismissing the
   warning, they will get an error message too.

   undefined: no @all/@everyone in message;
   false: user typed @all/@everyone;
   true: user clicked YES */

let uppy;

export function get_compose_upload_object() {
    return uppy;
}
export function compute_show_video_chat_button() {
    const available_providers = page_params.realm_available_video_chat_providers;
    if (page_params.realm_video_chat_provider === available_providers.disabled.id) {
        return false;
    }

    if (
        page_params.realm_video_chat_provider === available_providers.jitsi_meet.id &&
        !page_params.jitsi_server_url
    ) {
        return false;
    }

    return true;
}

export function update_audio_and_video_chat_button_display() {
    update_audio_chat_button_display();
    update_video_chat_button_display();
}

export function update_video_chat_button_display() {
    const show_video_chat_button = compute_show_video_chat_button();
    $("#below-compose-content .video_link").toggle(show_video_chat_button);
    $(".message-edit-feature-group .video_link").toggle(show_video_chat_button);
}

export function compute_show_audio_chat_button() {
    const available_providers = page_params.realm_available_video_chat_providers;
    if (
        (available_providers.jitsi_meet &&
            page_params.realm_video_chat_provider === available_providers.jitsi_meet.id) ||
        (available_providers.zoom &&
            page_params.realm_video_chat_provider === available_providers.zoom.id)
    ) {
        return true;
    }
    return false;
}

export function update_audio_chat_button_display() {
    const show_audio_chat_button = compute_show_audio_chat_button();
    $("#below-compose-content .audio_link").toggle(show_audio_chat_button);
    $(".message-edit-feature-group .audio_link").toggle(show_audio_chat_button);
}

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

export function abort_xhr() {
    $("#compose-send-button").prop("disabled", false);
    uppy.cancelAll();
}

export const zoom_token_callbacks = new Map();
export const video_call_xhrs = new Map();

export function abort_video_callbacks(edit_message_id = "") {
    zoom_token_callbacks.delete(edit_message_id);
    if (video_call_xhrs.has(edit_message_id)) {
        video_call_xhrs.get(edit_message_id).abort();
        video_call_xhrs.delete(edit_message_id);
    }
}

export function empty_topic_placeholder() {
    return $t({defaultMessage: "(no topic)"});
}

export function create_message_object() {
    // Topics are optional, and we provide a placeholder if one isn't given.
    let topic = compose_state.topic();
    if (topic === "") {
        topic = empty_topic_placeholder();
    }

    // Changes here must also be kept in sync with echo.try_deliver_locally
    const message = {
        type: compose_state.get_message_type(),
        content: compose_state.message_content(),
        sender_id: page_params.user_id,
        queue_id: page_params.queue_id,
        stream_id: "",
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
    popover_menus.reset_selected_schedule_timestamp();
}

export function send_message_success(local_id, message_id, locally_echoed) {
    if (!locally_echoed) {
        if ($("#compose-textarea").data("draft-id")) {
            drafts.draft_model.deleteDraft($("#compose-textarea").data("draft-id"));
        }
        clear_compose_box();
    }

    echo.reify_message_id(local_id, message_id);
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
        send_message_success(local_id, data.id, locally_echoed);
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

export function update_email(user_id, new_email) {
    let reply_to = compose_state.private_message_recipient();

    if (!reply_to) {
        return;
    }

    reply_to = people.update_email_in_reply_to(reply_to, user_id, new_email);

    compose_state.private_message_recipient(reply_to);
}

function insert_video_call_url(url, target_textarea) {
    const link_text = $t({defaultMessage: "Join video call."});
    compose_ui.insert_syntax_and_focus(`[${link_text}](${url})`, target_textarea, "block", 1);
}

function insert_audio_call_url(url, target_textarea) {
    const link_text = $t({defaultMessage: "Join audio call."});
    compose_ui.insert_syntax_and_focus(`[${link_text}](${url})`, target_textarea, "block", 1);
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

function setup_compose_actions_hooks() {
    compose_actions.register_compose_box_clear_hook(clear_invites);
    compose_actions.register_compose_box_clear_hook(clear_private_stream_alert);
    compose_actions.register_compose_box_clear_hook(clear_preview_area);

    compose_actions.register_compose_cancel_hook(abort_xhr);
    compose_actions.register_compose_cancel_hook(abort_video_callbacks);
}

export function initialize() {
    // Register hooks for compose_actions.
    setup_compose_actions_hooks();

    $("#below-compose-content .video_link").toggle(compute_show_video_chat_button());
    $("#below-compose-content .audio_link").toggle(compute_show_audio_chat_button());

    $("#compose-textarea").on("keydown", (event) => {
        compose_ui.handle_keydown(event, $("#compose-textarea").expectOne());
    });
    $("#compose-textarea").on("keyup", (event) => {
        compose_ui.handle_keyup(event, $("#compose-textarea").expectOne());
    });

    $("#compose-textarea").on("input propertychange", () => {
        compose_validate.warn_if_topic_resolved(false);
        const compose_text_length = compose_validate.check_overflow_text();
        if (compose_text_length !== 0 && $("#compose-textarea").hasClass("invalid")) {
            $("#compose-textarea").toggleClass("invalid", false);
        }
        // Change compose close button tooltip as per condition.
        // We save compose text in draft only if its length is > 2.
        if (compose_text_length > 2) {
            $("#compose_close").attr(
                "data-tooltip-template-id",
                "compose_close_and_save_tooltip_template",
            );
        } else {
            $("#compose_close").attr("data-tooltip-template-id", "compose_close_tooltip_template");
        }
    });

    $("#compose form").on("submit", (e) => {
        e.preventDefault();
        finish();
    });

    resize.watch_manual_resize("#compose-textarea");

    // Updates compose max-height and scroll to bottom button position when
    // there is a change in compose height like when a compose banner is displayed.
    const update_compose_max_height = new ResizeObserver(resize.reset_compose_message_max_height);
    update_compose_max_height.observe(document.querySelector("#compose"));

    upload.feature_check($("#compose .compose_upload_file"));

    function get_input_info(event) {
        const $edit_banners_container = $(event.target).closest(".edit_form_banners");
        const is_edit_input = Boolean($edit_banners_container.length);
        const $banner_container = $edit_banners_container.length
            ? $edit_banners_container
            : $("#compose_banners");
        return {is_edit_input, $banner_container};
    }

    $("body").on(
        "click",
        `.${CSS.escape(
            compose_banner.CLASSNAMES.wildcard_warning,
        )} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            const {$banner_container, is_edit_input} = get_input_info(event);
            const $row = $(event.target).closest(".message_row");
            compose_validate.clear_wildcard_warnings($banner_container);
            compose_validate.set_user_acknowledged_wildcard_flag(true);
            if (is_edit_input) {
                message_edit.save_message_row_edit($row);
            } else if (event.target.dataset.validationTrigger === "schedule") {
                popover_menus.open_send_later_menu();

                // We need to set this flag to true here because `open_send_later_menu` validates the message and sets
                // the user acknowledged wildcard flag back to 'false' and we don't want that to happen because then it
                // would again show the wildcard warning banner when we actually send the message from 'send-later' modal.
                compose_validate.set_user_acknowledged_wildcard_flag(true);
            } else {
                finish();
            }
        },
    );

    const user_not_subscribed_selector = `.${CSS.escape(
        compose_banner.CLASSNAMES.user_not_subscribed,
    )}`;
    $("body").on(
        "click",
        `${user_not_subscribed_selector} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();

            const stream_id = compose_state.stream_id();
            if (stream_id === "") {
                return;
            }
            const sub = stream_data.get_sub_by_id(stream_id);
            stream_settings_ui.sub_or_unsub(sub);
            $(user_not_subscribed_selector).remove();
        },
    );

    $("body").on(
        "click",
        `.${CSS.escape(compose_banner.CLASSNAMES.topic_resolved)} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();

            const $target = $(event.target).parents(".main-view-banner");
            const stream_id = Number.parseInt($target.attr("data-stream-id"), 10);
            const topic_name = $target.attr("data-topic-name");

            message_edit.with_first_message_id(stream_id, topic_name, (message_id) => {
                message_edit.toggle_resolve_topic(message_id, topic_name, true);
                compose_validate.clear_topic_resolved_warning(true);
            });
        },
    );

    $("body").on(
        "click",
        `.${CSS.escape(
            compose_banner.CLASSNAMES.unmute_topic_notification,
        )} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();

            const $target = $(event.target).parents(".main-view-banner");
            const stream_id = Number.parseInt($target.attr("data-stream-id"), 10);
            const topic_name = $target.attr("data-topic-name");

            user_topics.set_user_topic_visibility_policy(
                stream_id,
                topic_name,
                user_topics.all_visibility_policies.UNMUTED,
                false,
                true,
            );
        },
    );

    $("body").on(
        "click",
        `.${CSS.escape(
            compose_banner.CLASSNAMES.unscheduled_message,
        )} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            const send_at_timestamp = popover_menus.get_selected_send_later_timestamp();
            popover_menus.do_schedule_message(send_at_timestamp);
        },
    );

    $("body").on(
        "click",
        `.${CSS.escape(
            compose_banner.CLASSNAMES.recipient_not_subscribed,
        )} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            const {$banner_container} = get_input_info(event);
            const $invite_row = $(event.target).parents(".main-view-banner");

            const user_id = Number.parseInt($invite_row.data("user-id"), 10);
            const stream_id = Number.parseInt($invite_row.data("stream-id"), 10);

            function success() {
                $invite_row.remove();
            }

            function xhr_failure(xhr) {
                let error_message = "Failed to subscribe user!";
                if (xhr.responseJSON?.msg) {
                    error_message = xhr.responseJSON.msg;
                }
                clear_invites();
                compose_banner.show_error_message(
                    error_message,
                    compose_banner.CLASSNAMES.generic_compose_error,
                    $banner_container,
                    $("#compose-textarea"),
                );
                $(event.target).prop("disabled", true);
            }

            const sub = sub_store.get(stream_id);

            subscriber_api.add_user_ids_to_stream([user_id], sub, success, xhr_failure);
        },
    );

    for (const classname of Object.values(compose_banner.CLASSNAMES)) {
        const classname_selector = `.${CSS.escape(classname)}`;
        $("body").on("click", `${classname_selector} .main-view-banner-close-button`, (event) => {
            event.preventDefault();
            $(event.target).parents(classname_selector).remove();
        });
    }

    // Click event binding for "Attach files" button
    // Triggers a click on a hidden file input field

    $("#compose").on("click", ".compose_upload_file", (e) => {
        e.preventDefault();
        e.stopPropagation();

        $("#compose .file_input").trigger("click");
    });

    $("body").on("click", ".video_link", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const show_video_chat_button = compute_show_video_chat_button();

        if (!show_video_chat_button) {
            return;
        }

        generate_and_insert_audio_or_video_call_link($(e.target), false);
    });

    $("body").on("click", ".audio_link", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const show_audio_chat_button = compute_show_audio_chat_button();

        if (!show_audio_chat_button) {
            return;
        }

        generate_and_insert_audio_or_video_call_link($(e.target), true);
    });

    $("body").on("click", ".time_pick", (e) => {
        e.preventDefault();
        e.stopPropagation();

        $(e.target).toggleClass("has_popover");

        let $target_textarea;
        let edit_message_id;
        const compose_click_target = compose_ui.get_compose_click_target(e);
        if ($(compose_click_target).parents(".message_edit_form").length === 1) {
            edit_message_id = rows.id($(compose_click_target).parents(".message_row"));
            $target_textarea = $(`#edit_form_${CSS.escape(edit_message_id)} .message_edit_content`);
        } else {
            $target_textarea = $(compose_click_target).closest("form").find("textarea");
        }

        if ($(e.target).hasClass("has_popover")) {
            const on_timestamp_selection = (val) => {
                const timestr = `<time:${val}> `;
                compose_ui.insert_syntax_and_focus(timestr, $target_textarea);
            };

            flatpickr.show_flatpickr(
                $(compose_click_target)[0],
                on_timestamp_selection,
                get_timestamp_for_flatpickr(),
                {
                    // place the time picker wherever there is space and center it horizontally
                    position: "auto center",
                },
            );
        }
    });

    $("#compose").on("click", ".markdown_preview", (e) => {
        e.preventDefault();
        e.stopPropagation();

        // Disable unneeded compose_control_buttons as we don't
        // need them in preview mode.
        $("#compose").addClass("preview_mode");
        $("#compose .preview_mode_disabled .compose_control_button").attr("tabindex", -1);

        const content = $("#compose-textarea").val();
        $("#compose-textarea").hide();
        $("#compose .markdown_preview").hide();
        $("#compose .undo_markdown_preview").show();
        $("#compose .undo_markdown_preview").trigger("focus");
        $("#compose .preview_message_area").show();

        render_and_show_preview(
            $("#compose .markdown_preview_spinner"),
            $("#compose .preview_content"),
            content,
        );
    });

    $("#compose").on("click", ".undo_markdown_preview", (e) => {
        e.preventDefault();
        e.stopPropagation();

        clear_preview_area();
    });

    $("#compose").on("click", ".expand_composebox_button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        compose_ui.make_compose_box_full_size();
    });

    $("#compose").on("click", ".narrow_to_compose_recipients", (e) => {
        e.preventDefault();
        narrow.to_compose_target();
    });

    $("#compose").on("click", ".collapse_composebox_button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        compose_ui.make_compose_box_original_size();
    });

    uppy = upload.setup_upload({
        mode: "compose",
    });

    $("#compose-textarea").on("focus", () => {
        compose_recipient.update_placeholder_text();
    });

    $("#stream_message_recipient_topic").on("focus", () => {
        compose_recipient.update_placeholder_text();
    });

    $("body").on("click", ".formatting_button", (e) => {
        const $compose_click_target = $(compose_ui.get_compose_click_target(e));
        const $textarea = $compose_click_target.closest("form").find("textarea");
        const format_type = $(e.target).attr("data-format-type");
        compose_ui.format_text($textarea, format_type);
        $textarea.trigger("focus");
        e.preventDefault();
        e.stopPropagation();
    });

    if (page_params.narrow !== undefined) {
        if (page_params.narrow_topic !== undefined) {
            compose_actions.start("stream", {topic: page_params.narrow_topic});
        } else {
            compose_actions.start("stream", {});
        }
    }
}

function schedule_message_to_custom_date() {
    const compose_message_object = create_message_object();

    const deliver_at = popover_menus.get_formatted_selected_send_later_time();
    const scheduled_delivery_timestamp = popover_menus.get_selected_send_later_timestamp();

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

function generate_and_insert_audio_or_video_call_link($target_element, is_audio_call) {
    let $target_textarea;
    let edit_message_id;
    if ($target_element.parents(".message_edit_form").length === 1) {
        edit_message_id = rows.id($target_element.parents(".message_row"));
        $target_textarea = $(`#edit_form_${CSS.escape(edit_message_id)} .message_edit_content`);
    }

    const available_providers = page_params.realm_available_video_chat_providers;

    if (
        available_providers.zoom &&
        page_params.realm_video_chat_provider === available_providers.zoom.id
    ) {
        abort_video_callbacks(edit_message_id);
        const key = edit_message_id || "";

        const request = {
            is_video_call: !is_audio_call,
        };

        const make_zoom_call = () => {
            video_call_xhrs.set(
                key,
                channel.post({
                    url: "/json/calls/zoom/create",
                    data: request,
                    success(res) {
                        video_call_xhrs.delete(key);
                        if (is_audio_call) {
                            insert_audio_call_url(res.url, $target_textarea);
                        } else {
                            insert_video_call_url(res.url, $target_textarea);
                        }
                    },
                    error(xhr, status) {
                        video_call_xhrs.delete(key);
                        if (
                            status === "error" &&
                            xhr.responseJSON &&
                            xhr.responseJSON.code === "INVALID_ZOOM_TOKEN"
                        ) {
                            page_params.has_zoom_token = false;
                        }
                        if (status !== "abort") {
                            ui_report.generic_embed_error(
                                $t_html({defaultMessage: "Failed to create video call."}),
                            );
                        }
                    },
                }),
            );
        };

        if (page_params.has_zoom_token) {
            make_zoom_call();
        } else {
            zoom_token_callbacks.set(key, make_zoom_call);
            window.open(
                window.location.protocol + "//" + window.location.host + "/calls/zoom/register",
                "_blank",
                "width=800,height=500,noopener,noreferrer",
            );
        }
    } else if (
        available_providers.big_blue_button &&
        page_params.realm_video_chat_provider === available_providers.big_blue_button.id
    ) {
        if (is_audio_call) {
            // TODO: Add support for audio-only BigBlueButton calls here.
            return;
        }
        const meeting_name = get_recipient_label() + " meeting";
        channel.get({
            url: "/json/calls/bigbluebutton/create",
            data: {
                meeting_name,
            },
            success(response) {
                insert_video_call_url(response.url, $target_textarea);
            },
        });
    } else {
        // TODO: Use `new URL` to generate the URLs here.
        const video_call_id = util.random_int(100000000000000, 999999999999999);
        const video_call_link = page_params.jitsi_server_url + "/" + video_call_id;
        if (is_audio_call) {
            insert_audio_call_url(
                video_call_link + "#config.startWithVideoMuted=true",
                $target_textarea,
            );
        } else {
            /* Because Jitsi remembers what last call type you joined
               in browser local storage, we need to specify that video
               should not be muted in the video call case, or your
               next call will also join without video after joining an
               audio-only call.

               This has the annoying downside that it requires users
               who have a personal preference to disable video every
               time, but Jitsi's UI makes that very easy to do, and
               that inconvenience is probably less important than letting
               the person organizing a call specify their intended
               call type (video vs audio).
           */
            insert_video_call_url(
                video_call_link + "#config.startWithVideoMuted=false",
                $target_textarea,
            );
        }
    }
}
