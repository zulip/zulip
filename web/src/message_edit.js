import ClipboardJS from "clipboard";
import $ from "jquery";
import assert from "minimalistic-assert";

import * as resolved_topic from "../shared/src/resolved_topic";
import render_wildcard_mention_not_allowed_error from "../templates/compose_banner/wildcard_mention_not_allowed_error.hbs";
import render_delete_message_modal from "../templates/confirm_dialog/confirm_delete_message.hbs";
import render_confirm_merge_topics_with_rename from "../templates/confirm_dialog/confirm_merge_topics_with_rename.hbs";
import render_confirm_moving_messages_modal from "../templates/confirm_dialog/confirm_moving_messages.hbs";
import render_message_edit_form from "../templates/message_edit_form.hbs";
import render_message_moved_widget_body from "../templates/message_moved_widget_body.hbs";
import render_resolve_topic_time_limit_error_modal from "../templates/resolve_topic_time_limit_error_modal.hbs";
import render_topic_edit_form from "../templates/topic_edit_form.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as compose_actions from "./compose_actions";
import * as compose_banner from "./compose_banner";
import * as compose_call from "./compose_call";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as compose_validate from "./compose_validate";
import * as composebox_typeahead from "./composebox_typeahead";
import * as condense from "./condense";
import * as confirm_dialog from "./confirm_dialog";
import {show_copied_confirmation} from "./copied_tooltip";
import * as dialog_widget from "./dialog_widget";
import * as echo from "./echo";
import * as feedback_widget from "./feedback_widget";
import * as giphy from "./giphy";
import * as hash_util from "./hash_util";
import {$t, $t_html} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as loading from "./loading";
import * as markdown from "./markdown";
import * as message_lists from "./message_lists";
import * as message_live_update from "./message_live_update";
import * as message_store from "./message_store";
import * as message_viewport from "./message_viewport";
import * as people from "./people";
import * as resize from "./resize";
import * as rows from "./rows";
import * as settings_data from "./settings_data";
import {current_user, realm} from "./state_data";
import * as stream_data from "./stream_data";
import * as stream_topic_history from "./stream_topic_history";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";
import * as ui_report from "./ui_report";
import * as upload from "./upload";
import * as util from "./util";

const currently_editing_messages = new Map();
let currently_deleting_messages = [];
let currently_topic_editing_messages = [];
const currently_echoing_messages = new Map();
// These variables are designed to preserve the user's most recent
// choices when editing a group of messages, to make it convenient to
// move several topics in a row with the same settings.
export let notify_old_thread_default = false;

export let notify_new_thread_default = true;

export function is_topic_editable(message, edit_limit_seconds_buffer = 0) {
    if (!is_message_editable_ignoring_permissions(message)) {
        return false;
    }

    if (message.type !== "stream") {
        return false;
    }

    if (!settings_data.user_can_move_messages_to_another_topic()) {
        return false;
    }

    // Organization admins and moderators can edit message topics indefinitely,
    // irrespective of the topic editing deadline, if edit_topic_policy allows
    // them to do so.
    if (current_user.is_admin || current_user.is_moderator) {
        return true;
    }

    if (realm.realm_move_messages_within_stream_limit_seconds === null) {
        // This means no time limit for editing topics.
        return true;
    }

    // If you're using community topic editing, there's a deadline.
    return (
        realm.realm_move_messages_within_stream_limit_seconds +
            edit_limit_seconds_buffer +
            (message.timestamp - Date.now() / 1000) >
        0
    );
}

function is_widget_message(message) {
    if (message.submessages && message.submessages.length !== 0) {
        return true;
    }
    return false;
}

export function is_message_editable_ignoring_permissions(message) {
    if (!message) {
        return false;
    }

    if (message.failed_request) {
        // TODO: For completely failed requests, we should be able
        //       to "edit" the message, but it won't really be like
        //       other message updates.  This commit changed the result
        //       from FULL to NO, since the prior implementation was
        //       buggy.
        return false;
    }

    // Locally echoed messages are not editable, since the message hasn't
    // finished being sent yet.
    if (message.locally_echoed) {
        return false;
    }

    // Messages where we're currently locally echoing an edit not yet acknowledged
    // by the server.
    if (currently_echoing_messages.has(message.id)) {
        return false;
    }
    return true;
}

export function is_content_editable(message, edit_limit_seconds_buffer = 0) {
    if (!is_message_editable_ignoring_permissions(message)) {
        return false;
    }

    if (!realm.realm_allow_message_editing) {
        return false;
    }

    if (!message.sent_by_me) {
        return false;
    }

    if (is_widget_message(message)) {
        return false;
    }

    if (realm.realm_message_content_edit_limit_seconds === null) {
        return true;
    }

    if (
        realm.realm_message_content_edit_limit_seconds +
            edit_limit_seconds_buffer +
            (message.timestamp - Date.now() / 1000) >
        0
    ) {
        return true;
    }
    return false;
}

export function is_message_sent_by_my_bot(message) {
    const user = people.get_by_user_id(message.sender_id);
    if (user.bot_owner_id === undefined || user.bot_owner_id === null) {
        // The message was not sent by a bot or the message was sent
        // by a cross-realm bot which does not have an owner.
        return false;
    }

    return people.is_my_user_id(user.bot_owner_id);
}

export function get_deletability(message) {
    if (current_user.is_admin) {
        return true;
    }

    if (!message.sent_by_me && !is_message_sent_by_my_bot(message)) {
        return false;
    }
    if (message.locally_echoed) {
        return false;
    }
    if (!settings_data.user_can_delete_own_message()) {
        return false;
    }

    if (realm.realm_message_content_delete_limit_seconds === null) {
        // This means no time limit for message deletion.
        return true;
    }

    if (
        realm.realm_message_content_delete_limit_seconds + (message.timestamp - Date.now() / 1000) >
        0
    ) {
        return true;
    }
    return false;
}

