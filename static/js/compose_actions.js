import autosize from "autosize";
import $ from "jquery";
import _ from "lodash";

import * as fenced_code from "../shared/js/fenced_code";

import * as channel from "./channel";
import * as common from "./common";
import * as compose from "./compose";
import * as compose_fade from "./compose_fade";
import * as compose_pm_pill from "./compose_pm_pill";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as compose_validate from "./compose_validate";
import * as drafts from "./drafts";
import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as message_lists from "./message_lists";
import * as message_viewport from "./message_viewport";
import * as narrow_state from "./narrow_state";
import * as notifications from "./notifications";
import {page_params} from "./page_params";
import * as people from "./people";
import * as recent_topics_ui from "./recent_topics_ui";
import * as recent_topics_util from "./recent_topics_util";
import * as reload_state from "./reload_state";
import * as resize from "./resize";
import * as settings_config from "./settings_config";
import * as spectators from "./spectators";
import * as stream_bar from "./stream_bar";
import * as stream_data from "./stream_data";
import * as unread_ops from "./unread_ops";
import * as util from "./util";

export function blur_compose_inputs() {
    $(".message_comp").find("input, textarea, button, #private_message_recipient").trigger("blur");
}

function hide_box() {
    // This is the main hook for saving drafts when closing the compose box.
    drafts.update_draft();
    blur_compose_inputs();
    $("#stream-message").hide();
    $("#private-message").hide();
    $(".new_message_textarea").css("min-height", "");
    compose_fade.clear_compose();
    $(".message_comp").hide();
    $("#compose_controls").show();
}

function get_focus_area(msg_type, opts) {
    // Set focus to "Topic" when narrowed to a stream+topic and "New topic" button clicked.
    if (msg_type === "stream" && opts.stream && !opts.topic) {
        return "#stream_message_recipient_topic";
    } else if (
        (msg_type === "stream" && opts.stream) ||
        (msg_type === "private" && opts.private_message_recipient)
    ) {
        if (opts.trigger === "new topic button") {
            return "#stream_message_recipient_topic";
        }
        return "#compose-textarea";
    }

    if (msg_type === "stream") {
        return "#stream_message_recipient_stream";
    }
    return "#private_message_recipient";
}

// Export for testing
export const _get_focus_area = get_focus_area;

export function set_focus(msg_type, opts) {
    const focus_area = get_focus_area(msg_type, opts);
    if (window.getSelection().toString() === "" || opts.trigger !== "message click") {
        const $elt = $(focus_area);
        $elt.trigger("focus").trigger("select");
    }
}

function show_compose_box(msg_type, opts) {
    if (msg_type === "stream") {
        $("#private-message").hide();
        $("#stream-message").show();
        $("#stream_toggle").addClass("active");
        $("#private_message_toggle").removeClass("active");
    } else {
        $("#private-message").show();
        $("#stream-message").hide();
        $("#stream_toggle").removeClass("active");
        $("#private_message_toggle").addClass("active");
    }
    $("#compose-send-status").removeClass(common.status_classes).hide();
    $("#compose_banners").empty();
    $("#compose").css({visibility: "visible"});
    // When changing this, edit the 42px in _maybe_autoscroll
    $(".new_message_textarea").css("min-height", "3em");

    set_focus(msg_type, opts);
}

export function clear_textarea() {
    $("#compose").find("input[type=text], textarea").val("");
}

function clear_box() {
    compose.clear_invites();

    // TODO: Better encapsulate at-mention warnings.
    compose_validate.clear_topic_resolved_warning();
    compose_validate.clear_wildcard_warnings();
    compose.clear_private_stream_alert();
    compose_validate.set_user_acknowledged_wildcard_flag(undefined);

    compose.clear_preview_area();
    clear_textarea();
    compose_validate.check_overflow_text();
    $("#compose-textarea").removeData("draft-id");
    compose_ui.autosize_textarea($("#compose-textarea"));
    $("#compose-send-status").hide(0);
    $("#compose_banners").empty();
}

export function autosize_message_content() {
    if (!compose_ui.is_full_size()) {
        autosize($("#compose-textarea"), {
            callback() {
                maybe_scroll_up_selected_message();
            },
        });
    }
}

