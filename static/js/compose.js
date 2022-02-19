import autosize from "autosize";
import $ from "jquery";
import _ from "lodash";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as compose_actions from "./compose_actions";
import * as compose_error from "./compose_error";
import * as compose_fade from "./compose_fade";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as compose_validate from "./compose_validate";
import * as echo from "./echo";
import * as flatpickr from "./flatpickr";
import {$t, $t_html} from "./i18n";
import * as loading from "./loading";
import * as markdown from "./markdown";
import * as message_edit from "./message_edit";
import * as notifications from "./notifications";
import {page_params} from "./page_params";
import * as people from "./people";
import * as reminder from "./reminder";
import * as rendered_markdown from "./rendered_markdown";
import * as resize from "./resize";
import * as rows from "./rows";
import * as sent_messages from "./sent_messages";
import * as server_events from "./server_events";
import * as stream_data from "./stream_data";
import * as stream_settings_ui from "./stream_settings_ui";
import * as stream_subscribers_ui from "./stream_subscribers_ui";
import * as sub_store from "./sub_store";
import * as transmit from "./transmit";
import * as ui_report from "./ui_report";
import * as upload from "./upload";
import {user_settings} from "./user_settings";
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

export function update_video_chat_button_display() {
    const show_video_chat_button = compute_show_video_chat_button();
    $("#below-compose-content .video_link").toggle(show_video_chat_button);
    $(".message-edit-feature-group .video_link").toggle(show_video_chat_button);
}

export function clear_invites() {
    $("#compose_invite_users").hide();
    $("#compose_invite_users").empty();
}

export function clear_private_stream_alert() {
    $("#compose_private_stream_alert").hide();
    $("#compose_private_stream_alert").empty();
}

export function clear_preview_area() {
    $("#compose-textarea").show();
    $("#compose .undo_markdown_preview").hide();
    $("#compose .preview_message_area").hide();
    $("#compose .preview_content").empty();
    $("#compose .markdown_preview").show();
    autosize.update($("#compose-textarea"));
}

export function update_fade() {
    if (!compose_state.composing()) {
        return;
    }

    const msg_type = compose_state.get_message_type();
    compose_validate.warn_if_topic_resolved();
    compose_fade.set_focused_recipient(msg_type);
    compose_fade.update_all();
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
        stream: "",
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

        // Note: The `undefined` case is for situations like the
        // is_zephyr_mirror_realm case where users may be
        // automatically created when you try to send a private
        // message to their email address.
        if (message.to_user_ids !== undefined) {
            message.to = people.user_ids_string_to_ids_array(message.to_user_ids);
        }
    } else {
        const stream_name = compose_state.stream_name();
        message.stream = stream_name;
        const sub = stream_data.get_sub(stream_name);
        if (sub) {
            message.stream_id = sub.stream_id;
            message.to = sub.stream_id;
        } else {
            // We should be validating streams in calling code.  We'll
            // try to fall back to stream_name here just in case the
            // user started composing to the old stream name and
            // manually entered the stream name, and it got past
            // validation. We should try to kill this code off eventually.
            blueslip.error("Trying to send message with bad stream name: " + stream_name);
            message.to = stream_name;
        }
        message.topic = topic;
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
    $("#compose-textarea").removeData("draft-id");
    compose_ui.autosize_textarea($("#compose-textarea"));
    $("#compose-send-status").hide(0);
    compose_ui.hide_compose_spinner();
}

export function send_message_success(local_id, message_id, locally_echoed) {
    if (!locally_echoed) {
        clear_compose_box();
    }

    echo.reify_message_id(local_id, message_id);
}

export function send_message(request = create_message_object()) {
    if (request.type === "private") {
        request.to = JSON.stringify(request.to);
    } else {
        request.to = JSON.stringify([request.to]);
    }

    let local_id;
    let locally_echoed;

    const message = echo.try_deliver_locally(request);
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

    sent_messages.start_tracking_message({
        local_id,
        locally_echoed,
    });

    request.locally_echoed = locally_echoed;

    function success(data) {
        send_message_success(local_id, data.id, locally_echoed);
    }

    function error(response) {
        // If we're not local echo'ing messages, or if this message was not
        // locally echoed, show error in compose box
        if (!locally_echoed) {
            compose_error.show(_.escape(response), $("#compose-textarea"));
            return;
        }

        echo.message_send_error(message.id, response);
    }

    transmit.send_message(request, success, error);
    server_events.assert_get_events_running(
        "Restarting get_events because it was not running during send",
    );

    if (locally_echoed) {
        clear_compose_box();
    }
}

export function enter_with_preview_open() {
    if (user_settings.enter_sends) {
        // If enter_sends is enabled, we attempt to send the message
        finish();
    } else {
        // Otherwise, we return to the compose box and focus it
        $("#compose-textarea").trigger("focus");
    }
}