export function is_stream_editable(message, edit_limit_seconds_buffer = 0) {
    if (!is_message_editable_ignoring_permissions(message)) {
        return false;
    }

    if (message.type !== "stream") {
        return false;
    }

    if (!settings_data.user_can_move_messages_between_streams()) {
        return false;
    }

    // Organization admins and moderators can edit stream indefinitely,
    // irrespective of the stream editing deadline, if
    // move_messages_between_streams_policy allows them to do so.
    if (current_user.is_admin || current_user.is_moderator) {
        return true;
    }

    if (realm.realm_move_messages_between_streams_limit_seconds === null) {
        // This means no time limit for editing streams.
        return true;
    }

    return (
        realm.realm_move_messages_between_streams_limit_seconds +
            edit_limit_seconds_buffer +
            (message.timestamp - Date.now() / 1000) >
        0
    );
}

export function can_move_message(message) {
    return is_topic_editable(message) || is_stream_editable(message);
}

export function stream_and_topic_exist_in_edit_history(message, stream_id, topic) {
    /*  Checks to see if a stream_id and a topic match any historical
        stream_id and topic state in the message's edit history.

        Does not check the message's current stream_id and topic for
        a match to the stream_id and topic parameters.
     */
    const narrow_dict = {stream_id, topic};
    const message_dict = {stream_id: message.stream_id, topic: message.topic};

    if (!message.edit_history) {
        // If message edit history is disabled in the organization,
        // the client does not have the information locally to answer
        // this question correctly.
        return false;
    }

    for (const edit_history_event of message.edit_history) {
        if (!edit_history_event.prev_stream && !edit_history_event.prev_topic) {
            // Message was not moved in this edit event.
            continue;
        }

        if (edit_history_event.prev_stream) {
            // This edit event changed the stream.  We expect the
            // following to be true due to the invariants of the edit
            // history data structure:
            // edit_history_event.stream === message_dict.stream_id
            message_dict.stream_id = edit_history_event.prev_stream;
        }

        if (edit_history_event.prev_topic) {
            // This edit event changed the topic.  We expect the
            // following to be true due to the invariants of the edit
            // history data structure:
            // util.lower_same(edit_history_event.topic, message_dict.topic)
            message_dict.topic = edit_history_event.prev_topic;
        }

        if (util.same_stream_and_topic(narrow_dict, message_dict)) {
            return true;
        }
    }

    return false;
}

export function hide_message_edit_spinner($row) {
    $row.find(".loader").hide();
    $row.find(".message_edit_save span").show();
    $row.find(".message_edit_save").removeClass("disable-btn");
    $row.find(".message_edit_cancel").removeClass("disable-btn");
}

export function show_message_edit_spinner($row) {
    // Always show the white spinner like we
    // do for send button in compose box.
    loading.show_button_spinner($row.find(".loader"), true);
    $row.find(".message_edit_save span").hide();
    $row.find(".message_edit_save").addClass("disable-btn");
    $row.find(".message_edit_cancel").addClass("disable-btn");
}

export function show_topic_edit_spinner($row) {
    const $spinner = $row.find(".topic_edit_spinner");
    loading.make_indicator($spinner);
    $spinner.css({height: ""});
    $(".topic_edit_save").hide();
    $(".topic_edit_cancel").hide();
    $(".topic_edit_spinner").show();
}

export function end_if_focused_on_inline_topic_edit() {
    const $focused_elem = $(".topic_edit_form").find(":focus");
    if ($focused_elem.length === 1) {
        $focused_elem.trigger("blur");
        const $recipient_row = $focused_elem.closest(".recipient_row");
        end_inline_topic_edit($recipient_row);
    }
}

export function end_if_focused_on_message_row_edit() {
    const $focused_elem = $(".message_edit").find(":focus");
    if ($focused_elem.length === 1) {
        $focused_elem.trigger("blur");
        const $row = $focused_elem.closest(".message_row");
        end_message_row_edit($row);
    }
}

export function update_inline_topic_edit_ui() {
    // This function is called when
    // "realm_move_messages_within_stream_limit_seconds" setting is
    // changed. This is a rare event, so it's OK to be lazy and just
    // do a full rerender, even though the only thing we need to
    // change is the inline topic edit icons in recipient bars.
    message_live_update.rerender_messages_view();
}

function handle_message_row_edit_keydown(e) {
    if (keydown_util.is_enter_event(e)) {
        if ($(e.target).hasClass("message_edit_content")) {
            // Pressing Enter to save edits is coupled with Enter to send
            if (composebox_typeahead.should_enter_send(e)) {
                const $row = $(".message_edit_content:focus").closest(".message_row");
                const $message_edit_save_button = $row.find(".message_edit_save");
                if ($message_edit_save_button.prop("disabled")) {
                    // In cases when the save button is disabled
                    // we need to disable save on pressing Enter
                    // Prevent default to avoid new-line on pressing
                    // Enter inside the textarea in this case
                    e.preventDefault();
                    return;
                }
                save_message_row_edit($row);
                e.stopPropagation();
                e.preventDefault();
            } else {
                composebox_typeahead.handle_enter($(e.target), e);
                return;
            }
        } else if ($(".typeahead:visible").length > 0) {
            // Accepting typeahead is handled by the typeahead library.
            return;
        } else if (
            $(e.target).hasClass("message_edit_topic") ||
            $(e.target).hasClass("message_edit_topic_propagate")
        ) {
            // Enter should save the topic edit, as long as it's
            // not being used to accept typeahead.
            const $row = $(e.target).closest(".message_row");
            save_message_row_edit($row);
            e.stopPropagation();
        }
    } else if (e.key === "Escape") {
        end_if_focused_on_message_row_edit();
        e.stopPropagation();
        e.preventDefault();
    }
}