export function expand_compose_box() {
    $("#compose_close").show();
    $("#compose_controls").hide();
    $(".message_comp").show();
}

function composing_to_current_topic_narrow() {
    return (
        util.lower_same(compose_state.stream_name(), narrow_state.stream() || "") &&
        util.lower_same(compose_state.topic(), narrow_state.topic() || "")
    );
}

function composing_to_current_private_message_narrow() {
    const compose_state_recipient = compose_state.private_message_recipient();
    const narrow_state_recipient = narrow_state.pm_emails_string();
    return (
        compose_state_recipient &&
        narrow_state_recipient &&
        _.isEqual(
            compose_state_recipient
                .split(",")
                .map((s) => s.trim())
                .sort(),
            narrow_state_recipient
                .split(",")
                .map((s) => s.trim())
                .sort(),
        )
    );
}

export function update_narrow_to_recipient_visibility() {
    const message_type = compose_state.get_message_type();
    if (message_type === "stream") {
        const stream_name = compose_state.stream_name();
        const stream_exists = Boolean(stream_data.get_stream_id(stream_name));

        if (
            stream_exists &&
            !composing_to_current_topic_narrow() &&
            compose_state.has_full_recipient()
        ) {
            $(".narrow_to_compose_recipients").toggleClass("invisible", false);
            return;
        }
    } else if (message_type === "private") {
        const recipients = compose_state.private_message_recipient();
        if (
            recipients &&
            !composing_to_current_private_message_narrow() &&
            compose_state.has_full_recipient()
        ) {
            $(".narrow_to_compose_recipients").toggleClass("invisible", false);
            return;
        }
    }
    $(".narrow_to_compose_recipients").toggleClass("invisible", true);
}

export function complete_starting_tasks(msg_type, opts) {
    // This is sort of a kitchen sink function, and it's called only
    // by compose.start() for now.  Having this as a separate function
    // makes testing a bit easier.

    maybe_scroll_up_selected_message();
    compose_fade.start_compose(msg_type);
    stream_bar.decorate(opts.stream, $("#stream-message .message_header_stream"), true);
    $(document).trigger(new $.Event("compose_started.zulip", opts));
    update_placeholder_text();
    update_narrow_to_recipient_visibility();
}

export function maybe_scroll_up_selected_message() {
    // If the compose box is obscuring the currently selected message,
    // scroll up until the message is no longer occluded.
    if (message_lists.current.selected_id() === -1) {
        // If there's no selected message, there's no need to
        // scroll the compose box to avoid it.
        return;
    }
    const $selected_row = message_lists.current.selected_row();

    if ($selected_row.height() > message_viewport.height() - 100) {
        // For very tall messages whose height is close to the entire
        // height of the viewport, don't auto-scroll the viewport to
        // the end of the message (since that makes it feel annoying
        // to work with very tall messages).  See #8941 for details.
        return;
    }

    const cover = $selected_row.offset().top + $selected_row.height() - $("#compose").offset().top;
    if (cover > 0) {
        message_viewport.user_initiated_animate_scroll(cover + 20);
    }
}

function fill_in_opts_from_current_narrowed_view(msg_type, opts) {
    return {
        message_type: msg_type,
        stream: "",
        topic: "",
        private_message_recipient: "",
        trigger: "unknown",

        // Set default parameters based on the current narrowed view.
        ...narrow_state.set_compose_defaults(),

        // Set parameters based on provided opts, overwriting
        // those set based on current narrowed view, if necessary.
        ...opts,
    };
}

function same_recipient_as_before(msg_type, opts) {
    return (
        compose_state.get_message_type() === msg_type &&
        ((msg_type === "stream" &&
            opts.stream === compose_state.stream_name() &&
            opts.topic === compose_state.topic()) ||
            (msg_type === "private" &&
                opts.private_message_recipient === compose_state.private_message_recipient()))
    );
}

