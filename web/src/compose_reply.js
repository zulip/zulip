import $ from "jquery";
import assert from "minimalistic-assert";

import * as fenced_code from "../shared/src/fenced_code";

import * as channel from "./channel";
import * as compose_actions from "./compose_actions";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as copy_and_paste from "./copy_and_paste";
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
            compose_actions.start({
                message_type: "stream",
                trigger: "recent_view_nofocus",
                keep_composebox_empty: opts.keep_composebox_empty,
            });
            return;
        }
    } else if (inbox_util.is_visible()) {
        const message_opts = inbox_ui.get_focused_row_message();
        if (message_opts.message === undefined) {
            // If the user is not focused on inbox header, msg_type
            // is not defined, so we open empty compose with nothing prefilled.
            compose_actions.start({
                message_type: message_opts.msg_type ?? "stream",
                trigger: "inbox_nofocus",
                ...message_opts,
                keep_composebox_empty: opts.keep_composebox_empty,
            });
            return;
        }
        message = message_opts.message;
    } else {
        assert(message_lists.current !== undefined);

        message =
            message_lists.current.get(opts.message_id) || message_lists.current.selected_message();

        if (message === undefined) {
            // empty narrow implementation
            if (
                !narrow_state.narrowed_by_pm_reply() &&
                !narrow_state.narrowed_by_stream_reply() &&
                !narrow_state.narrowed_by_topic_reply()
            ) {
                compose_actions.start({
                    message_type: "stream",
                    trigger: "empty_narrow_compose",
                    keep_composebox_empty: opts.keep_composebox_empty,
                });
                return;
            }
            const current_filter = narrow_state.filter();
            const first_term = current_filter.terms()[0];
            const first_operator = first_term.operator;
            const first_operand = first_term.operand;

            if (first_operator === "stream" && !stream_data.is_subscribed_by_name(first_operand)) {
                compose_actions.start({
                    message_type: "stream",
                    trigger: "empty_narrow_compose",
                    keep_composebox_empty: opts.keep_composebox_empty,
                });
                return;
            }

            // Set msg_type to stream by default in the case of an empty
            // home view.
            msg_type = "stream";
            if (narrow_state.narrowed_by_pm_reply()) {
                msg_type = "private";
            }

            const new_opts = compose_actions.fill_in_opts_from_current_narrowed_view({
                ...opts,
                message_type: msg_type,
            });
            compose_actions.start({
                ...new_opts,
                keep_composebox_empty: opts.keep_composebox_empty,
            });
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

    compose_actions.start({
        message_type: msg_type,
        stream_id,
        topic,
        private_message_recipient: pm_recipient,
        trigger: opts.trigger,
        is_reply: true,
        keep_composebox_empty: opts.keep_composebox_empty,
    });
}

export function reply_with_mention(opts) {
    assert(message_lists.current !== undefined);
    respond_to_message({
        ...opts,
        keep_composebox_empty: true,
    });
    const message = message_lists.current.selected_message();
    const mention = people.get_mention_syntax(message.sender_full_name, message.sender_id);
    compose_ui.insert_syntax_and_focus(mention);
}

export function selection_within_message_id(selection = window.getSelection()) {
    // Returns the message_id if the selection is entirely within a message,
    // otherwise returns undefined.
    if (!selection.toString()) {
        return undefined;
    }
    const {start_id, end_id} = copy_and_paste.analyze_selection(selection);
    if (start_id === end_id) {
        return start_id;
    }
    return undefined;
}

function get_quote_target(opts) {
    assert(message_lists.current !== undefined);
    let message_id;
    let quote_content;
    if (opts.message_id) {
        // If triggered via the message actions popover
        message_id = opts.message_id;
        if (opts.quote_content) {
            quote_content = opts.quote_content;
        }
    } else {
        // If triggered via hotkey
        const selection_message_id = selection_within_message_id();
        if (selection_message_id) {
            // If the current selection is entirely within a message, we
            // quote that selection.
            message_id = selection_message_id;
            quote_content = get_message_selection();
        } else {
            // Else we pick the currently focused message.
            message_id = message_lists.current.selected_id();
        }
    }
    const message = message_lists.current.get(message_id);
    // If the current selection, if any, is not entirely within the target message,
    // we quote that entire message.
    quote_content ??= message.raw_content;
    return {message_id, message, quote_content};
}

export function quote_and_reply(opts) {
    const {message_id, message, quote_content} = get_quote_target(opts);
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
        respond_to_message({
            ...opts,
            keep_composebox_empty: true,
        });
    }

    compose_ui.insert_syntax_and_focus(quoting_placeholder, $textarea, "block");

    function replace_content(message, raw_content) {
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
        const fence = fenced_code.get_unused_fence(raw_content);
        content += `${fence}quote\n${raw_content}\n${fence}`;

        compose_ui.replace_syntax(quoting_placeholder, content, $textarea);
        compose_ui.autosize_textarea($textarea);
    }

    if (message && quote_content) {
        replace_content(message, quote_content);
        return;
    }

    channel.get({
        url: "/json/messages/" + message_id,
        success(data) {
            replace_content(message, data.raw_content);
        },
    });
}