function handle_inline_topic_edit_keydown(e) {
    if (keydown_util.is_enter_event(e)) {
        // Handle Enter key in the recipient bar/inline topic edit form
        if ($(".typeahead:visible").length > 0) {
            // Accepting typeahead should not trigger a save.
            e.preventDefault();
            return;
        }
        const $row = $(e.target).closest(".recipient_row");
        try_save_inline_topic_edit($row);
        e.stopPropagation();
        e.preventDefault();
    } else if (e.key === "Escape") {
        // Handle Esc
        end_if_focused_on_inline_topic_edit();
        e.stopPropagation();
        e.preventDefault();
    }
}

function timer_text(seconds_left) {
    const minutes = Math.floor(seconds_left / 60);
    const seconds = seconds_left % 60;
    if (minutes >= 1) {
        return $t({defaultMessage: "{minutes} min to edit"}, {minutes: minutes.toString()});
    } else if (seconds_left >= 10) {
        return $t(
            {defaultMessage: "{seconds} sec to edit"},
            {seconds: (seconds - (seconds % 5)).toString()},
        );
    }
    return $t({defaultMessage: "{seconds} sec to edit"}, {seconds: seconds.toString()});
}

function create_copy_to_clipboard_handler($row, source, message_id) {
    const clipboard = new ClipboardJS(source, {
        target: () =>
            document.querySelector(`#edit_form_${CSS.escape(message_id)} .message_edit_content`),
    });

    clipboard.on("success", () => {
        // Hide the Tippy and source box after a 600ms delay
        const tippy_timeout_in_ms = 600;
        show_copied_confirmation(
            $row.find(".copy_message")[0],
            () => {
                end_message_row_edit($row);
            },
            tippy_timeout_in_ms,
        );
    });
}

function edit_message($row, raw_content) {
    assert(message_lists.current !== undefined);
    const message = message_lists.current.get(rows.id($row));
    $row.find(".message_reactions").hide();
    condense.hide_message_expander($row);
    condense.hide_message_condenser($row);
    const content_top = $row.find(".message_controls")[0].getBoundingClientRect().top;

    // We potentially got to this function by clicking a button that implied the
    // user would be able to edit their message.  Give a little bit of buffer in
    // case the button has been around for a bit, e.g. we show the
    // edit_content_button (hovering pencil icon) as long as the user would have
    // been able to click it at the time the mouse entered the message_row. Also
    // a buffer in case their computer is slow, or stalled for a second, etc
    // If you change this number also change edit_limit_buffer in
    // zerver.actions.message_edit.check_update_message
    const seconds_left_buffer = 5;
    const max_file_upload_size = realm.max_file_upload_size_mib;
    let file_upload_enabled = false;

    if (max_file_upload_size > 0) {
        file_upload_enabled = true;
    }

    const is_editable = is_content_editable(message, seconds_left_buffer);

    const $form = $(
        render_message_edit_form({
            message_id: message.id,
            is_editable,
            content: raw_content,
            file_upload_enabled,
            giphy_enabled: giphy.is_giphy_enabled(),
            minutes_to_edit: Math.floor(realm.realm_message_content_edit_limit_seconds / 60),
            max_message_length: realm.max_message_length,
        }),
    );

    const edit_obj = {$form, raw_content};
    currently_editing_messages.set(message.id, edit_obj);
    message_lists.current.show_edit_message($row, edit_obj);

    $form.on("keydown", handle_message_row_edit_keydown);

    $form
        .find(".message-edit-feature-group .video_link")
        .toggle(compose_call.compute_show_video_chat_button());
    $form
        .find(".message-edit-feature-group .audio_link")
        .toggle(compose_call.compute_show_audio_chat_button());
    upload.feature_check($(`#edit_form_${CSS.escape(rows.id($row))} .compose_upload_file`));

    const $message_edit_content = $row.find("textarea.message_edit_content");
    const $message_edit_countdown_timer = $row.find(".message_edit_countdown_timer");
    const $copy_message = $row.find(".copy_message");

    if (!is_editable) {
        $message_edit_content.attr("readonly", "readonly");
        create_copy_to_clipboard_handler($row, $copy_message[0], message.id);
    } else {
        $copy_message.remove();
        const edit_id = `#edit_form_${CSS.escape(rows.id($row))} .message_edit_content`;
        const listeners = resize.watch_manual_resize(edit_id);
        if (listeners) {
            currently_editing_messages.get(rows.id($row)).listeners = listeners;
        }
        composebox_typeahead.initialize_compose_typeahead(edit_id);
        compose_ui.handle_keyup(null, $(edit_id).expectOne());
        $(edit_id).on("keydown", function (event) {
            compose_ui.handle_keydown(event, $(this).expectOne());
        });
        $(edit_id).on("keyup", function (event) {
            compose_ui.handle_keyup(event, $(this).expectOne());
        });
    }

    // Add tooltip and timer
    if (is_editable && realm.realm_message_content_edit_limit_seconds > 0) {
        $row.find(".message-edit-timer").show();

        // Give them at least 10 seconds.
        // If you change this number also change edit_limit_buffer in
        // zerver.actions.message_edit.check_update_message
        const min_seconds_to_edit = 10;
        let seconds_left =
            realm.realm_message_content_edit_limit_seconds +
            (message.timestamp - Date.now() / 1000);
        seconds_left = Math.floor(Math.max(seconds_left, min_seconds_to_edit));

        // I believe this needs to be defined outside the countdown_timer, since
        // row just refers to something like the currently selected message, and
        // can change out from under us
        const $message_edit_save_container = $row.find(".message_edit_save_container");
        const $message_edit_save = $row.find("button.message_edit_save");
        // Do this right away, rather than waiting for the timer to do its first update,
        // since otherwise there is a noticeable lag
        $message_edit_countdown_timer.text(timer_text(seconds_left));
        const countdown_timer = setInterval(() => {
            seconds_left -= 1;
            if (seconds_left <= 0) {
                clearInterval(countdown_timer);
                // We don't go directly to a "TOPIC_ONLY" type state (with an active Save button),
                // since it isn't clear what to do with the half-finished edit. It's nice to keep
                // the half-finished edit around so that they can copy-paste it, but we don't want
                // people to think "Save" will save the half-finished edit.
                $message_edit_save.prop("disabled", true);
                $message_edit_save_container.addClass("tippy-zulip-tooltip");
                $message_edit_countdown_timer.addClass("expired");
                $message_edit_countdown_timer.text($t({defaultMessage: "Time's up!"}));
            } else {
                $message_edit_countdown_timer.text(timer_text(seconds_left));
            }
        }, 1000);
    }

    if (!is_editable) {
        $row.find(".message_edit_close").trigger("focus");
    } else {
        $message_edit_content.trigger("focus");
        // Put cursor at end of input.
        const contents = $message_edit_content.val();
        $message_edit_content.val("");
        $message_edit_content.val(contents);
    }

    // Scroll to keep the top of the message content text in the same
    // place visually, adjusting for border and padding.
    const edit_top = $message_edit_content[0].getBoundingClientRect().top;
    const scroll_by = edit_top - content_top + 5 - 14;

    edit_obj.scrolled_by = scroll_by;
    message_viewport.scrollTop(message_viewport.scrollTop() + scroll_by);
}