export function update_placeholder_text() {
    // Change compose placeholder text only if compose box is open.
    if (!$("#compose-textarea").is(":visible")) {
        return;
    }

    const opts = {
        message_type: compose_state.get_message_type(),
        stream: $("#stream_message_recipient_stream").val(),
        topic: $("#stream_message_recipient_topic").val(),
        private_message_recipient: compose_pm_pill.get_emails(),
    };

    $("#compose-textarea").attr("placeholder", compose_ui.compute_placeholder_text(opts));
}

export function start(msg_type, opts) {
    if (page_params.is_spectator) {
        spectators.login_to_access();
        return;
    }

    // We may be able to clear it to change the recipient, so save any
    // existing content as a draft.
    drafts.update_draft();

    autosize_message_content();

    if (reload_state.is_in_progress()) {
        return;
    }
    notifications.clear_compose_notifications();
    expand_compose_box();

    opts = fill_in_opts_from_current_narrowed_view(msg_type, opts);

    // If we are invoked by a compose hotkey (c or x) or new topic
    // button, do not assume that we know what the message's topic or
    // PM recipient should be.
    if (
        opts.trigger === "compose_hotkey" ||
        opts.trigger === "new topic button" ||
        opts.trigger === "new private message"
    ) {
        opts.topic = "";
        opts.private_message_recipient = "";
    }

    const subbed_streams = stream_data.subscribed_subs();
    if (
        subbed_streams.length === 1 &&
        (opts.trigger === "new topic button" ||
            (opts.trigger === "compose_hotkey" && msg_type === "stream"))
    ) {
        opts.stream = subbed_streams[0].name;
    }

    if (compose_state.composing() && !same_recipient_as_before(msg_type, opts)) {
        // Clear the compose box if the existing message is to a different recipient
        clear_box();
    }

    // We set the stream/topic/private_message_recipient
    // unconditionally here, which assumes the caller will have passed
    // '' or undefined for these values if they are not appropriate
    // for this message.
    //
    // TODO: Move these into a conditional on message_type, using an
    // explicit "clear" function for compose_state.
    compose_state.stream_name(opts.stream);
    compose_state.topic(opts.topic);

    // Set the recipients with a space after each comma, so it looks nice.
    compose_state.private_message_recipient(opts.private_message_recipient.replace(/,\s*/g, ", "));

    // If the user opens the compose box, types some text, and then clicks on a
    // different stream/topic, we want to keep the text in the compose box
    if (opts.content !== undefined) {
        compose_state.message_content(opts.content);
    }

    if (opts.draft_id) {
        $("#compose-textarea").data("draft-id", opts.draft_id);
    }

    compose_state.set_message_type(msg_type);

    // Show either stream/topic fields or "You and" field.
    show_compose_box(msg_type, opts);

    // Show a warning if topic is resolved
    compose_validate.warn_if_topic_resolved(true);

    // Reset the `max-height` property of `compose-textarea` so that the
    // compose-box do not cover the last messages of the current stream
    // while writing a long message.
    resize.reset_compose_message_max_height();

    complete_starting_tasks(msg_type, opts);
}

export function cancel() {
    // As user closes the compose box, restore the compose box max height
    if (compose_ui.is_full_size()) {
        compose_ui.make_compose_box_original_size();
    }

    $("#compose-textarea").height(40 + "px");

    if (page_params.narrow !== undefined) {
        // Never close the compose box in narrow embedded windows, but
        // at least clear the topic and unfade.
        compose_fade.clear_compose();
        if (page_params.narrow_topic !== undefined) {
            compose_state.topic(page_params.narrow_topic);
        } else {
            compose_state.topic("");
        }
        return;
    }
    hide_box();
    $("#compose_close").hide();
    clear_box();
    notifications.clear_compose_notifications();
    compose.abort_xhr();
    compose.abort_video_callbacks(undefined);
    compose_state.set_message_type(false);
    compose_pm_pill.clear();
    $(document).trigger("compose_canceled.zulip");
}

