import ClipboardJS from "clipboard";
import $ from "jquery";

import * as resolved_topic from "../shared/js/resolved_topic";
import render_delete_message_modal from "../templates/confirm_dialog/confirm_delete_message.hbs";
import render_message_edit_form from "../templates/message_edit_form.hbs";
import render_topic_edit_form from "../templates/topic_edit_form.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as compose from "./compose";
import * as compose_actions from "./compose_actions";
import * as compose_ui from "./compose_ui";
import * as composebox_typeahead from "./composebox_typeahead";
import * as condense from "./condense";
import * as confirm_dialog from "./confirm_dialog";
import * as dialog_widget from "./dialog_widget";
import * as echo from "./echo";
import {$t, $t_html} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as loading from "./loading";
import * as markdown from "./markdown";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import * as message_viewport from "./message_viewport";
import {page_params} from "./page_params";
import * as resize from "./resize";
import * as rows from "./rows";
import * as settings_data from "./settings_data";
import * as stream_data from "./stream_data";
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

export const editability_types = {
    NO: 1,
    // Note: TOPIC_ONLY does not include stream messages with no topic sent
    // by someone else. You can edit the topic of such a message by editing
    // the topic of the whole recipient_row it appears in, but you can't
    // directly edit the topic of such a message.
    // Similar story for messages whose topic you can change only because
    // you are an admin.
    TOPIC_ONLY: 3,
    FULL: 4,
};