function start_edit_maintaining_scroll($row, content) {
    edit_message($row, content);
    const row_bottom = $row.get_offset_to_window().bottom;
    const composebox_top = $("#compose").get_offset_to_window().top;
    if (row_bottom > composebox_top) {
        message_viewport.scrollTop(message_viewport.scrollTop() + row_bottom - composebox_top);
    }
}

function start_edit_with_content($row, content, edit_box_open_callback) {
    start_edit_maintaining_scroll($row, content);
    if (edit_box_open_callback) {
        edit_box_open_callback();
    }
    const row_id = rows.id($row);
    upload.setup_upload({
        mode: "edit",
        row: row_id,
    });
}

export function start($row, edit_box_open_callback) {
    assert(message_lists.current !== undefined);
    const message = message_lists.current.get(rows.id($row));
    if (message === undefined) {
        blueslip.error("Couldn't find message ID for edit", {row_id: rows.id($row)});
        return;
    }

    if ($row.find(".message_edit_form form").length !== 0) {
        return;
    }

    if (message.raw_content) {
        start_edit_with_content($row, message.raw_content, edit_box_open_callback);
        return;
    }

    const msg_list = message_lists.current;
    channel.get({
        url: "/json/messages/" + message.id,
        success(data) {
            if (message_lists.current === msg_list) {
                message.raw_content = data.raw_content;
                start_edit_with_content($row, message.raw_content, edit_box_open_callback);
            }
        },
    });
}

function show_toggle_resolve_topic_spinner($row) {
    const $spinner = $row.find(".toggle_resolve_topic_spinner");
    loading.make_indicator($spinner);
    $spinner.css({width: "18px"});
    $row.find(".on_hover_topic_resolve, .on_hover_topic_unresolve").hide();
    $row.find(".toggle_resolve_topic_spinner").show();
}

function get_resolve_topic_time_limit_error_string(time_limit, time_limit_unit, topic_is_resolved) {
    if (topic_is_resolved) {
        if (time_limit_unit === "minute") {
            return $t(
                {
                    defaultMessage:
                        "You do not have permission to unresolve topics with messages older than {N, plural, one {# minute} other {# minutes}} in this organization.",
                },
                {N: time_limit},
            );
        } else if (time_limit_unit === "hour") {
            return $t(
                {
                    defaultMessage:
                        "You do not have permission to unresolve topics with messages older than {N, plural, one {# hour} other {# hours}} in this organization.",
                },
                {N: time_limit},
            );
        }
        return $t(
            {
                defaultMessage:
                    "You do not have permission to unresolve topics with messages older than {N, plural, one {# day} other {# days}} in this organization.",
            },
            {N: time_limit},
        );
    }

    if (time_limit_unit === "minute") {
        return $t(
            {
                defaultMessage:
                    "You do not have permission to resolve topics with messages older than {N, plural, one {# minute} other {# minutes}} in this organization.",
            },
            {N: time_limit},
        );
    } else if (time_limit_unit === "hour") {
        return $t(
            {
                defaultMessage:
                    "You do not have permission to resolve topics with messages older than {N, plural, one {# hour} other {# hours}} in this organization.",
            },
            {N: time_limit},
        );
    }
    return $t(
        {
            defaultMessage:
                "You do not have permission to resolve topics with messages older than {N, plural, one {# day} other {# days}} in this organization.",
        },
        {N: time_limit},
    );
}