export function finish() {
    clear_preview_area();
    clear_invites();
    clear_private_stream_alert();
    notifications.clear_compose_notifications();

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

    if (!compose_validate.validate()) {
        // If the message failed validation, hide compose spinner.
        compose_ui.hide_compose_spinner();
        return false;
    }

    if (reminder.is_deferred_delivery(message_content)) {
        reminder.schedule_message();
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
    const link_text = $t({defaultMessage: "Click to join video call"});
    compose_ui.insert_syntax_and_focus(`[${link_text}](${url})`, target_textarea);
}

export function render_and_show_preview(preview_spinner, preview_content_box, content) {
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

        preview_content_box.html(util.clean_user_content_links(rendered_preview_html));
        rendered_markdown.update_elements(preview_content_box);
    }

    if (content.length === 0) {
        show_preview($t_html({defaultMessage: "Nothing to preview"}));
    } else {
        if (markdown.contains_backend_only_syntax(content)) {
            const spinner = preview_spinner.expectOne();
            loading.make_indicator(spinner);
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
            idempotent: true,
            data: {content},
            success(response_data) {
                if (markdown.contains_backend_only_syntax(content)) {
                    loading.destroy_indicator(preview_spinner);
                }
                show_preview(response_data.rendered, content);
            },
            error() {
                if (markdown.contains_backend_only_syntax(content)) {
                    loading.destroy_indicator(preview_spinner);
                }
                show_preview($t_html({defaultMessage: "Failed to generate preview"}));
            },
        });
    }
}