export function respond_to_message(opts) {
    let message;
    let msg_type;
    if (recent_topics_util.is_visible()) {
        message = recent_topics_ui.get_focused_row_message();
        if (message === undefined) {
            // Open empty compose with nothing pre-filled since
            // user is not focused on any table row.
            start("stream", {trigger: "recent_topics_nofocus"});
            return;
        }
    } else {
        message = message_lists.current.selected_message();

        if (message === undefined) {
            // empty narrow implementation
            if (
                !narrow_state.narrowed_by_pm_reply() &&
                !narrow_state.narrowed_by_stream_reply() &&
                !narrow_state.narrowed_by_topic_reply()
            ) {
                start("stream", {trigger: "empty_narrow_compose"});
                return;
            }
            const current_filter = narrow_state.filter();
            const first_term = current_filter.operators()[0];
            const first_operator = first_term.operator;
            const first_operand = first_term.operand;

            if (first_operator === "stream" && !stream_data.is_subscribed_by_name(first_operand)) {
                start("stream", {trigger: "empty_narrow_compose"});
                return;
            }

            // Set msg_type to stream by default in the case of an empty
            // home view.
            msg_type = "stream";
            if (narrow_state.narrowed_by_pm_reply()) {
                msg_type = "private";
            }

            const new_opts = fill_in_opts_from_current_narrowed_view(msg_type, opts);
            start(new_opts.message_type, new_opts);
            return;
        }

        if (message_lists.current.can_mark_messages_read()) {
            unread_ops.notify_server_message_read(message);
        }
    }

    // Important note: A reply_type of 'personal' is for the R hotkey
    // (replying to a message's sender with a private message).  All
    // other replies can just copy message.type.
    if (opts.reply_type === "personal" || message.type === "private") {
        msg_type = "private";
    } else {
        msg_type = message.type;
    }

    let stream = "";
    let topic = "";
    let pm_recipient = "";
    if (msg_type === "stream") {
        stream = message.stream;
        topic = message.topic;
    } else {
        pm_recipient = message.reply_to;
        if (opts.reply_type === "personal") {
            // reply_to for private messages is everyone involved, so for
            // personals replies we need to set the private message
            // recipient to just the sender
            pm_recipient = people.get_by_user_id(message.sender_id).email;
        } else {
            pm_recipient = people.pm_reply_to(message);
        }
    }

    start(msg_type, {
        stream,
        topic,
        private_message_recipient: pm_recipient,
        trigger: opts.trigger,
    });
}

export function reply_with_mention(opts) {
    respond_to_message(opts);
    const message = message_lists.current.selected_message();
    const mention = people.get_mention_syntax(message.sender_full_name, message.sender_id);
    compose_ui.insert_syntax_and_focus(mention);
}

export function on_topic_narrow() {
    if (!compose_state.composing()) {
        // If our compose box is closed, then just
        // leave it closed, assuming that the user is
        // catching up on their feed and not actively
        // composing.
        return;
    }

    if (compose_state.stream_name() !== narrow_state.stream()) {
        // If we changed streams, then we only leave the
        // compose box open if there is content.
        if (compose_state.has_message_content()) {
            compose_fade.update_message_list();
            return;
        }

        // Otherwise, avoid a mix.
        cancel();
        return;
    }

    if (compose_state.topic() && compose_state.has_message_content()) {
        // If the user has written something to a different topic,
        // they probably want that content, so leave compose open.
        //
        // This effectively uses the heuristic of whether there is
        // content in compose to determine whether the user had firmly
        // decided to compose to the old topic or is just looking to
        // reply to what they see.
        compose_fade.update_message_list();
        return;
    }

    // If we got this far, then the compose box has the correct stream
    // filled in, and either compose is empty or no topic was set, so
    // we should update the compose topic to match the new narrow.
    // See #3300 for context--a couple users specifically asked for
    // this convenience.
    compose_state.topic(narrow_state.topic());
    compose_validate.warn_if_topic_resolved(true);
    compose_fade.set_focused_recipient("stream");
    compose_fade.update_message_list();
    $("#compose-textarea").trigger("focus");
}