function handle_resolve_topic_failure_due_to_time_limit(topic_is_resolved) {
    const time_limit_for_resolving_topic = timerender.get_time_limit_setting_in_appropriate_unit(
        realm.realm_move_messages_within_stream_limit_seconds,
    );
    const resolve_topic_time_limit_error_string = get_resolve_topic_time_limit_error_string(
        time_limit_for_resolving_topic.value,
        time_limit_for_resolving_topic.unit,
        topic_is_resolved,
    );

    const html_body = render_resolve_topic_time_limit_error_modal({
        topic_is_resolved,
        resolve_topic_time_limit_error_string,
    });
    let modal_heading;
    if (topic_is_resolved) {
        modal_heading = $t_html({defaultMessage: "Could not unresolve topic"});
    } else {
        modal_heading = $t_html({defaultMessage: "Could not resolve topic"});
    }
    dialog_widget.launch({
        html_heading: modal_heading,
        html_body,
        html_submit_button: $t_html({defaultMessage: "Close"}),
        on_click() {},
        single_footer_button: true,
        focus_submit_on_open: true,
    });
}

export function toggle_resolve_topic(
    message_id,
    old_topic_name,
    report_errors_in_global_banner,
    $row,
) {
    let new_topic_name;
    const topic_is_resolved = resolved_topic.is_resolved(old_topic_name);
    if (topic_is_resolved) {
        new_topic_name = resolved_topic.unresolve_name(old_topic_name);
    } else {
        new_topic_name = resolved_topic.resolve_name(old_topic_name);
    }

    if ($row) {
        show_toggle_resolve_topic_spinner($row);
    }

    const request = {
        propagate_mode: "change_all",
        topic: new_topic_name,
        send_notification_to_old_thread: false,
        send_notification_to_new_thread: true,
    };

    channel.patch({
        url: "/json/messages/" + message_id,
        data: request,
        success() {
            if ($row) {
                const $spinner = $row.find(".toggle_resolve_topic_spinner");
                loading.destroy_indicator($spinner);
            }
        },
        error(xhr) {
            if ($row) {
                const $spinner = $row.find(".toggle_resolve_topic_spinner");
                loading.destroy_indicator($spinner);
            }

            if (xhr.responseJSON) {
                if (xhr.responseJSON.code === "MOVE_MESSAGES_TIME_LIMIT_EXCEEDED") {
                    handle_resolve_topic_failure_due_to_time_limit(topic_is_resolved);
                    return;
                }

                if (report_errors_in_global_banner) {
                    ui_report.generic_embed_error(xhr.responseJSON.msg, 3500);
                }
            }
        },
    });
}

export function start_inline_topic_edit($recipient_row) {
    assert(message_lists.current !== undefined);
    const $form = $(
        render_topic_edit_form({
            max_topic_length: realm.max_topic_length,
        }),
    );
    message_lists.current.show_edit_topic_on_recipient_row($recipient_row, $form);
    $form.on("keydown", handle_inline_topic_edit_keydown);
    $(".topic_edit_spinner").hide();
    const msg_id = rows.id_for_recipient_row($recipient_row);
    const message = message_lists.current.get(msg_id);
    let topic = message.topic;
    if (topic === compose_state.empty_topic_placeholder()) {
        topic = "";
    }
    const $inline_topic_edit_input = $form.find(".inline_topic_edit");
    $inline_topic_edit_input.val(topic).trigger("select").trigger("focus");
    const stream_name = stream_data.get_stream_name_from_id(message.stream_id);
    composebox_typeahead.initialize_topic_edit_typeahead(
        $inline_topic_edit_input,
        stream_name,
        false,
    );
}

export function is_editing(id) {
    return currently_editing_messages.has(id);
}

export function end_inline_topic_edit($row) {
    assert(message_lists.current !== undefined);
    message_lists.current.hide_edit_topic_on_recipient_row($row);
}

export function end_message_row_edit($row) {
    assert(message_lists.current !== undefined);
    const row_id = rows.id($row);

    // Clean up the upload handler
    upload.deactivate_upload({mode: "edit", row: row_id});

    const message = message_lists.current.get(row_id);
    if (message !== undefined && currently_editing_messages.has(message.id)) {
        const scroll_by = currently_editing_messages.get(message.id).scrolled_by;
        const original_scrollTop = message_viewport.scrollTop();

        // Clean up resize event listeners
        const listeners = currently_editing_messages.get(message.id).listeners;
        const edit_box = document.querySelector(
            `#edit_form_${CSS.escape(message.id)} .message_edit_content`,
        );
        if (listeners !== undefined) {
            // Event listeners to clean up are only set in some edit types
            edit_box.removeEventListener("mousedown", listeners[0]);
            document.body.removeEventListener("mouseup", listeners[1]);
        }

        currently_editing_messages.delete(message.id);
        message_lists.current.hide_edit_message($row);
        message_viewport.scrollTop(original_scrollTop - scroll_by);

        compose_call.abort_video_callbacks(message.id);
    }
    if ($row.find(".condensed").length !== 0) {
        condense.show_message_expander($row);
    } else {
        condense.show_message_condenser($row);
    }
    $row.find(".message_reactions").show();

    // We have to blur out text fields, or else hotkeys.js
    // thinks we are still editing.
    $row.find(".message_edit").trigger("blur");
    // We should hide the editing typeahead if it is visible
    $row.find("input.message_edit_topic").trigger("blur");
}

export function end_message_edit(message_id) {
    const $row = message_lists.current?.get_row(message_id);
    if (message_lists.current !== undefined && $row.length > 0) {
        end_message_row_edit($row);
    } else if (currently_editing_messages.has(message_id)) {
        // We should delete the message_id from currently_editing_messages
        // if it exists there but we cannot find the row.
        currently_editing_messages.delete(message_id);
    }
}