function extract_range_html(range, preserve_ancestors = false) {
    // Returns the html of the range as a string, optionally preserving 2
    // levels of ancestors.
    const temp_div = document.createElement("div");
    if (!preserve_ancestors) {
        temp_div.append(range.cloneContents());
        return temp_div.innerHTML;
    }
    let container =
        range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
            ? range.commonAncestorContainer
            : range.commonAncestorContainer.parentElement;
    // The reason for preserving 2, not just 1, ancestors is code blocks; a
    // selection completely inside a code block has a code element as its
    // container element, inside a pre element, which is needed to identify
    // the selection as being part of a code block as opposed to inline code.
    const outer_container = container.parentElement.cloneNode();
    container = container.cloneNode();
    container.append(range.cloneContents());
    outer_container.append(container);
    temp_div.append(outer_container);
    return temp_div.innerHTML;
}

function get_range_intersection_with_element(range, element) {
    // Returns a new range that is a subset of range and is inside element.
    const intersection = document.createRange();
    intersection.selectNodeContents(element);

    if (intersection.compareBoundaryPoints(Range.START_TO_START, range) < 0) {
        intersection.setStart(range.startContainer, range.startOffset);
    }

    if (intersection.compareBoundaryPoints(Range.END_TO_END, range) > 0) {
        intersection.setEnd(range.endContainer, range.endOffset);
    }

    return intersection;
}

export function get_message_selection(selection = window.getSelection()) {
    let selected_message_content_raw = "";

    // We iterate over all ranges in the selection, to find the ranges containing
    // the message_content div or its descendants, if any, then convert the html
    // in those ranges to markdown for quoting (firefox can have multiple ranges
    // in one selection), and also compute their combined bounding rect.
    for (let i = 0; i < selection.rangeCount; i = i + 1) {
        let range = selection.getRangeAt(i);
        const range_common_ancestor = range.commonAncestorContainer;
        let html_to_convert = "";

        // If the common ancestor is the message_content div or its child, we can quote
        // this entire range at least.
        if (range_common_ancestor.classList?.contains("message_content")) {
            html_to_convert = extract_range_html(range);
        } else if ($(range_common_ancestor).parents(".message_content").length) {
            // We want to preserve the structure of the html with 2 levels of
            // ancestors (to retain code block / list formatting) in such a range.
            html_to_convert = extract_range_html(range, true);
        } else if (
            // If the common ancestor contains the message_content div, we can quote the part
            // of this range that is in the message_content div, if any.
            range_common_ancestor instanceof Element &&
            range_common_ancestor.querySelector(".message_content") &&
            range.cloneContents().querySelector(".message_content")
        ) {
            // Narrow down the range to the part that is in the message_content div.
            range = get_range_intersection_with_element(
                range,
                range_common_ancestor.querySelector(".message_content"),
            );
            html_to_convert = extract_range_html(range);
        } else {
            continue;
        }
        const markdown_text = copy_and_paste.paste_handler_converter(html_to_convert);
        selected_message_content_raw = selected_message_content_raw + "\n" + markdown_text;
    }
    selected_message_content_raw = selected_message_content_raw.trim();
    return selected_message_content_raw;
}

export function initialize() {
    $("body").on("click", ".compose_reply_button", () => {
        respond_to_message({trigger: "reply button"});
    });
}
