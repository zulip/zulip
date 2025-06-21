import ClipboardJS from "clipboard";
import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import {z} from "zod";

import * as resolved_topic from "../shared/src/resolved_topic.ts";
import render_wildcard_mention_not_allowed_error from "../templates/compose_banner/wildcard_mention_not_allowed_error.hbs";
import render_delete_message_modal from "../templates/confirm_dialog/confirm_delete_message.hbs";
import render_confirm_edit_messages from "../templates/confirm_dialog/confirm_edit_messages.hbs";
import render_confirm_merge_topics_with_rename from "../templates/confirm_dialog/confirm_merge_topics_with_rename.hbs";
import render_confirm_moving_messages_modal from "../templates/confirm_dialog/confirm_moving_messages.hbs";
import render_intro_resolve_topic_modal from "../templates/confirm_dialog/intro_resolve_topic.hbs";
import render_message_edit_form from "../templates/message_edit_form.hbs";
import render_message_moved_widget_body from "../templates/message_moved_widget_body.hbs";
import render_resolve_topic_time_limit_error_modal from "../templates/resolve_topic_time_limit_error_modal.hbs";
import render_topic_edit_form from "../templates/topic_edit_form.hbs";

import {detached_uploads_api_response_schema} from "./attachments.ts";
import * as attachments_ui from "./attachments_ui.ts";
import * as blueslip from "./blueslip.ts";
import type {Typeahead} from "./bootstrap_typeahead.ts";
import * as channel from "./channel.ts";
import * as compose_actions from "./compose_actions.ts";
import * as compose_banner from "./compose_banner.ts";
import * as compose_call from "./compose_call.ts";
import * as compose_tooltips from "./compose_tooltips.ts";
import * as compose_ui from "./compose_ui.ts";
import * as compose_validate from "./compose_validate.ts";
import * as composebox_typeahead from "./composebox_typeahead.ts";
import * as condense from "./condense.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import {show_copied_confirmation} from "./copied_tooltip.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as echo from "./echo.ts";
import * as feedback_widget from "./feedback_widget.ts";
import * as giphy_state from "./giphy_state.ts";
import * as hash_util from "./hash_util.ts";
import {$t, $t_html} from "./i18n.ts";
import * as keydown_util from "./keydown_util.ts";
import * as loading from "./loading.ts";
import * as markdown from "./markdown.ts";
import * as message_lists from "./message_lists.ts";
import * as message_live_update from "./message_live_update.ts";
import * as message_store from "./message_store.ts";
import type {Message} from "./message_store.ts";
import * as message_viewport from "./message_viewport.ts";
import * as onboarding_steps from "./onboarding_steps.ts";
import * as people from "./people.ts";
import * as resize from "./resize.ts";
import * as rows from "./rows.ts";
import * as saved_snippets_ui from "./saved_snippets_ui.ts";
import * as settings_data from "./settings_data.ts";
import {current_user, realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as sub_store from "./sub_store.ts";
import * as timerender from "./timerender.ts";
import * as typing from "./typing.ts";
import * as ui_report from "./ui_report.ts";
import * as upload from "./upload.ts";
import {the} from "./util.ts";
import * as util from "./util.ts";

// Stores the message ID of the message being edited, and the
// textarea element which has the modified content.
// Storing textarea makes it easy to get the current content.
export const currently_editing_messages = new Map<number, JQuery<HTMLTextAreaElement>>();
let currently_deleting_messages: number[] = [];
let currently_topic_editing_message_ids: number[] = [];
const currently_echoing_messages = new Map<number, EchoedMessageData>();

type EchoedMessageData = {
    raw_content: string;
    orig_content: string;
    orig_raw_content: string;

    // Store flags that are about user interaction with the
    // message so that echo.edit_locally() can restore these
    // flags.
    starred: boolean;
    historical: boolean;
    collapsed: boolean;

    // These flags are rendering artifacts we'll want if the
    // edit fails and we need to revert to the original
    // rendering of the message.
    alerted: boolean;
    mentioned: boolean;
    mentioned_me_directly: boolean;
};

// These variables are designed to preserve the user's most recent
// choices when editing a group of messages, to make it convenient to
// move several topics in a row with the same settings.
export let notify_old_thread_default = false;

export let notify_new_thread_default = true;

export function is_topic_editable(message: Message, edit_limit_seconds_buffer = 0): boolean {
    if (!is_message_editable_ignoring_permissions(message)) {
        return false;
    }

    if (message.type !== "stream") {
        return false;
    }

    if (message.type === "stream" && stream_data.is_stream_archived(message.stream_id)) {
        return false;
    }

    const stream = stream_data.get_sub_by_id(message.stream_id);
    assert(stream !== undefined);
    if (!stream_data.user_can_move_messages_within_channel(stream)) {
        return false;
    }

    // Organization admins and moderators can edit message topics indefinitely,
    // irrespective of the topic editing deadline, if they are in the
    // can_move_messages_between_topics_group.
    if (current_user.is_moderator) {
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

function is_widget_message(message: Message): boolean {
    if (message.submessages && message.submessages.length > 0) {
        return true;
    }
    return false;
}

export function is_message_editable_ignoring_permissions(message: Message): boolean {
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

export function is_content_editable(message: Message, edit_limit_seconds_buffer = 0): boolean {
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

    if (message.type === "stream" && stream_data.is_stream_archived(message.stream_id)) {
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

export function is_message_sent_by_my_bot(message: Message): boolean {
    const user = people.get_by_user_id(message.sender_id);
    if (!user.is_bot || user.bot_owner_id === null) {
        // The message was not sent by a bot or the message was sent
        // by a cross-realm bot which does not have an owner.
        return false;
    }

    return people.is_my_user_id(user.bot_owner_id);
}

export function get_deletability(message: Message): boolean {
    if (message.type === "stream" && stream_data.is_stream_archived(message.stream_id)) {
        return false;
    }

    if (settings_data.user_can_delete_any_message()) {
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

export function is_stream_editable(message: Message, edit_limit_seconds_buffer = 0): boolean {
    if (!is_message_editable_ignoring_permissions(message)) {
        return false;
    }

    if (message.type !== "stream") {
        return false;
    }

    if (message.type === "stream" && stream_data.is_stream_archived(message.stream_id)) {
        return false;
    }

    const stream = stream_data.get_sub_by_id(message.stream_id);
    assert(stream !== undefined);
    if (!stream_data.user_can_move_messages_out_of_channel(stream)) {
        return false;
    }

    // Organization admins and moderators can edit stream indefinitely,
    // irrespective of the stream editing deadline, if they are in the
    // can_move_messages_between_channels_group.
    if (current_user.is_moderator) {
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

export function can_move_message(message: Message): boolean {
    return is_topic_editable(message) || is_stream_editable(message);
}

export function stream_and_topic_exist_in_edit_history(
    message: Message,
    stream_id: number,
    topic: string,
): boolean {
    /*  Checks to see if a stream_id and a topic match any historical
        stream_id and topic state in the message's edit history.

        Does not check the message's current stream_id and topic for
        a match to the stream_id and topic parameters.
     */
    if (message.type !== "stream") {
        return false;
    }
    const narrow_dict = {stream_id, topic};
    const message_dict = {stream_id: message.stream_id, topic: message.topic};

    if (!message.edit_history) {
        // If message edit history is disabled in the organization,
        // the client does not have the information locally to answer
        // this question correctly.
        return false;
    }

    for (const edit_history_event of message.edit_history) {
        if (!edit_history_event.prev_stream && edit_history_event.prev_topic === undefined) {
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

        if (edit_history_event.prev_topic !== undefined) {
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

export function hide_message_edit_spinner($row: JQuery): void {
    $row.find(".loader").hide();
    $row.find(".message_edit_save span").removeClass("showing-button-spinner");
    $row.find(".message_edit_save").removeClass("message-edit-button-disabled");
    $row.find(".message_edit_cancel").removeClass("message-edit-button-disabled");
}

export function show_message_edit_spinner($row: JQuery): void {
    // Always show the white spinner like we
    // do for send button in compose box.
    loading.show_button_spinner($row.find(".loader"), true);
    $row.find(".message_edit_save span").addClass("showing-button-spinner");
    $row.find(".message_edit_save").addClass("message-edit-button-disabled");
    $row.find(".message_edit_cancel").addClass("message-edit-button-disabled");
}

export function show_topic_edit_spinner($row: JQuery): void {
    const $spinner = $row.find(".topic_edit_spinner");
    loading.make_indicator($spinner);
    $spinner.css({height: ""});
    $(".topic_edit_save").hide();
    $(".topic_edit_cancel").hide();
    $(".topic_edit_spinner").show();
}

export function end_if_focused_on_inline_topic_edit(): void {
    const $focused_elem = $(".topic_edit").find(":focus");
    if ($focused_elem.length === 1) {
        $focused_elem.trigger("blur");
        const $recipient_row = $focused_elem.closest(".recipient_row");
        end_inline_topic_edit($recipient_row);
    }
}

export function end_if_focused_on_message_row_edit(): void {
    const $focused_elem = $(".message_edit").find(":focus");
    if ($focused_elem.length === 1) {
        $focused_elem.trigger("blur");
        const $row = $focused_elem.closest(".message_row");
        end_message_row_edit($row);
    }
}

export function update_inline_topic_edit_ui(): void {
    // This function is called when
    // "realm_move_messages_within_stream_limit_seconds" setting is
    // changed. This is a rare event, so it's OK to be lazy and just
    // do a full rerender, even though the only thing we need to
    // change is the inline topic edit icons in recipient bars.
    message_live_update.rerender_messages_view();
}

function handle_message_edit_enter(
    e: JQuery.KeyDownEvent,
    $message_edit_content: JQuery<HTMLTextAreaElement>,
): void {
    // Pressing Enter to save edits is coupled with Enter to send
    if (composebox_typeahead.should_enter_send(e)) {
        const $row = $message_edit_content.closest(".message_row");
        const $message_edit_save_button = $row.find(".message_edit_save");
        if ($message_edit_save_button.prop("disabled")) {
            // In cases when the save button is disabled
            // we need to disable save on pressing Enter
            // Prevent default to avoid new-line on pressing
            // Enter inside the textarea in this case
            e.preventDefault();
            compose_validate.validate_message_length($row);
            return;
        }
        void save_message_row_edit($row);
        e.stopPropagation();
        e.preventDefault();
    } else {
        composebox_typeahead.handle_enter($message_edit_content, e);
        return;
    }
}

function handle_message_row_edit_escape(e: JQuery.KeyDownEvent): void {
    end_if_focused_on_message_row_edit();
    e.stopPropagation();
    e.preventDefault();
}

function handle_inline_topic_edit_keydown(
    $form: JQuery,
    typeahead: Typeahead<string>,
    e: JQuery.KeyDownEvent,
): void {
    e.stopPropagation();
    const $form_inline_input = $form.find<HTMLInputElement>("input.inline_topic_edit");

    if ($form_inline_input.is(":focus") && keydown_util.is_enter_event(e)) {
        // Handle Enter key event in the inline topic edit UI.
        e.preventDefault();
        if (typeahead.shown) {
            // Accepting a suggestion from the typeahead should not trigger a save.
            return;
        }
        const $recipient_row = $form.closest(".recipient_row");
        try_save_inline_topic_edit($recipient_row);
    } else if (e.key === "Escape") {
        // Handle Escape key event in the inline topic edit UI.
        e.preventDefault();
        end_if_focused_on_inline_topic_edit();
    }
}

function update_inline_topic_edit_input_max_width(
    $inline_topic_edit_input: JQuery<HTMLInputElement>,
): void {
    // We use a hidden span element, which we update with the value
    // of the input field on every input change to calculate the
    // width of the topic value. This allows us to dynamically adjust
    // the max-width of the input field.
    const $topic_value_mirror = $inline_topic_edit_input
        .closest(".topic_edit_form")
        .find(".topic_value_mirror");
    const input_value = $inline_topic_edit_input.val()!;
    $topic_value_mirror.text(input_value);
    const topic_width = $topic_value_mirror.width();
    if (input_value.length > 0) {
        // When the user starts typing in the inline topic edit input field,
        // we dynamically adjust the max-width of the input field to match
        // width of the text in the input field + 1ch width for some cushion.
        $inline_topic_edit_input.css("max-width", `calc(${topic_width}px + 1ch)`);
    } else {
        // When the user deletes all the text in the inline topic edit input field,
        // we check if the input field has a placeholder and if it does, we set the
        // max-width of the input field to the length of the placeholder + 1ch
        // width for some cushion.
        const $placeholder = $inline_topic_edit_input
            .closest(".topic_edit_form")
            .find(".inline-topic-edit-placeholder");
        if ($placeholder.length > 0) {
            const placeholder_width = $placeholder.width();
            $inline_topic_edit_input.css("max-width", `calc(${placeholder_width}px + 1ch)`);
        } else {
            // Otherwise, we set the max-width to a reasonable 20ch width.
            $inline_topic_edit_input.css("max-width", "20ch");
        }
    }
}

function handle_inline_topic_edit_change(elem: HTMLInputElement, stream_id: number): void {
    const $inline_topic_edit_input = $(elem);

    update_inline_topic_edit_input_max_width($inline_topic_edit_input);

    if ($inline_topic_edit_input.hasClass("invalid-input")) {
        // If invalid-input class is present on the inline topic edit
        // input field, remove it as soon as the user starts typing
        // as that probably means the user is trying to fix the error.
        $inline_topic_edit_input.removeClass("invalid-input");
    }

    const $topic_edit_save_button = $inline_topic_edit_input
        .closest(".topic_edit_form")
        .find(".topic_edit_save");
    if (
        !stream_data.can_use_empty_topic(stream_id) &&
        util.is_topic_name_considered_empty(elem.value)
    ) {
        // When the topic is mandatory in a realm and the new topic is considered empty,
        // we disable the save button and show a tooltip with an error message.
        $topic_edit_save_button.prop("disabled", true);
        return;
    }
    // If we reach here, it means the save button was disabled previously
    // and the user has started typing in the input field, probably to fix
    // the error. So, we re-enable the save button.
    $topic_edit_save_button.prop("disabled", false);

    if (stream_data.can_use_empty_topic(stream_id)) {
        const $topic_not_mandatory_placeholder = $(".inline-topic-edit-placeholder");
        $topic_not_mandatory_placeholder.toggleClass(
            "inline-topic-edit-placeholder-visible",
            $inline_topic_edit_input.val() === "",
        );
    }
}

function timer_text(seconds_left: number): string {
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

function create_copy_to_clipboard_handler(
    $row: JQuery,
    source: HTMLElement,
    $message_edit_content: JQuery,
): void {
    const clipboard = new ClipboardJS(source, {
        target: () => the($message_edit_content),
    });

    clipboard.on("success", () => {
        // Hide the Tippy and source box after a 1000ms delay
        const tippy_timeout_in_ms = 1000;
        show_copied_confirmation(the($row.find(".copy_message")), {
            show_check_icon: true,
            timeout_in_ms: tippy_timeout_in_ms,
            on_hide_callback() {
                end_message_row_edit($row);
            },
        });
    });
}

function edit_message($row: JQuery, raw_content: string): void {
    // Open the message-edit UI for a given message.
    //
    // Notably, when switching views, this can be called for a row
    // that hasn't been added to the DOM yet so, keep all the selector
    // queries and events to operate on `$row` or `$form`.
    assert(message_lists.current !== undefined);
    const message = message_lists.current.get(rows.id($row));
    assert(message !== undefined);
    $row.find(".message_reactions").hide();
    condense.hide_message_length_toggle($row);

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

    if (max_file_upload_size > 0 && upload.feature_check()) {
        file_upload_enabled = true;
    }

    const is_editable = is_content_editable(message, seconds_left_buffer);

    const $form = $(
        render_message_edit_form({
            message_id: message.id,
            is_editable,
            content: raw_content,
            file_upload_enabled,
            giphy_enabled: giphy_state.is_giphy_enabled(),
            minutes_to_edit: Math.floor((realm.realm_message_content_edit_limit_seconds ?? 0) / 60),
            max_message_length: realm.max_message_length,
        }),
    );

    const $button_bar = $form.find(".compose-scrollable-buttons");

    const $message_edit_content = $form.find<HTMLTextAreaElement>("textarea.message_edit_content");
    assert($message_edit_content.length === 1);
    currently_editing_messages.set(message.id, $message_edit_content);
    message_lists.current.show_edit_message($row, $form);

    // Attach event handlers to `form` instead of `textarea` to allow
    // typeahead to call stopPropagation if it can handle the event
    // and prevent the form from submitting.
    $form.on("keydown", (e) => {
        if (e.target.classList.contains("message_edit_content") && keydown_util.is_enter_event(e)) {
            handle_message_edit_enter(e, $message_edit_content);
        }
    });

    $form.on("keydown", (e) => {
        if (e.key === "Escape") {
            handle_message_row_edit_escape(e);
        }
    });

    $form.on("input", () => {
        compose_validate.check_overflow_text($row);
    });

    $form
        .find(".message-edit-feature-group .video_link")
        .toggle(compose_call.compute_show_video_chat_button());
    $form
        .find(".message-edit-feature-group .audio_link")
        .toggle(compose_call.compute_show_audio_chat_button());

    $button_bar.on(
        "scroll",
        _.throttle((e: JQuery.ScrollEvent) => {
            compose_ui.handle_scrolling_formatting_buttons(e);
        }, 150),
    );

    const $message_edit_countdown_timer = $row.find(".message_edit_countdown_timer");
    const $copy_message = $row.find(".copy_message");

    if (!is_editable) {
        $message_edit_content.attr("readonly", "readonly");
        create_copy_to_clipboard_handler($row, the($copy_message), $message_edit_content);
    } else {
        $copy_message.remove();
        resize.watch_manual_resize_for_element(the($message_edit_content));
        composebox_typeahead.initialize_compose_typeahead($message_edit_content);
        compose_ui.handle_keyup(null, $message_edit_content);
        $message_edit_content.on("keydown", (event) => {
            compose_ui.handle_keydown(event, $message_edit_content);
        });
        $message_edit_content.on("keyup", (event) => {
            compose_ui.handle_keyup(event, $message_edit_content);
        });
    }

    // Add tooltip and timer
    const realm_message_content_edit_limit_seconds =
        realm.realm_message_content_edit_limit_seconds ?? 0;
    if (is_editable && realm_message_content_edit_limit_seconds > 0) {
        $row.find(".message-edit-timer").show();

        // Give them at least 10 seconds.
        // If you change this number also change edit_limit_buffer in
        // zerver.actions.message_edit.check_update_message
        const min_seconds_to_edit = 10;
        let seconds_left =
            realm_message_content_edit_limit_seconds + (message.timestamp - Date.now() / 1000);
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
                $message_edit_save_container.addClass("message-edit-time-limit-expired");
                $message_edit_save_container.addClass("disabled-message-edit-save");
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
        if (contents) {
            $message_edit_content.val(contents);
        }
        compose_validate.check_overflow_text($row);
    }
}

function start_edit_maintaining_scroll($row: JQuery, content: string): void {
    // This function makes the bottom of the edit form visible, so
    // call this for cases where it is important to show the bottom
    // like showing error messages or upload status.
    edit_message($row, content);
    const row_bottom = $row.get_offset_to_window().bottom;
    const composebox_top = $("#compose").get_offset_to_window().top;
    if (row_bottom > composebox_top) {
        message_viewport.scrollTop(message_viewport.scrollTop() + row_bottom - composebox_top);
    }
}

function start_edit_with_content(
    $row: JQuery,
    content: string,
    edit_box_open_callback?: () => void,
): void {
    start_edit_maintaining_scroll($row, content);
    if (edit_box_open_callback) {
        edit_box_open_callback();
    }
    const row_id = rows.id($row);
    upload.setup_upload(upload.edit_config(row_id));
    // Setup dropdown for saved snippets button in the current
    // message edit control buttons tray.
    saved_snippets_ui.setup_saved_snippets_dropdown_widget(
        `.saved-snippets-message-edit-widget[data-message-id="${CSS.escape(row_id.toString())}"]`,
    );
}

export function start($row: JQuery, edit_box_open_callback?: () => void): void {
    assert(message_lists.current !== undefined);
    const message = message_lists.current.get(rows.id($row));
    if (message === undefined) {
        blueslip.error("Couldn't find message ID for edit", {row_id: rows.id($row)});
        return;
    }

    if ($row.find(".message_edit_form form").length > 0) {
        return;
    }

    if (message.raw_content) {
        start_edit_with_content($row, message.raw_content, edit_box_open_callback);
        return;
    }

    const msg_list = message_lists.current;
    void channel.get({
        url: "/json/messages/" + message.id,
        data: {allow_empty_topic_name: true},
        success(data) {
            const {raw_content} = z.object({raw_content: z.string()}).parse(data);
            if (message_lists.current === msg_list) {
                message.raw_content = raw_content;
                start_edit_with_content($row, message.raw_content, edit_box_open_callback);
            }
        },
    });
}

function show_toggle_resolve_topic_spinner($row: JQuery): void {
    const $spinner = $row.find(".toggle_resolve_topic_spinner");
    loading.make_indicator($spinner);
    $spinner.css({width: "1em"});
    $row.find(".on_hover_topic_resolve, .on_hover_topic_unresolve").hide();
    $row.find(".toggle_resolve_topic_spinner").show();
}

function get_resolve_topic_time_limit_error_string(
    time_limit: number,
    time_limit_unit: string,
    topic_is_resolved: boolean,
): string {
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

function handle_resolve_topic_failure_due_to_time_limit(topic_is_resolved: boolean): void {
    const time_limit_for_resolving_topic = timerender.get_time_limit_setting_in_appropriate_unit(
        realm.realm_move_messages_within_stream_limit_seconds ?? 0,
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
        on_click() {
            /* Nothing extra needs to happen when the dialog is closed. */
        },
        single_footer_button: true,
        focus_submit_on_open: true,
    });
}

function show_intro_resolve_topic_modal(topic_name: string, cb: () => void): void {
    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Mark topic as resolved"}),
        html_body: render_intro_resolve_topic_modal({topic_name}),
        id: "intro_resolve_topic_modal",
        on_click: cb,
        html_submit_button: $t({defaultMessage: "Got it — Confirm"}),
        html_exit_button: $t({defaultMessage: "Got it — Cancel"}),
    });
}

export function toggle_resolve_topic(
    message_id: number,
    old_topic_name: string,
    report_errors_in_global_banner: boolean,
    $row?: JQuery,
): void {
    let new_topic_name;
    const topic_is_resolved = resolved_topic.is_resolved(old_topic_name);
    if (topic_is_resolved) {
        new_topic_name = resolved_topic.unresolve_name(old_topic_name);
    } else {
        new_topic_name = resolved_topic.resolve_name(old_topic_name);
    }

    if (
        !topic_is_resolved &&
        onboarding_steps.ONE_TIME_NOTICES_TO_DISPLAY.has("intro_resolve_topic")
    ) {
        show_intro_resolve_topic_modal(old_topic_name, () => {
            do_toggle_resolve_topic(
                message_id,
                new_topic_name,
                topic_is_resolved,
                report_errors_in_global_banner,
                $row,
            );
        });
        onboarding_steps.post_onboarding_step_as_read("intro_resolve_topic");
        return;
    }

    do_toggle_resolve_topic(
        message_id,
        new_topic_name,
        topic_is_resolved,
        report_errors_in_global_banner,
        $row,
    );
}

function do_toggle_resolve_topic(
    message_id: number,
    new_topic_name: string,
    topic_is_resolved: boolean,
    report_errors_in_global_banner: boolean,
    $row?: JQuery,
): void {
    if ($row) {
        show_toggle_resolve_topic_spinner($row);
    }

    const request = {
        propagate_mode: "change_all",
        topic: new_topic_name,
        send_notification_to_old_thread: false,
        send_notification_to_new_thread: true,
    };

    void channel.patch({
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
                const {code} = z.object({code: z.string()}).parse(xhr.responseJSON);
                if (code === "MOVE_MESSAGES_TIME_LIMIT_EXCEEDED") {
                    handle_resolve_topic_failure_due_to_time_limit(topic_is_resolved);
                    return;
                }

                if (report_errors_in_global_banner) {
                    const {msg} = z.object({msg: z.string()}).parse(xhr.responseJSON);
                    ui_report.generic_embed_error(msg, 3500);
                }
            }
        },
    });
}

export function start_inline_topic_edit($recipient_row: JQuery): void {
    assert(message_lists.current !== undefined);
    const msg_id = rows.id_for_recipient_row($recipient_row);
    const message = message_lists.current.get(msg_id);
    assert(message?.type === "stream");
    const $form = $(
        render_topic_edit_form({
            max_topic_length: realm.max_topic_length,
            is_mandatory_topics: !stream_data.can_use_empty_topic(message.stream_id),
            empty_string_topic_display_name: util.get_final_topic_display_name(""),
        }),
    );
    message_lists.current.show_edit_topic_on_recipient_row($recipient_row, $form);
    $(".topic_edit_spinner").hide();
    const topic = message.topic;
    const $inline_topic_edit_input = $form.find<HTMLInputElement>("input.inline_topic_edit");
    $inline_topic_edit_input.val(topic).trigger("select").trigger("focus");
    update_inline_topic_edit_input_max_width($inline_topic_edit_input);
    const stream_name = stream_data.get_stream_name_from_id(message.stream_id);
    const typeahead = composebox_typeahead.initialize_topic_edit_typeahead(
        $inline_topic_edit_input,
        stream_name,
        false,
    );

    $form.on("keydown", (event) => {
        handle_inline_topic_edit_keydown($form, typeahead, event);
    });

    $inline_topic_edit_input.on("input", function (this: HTMLInputElement) {
        handle_inline_topic_edit_change(this, message.stream_id);
    });

    if (stream_data.can_use_empty_topic(message.stream_id)) {
        const $topic_not_mandatory_placeholder = $(".inline-topic-edit-placeholder");

        if (topic === "") {
            $topic_not_mandatory_placeholder.addClass("inline-topic-edit-placeholder-visible");
        }

        $inline_topic_edit_input.on("blur", () => {
            if ($inline_topic_edit_input.val() === "") {
                $topic_not_mandatory_placeholder.removeClass(
                    "inline-topic-edit-placeholder-visible",
                );
                $inline_topic_edit_input.attr("placeholder", util.get_final_topic_display_name(""));
                $inline_topic_edit_input.addClass("empty-topic-display");
            }
        });

        $inline_topic_edit_input.on("focus", () => {
            if ($inline_topic_edit_input.val() === "") {
                $inline_topic_edit_input.attr("placeholder", "");
                $inline_topic_edit_input.removeClass("empty-topic-display");
                $topic_not_mandatory_placeholder.addClass("inline-topic-edit-placeholder-visible");
            }
        });
    }
}

export function end_inline_topic_edit($row: JQuery): void {
    assert(message_lists.current !== undefined);
    message_lists.current.hide_edit_topic_on_recipient_row($row);
}

export function end_message_row_edit($row: JQuery): void {
    assert(message_lists.current !== undefined);
    const row_id = rows.id($row);

    // Clean up the upload handler
    upload.deactivate_upload(upload.edit_config(row_id));

    // Check if the row is in preview mode, and clear the preview area if it is.
    if ($row.hasClass("preview_mode")) {
        clear_preview_area($row);
    }

    const message = message_lists.current.get(row_id);
    if (message !== undefined && currently_editing_messages.has(message.id)) {
        typing.stop_message_edit_notifications(message.id);
        currently_editing_messages.delete(message.id);
        message_lists.current.hide_edit_message($row);
        compose_call.abort_video_callbacks(message.id.toString());
    }
    if ($row.find(".could-be-condensed").length > 0) {
        if ($row.find(".condensed").length > 0) {
            condense.show_message_expander($row);
        } else {
            condense.show_message_condenser($row);
        }
    }
    $row.find(".message_reactions").show();

    // We have to blur out text fields, or else hotkeys.js
    // thinks we are still editing.
    $row.find(".message_edit").trigger("blur");
    // We should hide the editing typeahead if it is visible
    $row.find("input.message_edit_topic").trigger("blur");
}

export function end_message_edit(message_id: number): void {
    const $row = message_lists.current?.get_row(message_id);
    if ($row !== undefined && $row.length > 0) {
        end_message_row_edit($row);
    } else if (currently_editing_messages.has(message_id)) {
        // We should delete the message_id from currently_editing_messages
        // if it exists there but we cannot find the row.
        currently_editing_messages.delete(message_id);
    }
}

export function try_save_inline_topic_edit($row: JQuery): void {
    assert(message_lists.current !== undefined);
    const message_id = rows.id_for_recipient_row($row);
    const message = message_lists.current.get(message_id);
    assert(message?.type === "stream");
    const old_topic = message.topic;
    const $inline_topic_edit_input = $row.find<HTMLInputElement>("input.inline_topic_edit");
    const new_topic = $inline_topic_edit_input.val()?.trim();
    assert(new_topic !== undefined);
    const topic_changed = new_topic !== old_topic;

    if (!topic_changed) {
        // this means the inline_topic_edit was opened and submitted without
        // changing anything, therefore, we should just close the inline topic edit.
        end_inline_topic_edit($row);
        return;
    }

    if (
        !stream_data.can_use_empty_topic(message.stream_id) &&
        util.is_topic_name_considered_empty(new_topic)
    ) {
        // When the topic is mandatory in a realm and the new topic is considered
        // empty, we don't allow the user to save the topic. Instead, we show the
        // error visually via the invalid-input class and focus on the input field.
        $inline_topic_edit_input.addClass("invalid-input");
        $inline_topic_edit_input.trigger("focus");
        return;
    }

    const $message_header = $row.find(".message_header").expectOne();
    const stream_id = Number.parseInt($message_header.attr("data-stream-id")!, 10);
    const stream_topics = stream_topic_history.get_recent_topic_names(stream_id);
    if (stream_topics.includes(new_topic)) {
        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Merge with another topic?"}),
            html_body: render_confirm_merge_topics_with_rename({
                topic_display_name: util.get_final_topic_display_name(new_topic),
                is_empty_string_topic: new_topic === "",
            }),
            on_click() {
                do_save_inline_topic_edit($row, message, new_topic);
            },
        });
    } else {
        do_save_inline_topic_edit($row, message, new_topic);
    }
}

export function do_save_inline_topic_edit($row: JQuery, message: Message, new_topic: string): void {
    show_topic_edit_spinner($row);

    if (message.locally_echoed) {
        message = echo.edit_locally(message, {new_topic});
        assert(message_lists.current !== undefined);
        $row = message_lists.current.get_row(message.id);
        end_inline_topic_edit($row);
        return;
    }

    const request = {
        topic: new_topic,
        propagate_mode: "change_all",
        send_notification_to_old_thread: false,
        send_notification_to_new_thread: false,
    };

    void channel.patch({
        url: "/json/messages/" + message.id,
        data: request,
        success() {
            const $spinner = $row.find(".topic_edit_spinner");
            loading.destroy_indicator($spinner);
        },
        error(xhr) {
            const $spinner = $row.find(".topic_edit_spinner");
            if (xhr.responseJSON === undefined) {
                return;
            }
            const {code} = z.object({code: z.string()}).parse(xhr.responseJSON);
            if (code === "MOVE_MESSAGES_TIME_LIMIT_EXCEEDED") {
                const {first_message_id_allowed_to_move} = z
                    .object({first_message_id_allowed_to_move: z.number()})
                    .parse(xhr.responseJSON);
                const send_notification_to_old_thread = false;
                const send_notification_to_new_thread = false;
                // We are not changing stream in this UI.
                const new_stream_id = undefined;
                function handle_confirm(): void {
                    move_topic_containing_message_to_stream(
                        first_message_id_allowed_to_move,
                        new_stream_id,
                        new_topic,
                        send_notification_to_new_thread,
                        send_notification_to_old_thread,
                        "change_later",
                    );
                }
                const on_hide_callback = (): void => {
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
        },
    });
}

export async function save_message_row_edit($row: JQuery): Promise<void> {
    compose_tooltips.hide_compose_control_button_tooltips($row);

    assert(message_lists.current !== undefined);
    const $banner_container = compose_banner.get_compose_banner_container(
        $row.find(".message_edit_form textarea"),
    );
    let stream_id: number | undefined;
    const stream_id_data = rows.get_message_recipient_header($row).attr("data-stream-id");
    if (stream_id_data !== undefined) {
        stream_id = Number.parseInt(stream_id_data, 10);
    }
    const msg_list = message_lists.current;
    let message_id = rows.id($row);
    let message = message_lists.current.get(message_id);
    assert(message !== undefined);
    let changed = false;
    let edit_locally_echoed = false;

    let new_content;
    const old_content = message.raw_content;
    assert(old_content !== undefined);

    const $edit_content_input = $row.find<HTMLTextAreaElement>("textarea.message_edit_content");
    const can_edit_content = $edit_content_input.attr("readonly") !== "readonly";
    if (can_edit_content) {
        new_content = $edit_content_input.val();
        changed = old_content !== new_content;
    }

    const already_has_stream_wildcard_mention = message.stream_wildcard_mentioned;
    if (stream_id !== undefined && !already_has_stream_wildcard_mention) {
        const stream_wildcard_mention = util.find_stream_wildcard_mentions(new_content ?? "");
        const is_stream_message_mentions_valid = compose_validate.validate_stream_message_mentions({
            stream_id,
            $banner_container,
            stream_wildcard_mention,
            scheduling_message: false,
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

    const request = {
        content: new_content,
        prev_content_sha256: await util.sha256_hash(old_content),
    };

    if (!markdown.contains_backend_only_syntax(new_content ?? "")) {
        // If the new message content could have been locally echoed,
        // than we can locally echo the edit.
        currently_echoing_messages.set(message_id, {
            raw_content: new_content ?? "",
            orig_content: message.content,
            orig_raw_content: message.raw_content ?? "",
            starred: message.starred,
            historical: message.historical,
            collapsed: message.collapsed,
            alerted: message.alerted,
            mentioned: message.mentioned,
            mentioned_me_directly: message.mentioned,
        });
        edit_locally_echoed = true;

        // Settings these attributes causes a "SAVING" notice to
        // briefly appear where "EDITED" would normally appear until
        // the message is acknowledged by the server.
        message.local_edit_timestamp = Math.round(Date.now() / 1000);

        message = echo.edit_locally(message, currently_echoing_messages.get(message_id)!);

        $row = message_lists.current.get_row(message_id);
        end_message_row_edit($row);
    }

    assert(message !== undefined);
    void channel.patch({
        url: "/json/messages/" + message.id,
        data: request,
        success(res) {
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

            const {detached_uploads} = detached_uploads_api_response_schema.parse(res);
            if (detached_uploads.length > 0) {
                attachments_ui.suggest_delete_detached_attachments(detached_uploads);
            }
        },
        error(xhr) {
            if (msg_list === message_lists.current) {
                message_id = rows.id($row);

                if (edit_locally_echoed) {
                    let echoed_message = message_store.get(message_id);
                    assert(echoed_message !== undefined);
                    const echo_data = currently_echoing_messages.get(message_id);
                    assert(echo_data !== undefined);

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
                    if (!currently_editing_messages.has(message_id)) {
                        // Return to the message editing open UI state with the edited content.
                        start_edit_maintaining_scroll($row, echo_data.raw_content);
                    }
                }

                hide_message_edit_spinner($row);
                if (xhr.readyState !== 0) {
                    const $container = compose_banner.get_compose_banner_container(
                        $row.find("textarea"),
                    );

                    if (xhr.responseJSON !== undefined) {
                        const {code} = z.object({code: z.string()}).parse(xhr.responseJSON);
                        if (code === "TOPIC_WILDCARD_MENTION_NOT_ALLOWED") {
                            const new_row_html = render_wildcard_mention_not_allowed_error({
                                banner_type: compose_banner.ERROR,
                                classname: compose_banner.CLASSNAMES.wildcards_not_allowed,
                            });
                            compose_banner.append_compose_banner_to_banner_list(
                                $(new_row_html),
                                $container,
                            );
                            return;
                        } else if (code === "EXPECTATION_MISMATCH") {
                            const message = $t({
                                defaultMessage:
                                    "Error editing message: Message was edited by another client.",
                            });
                            compose_banner.show_error_message(
                                message,
                                compose_banner.CLASSNAMES.generic_compose_error,
                                $container,
                            );
                            return;
                        }
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

export function maybe_show_edit($row: JQuery, id: number): void {
    if (message_lists.current === undefined) {
        return;
    }

    if (currently_editing_messages.has(id)) {
        const $message_edit_content = currently_editing_messages.get(id);
        edit_message($row, $message_edit_content?.val() ?? "");
    }
}

function warn_user_about_unread_msgs(last_sent_msg_id: number, num_unread: number): void {
    confirm_dialog.launch({
        html_heading: $t({defaultMessage: "Edit your last message?"}),
        html_body: render_confirm_edit_messages({
            num_unread,
        }),
        on_click() {
            // Select the message we want to edit to mark messages between it and the
            // current selected id as read.
            message_lists.current?.select_id(last_sent_msg_id, {
                then_scroll: true,
            });
            edit_last_sent_message();
        },
    });
}

export function edit_last_sent_message(): void {
    if (message_lists.current === undefined) {
        return;
    }

    const last_sent_msg = message_lists.current.get_last_message_sent_by_me();

    if (!last_sent_msg) {
        return;
    }

    if (!last_sent_msg.id) {
        blueslip.error("Message has invalid id in edit_last_sent_message.");
        return;
    }

    if (!is_content_editable(last_sent_msg, 5)) {
        return;
    }

    const current_selected_msg = message_store.get(message_lists.current.selected_id());
    if (
        current_selected_msg &&
        current_selected_msg.id < last_sent_msg.id &&
        message_lists.current.can_mark_messages_read()
    ) {
        // If there are any unread messages between the selected message and the
        // message we want to edit, we don't edit the last sent message to avoid
        // marking messages as read unintentionally.
        let num_unread = 0;
        for (const msg of message_lists.current.all_messages()) {
            if (current_selected_msg.id < msg.id && msg.id < last_sent_msg.id && msg.unread) {
                num_unread += 1;
            }
        }
        if (num_unread > 0) {
            warn_user_about_unread_msgs(last_sent_msg.id, num_unread);
            return;
        }
    }

    message_lists.current.select_id(last_sent_msg.id, {then_scroll: true});

    const $msg_row = message_lists.current.get_row(last_sent_msg.id);
    if (!$msg_row) {
        // This should never happen, since we got the message above
        // from message_lists.current.
        blueslip.error("Could not find row for id", {msg_id: last_sent_msg.id});
        return;
    }

    // Finally do the real work!
    compose_actions.cancel();
    start($msg_row, () => {
        $(".message_edit_content").trigger("focus");
    });
}

export function delete_message(msg_id: number): void {
    const html_body = render_delete_message_modal();

    function do_delete_message(): void {
        currently_deleting_messages.push(msg_id);
        void channel.del({
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

export function delete_topic(stream_id: number, topic_name: string, failures = 0): void {
    void channel.post({
        url: "/json/streams/" + stream_id + "/delete_topic",
        data: {
            topic_name,
        },
        success(data) {
            const {complete} = z.object({complete: z.boolean()}).parse(data);
            if (!complete) {
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

export function restore_edit_state_after_message_view_change(): void {
    assert(message_lists.current !== undefined);
    for (const [idx, $content] of currently_editing_messages) {
        if (message_lists.current.get(idx) !== undefined) {
            const $row = message_lists.current.get_row(idx);
            edit_message($row, $content.val() ?? "");
        }
    }
}

function handle_message_move_failure_due_to_time_limit(
    xhr: JQuery.jqXHR,
    handle_confirm: (e: JQuery.ClickEvent) => void,
    on_hide_callback?: () => void,
): void {
    const {total_messages_allowed_to_move, total_messages_in_topic} = z
        .object({
            total_messages_allowed_to_move: z.number(),
            total_messages_in_topic: z.number(),
        })
        .parse(xhr.responseJSON);
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
            messages_not_allowed_to_move: total_messages_in_topic - total_messages_allowed_to_move,
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
        ...(on_hide_callback !== undefined && {on_hide: on_hide_callback}),
    });
}

type ToastParams = {
    new_stream_id: number;
    new_topic_name: string;
};

function show_message_moved_toast(toast_params: ToastParams): void {
    const new_stream_name = sub_store.maybe_get_stream_name(toast_params.new_stream_id);
    const new_topic_display_name = util.get_final_topic_display_name(toast_params.new_topic_name);
    const is_empty_string_topic = toast_params.new_topic_name === "";
    const new_location_url = hash_util.by_stream_topic_url(
        toast_params.new_stream_id,
        toast_params.new_topic_name,
    );
    feedback_widget.show({
        populate($container) {
            const widget_body_html = render_message_moved_widget_body({
                new_stream_name,
                new_topic_display_name,
                new_location_url,
                is_empty_string_topic,
            });
            $container.html(widget_body_html);
        },
        title_text: $t({defaultMessage: "Message moved"}),
    });
}

export function move_topic_containing_message_to_stream(
    message_id: number,
    new_stream_id: number | undefined,
    new_topic_name: string | undefined,
    send_notification_to_new_thread: boolean,
    send_notification_to_old_thread: boolean,
    propagate_mode: string,
    toast_params: ToastParams | undefined = undefined,
): void {
    function reset_modal_ui(): void {
        currently_topic_editing_message_ids = currently_topic_editing_message_ids.filter(
            (id) => id !== message_id,
        );
        dialog_widget.hide_dialog_spinner();
    }
    if (currently_topic_editing_message_ids.includes(message_id)) {
        ui_report.client_error(
            $t_html({defaultMessage: "A Topic Move already in progress."}),
            $("#move_topic_modal #dialog_error"),
        );
        return;
    }
    currently_topic_editing_message_ids.push(message_id);

    const request = {
        stream_id: new_stream_id,
        propagate_mode,
        topic: new_topic_name,
        send_notification_to_old_thread,
        send_notification_to_new_thread,
    };
    notify_old_thread_default = send_notification_to_old_thread;
    notify_new_thread_default = send_notification_to_new_thread;
    void channel.patch({
        url: "/json/messages/" + message_id,
        data: request,
        success(): void {
            // The main UI will update via receiving the event
            // from server_events.js.
            reset_modal_ui();
            dialog_widget.close();
            if (toast_params) {
                show_message_moved_toast(toast_params);
            }
        },
        error(xhr): void {
            reset_modal_ui();
            if (xhr.responseJSON !== undefined) {
                const {code} = z.object({code: z.string()}).parse(xhr.responseJSON);
                if (code === "MOVE_MESSAGES_TIME_LIMIT_EXCEEDED") {
                    const {first_message_id_allowed_to_move} = z
                        .object({first_message_id_allowed_to_move: z.number()})
                        .parse(xhr.responseJSON);
                    function handle_confirm(): void {
                        move_topic_containing_message_to_stream(
                            first_message_id_allowed_to_move,
                            new_stream_id,
                            new_topic_name,
                            send_notification_to_new_thread,
                            send_notification_to_old_thread,
                            "change_later",
                        );
                    }

                    const partial_move_confirmation_modal_callback = (): void => {
                        handle_message_move_failure_due_to_time_limit(xhr, handle_confirm);
                    };
                    dialog_widget.close(partial_move_confirmation_modal_callback);
                    return;
                }
            }
            ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
        },
    });
}

export function with_first_message_id(
    stream_id: number,
    topic_name: string,
    success_cb: (message_id: number | undefined) => void,
    error_cb?: (xhr: JQuery.jqXHR) => void,
): void {
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
        allow_empty_topic_name: true,
    };

    void channel.get({
        url: "/json/messages",
        data,
        success(data) {
            const {messages} = z
                .object({messages: z.array(z.object({id: z.number()}))})
                .parse(data);
            const message_id = messages[0]?.id;
            success_cb(message_id);
        },
        error:
            error_cb ??
            (() => {
                /* By default do nothing */
            }),
    });
}

export function is_message_oldest_or_newest(
    stream_id: number,
    topic_name: string,
    message_id: number,
    success_callback: (is_oldest: boolean, is_newest: boolean) => void,
    error_callback?: (xhr: JQuery.jqXHR) => void,
): void {
    const data = {
        anchor: message_id,
        num_before: 1,
        num_after: 1,
        narrow: JSON.stringify([
            {operator: "channel", operand: stream_id},
            {operator: "topic", operand: topic_name},
        ]),
        allow_empty_topic_name: true,
    };

    void channel.get({
        url: "/json/messages",
        data,
        success(data) {
            const {messages} = z
                .object({messages: z.array(z.object({id: z.number()}))})
                .parse(data);
            let is_oldest = true;
            let is_newest = true;
            for (const message of messages) {
                if (message.id < message_id) {
                    is_oldest = false;
                } else if (message.id > message_id) {
                    is_newest = false;
                }
            }
            success_callback(is_oldest, is_newest);
        },
        error:
            error_callback ??
            (() => {
                /* By default do nothing */
            }),
    });
}

export function show_preview_area($element: JQuery): void {
    const $row = rows.get_closest_row($element);

    // Disable unneeded compose_control_buttons as we don't
    // need them in preview mode.
    $row.addClass("preview_mode");
    $row.find(".preview_mode_disabled .compose_control_button").attr("tabindex", -1);

    $row.find(".markdown_preview").hide();
    $row.find(".undo_markdown_preview").show();

    render_preview_area($row);
}

export function render_preview_area($row: JQuery): void {
    const $msg_edit_content = $row.find<HTMLTextAreaElement>("textarea.message_edit_content");
    const content = $msg_edit_content.val();
    assert(content !== undefined);
    const $preview_message_area = $row.find(".preview_message_area");
    compose_ui.render_and_show_preview(
        $row,
        $row.find(".markdown_preview_spinner"),
        $row.find(".preview_content"),
        content,
    );
    const edit_height = $msg_edit_content.height();
    $preview_message_area.css({"min-height": edit_height + "px"});
    $preview_message_area.show();
}

export function clear_preview_area($element: JQuery): void {
    const $row = rows.get_closest_row($element);

    // While in preview mode we disable unneeded compose_control_buttons,
    // so here we are re-enabling those compose_control_buttons
    $row.removeClass("preview_mode");
    $row.find(".preview_mode_disabled .compose_control_button").attr("tabindex", 0);

    $row.find(".undo_markdown_preview").hide();
    $row.find(".preview_message_area").hide();
    $row.find(".preview_content").empty();
    $row.find(".markdown_preview").show();
}