export function try_save_inline_topic_edit($row) {
    assert(message_lists.current !== undefined);
    const message_id = rows.id_for_recipient_row($row);
    const message = message_lists.current.get(message_id);

    const old_topic = message.topic;
    const new_topic = $row.find(".inline_topic_edit").val();
    const topic_changed = new_topic !== old_topic && new_topic.trim() !== "";

    if (!topic_changed) {
        // this means the inline_topic_edit was opened and submitted without
        // changing anything, therefore, we should just close the inline topic edit.
        end_inline_topic_edit($row);
        return;
    }

    const $message_header = $row.find(".message_header").expectOne();
    const stream_id = Number.parseInt($message_header.attr("data-stream-id"), 10);
    const stream_topics = stream_topic_history.get_recent_topic_names(stream_id);
    if (stream_topics.includes(new_topic)) {
        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Merge with another topic?"}),
            html_body: render_confirm_merge_topics_with_rename({
                topic_name: new_topic,
            }),
            focus_submit_on_open: false,
            on_click: () => do_save_inline_topic_edit($row, message, new_topic),
        });
    } else {
        do_save_inline_topic_edit($row, message, new_topic);
    }
}

export function do_save_inline_topic_edit($row, message, new_topic) {
    const msg_list = message_lists.current;
    show_topic_edit_spinner($row);

    if (message.locally_echoed) {
        message = echo.edit_locally(message, {new_topic});
        $row = message_lists.current.get_row(message.id);
        end_inline_topic_edit($row);
        return;
    }

    const request = {
        message_id: message.id,
        topic: new_topic,
        propagate_mode: "change_all",
        send_notification_to_old_thread: false,
        send_notification_to_new_thread: false,
    };

    channel.patch({
        url: "/json/messages/" + message.id,
        data: request,
        success() {
            const $spinner = $row.find(".topic_edit_spinner");
            loading.destroy_indicator($spinner);
        },
        error(xhr) {
            const $spinner = $row.find(".topic_edit_spinner");
            if (xhr.responseJSON?.code === "MOVE_MESSAGES_TIME_LIMIT_EXCEEDED") {
                const allowed_message_id = xhr.responseJSON.first_message_id_allowed_to_move;
                const send_notification_to_old_thread = false;
                const send_notification_to_new_thread = false;
                // We are not changing stream in this UI.
                const new_stream_id = undefined;
                function handle_confirm() {
                    move_topic_containing_message_to_stream(
                        allowed_message_id,
                        new_stream_id,
                        new_topic,
                        send_notification_to_new_thread,
                        send_notification_to_old_thread,
                        "change_later",
                    );
                }
                const on_hide_callback = () => {
                    loading.destroy_indicator($spinner);
                    end_inline_topic_edit($row);
                };

                handle_message_move_failure_due_to_time_limit(
                    xhr,
                    handle_confirm,
                    on_hide_callback,
                );
                return;
            }
            loading.destroy_indicator($spinner);
            if (msg_list === message_lists.current) {
                const message = channel.xhr_error_message(
                    $t({defaultMessage: "Error saving edit"}),
                    xhr,
                );
                $row.find(".edit_error").text(message).css("display", "inline-block");
            }
        },
    });
}

export function save_message_row_edit($row) {
    assert(message_lists.current !== undefined);
    const $banner_container = compose_banner.get_compose_banner_container(
        $row.find(".message_edit_form textarea"),
    );
    const stream_id = Number.parseInt(
        rows.get_message_recipient_header($row).attr("data-stream-id"),
        10,
    );
    const msg_list = message_lists.current;
    let message_id = rows.id($row);
    let message = message_lists.current.get(message_id);
    let changed = false;
    let edit_locally_echoed = false;

    let new_content;
    const old_content = message.raw_content;

    const $edit_content_input = $row.find(".message_edit_content");
    const can_edit_content = $edit_content_input.attr("readonly") !== "readonly";
    if (can_edit_content) {
        new_content = $edit_content_input.val();
        changed = old_content !== new_content;
    }

    const already_has_stream_wildcard_mention = message.stream_wildcard_mentioned;
    if (!already_has_stream_wildcard_mention) {
        const stream_wildcard_mention = util.find_stream_wildcard_mentions(new_content);
        const is_stream_message_mentions_valid = compose_validate.validate_stream_message_mentions({
            stream_id,
            $banner_container,
            stream_wildcard_mention,
        });

        if (!is_stream_message_mentions_valid) {
            return;
        }
    }

    show_message_edit_spinner($row);

    // Editing a not-yet-acked message (because the original send attempt failed)
    // just results in the in-memory message being changed
    if (message.locally_echoed) {
        if (new_content !== message.raw_content) {
            // `edit_locally` handles the case where `new_topic/new_stream_id` is undefined
            message = echo.edit_locally(message, {
                raw_content: new_content,
            });
            $row = message_lists.current.get_row(message_id);
        }
        end_message_row_edit($row);
        return;
    }

    if (!changed) {
        // If they didn't change anything, just cancel it.
        end_message_row_edit($row);
        return;
    }

    const request = {message_id: message.id, content: new_content};

    if (!markdown.contains_backend_only_syntax(new_content)) {
        // If the new message content could have been locally echoed,
        // than we can locally echo the edit.
        currently_echoing_messages.set(message_id, {
            raw_content: new_content,
            orig_content: message.content,
            orig_raw_content: message.raw_content,

            // Store flags that are about user interaction with the
            // message so that echo.edit_locally() can restore these
            // flags.
            starred: message.starred,
            historical: message.historical,
            collapsed: message.collapsed,

            // These flags are rendering artifacts we'll want if the
            // edit fails and we need to revert to the original
            // rendering of the message.
            alerted: message.alerted,
            mentioned: message.mentioned,
            mentioned_me_directly: message.mentioned,
        });
        edit_locally_echoed = true;

        // Settings these attributes causes a "SAVING" notice to
        // briefly appear where "EDITED" would normally appear until
        // the message is acknowledged by the server.
        message.local_edit_timestamp = Math.round(Date.now() / 1000);

        message = echo.edit_locally(message, currently_echoing_messages.get(message_id));

        $row = message_lists.current.get_row(message_id);
        end_message_row_edit($row);
    }

    channel.patch({
        url: "/json/messages/" + message.id,
        data: request,
        success() {
            if (edit_locally_echoed) {
                delete message.local_edit_timestamp;
                currently_echoing_messages.delete(message_id);
            }
            // Ordinarily, in a code path like this, we'd make
            // a call to `hide_message_edit_spinner()`. But in
            // this instance, we want to avoid a momentary flash
            // of the Save button text before the edited message
            // re-renders. Note that any subsequent editing will
            // create a fresh Save button, without the spinner
            // class attached.
        },
        error(xhr) {
            if (msg_list === message_lists.current) {
                message_id = rows.id($row);

                if (edit_locally_echoed) {
                    let echoed_message = message_store.get(message_id);
                    const echo_data = currently_echoing_messages.get(message_id);

                    delete echoed_message.local_edit_timestamp;
                    currently_echoing_messages.delete(message_id);

                    // Restore the original content.
                    echoed_message = echo.edit_locally(echoed_message, {
                        content: echo_data.orig_content,
                        raw_content: echo_data.orig_raw_content,
                        mentioned: echo_data.mentioned,
                        mentioned_me_directly: echo_data.mentioned_me_directly,
                        alerted: echo_data.alerted,
                    });

                    $row = message_lists.current.get_row(message_id);
                    if (!is_editing(message_id)) {
                        // Return to the message editing open UI state with the edited content.
                        start_edit_maintaining_scroll($row, echo_data.raw_content);
                    }
                }

                hide_message_edit_spinner($row);
                if (xhr.readyState !== 0) {
                    const $container = compose_banner.get_compose_banner_container(
                        $row.find("textarea"),
                    );

                    if (xhr.responseJSON?.code === "TOPIC_WILDCARD_MENTION_NOT_ALLOWED") {
                        const new_row_html = render_wildcard_mention_not_allowed_error({
                            banner_type: compose_banner.ERROR,
                            classname: compose_banner.CLASSNAMES.wildcards_not_allowed,
                        });
                        compose_banner.append_compose_banner_to_banner_list(
                            $(new_row_html),
                            $container,
                        );
                        return;
                    }

                    const message = channel.xhr_error_message(
                        $t({defaultMessage: "Error editing message"}),
                        xhr,
                    );
                    compose_banner.show_error_message(
                        message,
                        compose_banner.CLASSNAMES.generic_compose_error,
                        $container,
                    );
                }
            }
        },
    });
    // The message will automatically get replaced via message_list.update_message.
}