export function quote_and_reply(opts) {
    const $textarea = $("#compose-textarea");
    const message_id = message_lists.current.selected_id();
    const message = message_lists.current.selected_message();
    const quoting_placeholder = $t({defaultMessage: "[Quoting…]"});

    if (compose_state.has_message_content()) {
        // The user already started typing a message,
        // so we won't re-open the compose box.
        // (If you did re-open the compose box, you
        // are prone to glitches where you select the
        // text, plus it's a complicated codepath that
        // can have other unintended consequences.)

        if ($textarea.caret() !== 0) {
            // Insert a newline before quoted message if there is
            // already some content in the compose box and quoted
            // message is not being inserted at the beginning.
            $textarea.caret("\n");
        }
    } else {
        respond_to_message(opts);
    }

    compose_ui.insert_syntax_and_focus(quoting_placeholder + "\n", $textarea);

    function replace_content(message) {
        // Final message looks like:
        //     @_**Iago|5** [said](link to message):
        //     ```quote
        //     message content
        //     ```
        const prev_caret = $textarea.caret();
        let content = $t(
            {defaultMessage: "{username} [said]({link_to_message}):"},
            {
                username: `@_**${message.sender_full_name}|${message.sender_id}**`,
                link_to_message: `${hash_util.by_conversation_and_time_url(message)}`,
            },
        );
        content += "\n";
        const fence = fenced_code.get_unused_fence(message.raw_content);
        content += `${fence}quote\n${message.raw_content}\n${fence}`;

        const placeholder_offset = $textarea.val().indexOf(quoting_placeholder);
        compose_ui.replace_syntax(quoting_placeholder, content, $textarea);
        compose_ui.autosize_textarea($("#compose-textarea"));

        // When replacing content in a textarea, we need to move the
        // cursor to preserve its logical position if and only if the
        // content we just added was before the current cursor
        // position.  If we do, we need to move it by the increase in
        // the length of the content before the placeholder.
        if (prev_caret >= placeholder_offset + quoting_placeholder.length) {
            $textarea.caret(prev_caret + content.length - quoting_placeholder.length);
        } else if (prev_caret > placeholder_offset) {
            /* In the rare case that our cursor was inside the
             * placeholder, we treat that as though the cursor was
             * just after the placeholder. */
            $textarea.caret(placeholder_offset + content.length + 1);
        } else {
            $textarea.caret(prev_caret);
        }
    }

    if (message && message.raw_content) {
        replace_content(message);
        return;
    }

    channel.get({
        url: "/json/messages/" + message_id,
        success(data) {
            message.raw_content = data.raw_content;
            replace_content(message);
        },
    });
}

export function on_narrow(opts) {
    // We use force_close when jumping between PM narrows with the "p" key,
    // so that we don't have an open compose box that makes it difficult
    // to cycle quickly through unread messages.
    if (opts.force_close) {
        // This closes the compose box if it was already open, and it is
        // basically a noop otherwise.
        cancel();
        return;
    }

    if (opts.trigger === "narrow_to_compose_target") {
        compose_fade.update_message_list();
        return;
    }

    if (narrow_state.narrowed_by_topic_reply()) {
        on_topic_narrow();
        return;
    }

    if (compose_state.has_message_content()) {
        compose_fade.update_message_list();
        return;
    }

    if (narrow_state.narrowed_by_pm_reply()) {
        opts = fill_in_opts_from_current_narrowed_view("private", opts);
        // Do not open compose box if an invalid recipient is present.
        if (!opts.private_message_recipient) {
            if (compose_state.composing()) {
                cancel();
            }
            return;
        }
        // Do not open compose box if organization has disabled sending
        // private messages and recipient is not a bot.
        if (
            page_params.realm_private_message_policy ===
                settings_config.private_message_policy_values.disabled.code &&
            opts.private_message_recipient
        ) {
            const emails = opts.private_message_recipient.split(",");
            if (emails.length !== 1 || !people.get_by_email(emails[0]).is_bot) {
                // If we are navigating between private message conversations,
                // we want the compose box to close for non-bot users.
                if (compose_state.composing()) {
                    cancel();
                }
                return;
            }
        }
        start("private");
        return;
    }

    // If we got this far, then we assume the user is now in "reading"
    // mode, so we close the compose box to make it easier to use navigation
    // hotkeys and to provide more screen real estate for messages.
    cancel();
}
