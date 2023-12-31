import $ from "jquery";

import * as fenced_code from "../shared/src/fenced_code";

import * as channel from "./channel";
import * as compose_actions from "./compose_actions";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as inbox_ui from "./inbox_ui";
import * as inbox_util from "./inbox_util";
import * as message_lists from "./message_lists";
import * as narrow_state from "./narrow_state";
import * as people from "./people";
import * as recent_view_ui from "./recent_view_ui";
import * as recent_view_util from "./recent_view_util";
import * as stream_data from "./stream_data";
import * as unread_ops from "./unread_ops";

export function respond_to_message(opts) {
    let message;
    let msg_type;
    if (recent_view_util.is_visible()) {
        message = recent_view_ui.get_focused_row_message();
        if (message === undefined) {
            // Open empty compose with nothing pre-filled since
            // user is not focused on any table row.
            compose_actions.start("stream", {trigger: "recent_view_nofocus"});
            return;
        }
    } else if (inbox_util.is_visible()) {
        const message_opts = inbox_ui.get_focused_row_message();
        if (message_opts.message === undefined) {
            // If the user is not focused on inbox header, msg_type
            // is not defined, so we open empty compose with nothing prefilled.
            compose_actions.start(message_opts.msg_type ?? "stream", {
                trigger: "inbox_nofocus",
                ...message_opts,
            });
            return;
        }
        message = message_opts.message;
    } else {
        message =
            message_lists.current.get(opts.message_id) || message_lists.current.selected_message();

        if (message === undefined) {
            // empty narrow implementation
            if (
                !narrow_state.narrowed_by_pm_reply() &&
                !narrow_state.narrowed_by_stream_reply() &&
                !narrow_state.narrowed_by_topic_reply()
            ) {
                compose_actions.start("stream", {trigger: "empty_narrow_compose"});
                return;
            }
            const current_filter = narrow_state.filter();
            const first_term = current_filter.operators()[0];
            const first_operator = first_term.operator;
            const first_operand = first_term.operand;

            if (first_operator === "stream" && !stream_data.is_subscribed_by_name(first_operand)) {
                compose_actions.start("stream", {trigger: "empty_narrow_compose"});
                return;
            }

            // Set msg_type to stream by default in the case of an empty
            // home view.
            msg_type = "stream";
            if (narrow_state.narrowed_by_pm_reply()) {
                msg_type = "private";
            }

            const new_opts = compose_actions.fill_in_opts_from_current_narrowed_view(
                msg_type,
                opts,
            );
            compose_actions.start(new_opts.message_type, new_opts);
            return;
        }

        if (message_lists.current.can_mark_messages_read()) {
            unread_ops.notify_server_message_read(message);
        }
    }

    // Important note: A reply_type of 'personal' is for the R hotkey
    // (replying to a message's sender with a direct message). All
    // other replies can just copy message.type.
    if (opts.reply_type === "personal" || message.type === "private") {
        msg_type = "private";
    } else {
        msg_type = message.type;
    }

    let stream_id = "";
    let topic = "";
    let pm_recipient = "";
    if (msg_type === "stream") {
        stream_id = message.stream_id;
        topic = message.topic;
    } else if (opts.reply_type === "personal") {
        // reply_to for direct messages is everyone involved, so for
        // personals replies we need to set the direct message
        // recipient to just the sender
        pm_recipient = people.get_by_user_id(message.sender_id).email;
    } else {
        pm_recipient = people.pm_reply_to(message);
    }

    compose_actions.start(msg_type, {
        stream_id,
        topic,
        private_message_recipient: pm_recipient,
        trigger: opts.trigger,
        is_reply: true,
    });
}

export function reply_with_mention(opts) {
    respond_to_message(opts);
    const message = message_lists.current.selected_message();
    const mention = people.get_mention_syntax(message.sender_full_name, message.sender_id);
    compose_ui.insert_syntax_and_focus(mention);
}

export function quote_and_reply(opts) {
    const message_id = opts.message_id || message_lists.current.selected_id();
    const message = message_lists.current.get(message_id);
    const quoting_placeholder = $t({defaultMessage: "[Quoting…]"});

    // If the last compose type textarea focused on is still in the DOM, we add
    // the quote in that textarea, else we default to the compose box.
    const $textarea = compose_state.get_last_focused_compose_type_input()?.isConnected
        ? $(compose_state.get_last_focused_compose_type_input())
        : $("textarea#compose-textarea");

    if ($textarea.attr("id") === "compose-textarea" && !compose_state.has_message_content()) {
        // The user has not started typing a message,
        // but is quoting into the compose box,
        // so we will re-open the compose box.
        // (If you did re-open the compose box, you
        // are prone to glitches where you select the
        // text, plus it's a complicated codepath that
        // can have other unintended consequences.)
        respond_to_message(opts);
    }

    compose_ui.insert_syntax_and_focus(quoting_placeholder, $textarea, "block");

    function replace_content(message) {
        // Final message looks like:
        //     @_**Iago|5** [said](link to message):
        //     ```quote
        //     message content
        //     ```
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

        compose_ui.replace_syntax(quoting_placeholder, content, $textarea);
        compose_ui.autosize_textarea($textarea);
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

export function initialize() {
    $("body").on("click", ".compose_reply_button", () => {
        respond_to_message({trigger: "reply button"});
    });
}