export function maybe_show_edit($row, id) {
    if (message_lists.current === undefined) {
        return;
    }

    if (currently_editing_messages.has(id)) {
        message_lists.current.show_edit_message($row, currently_editing_messages.get(id));
    }
}

export function edit_last_sent_message() {
    if (message_lists.current === undefined) {
        return;
    }

    const msg = message_lists.current.get_last_message_sent_by_me();

    if (!msg) {
        return;
    }

    if (!msg.id) {
        blueslip.error("Message has invalid id in edit_last_sent_message.");
        return;
    }

    if (!is_content_editable(msg, 5)) {
        return;
    }

    message_lists.current.select_id(msg.id, {then_scroll: true, from_scroll: true});

    const $msg_row = message_lists.current.get_row(msg.id);
    if (!$msg_row) {
        // This should never happen, since we got the message above
        // from message_lists.current.
        blueslip.error("Could not find row for id", {msg_id: msg.id});
        return;
    }

    // Finally do the real work!
    compose_actions.cancel();
    start($msg_row, () => {
        $(".message_edit_content").trigger("focus");
    });
}

export function delete_message(msg_id) {
    const html_body = render_delete_message_modal();

    function do_delete_message() {
        currently_deleting_messages.push(msg_id);
        channel.del({
            url: "/json/messages/" + msg_id,
            success() {
                currently_deleting_messages = currently_deleting_messages.filter(
                    (id) => id !== msg_id,
                );
                dialog_widget.hide_dialog_spinner();
                dialog_widget.close();
            },
            error(xhr) {
                currently_deleting_messages = currently_deleting_messages.filter(
                    (id) => id !== msg_id,
                );

                dialog_widget.hide_dialog_spinner();
                ui_report.error(
                    $t_html({defaultMessage: "Error deleting message"}),
                    xhr,
                    $("#dialog_error"),
                );
            },
        });
    }

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Delete message?"}),
        html_body,
        help_link: "/help/delete-a-message#delete-a-message-completely",
        on_click: do_delete_message,
        loading_spinner: true,
    });
}

export function delete_topic(stream_id, topic_name, failures = 0) {
    channel.post({
        url: "/json/streams/" + stream_id + "/delete_topic",
        data: {
            topic_name,
        },
        success(data) {
            if (data.complete === false) {
                if (failures >= 9) {
                    // Don't keep retrying indefinitely to avoid DoSing the server.
                    return;
                }

                failures += 1;
                /* When trying to delete a very large topic, it's
                   possible for the request to the server to
                   time out after making some progress. Retry the
                   request, so that the user can just do nothing and
                   watch the topic slowly be deleted.

                   TODO: Show a nice loading indicator experience.
                */
                delete_topic(stream_id, topic_name, failures);
            }
        },
    });
}

export function restore_edit_state_after_message_view_change() {
    assert(message_lists.current !== undefined);
    for (const [idx, elem] of currently_editing_messages) {
        if (message_lists.current.get(idx) !== undefined) {
            const $row = message_lists.current.get_row(idx);
            message_lists.current.show_edit_message($row, elem);
        }
    }
}