export function initialize() {
    $("#below-compose-content .video_link").toggle(compute_show_video_chat_button());
    $(
        "#stream_message_recipient_stream,#stream_message_recipient_topic,#private_message_recipient",
    ).on("keyup", update_fade);
    $(
        "#stream_message_recipient_stream,#stream_message_recipient_topic,#private_message_recipient",
    ).on("change", update_fade);
    $("#compose-textarea").on("keydown", (event) => {
        compose_ui.handle_keydown(event, $("#compose-textarea").expectOne());
    });
    $("#compose-textarea").on("keyup", (event) => {
        compose_ui.handle_keyup(event, $("#compose-textarea").expectOne());
    });

    $("#compose-textarea").on("input propertychange", () => {
        compose_validate.check_overflow_text();
    });

    $("#compose form").on("submit", (e) => {
        e.preventDefault();
        finish();
    });

    resize.watch_manual_resize("#compose-textarea");

    // Update position of scroll to bottom button based on
    // height of the compose box.
    const update_scroll_to_bottom_position = new ResizeObserver(() => {
        $("#scroll-to-bottom-button-container").css("bottom", $("#compose").outerHeight());
    });
    update_scroll_to_bottom_position.observe(document.querySelector("#compose"));

    upload.feature_check($("#compose .compose_upload_file"));

    $("#compose-all-everyone").on("click", ".compose-all-everyone-confirm", (event) => {
        event.preventDefault();

        $(event.target).parents(".compose-all-everyone").remove();
        compose_validate.set_user_acknowledged_all_everyone_flag(true);
        compose_validate.clear_all_everyone_warnings();
        finish();
    });

    $("#compose-announce").on("click", ".compose-announce-confirm", (event) => {
        event.preventDefault();

        $(event.target).parents(".compose-announce").remove();
        compose_validate.set_user_acknowledged_announce_flag(true);
        compose_validate.clear_announce_warnings();
        finish();
    });

    $("#compose-send-status").on("click", ".sub_unsub_button", (event) => {
        event.preventDefault();

        const stream_name = $("#stream_message_recipient_stream").val();
        if (stream_name === undefined) {
            return;
        }
        const sub = stream_data.get_sub(stream_name);
        stream_settings_ui.sub_or_unsub(sub);
        $("#compose-send-status").hide();
    });

    $("#compose-send-status").on("click", "#compose_not_subscribed_close", (event) => {
        event.preventDefault();

        $("#compose-send-status").hide();
    });

    $("#compose_resolved_topic").on("click", ".compose_unresolve_topic", (event) => {
        event.preventDefault();

        const target = $(event.target).parents(".compose_resolved_topic");
        const stream_id = Number.parseInt(target.attr("data-stream-id"), 10);
        const topic_name = target.attr("data-topic-name");

        message_edit.with_first_message_id(stream_id, topic_name, (message_id) => {
            message_edit.toggle_resolve_topic(message_id, topic_name);
            compose_validate.clear_topic_resolved_warning();
        });
    });

    $("#compose_resolved_topic").on("click", ".compose_resolved_topic_close", (event) => {
        event.preventDefault();

        compose_validate.clear_topic_resolved_warning();
    });

    $("#compose_invite_users").on("click", ".compose_invite_link", (event) => {
        event.preventDefault();

        const invite_row = $(event.target).parents(".compose_invite_user");

        const user_id = Number.parseInt($(invite_row).data("user-id"), 10);
        const stream_id = Number.parseInt($(invite_row).data("stream-id"), 10);

        function success() {
            const all_invites = $("#compose_invite_users");
            invite_row.remove();

            if (all_invites.children().length === 0) {
                all_invites.hide();
            }
        }

        function failure(error_msg) {
            clear_invites();
            compose_error.show(_.escape(error_msg), $("#compose-textarea"));
            $(event.target).prop("disabled", true);
        }

        function xhr_failure(xhr) {
            const error = JSON.parse(xhr.responseText);
            failure(error.msg);
        }

        const sub = sub_store.get(stream_id);

        stream_subscribers_ui.invite_user_to_stream([user_id], sub, success, xhr_failure);
    });

    $("#compose_invite_users").on("click", ".compose_invite_close", (event) => {
        const invite_row = $(event.target).parents(".compose_invite_user");
        const all_invites = $("#compose_invite_users");

        invite_row.remove();

        if (all_invites.children().length === 0) {
            all_invites.hide();
        }
    });

    $("#compose_private_stream_alert").on(
        "click",
        ".compose_private_stream_alert_close",
        (event) => {
            const stream_alert_row = $(event.target).parents(".compose_private_stream_alert");
            const stream_alert = $("#compose_private_stream_alert");

            stream_alert_row.remove();

            if (stream_alert.children().length === 0) {
                stream_alert.hide();
            }
        },
    );

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

        let target_textarea;
        let edit_message_id;
        if ($(e.target).parents(".message_edit_form").length === 1) {
            edit_message_id = rows.id($(e.target).parents(".message_row"));
            target_textarea = $(`#edit_form_${CSS.escape(edit_message_id)} .message_edit_content`);
        }

        let video_call_link;
        const available_providers = page_params.realm_available_video_chat_providers;
        const show_video_chat_button = compute_show_video_chat_button();

        if (!show_video_chat_button) {
            return;
        }

        if (
            available_providers.zoom &&
            page_params.realm_video_chat_provider === available_providers.zoom.id
        ) {
            abort_video_callbacks(edit_message_id);
            const key = edit_message_id || "";

            const make_zoom_call = () => {
                video_call_xhrs.set(
                    key,
                    channel.post({
                        url: "/json/calls/zoom/create",
                        success(res) {
                            video_call_xhrs.delete(key);
                            insert_video_call_url(res.url, target_textarea);
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
            channel.get({
                url: "/json/calls/bigbluebutton/create",
                success(response) {
                    insert_video_call_url(response.url, target_textarea);
                },
            });
        } else {
            const video_call_id = util.random_int(100000000000000, 999999999999999);
            video_call_link = page_params.jitsi_server_url + "/" + video_call_id;
            insert_video_call_url(video_call_link, target_textarea);
        }
    });

    $("body").on("click", ".time_pick", (e) => {
        e.preventDefault();
        e.stopPropagation();

        $(e.target).toggleClass("has_popover");

        let target_textarea;
        let edit_message_id;
        const compose_click_target = compose_ui.get_compose_click_target(e);
        if ($(compose_click_target).parents(".message_edit_form").length === 1) {
            edit_message_id = rows.id($(compose_click_target).parents(".message_row"));
            target_textarea = $(`#edit_form_${CSS.escape(edit_message_id)} .message_edit_content`);
        } else {
            target_textarea = $(compose_click_target).closest("form").find("textarea");
        }

        if ($(e.target).hasClass("has_popover")) {
            const on_timestamp_selection = (val) => {
                const timestr = `<time:${val}> `;
                compose_ui.insert_syntax_and_focus(timestr, target_textarea);
            };

            flatpickr.show_flatpickr(
                $(compose_click_target)[0],
                on_timestamp_selection,
                new Date(),
                {
                    // place the time picker above the icon and center it horizontally
                    position: "above center",
                },
            );
        }
    });

    $("#compose").on("click", ".markdown_preview", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const content = $("#compose-textarea").val();
        $("#compose-textarea").hide();
        $("#compose .markdown_preview").hide();
        $("#compose .undo_markdown_preview").show();
        $("#compose .preview_message_area").show();

        render_and_show_preview(
            $("#compose .markdown_preview_spinner"),
            $("#compose .preview_content"),
            content,
        );
        resize.reset_compose_message_max_height();
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

    $("#compose").on("click", ".collapse_composebox_button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        compose_ui.make_compose_box_original_size();
    });

    uppy = upload.setup_upload({
        mode: "compose",
    });

    $("#compose-textarea").on("focus", () => {
        compose_actions.update_placeholder_text();
    });

    $("#stream_message_recipient_topic").on("focus", () => {
        compose_actions.update_placeholder_text();
    });

    $("body").on("click", ".formatting_button", (e) => {
        const $compose_click_target = $(compose_ui.get_compose_click_target(e));
        const textarea = $compose_click_target.closest("form").find("textarea");
        const format_type = $(e.target).attr("data-format-type");
        compose_ui.format_text(textarea, format_type);
        textarea.trigger("focus");
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