export function is_topic_editable(message, edit_limit_seconds_buffer = 0) {
    if (!is_message_editable_ignoring_permissions(message)) {
        return false;
    }

    if (!page_params.realm_allow_message_editing) {
        // If message editing is disabled, so is topic editing.
        return false;
    }
    // Organization admins and message senders can edit message topics indefinitely.
    if (page_params.is_admin) {
        return true;
    }
    if (message.sent_by_me) {
        return true;
    }

    if (message.topic === compose.empty_topic_placeholder()) {
        return true;
    }

    if (!settings_data.user_can_edit_topic_of_any_message()) {
        return false;
    }

    // moderators can edit the topic if edit_topic_policy allows them to do so,
    // irrespective of the topic editing deadline.
    if (page_params.is_moderator) {
        return true;
    }

    // If you're using community topic editing, there's a deadline.
    return (
        page_params.realm_community_topic_editing_limit_seconds +
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

export function get_editability(message, edit_limit_seconds_buffer = 0) {
    if (!is_message_editable_ignoring_permissions(message)) {
        return editability_types.NO;
    }

    if (!is_topic_editable(message, edit_limit_seconds_buffer)) {
        return editability_types.NO;
    }

    if (!page_params.realm_allow_message_editing) {
        return editability_types.NO;
    }

    if (
        page_params.realm_message_content_edit_limit_seconds === null &&
        message.sent_by_me &&
        !is_widget_message(message)
    ) {
        return editability_types.FULL;
    }

    if (
        page_params.realm_message_content_edit_limit_seconds +
            edit_limit_seconds_buffer +
            (message.timestamp - Date.now() / 1000) >
            0 &&
        message.sent_by_me &&
        !is_widget_message(message)
    ) {
        return editability_types.FULL;
    }

    // time's up!
    if (message.type === "stream") {
        return editability_types.TOPIC_ONLY;
    }
    return editability_types.NO;
}

export function get_deletability(message) {
    if (page_params.is_admin) {
        return true;
    }

    if (!message.sent_by_me) {
        return false;
    }
    if (message.locally_echoed) {
        return false;
    }
    if (!settings_data.user_can_delete_own_message()) {
        return false;
    }

    if (page_params.realm_message_content_delete_limit_seconds === null) {
        // This means no time limit for message deletion.
        return true;
    }

    if (
        page_params.realm_message_content_delete_limit_seconds +
            (message.timestamp - Date.now() / 1000) >
        0
    ) {
        return true;
    }
    return false;
}

export function can_move_message(message) {
    if (!page_params.realm_allow_message_editing) {
        return false;
    }

    if (!message.is_stream) {
        return false;
    }

    if (!is_message_editable_ignoring_permissions(message)) {
        return false;
    }

    return (
        get_editability(message) !== editability_types.NO ||
        settings_data.user_can_move_messages_between_streams()
    );
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

export function update_message_topic_editing_pencil() {
    if (page_params.realm_allow_message_editing) {
        $(".on_hover_topic_edit, .always_visible_topic_edit").show();
    } else {
        $(".on_hover_topic_edit, .always_visible_topic_edit").hide();
    }
}

export function hide_message_edit_spinner($row) {
    $row.find(".loader").hide();
    $row.find(".message_edit_save span").show();
    $row.find(".message_edit_save").removeClass("disable-btn");
    $row.find(".message_edit_cancel").removeClass("disable-btn");
}

export function show_message_edit_spinner($row) {
    const using_dark_theme = settings_data.using_dark_theme();
    loading.show_button_spinner($row.find(".loader"), using_dark_theme);
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
        save_inline_topic_edit($row);
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
        end_message_row_edit($row);
        $row.find(".alert-msg").text($t({defaultMessage: "Copied!"}));
        $row.find(".alert-msg").css("display", "block");
        $row.find(".alert-msg").delay(1000).fadeOut(300);
        if ($(".tooltip").is(":visible")) {
            $(".tooltip").hide();
        }
    });
}

export function get_available_streams_for_moving_messages(current_stream_id) {
    return stream_data
        .subscribed_subs()
        .filter((stream) => {
            if (stream.id === current_stream_id) {
                return true;
            }
            return stream_data.can_post_messages_in_stream(stream);
        })
        .map((stream) => ({
            name: stream.name,
            value: stream.stream_id.toString(),
        }))
        .sort((a, b) => {
            if (a.name.toLowerCase() < b.name.toLowerCase()) {
                return -1;
            }
            if (a.name.toLowerCase() > b.name.toLowerCase()) {
                return 1;
            }
            return 0;
        });
}

function edit_message($row, raw_content) {
    $row.find(".message_reactions").hide();
    condense.hide_message_expander($row);
    condense.hide_message_condenser($row);
    const content_top = $row.find(".message_top_line")[0].getBoundingClientRect().top;

    const message = message_lists.current.get(rows.id($row));

    // We potentially got to this function by clicking a button that implied the
    // user would be able to edit their message.  Give a little bit of buffer in
    // case the button has been around for a bit, e.g. we show the
    // edit_content_button (hovering pencil icon) as long as the user would have
    // been able to click it at the time the mouse entered the message_row. Also
    // a buffer in case their computer is slow, or stalled for a second, etc
    // If you change this number also change edit_limit_buffer in
    // zerver.actions.message_edit.check_update_message
    const seconds_left_buffer = 5;
    const editability = get_editability(message, seconds_left_buffer);
    const max_file_upload_size = page_params.max_file_upload_size_mib;
    let file_upload_enabled = false;

    if (max_file_upload_size > 0) {
        file_upload_enabled = true;
    }

    const is_editable = editability === editability_types.FULL;

    const $form = $(
        render_message_edit_form({
            message_id: message.id,
            is_editable,
            content: raw_content,
            file_upload_enabled,
            minutes_to_edit: Math.floor(page_params.realm_message_content_edit_limit_seconds / 60),
            max_message_length: page_params.max_message_length,
        }),
    );

    const edit_obj = {$form, raw_content};
    currently_editing_messages.set(message.id, edit_obj);
    message_lists.current.show_edit_message($row, edit_obj);

    $form.on("keydown", handle_message_row_edit_keydown);

    $form
        .find(".message-edit-feature-group .video_link")
        .toggle(compose.compute_show_video_chat_button());
    upload.feature_check($(`#edit_form_${CSS.escape(rows.id($row))} .compose_upload_file`));

    const $message_edit_content = $row.find("textarea.message_edit_content");
    const $message_edit_countdown_timer = $row.find(".message_edit_countdown_timer");
    const $copy_message = $row.find(".copy_message");

    if (editability !== editability_types.FULL) {
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
    if (
        editability === editability_types.FULL &&
        page_params.realm_message_content_edit_limit_seconds > 0
    ) {
        $row.find(".message-edit-timer").show();

        // Give them at least 10 seconds.
        // If you change this number also change edit_limit_buffer in
        // zerver.actions.message_edit.check_update_message
        const min_seconds_to_edit = 10;
        let seconds_left =
            page_params.realm_message_content_edit_limit_seconds +
            (message.timestamp - Date.now() / 1000);
        seconds_left = Math.floor(Math.max(seconds_left, min_seconds_to_edit));

        // I believe this needs to be defined outside the countdown_timer, since
        // row just refers to something like the currently selected message, and
        // can change out from under us
        const $message_edit_save = $row.find("button.message_edit_save");
        // Do this right away, rather than waiting for the timer to do its first update,
        // since otherwise there is a noticeable lag
        $message_edit_countdown_timer.text(timer_text(seconds_left));
        const countdown_timer = setInterval(() => {
            seconds_left -= 1;
            if (seconds_left <= 0) {
                clearInterval(countdown_timer);
                $message_edit_content.prop("readonly", "readonly");
                // We don't go directly to a "TOPIC_ONLY" type state (with an active Save button),
                // since it isn't clear what to do with the half-finished edit. It's nice to keep
                // the half-finished edit around so that they can copy-paste it, but we don't want
                // people to think "Save" will save the half-finished edit.
                $message_edit_save.addClass("disabled");
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
    const row_bottom = $row.height() + $row.offset().top;
    const composebox_top = $("#compose").offset().top;
    if (row_bottom > composebox_top) {
        message_viewport.scrollTop(message_viewport.scrollTop() + row_bottom - composebox_top);
    }
}

function start_edit_with_content($row, content, edit_box_open_callback) {
    start_edit_maintaining_scroll($row, content);
    if (edit_box_open_callback) {
        edit_box_open_callback();
    }

    upload.setup_upload({
        mode: "edit",
        row: rows.id($row),
    });
}

export function start($row, edit_box_open_callback) {
    const message = message_lists.current.get(rows.id($row));
    if (message === undefined) {
        blueslip.error("Couldn't find message ID for edit " + rows.id($row));
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

export function toggle_resolve_topic(message_id, old_topic_name) {
    let new_topic_name;
    if (resolved_topic.is_resolved(old_topic_name)) {
        new_topic_name = resolved_topic.unresolve_name(old_topic_name);
    } else {
        new_topic_name = resolved_topic.resolve_name(old_topic_name);
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
    });
}

export function start_inline_topic_edit($recipient_row) {
    const $form = $(
        render_topic_edit_form({
            max_topic_length: page_params.max_topic_length,
        }),
    );
    message_lists.current.show_edit_topic_on_recipient_row($recipient_row, $form);
    $form.on("keydown", handle_inline_topic_edit_keydown);
    $(".topic_edit_spinner").hide();
    const msg_id = rows.id_for_recipient_row($recipient_row);
    const message = message_lists.current.get(msg_id);
    let topic = message.topic;
    if (topic === compose.empty_topic_placeholder()) {
        topic = "";
    }
    const $inline_topic_edit_input = $form.find(".inline_topic_edit");
    $inline_topic_edit_input.val(topic).trigger("select").trigger("focus");
    composebox_typeahead.initialize_topic_edit_typeahead(
        $inline_topic_edit_input,
        message.stream,
        false,
    );
}

export function is_editing(id) {
    return currently_editing_messages.has(id);
}

export function end_inline_topic_edit($row) {
    message_lists.current.hide_edit_topic_on_recipient_row($row);
}

export function end_message_row_edit($row) {
    const message = message_lists.current.get(rows.id($row));
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

        compose.abort_video_callbacks(message.id);
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
    const $row = message_lists.current.get_row(message_id);
    if ($row.length > 0) {
        end_message_row_edit($row);
    } else if (currently_editing_messages.has(message_id)) {
        // We should delete the message_id from currently_editing_messages
        // if it exists there but we cannot find the row.
        currently_editing_messages.delete(message_id);
    }
}

export function save_inline_topic_edit($row) {
    const msg_list = message_lists.current;
    let message_id = rows.id_for_recipient_row($row);
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

    show_topic_edit_spinner($row);

    if (message.locally_echoed) {
        if (topic_changed) {
            echo.edit_locally(message, {new_topic});
            $row = message_lists.current.get_row(message_id);
        }
        end_inline_topic_edit($row);
        return;
    }

    const request = {
        message_id: message.id,
        topic: new_topic,
        propagate_mode: "change_later",
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
            loading.destroy_indicator($spinner);
            if (msg_list === message_lists.current) {
                message_id = rows.id_for_recipient_row($row);
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
    const msg_list = message_lists.current;
    let message_id = rows.id($row);
    const message = message_lists.current.get(message_id);
    let changed = false;
    let edit_locally_echoed = false;

    let new_content;
    const old_content = message.raw_content;

    show_message_edit_spinner($row);

    const $edit_content_input = $row.find(".message_edit_content");
    const can_edit_content = $edit_content_input.attr("readonly") !== "readonly";
    if (can_edit_content) {
        new_content = $edit_content_input.val();
        changed = old_content !== new_content;
    }

    // Editing a not-yet-acked message (because the original send attempt failed)
    // just results in the in-memory message being changed
    if (message.locally_echoed) {
        if (new_content !== message.raw_content) {
            // `edit_locally` handles the case where `new_topic/new_stream_id` is undefined
            echo.edit_locally(message, {
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

        echo.edit_locally(message, currently_echoing_messages.get(message_id));

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
            hide_message_edit_spinner($row);
        },
        error(xhr) {
            if (msg_list === message_lists.current) {
                message_id = rows.id($row);

                if (edit_locally_echoed) {
                    const echoed_message = message_store.get(message_id);
                    const echo_data = currently_echoing_messages.get(message_id);

                    delete echoed_message.local_edit_timestamp;
                    currently_echoing_messages.delete(message_id);

                    // Restore the original content.
                    echo.edit_locally(echoed_message, {
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
                const message = channel.xhr_error_message(
                    $t({defaultMessage: "Error saving edit"}),
                    xhr,
                );
                $row.find(".edit_error").text(message).show();
            }
        },
    });
    // The message will automatically get replaced via message_list.update_message.
}

export function maybe_show_edit($row, id) {
    if (currently_editing_messages.has(id)) {
        message_lists.current.show_edit_message($row, currently_editing_messages.get(id));
    }
}

export function edit_last_sent_message() {
    const msg = message_lists.current.get_last_message_sent_by_me();

    if (!msg) {
        return;
    }

    if (!msg.id) {
        blueslip.error("Message has invalid id in edit_last_sent_message.");
        return;
    }

    const msg_editability_type = get_editability(msg, 5);
    if (msg_editability_type !== editability_types.FULL) {
        return;
    }

    const $msg_row = message_lists.current.get_row(msg.id);
    if (!$msg_row) {
        // This should never happen, since we got the message above
        // from message_lists.current.
        blueslip.error("Could not find row for id " + msg.id);
        return;
    }

    message_lists.current.select_id(msg.id, {then_scroll: true, from_scroll: true});

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
                dialog_widget.close_modal();
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
        help_link: "/help/edit-or-delete-a-message#delete-a-message",
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
            if (data.result === "partially_completed") {
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

export function handle_narrow_deactivated() {
    for (const [idx, elem] of currently_editing_messages) {
        if (message_lists.current.get(idx) !== undefined) {
            const $row = message_lists.current.get_row(idx);
            message_lists.current.show_edit_message($row, elem);
        }
    }
}

export function move_topic_containing_message_to_stream(
    message_id,
    new_stream_id,
    new_topic_name,
    send_notification_to_new_thread,
    send_notification_to_old_thread,
    propagate_mode,
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
            dialog_widget.close_modal();
        },
        error(xhr) {
            reset_modal_ui();
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
    // within the topic.  (The comments in stream_topic_history.js
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
            {operator: "stream", operand: stream_id},
            {operator: "topic", operand: topic_name},
        ]),
    };

    channel.get({
        url: "/json/messages",
        data,
        success(data) {
            const message_id = data.messages[0].id;
            success_cb(message_id);
        },
        error: error_cb,
    });
}