function handle_message_move_failure_due_to_time_limit(xhr, handle_confirm, on_hide_callback) {
    const total_messages_allowed_to_move = xhr.responseJSON.total_messages_allowed_to_move;
    const messages_allowed_to_move_text = $t(
        {
            defaultMessage:
                "Do you still want to move the latest {total_messages_allowed_to_move, plural, one {message} other {# messages}}?",
        },
        {total_messages_allowed_to_move},
    );
    const messages_not_allowed_to_move_text = $t(
        {
            defaultMessage:
                "{messages_not_allowed_to_move, plural, one {# message} other {# messages}} will remain in the current topic.",
        },
        {
            messages_not_allowed_to_move:
                xhr.responseJSON.total_messages_in_topic - total_messages_allowed_to_move,
        },
    );

    const html_body = render_confirm_moving_messages_modal({
        messages_allowed_to_move_text,
        messages_not_allowed_to_move_text,
    });
    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Move some messages?"}),
        html_body,
        on_click: handle_confirm,
        loading_spinner: true,
        on_hide: on_hide_callback,
    });
}

function show_message_moved_toast(toast_params) {
    const new_stream_name = sub_store.maybe_get_stream_name(toast_params.new_stream_id);
    const stream_topic = `#${new_stream_name} > ${toast_params.new_topic_name}`;
    const new_location_url = hash_util.by_stream_topic_url(
        toast_params.new_stream_id,
        toast_params.new_topic_name,
    );
    feedback_widget.show({
        populate($container) {
            const widget_body_html = render_message_moved_widget_body({
                stream_topic,
                new_location_url,
            });
            $container.html(widget_body_html);
        },
        title_text: $t({defaultMessage: "Message moved"}),
    });
}

export function move_topic_containing_message_to_stream(
    message_id,
    new_stream_id,
    new_topic_name,
    send_notification_to_new_thread,
    send_notification_to_old_thread,
    propagate_mode,
    toast_params,
) {
    function reset_modal_ui() {
        currently_topic_editing_messages = currently_topic_editing_messages.filter(
            (id) => id !== message_id,
        );
        dialog_widget.hide_dialog_spinner();
    }
    if (currently_topic_editing_messages.includes(message_id)) {
        ui_report.client_error(
            $t_html({defaultMessage: "A Topic Move already in progress."}),
            $("#move_topic_modal #dialog_error"),
        );
        return;
    }
    currently_topic_editing_messages.push(message_id);

    const request = {
        stream_id: new_stream_id,
        propagate_mode,
        topic: new_topic_name,
        send_notification_to_old_thread,
        send_notification_to_new_thread,
    };
    notify_old_thread_default = send_notification_to_old_thread;
    notify_new_thread_default = send_notification_to_new_thread;
    channel.patch({
        url: "/json/messages/" + message_id,
        data: request,
        success() {
            // The main UI will update via receiving the event
            // from server_events.js.
            reset_modal_ui();
            dialog_widget.close();
            if (toast_params) {
                show_message_moved_toast(toast_params);
            }
        },
        error(xhr) {
            reset_modal_ui();
            if (xhr.responseJSON?.code === "MOVE_MESSAGES_TIME_LIMIT_EXCEEDED") {
                const allowed_message_id = xhr.responseJSON.first_message_id_allowed_to_move;
                function handle_confirm() {
                    move_topic_containing_message_to_stream(
                        allowed_message_id,
                        new_stream_id,
                        new_topic_name,
                        send_notification_to_new_thread,
                        send_notification_to_old_thread,
                        "change_later",
                    );
                }

                const partial_move_confirmation_modal_callback = () =>
                    handle_message_move_failure_due_to_time_limit(xhr, handle_confirm);
                dialog_widget.close(partial_move_confirmation_modal_callback);
                return;
            }
            ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
        },
    });
}

export function with_first_message_id(stream_id, topic_name, success_cb, error_cb) {
    // The API endpoint for editing messages to change their
    // content, topic, or stream requires a message ID.
    //
    // Because we don't have full data in the browser client, it's
    // possible that we might display a topic in the left sidebar
    // (and thus expose the UI for moving its topic to another
    // stream) without having a message ID that is definitely
    // within the topic.  (The comments in stream_topic_history.ts
    // discuss the tricky issues around message deletion that are
    // involved here).
    //
    // To ensure this option works reliably at a small latency
    // cost for a rare operation, we just ask the server for the
    // latest message ID in the topic.
    const data = {
        anchor: "newest",
        num_before: 1,
        num_after: 0,
        narrow: JSON.stringify([
            {operator: "channel", operand: stream_id},
            {operator: "topic", operand: topic_name},
        ]),
    };

    channel.get({
        url: "/json/messages",
        data,
        success(data) {
            const message_id = data.messages[0]?.id;
            success_cb(message_id);
        },
        error: error_cb,
    });
}

export function is_message_oldest_or_newest(
    stream_id,
    topic_name,
    message_id,
    success_callback,
    error_callback,
) {
    const data = {
        anchor: message_id,
        num_before: 1,
        num_after: 1,
        narrow: JSON.stringify([
            {operator: "channel", operand: stream_id},
            {operator: "topic", operand: topic_name},
        ]),
    };

    channel.get({
        url: "/json/messages",
        data,
        success(data) {
            let is_oldest = true;
            let is_newest = true;
            for (const message of data.messages) {
                if (message.id < message_id) {
                    is_oldest = false;
                } else if (message.id > message_id) {
                    is_newest = false;
                }
            }
            success_callback(is_oldest, is_newest);
        },
        error: error_callback,
    });
}
