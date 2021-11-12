import ClipboardJS from "clipboard";
import $ from "jquery";
import _ from "lodash";

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
import {DropdownListWidget} from "./dropdown_list_widget";
import * as echo from "./echo";
import * as giphy from "./giphy";
import {$t, $t_html} from "./i18n";
import * as loading from "./loading";
import * as markdown from "./markdown";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import * as message_viewport from "./message_viewport";
import {page_params} from "./page_params";
import * as resize from "./resize";
import * as rows from "./rows";
import * as settings_data from "./settings_data";
import * as stream_bar from "./stream_bar";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import * as ui_report from "./ui_report";
import * as upload from "./upload";

const currently_editing_messages = new Map();
let currently_deleting_messages = [];
let currently_topic_editing_messages = [];
const currently_echoing_messages = new Map();
export const RESOLVED_TOPIC_PREFIX = "✔ ";

// These variables are designed to preserve the user's most recent
// choices when editing a group of messages, to make it convenient to
// move several topics in a row with the same settings.
export let notify_old_thread_default = true;

export let notify_new_thread_default = true;

export const editability_types = {
    NO: 1,
    NO_LONGER: 2,
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

export function get_editability(message, edit_limit_seconds_buffer = 0) {
    if (!message) {
        return editability_types.NO;
    }
    if (!is_topic_editable(message, edit_limit_seconds_buffer)) {
        return editability_types.NO;
    }

    if (message.failed_request) {
        // TODO: For completely failed requests, we should be able
        //       to "edit" the message, but it won't really be like
        //       other message updates.  This commit changed the result
        //       from FULL to NO, since the prior implementation was
        //       buggy.
        return editability_types.NO;
    }

    // Locally echoed messages are not editable, since the message hasn't
    // finished being sent yet.
    if (message.locally_echoed) {
        return editability_types.NO;
    }

    if (!page_params.realm_allow_message_editing) {
        return editability_types.NO;
    }

    if (
        page_params.realm_message_content_edit_limit_seconds === 0 &&
        message.sent_by_me &&
        !is_widget_message(message)
    ) {
        return editability_types.FULL;
    }

    if (currently_echoing_messages.has(message.id)) {
        return editability_types.NO;
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
    return editability_types.NO_LONGER;
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

export function update_message_topic_editing_pencil() {
    if (page_params.realm_allow_message_editing) {
        $(".on_hover_topic_edit, .always_visible_topic_edit").show();
    } else {
        $(".on_hover_topic_edit, .always_visible_topic_edit").hide();
    }
}

export function hide_message_edit_spinner(row) {
    row.find(".loader").hide();
    row.find(".message_edit_save span").show();
    row.find(".message_edit_save").removeClass("disable-btn");
    row.find(".message_edit_cancel").removeClass("disable-btn");
}

export function show_message_edit_spinner(row) {
    const using_dark_theme = settings_data.using_dark_theme();
    loading.show_button_spinner(row.find(".loader"), using_dark_theme);
    row.find(".message_edit_save span").hide();
    row.find(".message_edit_save").addClass("disable-btn");
    row.find(".message_edit_cancel").addClass("disable-btn");
}

export function show_topic_edit_spinner(row) {
    const spinner = row.find(".topic_edit_spinner");
    loading.make_indicator(spinner);
    spinner.css({height: ""});
    $(".topic_edit_save").hide();
    $(".topic_edit_cancel").hide();
    $(".topic_edit_spinner").show();
}

export function end_if_focused_on_inline_topic_edit() {
    const focused_elem = $(".topic_edit_form").find(":focus");
    if (focused_elem.length === 1) {
        focused_elem.trigger("blur");
        const recipient_row = focused_elem.closest(".recipient_row");
        end_inline_topic_edit(recipient_row);
    }
}

export function end_if_focused_on_message_row_edit() {
    const focused_elem = $(".message_edit").find(":focus");
    if (focused_elem.length === 1) {
        focused_elem.trigger("blur");
        const row = focused_elem.closest(".message_row");
        end_message_row_edit(row);
    }
}

function handle_message_row_edit_keydown(e) {
    switch (e.key) {
        case "Enter":
            if ($(e.target).hasClass("message_edit_content")) {
                // Pressing Enter to save edits is coupled with Enter to send
                if (composebox_typeahead.should_enter_send(e)) {
                    const row = $(".message_edit_content:focus").closest(".message_row");
                    const message_edit_save_button = row.find(".message_edit_save");
                    if (message_edit_save_button.prop("disabled")) {
                        // In cases when the save button is disabled
                        // we need to disable save on pressing Enter
                        // Prevent default to avoid new-line on pressing
                        // Enter inside the textarea in this case
                        e.preventDefault();
                        return;
                    }
                    save_message_row_edit(row);
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
                const row = $(e.target).closest(".message_row");
                save_message_row_edit(row);
                e.stopPropagation();
            }
            return;
        case "Escape": // Handle escape keys in the message_edit form.
            end_if_focused_on_message_row_edit();
            e.stopPropagation();
            e.preventDefault();
            return;
        default:
            return;
    }
}

function handle_inline_topic_edit_keydown(e) {
    let row;
    switch (e.key) {
        case "Enter": // Handle Enter key in the recipient bar/inline topic edit form
            if ($(".typeahead:visible").length > 0) {
                // Accepting typeahead should not trigger a save.
                e.preventDefault();
                return;
            }
            row = $(e.target).closest(".recipient_row");
            save_inline_topic_edit(row);
            e.stopPropagation();
            e.preventDefault();
            return;
        case "Escape": // handle Esc
            end_if_focused_on_inline_topic_edit();
            e.stopPropagation();
            e.preventDefault();
            return;
        default:
            return;
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

function create_copy_to_clipboard_handler(row, source, message_id) {
    const clipboard = new ClipboardJS(source, {
        target: () =>
            document.querySelector(`#edit_form_${CSS.escape(message_id)} .message_edit_content`),
    });

    clipboard.on("success", () => {
        end_message_row_edit(row);
        row.find(".alert-msg").text($t({defaultMessage: "Copied!"}));
        row.find(".alert-msg").css("display", "block");
        row.find(".alert-msg").delay(1000).fadeOut(300);
        if ($(".tooltip").is(":visible")) {
            $(".tooltip").hide();
        }
    });
}

function edit_message(row, raw_content) {
    let stream_widget;
    row.find(".message_reactions").hide();
    condense.hide_message_expander(row);
    condense.hide_message_condenser(row);
    const content_top = row.find(".message_top_line")[0].getBoundingClientRect().top;

    const message = message_lists.current.get(rows.id(row));

    // We potentially got to this function by clicking a button that implied the
    // user would be able to edit their message.  Give a little bit of buffer in
    // case the button has been around for a bit, e.g. we show the
    // edit_content_button (hovering pencil icon) as long as the user would have
    // been able to click it at the time the mouse entered the message_row. Also
    // a buffer in case their computer is slow, or stalled for a second, etc
    // If you change this number also change edit_limit_buffer in
    // zerver.lib.actions.check_update_message
    const seconds_left_buffer = 5;
    const editability = get_editability(message, seconds_left_buffer);
    const max_file_upload_size = page_params.max_file_upload_size_mib;
    let file_upload_enabled = false;

    if (max_file_upload_size > 0) {
        file_upload_enabled = true;
    }

    const is_stream_editable =
        message.is_stream && settings_data.user_can_move_messages_between_streams();
    const is_editable =
        editability === editability_types.TOPIC_ONLY ||
        editability === editability_types.FULL ||
        is_stream_editable;
    // current message's stream has been already been added and selected in handlebar
    const available_streams = is_stream_editable
        ? stream_data.subscribed_subs().map((stream) => ({
              name: stream.name,
              value: stream.stream_id.toString(),
          }))
        : null;

    const select_move_stream_widget_name = `select_move_stream_${message.id}`;
    const opts = {
        widget_name: select_move_stream_widget_name,
        data: available_streams,
        default_text: $t({defaultMessage: "No streams"}),
        include_current_item: true,
        value: message.stream_id,
        on_update: set_propagate_selector_display,
    };

    const form = $(
        render_message_edit_form({
            is_stream: message.type === "stream",
            message_id: message.id,
            is_editable,
            is_content_editable: editability === editability_types.FULL,
            is_widget_message: is_widget_message(message),
            has_been_editable: editability !== editability_types.NO,
            topic: message.topic,
            content: raw_content,
            file_upload_enabled,
            minutes_to_edit: Math.floor(page_params.realm_message_content_edit_limit_seconds / 60),
            is_stream_editable,
            select_move_stream_widget_name,
            notify_new_thread: notify_new_thread_default,
            notify_old_thread: notify_old_thread_default,
            giphy_enabled: giphy.is_giphy_enabled(),
        }),
    );

    const edit_obj = {form, raw_content};
    currently_editing_messages.set(message.id, edit_obj);
    message_lists.current.show_edit_message(row, edit_obj);

    form.on("keydown", handle_message_row_edit_keydown);

    form.find(".message-edit-feature-group .video_link").toggle(
        compose.compute_show_video_chat_button(),
    );
    upload.feature_check($(`#edit_form_${CSS.escape(rows.id(row))} .compose_upload_file`));

    const stream_header_colorblock = row.find(".stream_header_colorblock");
    const message_edit_content = row.find("textarea.message_edit_content");
    const message_edit_topic = row.find("input.message_edit_topic");
    const message_edit_topic_propagate = row.find("select.message_edit_topic_propagate");
    const message_edit_breadcrumb_messages = row.find("div.message_edit_breadcrumb_messages");
    const message_edit_countdown_timer = row.find(".message_edit_countdown_timer");
    const copy_message = row.find(".copy_message");

    if (is_stream_editable) {
        stream_widget = new DropdownListWidget(opts);
    }
    stream_bar.decorate(message.stream, stream_header_colorblock, false);

    switch (editability) {
        case editability_types.NO:
            message_edit_content.attr("readonly", "readonly");
            message_edit_topic.attr("readonly", "readonly");
            create_copy_to_clipboard_handler(row, copy_message[0], message.id);
            break;
        case editability_types.NO_LONGER:
            // You can currently only reach this state in non-streams. If that
            // changes (e.g. if we stop allowing topics to be modified forever
            // in streams), then we'll need to disable
            // row.find('input.message_edit_topic') as well.
            message_edit_content.attr("readonly", "readonly");
            message_edit_countdown_timer.text($t({defaultMessage: "View source"}));
            create_copy_to_clipboard_handler(row, copy_message[0], message.id);
            break;
        case editability_types.TOPIC_ONLY:
            message_edit_content.attr("readonly", "readonly");
            // Hint why you can edit the topic but not the message content
            message_edit_countdown_timer.text($t({defaultMessage: "Topic editing only"}));
            create_copy_to_clipboard_handler(row, copy_message[0], message.id);
            break;
        case editability_types.FULL: {
            copy_message.remove();
            const edit_id = `#edit_form_${CSS.escape(rows.id(row))} .message_edit_content`;
            const listeners = resize.watch_manual_resize(edit_id);
            if (listeners) {
                currently_editing_messages.get(rows.id(row)).listeners = listeners;
            }
            composebox_typeahead.initialize_compose_typeahead(edit_id);
            compose_ui.handle_keyup(null, $(edit_id).expectOne());
            $(edit_id).on("keydown", function (event) {
                compose_ui.handle_keydown(event, $(this).expectOne());
            });
            $(edit_id).on("keyup", function (event) {
                compose_ui.handle_keyup(event, $(this).expectOne());
            });
            break;
        }
    }

    // Add tooltip
    if (
        editability !== editability_types.NO &&
        page_params.realm_message_content_edit_limit_seconds > 0
    ) {
        row.find(".message-edit-timer-control-group").show();
    }

    // add timer
    if (
        editability === editability_types.FULL &&
        page_params.realm_message_content_edit_limit_seconds > 0
    ) {
        // Give them at least 10 seconds.
        // If you change this number also change edit_limit_buffer in
        // zerver.lib.actions.check_update_message
        const min_seconds_to_edit = 10;
        let seconds_left =
            page_params.realm_message_content_edit_limit_seconds +
            (message.timestamp - Date.now() / 1000);
        seconds_left = Math.floor(Math.max(seconds_left, min_seconds_to_edit));

        // I believe this needs to be defined outside the countdown_timer, since
        // row just refers to something like the currently selected message, and
        // can change out from under us
        const message_edit_save = row.find("button.message_edit_save");
        // Do this right away, rather than waiting for the timer to do its first update,
        // since otherwise there is a noticeable lag
        message_edit_countdown_timer.text(timer_text(seconds_left));
        const countdown_timer = setInterval(() => {
            seconds_left -= 1;
            if (seconds_left <= 0) {
                clearInterval(countdown_timer);
                message_edit_content.prop("readonly", "readonly");
                if (message.type === "stream") {
                    message_edit_topic.prop("readonly", "readonly");
                    message_edit_topic_propagate.hide();
                    message_edit_breadcrumb_messages.hide();
                }
                // We don't go directly to a "TOPIC_ONLY" type state (with an active Save button),
                // since it isn't clear what to do with the half-finished edit. It's nice to keep
                // the half-finished edit around so that they can copy-paste it, but we don't want
                // people to think "Save" will save the half-finished edit.
                message_edit_save.addClass("disabled");
                message_edit_countdown_timer.text($t({defaultMessage: "Time's up!"}));
            } else {
                message_edit_countdown_timer.text(timer_text(seconds_left));
            }
        }, 1000);
    }

    if (!is_editable) {
        row.find(".message_edit_close").trigger("focus");
    } else if (message.type === "stream" && message.topic === compose.empty_topic_placeholder()) {
        message_edit_topic.val("");
        message_edit_topic.trigger("focus");
    } else if (editability === editability_types.TOPIC_ONLY) {
        row.find(".message_edit_topic").trigger("focus");
    } else {
        message_edit_content.trigger("focus");
        // Put cursor at end of input.
        const contents = message_edit_content.val();
        message_edit_content.val("");
        message_edit_content.val(contents);
    }

    // Scroll to keep the top of the message content text in the same
    // place visually, adjusting for border and padding.
    const edit_top = message_edit_content[0].getBoundingClientRect().top;
    const scroll_by = edit_top - content_top + 5 - 14;

    edit_obj.scrolled_by = scroll_by;
    message_viewport.scrollTop(message_viewport.scrollTop() + scroll_by);

    const original_stream_id = message.stream_id;
    const original_topic = message.topic;

    // Change the `stream_header_colorblock` when clicked on any dropdown item.
    function update_stream_header_colorblock() {
        // Stop the execution if stream_widget is undefined.
        if (!stream_widget) {
            return;
        }
        const stream_name = stream_data.maybe_get_stream_name(
            Number.parseInt(stream_widget.value(), 10),
        );

        stream_bar.decorate(stream_name, stream_header_colorblock, false);
    }

    function set_propagate_selector_display() {
        update_stream_header_colorblock();
        const new_topic = message_edit_topic.val();
        const new_stream_id = is_stream_editable
            ? Number.parseInt(stream_widget.value(), 10)
            : null;
        const is_topic_edited = new_topic !== original_topic && new_topic !== "";
        const is_stream_edited = is_stream_editable ? new_stream_id !== original_stream_id : false;
        message_edit_topic_propagate.toggle(is_topic_edited || is_stream_edited);
        message_edit_breadcrumb_messages.toggle(is_stream_edited);

        if (is_stream_edited) {
            /* Reinitialize the typeahead component with content for the new stream. */
            const new_stream_name = sub_store.get(new_stream_id).name;
            message_edit_topic.data("typeahead").unlisten();
            composebox_typeahead.initialize_topic_edit_typeahead(
                message_edit_topic,
                new_stream_name,
                true,
            );
        }
    }

    if (!message.locally_echoed) {
        message_edit_topic.on("keyup", () => {
            set_propagate_selector_display();
        });
    }
    composebox_typeahead.initialize_topic_edit_typeahead(message_edit_topic, message.stream, true);
}

function start_edit_maintaining_scroll(row, content) {
    edit_message(row, content);
    const row_bottom = row.height() + row.offset().top;
    const composebox_top = $("#compose").offset().top;
    if (row_bottom > composebox_top) {
        message_viewport.scrollTop(message_viewport.scrollTop() + row_bottom - composebox_top);
    }
}

function start_edit_with_content(row, content, edit_box_open_callback) {
    start_edit_maintaining_scroll(row, content);
    if (edit_box_open_callback) {
        edit_box_open_callback();
    }

    upload.setup_upload({
        mode: "edit",
        row: rows.id(row),
    });
}

export function start(row, edit_box_open_callback) {
    const message = message_lists.current.get(rows.id(row));
    if (message === undefined) {
        blueslip.error("Couldn't find message ID for edit " + rows.id(row));
        return;
    }

    if (message.raw_content) {
        start_edit_with_content(row, message.raw_content, edit_box_open_callback);
        return;
    }

    const msg_list = message_lists.current;
    channel.get({
        url: "/json/messages/" + message.id,
        idempotent: true,
        success(data) {
            if (message_lists.current === msg_list) {
                message.raw_content = data.raw_content;
                start_edit_with_content(row, message.raw_content, edit_box_open_callback);
            }
        },
    });
}

export function toggle_resolve_topic(message_id, old_topic_name) {
    let new_topic_name;
    if (old_topic_name.startsWith(RESOLVED_TOPIC_PREFIX)) {
        new_topic_name = _.trimStart(old_topic_name, RESOLVED_TOPIC_PREFIX);
    } else {
        new_topic_name = RESOLVED_TOPIC_PREFIX + old_topic_name;
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

export function start_inline_topic_edit(recipient_row) {
    const form = $(render_topic_edit_form());
    message_lists.current.show_edit_topic_on_recipient_row(recipient_row, form);
    form.on("keydown", handle_inline_topic_edit_keydown);
    $(".topic_edit_spinner").hide();
    const msg_id = rows.id_for_recipient_row(recipient_row);
    const message = message_lists.current.get(msg_id);
    let topic = message.topic;
    if (topic === compose.empty_topic_placeholder()) {
        topic = "";
    }
    const inline_topic_edit_input = form.find(".inline_topic_edit");
    inline_topic_edit_input.val(topic).trigger("select").trigger("focus");
    composebox_typeahead.initialize_topic_edit_typeahead(
        inline_topic_edit_input,
        message.stream,
        false,
    );
}

export function is_editing(id) {
    return currently_editing_messages.has(id);
}

export function end_inline_topic_edit(row) {
    message_lists.current.hide_edit_topic_on_recipient_row(row);
}

export function end_message_row_edit(row) {
    const message = message_lists.current.get(rows.id(row));
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
        message_lists.current.hide_edit_message(row);
        message_viewport.scrollTop(original_scrollTop - scroll_by);

        compose.abort_video_callbacks(message.id);
    }
    if (row.find(".condensed").length !== 0) {
        condense.show_message_expander(row);
    } else {
        condense.show_message_condenser(row);
    }
    row.find(".message_reactions").show();

    // We have to blur out text fields, or else hotkeys.js
    // thinks we are still editing.
    row.find(".message_edit").trigger("blur");
    // We should hide the editing typeahead if it is visible
    row.find("input.message_edit_topic").trigger("blur");
}

export function save_inline_topic_edit(row) {
    const msg_list = message_lists.current;
    let message_id = rows.id_for_recipient_row(row);
    const message = message_lists.current.get(message_id);

    const old_topic = message.topic;
    const new_topic = row.find(".inline_topic_edit").val();
    const topic_changed = new_topic !== old_topic && new_topic.trim() !== "";

    if (!topic_changed) {
        // this means the inline_topic_edit was opened and submitted without
        // changing anything, therefore, we should just close the inline topic edit.
        end_inline_topic_edit(row);
        return;
    }

    show_topic_edit_spinner(row);

    if (message.locally_echoed) {
        if (topic_changed) {
            echo.edit_locally(message, {new_topic});
            row = message_lists.current.get_row(message_id);
        }
        end_inline_topic_edit(row);
        return;
    }

    const request = {
        message_id: message.id,
        topic: new_topic,
        propagate_mode: "change_later",
    };

    channel.patch({
        url: "/json/messages/" + message.id,
        data: request,
        success() {
            const spinner = row.find(".topic_edit_spinner");
            loading.destroy_indicator(spinner);
        },
        error(xhr) {
            const spinner = row.find(".topic_edit_spinner");
            loading.destroy_indicator(spinner);
            if (msg_list === message_lists.current) {
                message_id = rows.id_for_recipient_row(row);
                const message = channel.xhr_error_message(
                    $t({defaultMessage: "Error saving edit"}),
                    xhr,
                );
                row.find(".edit_error").text(message).css("display", "inline-block");
            }
        },
    });
}

export function save_message_row_edit(row) {
    const msg_list = message_lists.current;
    let message_id = rows.id(row);
    const message = message_lists.current.get(message_id);
    const can_edit_stream =
        message.is_stream && settings_data.user_can_move_messages_between_streams();
    let changed = false;
    let edit_locally_echoed = false;

    const new_content = row.find(".message_edit_content").val();
    let topic_changed = false;
    let new_topic;
    const old_topic = message.topic;

    let stream_changed = false;
    let new_stream_id;
    const old_stream_id = message.stream_id;

    show_message_edit_spinner(row);

    if (message.type === "stream") {
        new_topic = row.find(".message_edit_topic").val();
        topic_changed = new_topic !== old_topic && new_topic.trim() !== "";

        if (can_edit_stream) {
            const dropdown_list_widget_value_elem = $(`#id_select_move_stream_${message_id}`);
            new_stream_id = Number.parseInt(dropdown_list_widget_value_elem.data("value"), 10);
            stream_changed = new_stream_id !== old_stream_id;
        }
    }
    // Editing a not-yet-acked message (because the original send attempt failed)
    // just results in the in-memory message being changed
    if (message.locally_echoed) {
        if (new_content !== message.raw_content || topic_changed || stream_changed) {
            // `edit_locally` handles the case where `new_topic/new_stream_id` is undefined
            echo.edit_locally(message, {
                raw_content: new_content,
                new_topic,
                new_stream_id,
            });
            row = message_lists.current.get_row(message_id);
        }
        end_message_row_edit(row);
        return;
    }

    const request = {message_id: message.id};

    if (topic_changed || stream_changed) {
        const selected_topic_propagation =
            row.find("select.message_edit_topic_propagate").val() || "change_later";
        const send_notification_to_old_thread = row
            .find(".send_notification_to_old_thread")
            .is(":checked");
        const send_notification_to_new_thread = row
            .find(".send_notification_to_new_thread")
            .is(":checked");
        request.propagate_mode = selected_topic_propagation;
        request.send_notification_to_old_thread = send_notification_to_old_thread;
        request.send_notification_to_new_thread = send_notification_to_new_thread;
        notify_old_thread_default = send_notification_to_old_thread;
        notify_new_thread_default = send_notification_to_new_thread;
        changed = true;
    }

    if (topic_changed) {
        request.topic = new_topic;
    }
    if (stream_changed) {
        request.stream_id = new_stream_id;
    }
    if (new_content !== message.raw_content) {
        request.content = new_content;
        changed = true;
    }

    if (!changed) {
        // If they didn't change anything, just cancel it.
        end_message_row_edit(row);
        return;
    }

    if (
        changed &&
        !topic_changed &&
        !stream_changed &&
        !markdown.contains_backend_only_syntax(new_content)
    ) {
        // If the topic isn't changed, and the new message content
        // could have been locally echoed, than we can locally echo
        // the edit.
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

        row = message_lists.current.get_row(message_id);
        end_message_row_edit(row);
    }

    channel.patch({
        url: "/json/messages/" + message.id,
        data: request,
        success() {
            if (edit_locally_echoed) {
                delete message.local_edit_timestamp;
                currently_echoing_messages.delete(message_id);
            }
            hide_message_edit_spinner(row);
        },
        error(xhr) {
            if (msg_list === message_lists.current) {
                message_id = rows.id(row);

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

                    row = message_lists.current.get_row(message_id);
                    if (!is_editing(message_id)) {
                        // Return to the message editing open UI state with the edited content.
                        start_edit_maintaining_scroll(row, echo_data.raw_content);
                    }
                }

                hide_message_edit_spinner(row);
                const message = channel.xhr_error_message(
                    $t({defaultMessage: "Error saving edit"}),
                    xhr,
                );
                row.find(".edit_error").text(message).show();
            }
        },
    });
    // The message will automatically get replaced via message_list.update_message.
}

export function maybe_show_edit(row, id) {
    if (currently_editing_messages.has(id)) {
        message_lists.current.show_edit_message(row, currently_editing_messages.get(id));
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

    const msg_row = message_lists.current.get_row(msg.id);
    if (!msg_row) {
        // This should never happen, since we got the message above
        // from message_lists.current.
        blueslip.error("Could not find row for id " + msg.id);
        return;
    }

    message_lists.current.select_id(msg.id, {then_scroll: true, from_scroll: true});

    // Finally do the real work!
    compose_actions.cancel();
    start(msg_row, () => {
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
        html_heading: $t_html({defaultMessage: "Delete message"}),
        html_body,
        help_link: "/help/edit-or-delete-a-message#delete-a-message",
        on_click: do_delete_message,
        loading_spinner: true,
    });
}

export function delete_topic(stream_id, topic_name) {
    channel.post({
        url: "/json/streams/" + stream_id + "/delete_topic",
        data: {
            topic_name,
        },
    });
}

export function handle_narrow_deactivated() {
    for (const [idx, elem] of currently_editing_messages) {
        if (message_lists.current.get(idx) !== undefined) {
            const row = message_lists.current.get_row(idx);
            message_lists.current.show_edit_message(row, elem);
        }
    }
}

export function move_topic_containing_message_to_stream(
    message_id,
    new_stream_id,
    new_topic_name,
    send_notification_to_new_thread,
    send_notification_to_old_thread,
) {
    function reset_modal_ui() {
        currently_topic_editing_messages = currently_topic_editing_messages.filter(
            (id) => id !== message_id,
        );
        dialog_widget.hide_dialog_spinner();
        dialog_widget.close_modal();
    }
    if (currently_topic_editing_messages.includes(message_id)) {
        $("#topic_stream_edit_form_error .error-msg").text(
            $t({defaultMessage: "A Topic Move already in progress."}),
        );
        $("#topic_stream_edit_form_error").show();
        return;
    }
    currently_topic_editing_messages.push(message_id);

    const request = {
        stream_id: new_stream_id,
        propagate_mode: "change_all",
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
        },
        error(xhr) {
            reset_modal_ui();
            ui_report.error(
                $t_html({defaultMessage: "Error moving the topic"}),
                xhr,
                $("#home-error"),
                4000,
            );
        },
    });
}
