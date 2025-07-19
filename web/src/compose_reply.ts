import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import * as fenced_code from "../shared/src/fenced_code.ts";

import * as channel from "./channel.ts";
import * as compose_actions from "./compose_actions.ts";
import * as compose_paste from "./compose_paste.ts";
import * as compose_recipient from "./compose_recipient.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_ui from "./compose_ui.ts";
import * as copy_messages from "./copy_messages.ts";
import * as hash_util from "./hash_util.ts";
import {$t} from "./i18n.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as inbox_util from "./inbox_util.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import * as narrow_state from "./narrow_state.ts";
import * as people from "./people.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as recent_view_util from "./recent_view_util.ts";
import * as stream_data from "./stream_data.ts";
import * as unread_ops from "./unread_ops.ts";

export let respond_to_message = (opts: {
    keep_composebox_empty?: boolean;
    message_id?: number;
    reply_type?: "personal";
    trigger?: string;
}): void => {
    let message;
    let msg_type: "private" | "stream";
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
            (opts.message_id === undefined
                ? undefined
                : message_lists.current.get(opts.message_id)) ??
            message_lists.current.selected_message();

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

            const narrow_stream_id = narrow_state.stream_id();
            if (narrow_stream_id && !stream_data.is_subscribed(narrow_stream_id)) {
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

    let stream_id: number | undefined;
    let topic = "";
    let private_message_recipient_ids: number[] | undefined;
    if (msg_type === "stream") {
        assert(message.type === "stream");
        stream_id = message.stream_id;
        topic = message.topic;
    } else if (opts.reply_type === "personal") {
        // reply_to for direct messages is everyone involved, so for
        // personals replies we need to set the direct message
        // recipient to just the sender
        private_message_recipient_ids = [message.sender_id];
    } else {
        private_message_recipient_ids = people.pm_with_user_ids(message);
    }

    compose_actions.start({
        message_type: msg_type,
        stream_id,
        topic,
        ...(private_message_recipient_ids !== undefined && {private_message_recipient_ids}),
        ...(opts.trigger !== undefined && {trigger: opts.trigger}),
        is_reply: true,
        keep_composebox_empty: opts.keep_composebox_empty,
    });
};

export function rewire_respond_to_message(value: typeof respond_to_message): void {
    respond_to_message = value;
}

export function reply_with_mention(opts: {
    keep_composebox_empty?: boolean;
    message_id?: number;
    reply_type?: "personal";
    trigger?: string;
}): void {
    assert(message_lists.current !== undefined);
    respond_to_message({
        ...opts,
        keep_composebox_empty: true,
    });
    const message = message_lists.current.selected_message();
    assert(message !== undefined);
    const mention = people.get_mention_syntax(message.sender_full_name, message.sender_id);
    compose_ui.insert_syntax_and_focus(mention);
}

export let selection_within_message_id = (
    selection = window.getSelection(),
): number | undefined => {
    // Returns the message_id if the selection is entirely within a message,
    // otherwise returns undefined.
    assert(selection !== null);
    if (!selection.toString()) {
        return undefined;
    }
    const {start_id, end_id} = copy_messages.analyze_selection(selection);
    if (start_id === end_id) {
        return start_id;
    }
    return undefined;
};

export function rewire_selection_within_message_id(
    value: typeof selection_within_message_id,
): void {
    selection_within_message_id = value;
}

function get_quote_target(opts: {message_id?: number; quote_content?: string | undefined}): {
    message_id: number;
    message: Message;
    quote_content: string | undefined;
} {
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
    assert(message !== undefined);
    // If the current selection, if any, is not entirely within the target message,
    // we quote that entire message.
    quote_content ??= message.raw_content;
    return {message_id, message, quote_content};
}

export function quote_message(opts: {
    message_id: number;
    quote_content?: string | undefined;
    keep_composebox_empty?: boolean;
    reply_type?: "personal";
    trigger?: string;
    forward_message?: boolean;
}): void {
    const {message_id, message, quote_content} = get_quote_target(opts);
    const quoting_placeholder = $t({defaultMessage: "[Quoting…]"});

    // If the last compose type textarea focused on is still in the DOM, we add
    // the quote in that textarea, else we default to the compose box.
    const last_focused_compose_type_input = compose_state.get_last_focused_compose_type_input();
    const $textarea =
        last_focused_compose_type_input?.isConnected && !opts.forward_message
            ? $(last_focused_compose_type_input)
            : $<HTMLTextAreaElement>("textarea#compose-textarea");

    if (opts.forward_message) {
        let topic = "";
        let stream_id: number | undefined;
        if (message.is_stream) {
            topic = message.topic;
            stream_id = message.stream_id;
        }
        compose_state.set_is_processing_forward_message(true);
        compose_actions.start({
            message_type: message.type,
            topic,
            keep_composebox_empty: opts.keep_composebox_empty,
            content: quoting_placeholder,
            stream_id,
            private_message_recipient_ids: [],
        });
        compose_recipient.toggle_compose_recipient_dropdown();
    } else {
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
    }

    function replace_content(message: Message, raw_content: string): void {
        // Final message looks like:
        //     @_**Iago|5** [said](link to message):
        //     ```quote
        //     message content
        //     ```
        // Keep syntax in sync with zerver/lib/reminders.py
        let content = $t(
            {defaultMessage: "{username} [said]({link_to_message}):"},
            {
                username: `@_**${message.sender_full_name}|${message.sender_id}**`,
                link_to_message: hash_util.by_conversation_and_time_url(message),
            },
        );
        content += "\n";
        const fence = fenced_code.get_unused_fence(raw_content);
        content += `${fence}quote\n${raw_content}\n${fence}`;

        compose_ui.replace_syntax(quoting_placeholder, content, $textarea, opts.forward_message);
        compose_ui.autosize_textarea($textarea);

        if (!opts.forward_message) {
            return;
        }
        const select_recipient_widget: tippy.ReferenceElement | undefined = $(
            "#compose_select_recipient_widget",
        )[0];
        if (select_recipient_widget !== undefined) {
            void select_recipient_widget._tippy?.popperInstance?.update();
        }
    }

    if (message && quote_content) {
        replace_content(message, quote_content);
        return;
    }

    void channel.get({
        url: "/json/messages/" + message_id,
        data: {allow_empty_topic_name: true},
        success(raw_data) {
            const data = z.object({raw_content: z.string()}).parse(raw_data);
            replace_content(message, data.raw_content);
        },
        error() {
            compose_ui.replace_syntax(
                quoting_placeholder,
                $t({defaultMessage: "[Error fetching message content.]"}),
                $textarea,
                opts.forward_message,
            );
            compose_ui.autosize_textarea($textarea);
        },
    });
}

function extract_range_html(range: Range, preserve_ancestors = false): string {
    // Returns the html of the range as a string, optionally preserving 2
    // levels of ancestors.
    const temp_div = document.createElement("div");
    if (!preserve_ancestors) {
        temp_div.append(range.cloneContents());
        return temp_div.innerHTML;
    }
    const container =
        range.commonAncestorContainer instanceof HTMLElement
            ? range.commonAncestorContainer
            : range.commonAncestorContainer.parentElement;
    assert(container !== null);
    assert(container.parentElement !== null);
    // The reason for preserving 2, not just 1, ancestors is code blocks; a
    // selection completely inside a code block has a code element as its
    // container element, inside a pre element, which is needed to identify
    // the selection as being part of a code block as opposed to inline code.
    const outer_container = container.parentElement.cloneNode();
    assert(outer_container instanceof HTMLElement); // https://github.com/microsoft/TypeScript/issues/283
    const container_clone = container.cloneNode();
    assert(container_clone instanceof HTMLElement); // https://github.com/microsoft/TypeScript/issues/283
    container_clone.append(range.cloneContents());
    outer_container.append(container_clone);
    temp_div.append(outer_container);
    return temp_div.innerHTML;
}

function get_range_intersection_with_element(range: Range, element: Node): Range {
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

export function get_message_selection(selection = window.getSelection()): string {
    assert(selection !== null);
    let selected_message_content_raw = "";

    // We iterate over all ranges in the selection, to find the ranges containing
    // the message_content div or its descendants, if any, then convert the html
    // in those ranges to markdown for quoting (firefox can have multiple ranges
    // in one selection), and also compute their combined bounding rect.
    for (let i = 0; i < selection.rangeCount; i = i + 1) {
        let range = selection.getRangeAt(i);
        const range_common_ancestor = range.commonAncestorContainer;
        let html_to_convert = "";
        let message_content;

        // If the common ancestor is the message_content div or its child, we can quote
        // this entire range at least.
        if (
            range_common_ancestor instanceof Element &&
            range_common_ancestor.classList.contains("message_content")
        ) {
            html_to_convert = extract_range_html(range);
        } else if ($(range_common_ancestor).parents(".message_content").length > 0) {
            // We want to preserve the structure of the html with 2 levels of
            // ancestors (to retain code block / list formatting) in such a range.
            html_to_convert = extract_range_html(range, true);
        } else if (
            // If the common ancestor contains the message_content div, we can quote the part
            // of this range that is in the message_content div, if any.
            range_common_ancestor instanceof Element &&
            (message_content = range_common_ancestor.querySelector(".message_content")) !== null &&
            range.cloneContents().querySelector(".message_content")
        ) {
            // Narrow down the range to the part that is in the message_content div.
            range = get_range_intersection_with_element(range, message_content);
            html_to_convert = extract_range_html(range);
        } else {
            continue;
        }
        const markdown_text = compose_paste.paste_handler_converter(html_to_convert);
        selected_message_content_raw = selected_message_content_raw + "\n" + markdown_text;
    }
    selected_message_content_raw = selected_message_content_raw.trim();
    return selected_message_content_raw;
}

export function initialize(): void {
    $("body").on("click", ".compose_reply_button", () => {
        respond_to_message({trigger: "reply button"});
    });
}
