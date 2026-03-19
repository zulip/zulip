import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import * as compose_actions from "./compose_actions.ts";
import * as compose_paste from "./compose_paste.ts";
import * as compose_recipient from "./compose_recipient.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_ui from "./compose_ui.ts";
import * as copy_messages from "./copy_messages.ts";
import * as fenced_code from "./fenced_code.ts";
import * as hash_util from "./hash_util.ts";
import {$t} from "./i18n.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as inbox_util from "./inbox_util.ts";
import * as internal_url from "./internal_url.ts";
import * as message_fetch_raw_content from "./message_fetch_raw_content.ts";
import * as message_lists from "./message_lists.ts";
import * as message_store from "./message_store.ts";
import {type Message} from "./message_store.ts";
import * as narrow_state from "./narrow_state.ts";
import * as people from "./people.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as recent_view_util from "./recent_view_util.ts";
import * as rows from "./rows.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import * as topic_link_util from "./topic_link_util.ts";
import * as unread_ops from "./unread_ops.ts";

type QuoteMessageOpts = {
    message_id?: number;
    quote_content?: string | undefined;
    keep_composebox_empty?: boolean;
    reply_type?: "personal";
    trigger?: string;
    forward_message?: boolean;
    highlighted_message_ids?: number[];
};

type ReplaceContentOpts = {
    message: Message;
    raw_content: string;
    forward_message: boolean | undefined;
    previous_message?: Message | undefined;
    is_first_message_from_quote_chain?: boolean;
};

const quoting_placeholder = $t({defaultMessage: "[Quoting…]"});

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

    // On message click, if compose box is already open,
    // never scroll the selected message.
    const skip_scrolling_selected_message =
        opts.trigger === "message click" && compose_state.composing();
    compose_actions.start({
        message_type: msg_type,
        stream_id,
        topic,
        ...(private_message_recipient_ids !== undefined && {private_message_recipient_ids}),
        ...(opts.trigger !== undefined && {trigger: opts.trigger}),
        is_reply: true,
        keep_composebox_empty: opts.keep_composebox_empty,
        skip_scrolling_selected_message,
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

export let get_highlighted_message_ids = (
    selection = window.getSelection(),
): number[] | undefined => {
    // Returns the message_ids for a selection.
    assert(selection !== null);
    if (!selection.toString()) {
        return undefined;
    }
    const {start_id, end_id} = copy_messages.analyze_selection(selection);
    // Unlikely to ever occur.
    if (start_id === undefined && end_id === undefined) {
        return undefined;
    }
    // This is a weird case and we should fallback to quoting
    // the selected message.
    if (start_id === undefined || end_id === undefined) {
        return undefined;
    }
    return rows.get_ids_in_range(start_id, end_id);
};

export function rewire_get_highlighted_message_ids(
    value: typeof get_highlighted_message_ids,
): void {
    get_highlighted_message_ids = value;
}

function get_quote_target_for_single_message(opts: {
    message_id?: number;
    quote_content?: string | undefined;
    highlighted_message_ids?: number[];
}): {
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
        if (opts.highlighted_message_ids) {
            assert(opts.highlighted_message_ids.length === 1);
            const highlighted_message_id = opts.highlighted_message_ids[0];
            assert(highlighted_message_id !== undefined);
            // If the current content selection is entirely within a message,
            // we quote that selection.
            message_id = highlighted_message_id;
            quote_content = get_message_selection();
        } else {
            // Else we pick the currently focused message.
            message_id = message_lists.current.selected_id();
        }
    }
    const message = message_lists.current.get(message_id);
    assert(message !== undefined);
    // If we don't have quote_content yet (either because there was no valid
    // in-message selection, or because the caller only supplied a message_id),
    // fall back to quoting the entire message using its cached
    // raw_content (Zulip-flavored markdown), if it is available.
    // In case of selections that aren't contained within a single message, we
    // quote the raw_content of the currently focused message.
    quote_content ??= message.raw_content;
    return {message_id, message, quote_content};
}

function get_textarea_to_quote(forward_message?: boolean): JQuery<HTMLTextAreaElement> {
    // If the last compose type textarea focused on is still in the DOM, we add
    // the quote in that textarea, else we default to the compose box.
    const last_focused_compose_type_input = compose_state.get_last_focused_compose_type_input();
    const $textarea =
        last_focused_compose_type_input?.isConnected && forward_message
            ? $(last_focused_compose_type_input)
            : $<HTMLTextAreaElement>("textarea#compose-textarea");
    return $textarea;
}

function setup_compose_to_forward_single_message(message: Message, opts: QuoteMessageOpts): void {
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
}

function setup_compose_to_quote_single_message(message_id: number, opts: QuoteMessageOpts): void {
    const $textarea = get_textarea_to_quote(opts.forward_message);
    if ($textarea.attr("id") === "compose-textarea" && !compose_state.has_message_content()) {
        // Whether or not the compose box is open, it's empty, so
        // we start a new message replying to the quoted message.
        respond_to_message({
            ...opts,
            // Critically, we pass the message_id of the message we
            // just quoted, to avoid incorrectly replying to an
            // unrelated selected message in interleaved views.
            message_id,
            keep_composebox_empty: true,
        });
    }

    compose_ui.insert_syntax_and_focus(quoting_placeholder, $textarea, "block");
}

function setup_compose_for_unknown_recipient(opts: QuoteMessageOpts): void {
    compose_actions.start({
        message_type: "stream",
        keep_composebox_empty: opts.keep_composebox_empty,
        content: quoting_placeholder,
    });
}

function setup_compose_for_same_channel_messages(message: Message, opts: QuoteMessageOpts): void {
    assert(message.type === "stream");
    compose_actions.start({
        content: quoting_placeholder,
        message_type: "stream",
        topic: message.topic,
        keep_composebox_empty: opts.keep_composebox_empty,
        stream_id: message.stream_id,
    });
    $("#stream_message_recipient_topic").trigger("focus");
}

function setup_compose_for_quoting_dm_conversations(opts: QuoteMessageOpts): void {
    compose_actions.start({
        content: quoting_placeholder,
        message_type: "private",
        keep_composebox_empty: opts.keep_composebox_empty,
    });
    $("#private_message_recipient").trigger("focus");
}

function generate_sender_mention(sent_message: Message): string {
    return `@_**${sent_message.sender_full_name}|${sent_message.sender_id}**`;
}

function generate_sender_only_quote_context(message: Message): string {
    const sender_mention = generate_sender_mention(message);
    // Final message looks like:
    //     @_**Iago|5** [said](link to message):
    //     ```quote
    //     message content
    //     ```
    return $t(
        {defaultMessage: "{username} [said]({link_to_message}):"},
        {
            username: sender_mention,
            link_to_message: hash_util.by_conversation_and_time_url(message),
        },
    );
}

function generate_channel_message_quote_context(message: Message): string {
    assert(message.type === "stream");
    const sender_mention = generate_sender_mention(message);
    const link = internal_url.by_stream_topic_url(
        message.stream_id,
        message.topic,
        sub_store.maybe_get_stream_name,
        message.id,
    );
    const channel_name = sub_store.maybe_get_stream_name(message.stream_id)!;
    const topic_link_syntax = topic_link_util.get_stream_topic_link_syntax(
        channel_name,
        message.topic,
        true,
    );
    // Final message looks like:
    //     @_**Iago|5** [said](link to message) in [#channel > topic](link to topic):
    //     ```quote
    //     message content
    //     ```
    // Keep syntax in sync with channel message reminder format in zerver/lib/reminders.py
    return $t(
        {
            defaultMessage: "{username} [said]({link_to_message}) in {topic_link_syntax}:",
        },
        {
            username: sender_mention,
            link_to_message: hash_util.by_conversation_and_time_url(message),
            topic_link_syntax: topic_link_util.as_markdown_link_syntax(topic_link_syntax, link),
        },
    );
}

function generate_private_message_quote_context(message: Message): string {
    assert(message.type === "private");
    const sender_mention = generate_sender_mention(message);

    const dm_user_ids = people.all_user_ids_in_pm(message)!;
    const recipient_user_ids =
        dm_user_ids.length > 1
            ? dm_user_ids.filter((id) => id !== message.sender_id)
            : [message.sender_id];
    const recipient_users = recipient_user_ids.map((recipient_id) =>
        people.get_by_user_id(recipient_id),
    );
    // Final message looks like:
    //     @_**Iago|5** [said](link to message) to {direct message recipient mentions}:
    //     ```quote
    //     message content
    //     ```
    // Keep syntax in sync with direct message reminder format in zerver/lib/reminders.py
    return $t(
        {
            defaultMessage: "{username} [said]({link_to_message}) to {list_of_recipient_mentions}:",
        },
        {
            username: sender_mention,
            link_to_message: hash_util.by_conversation_and_time_url(message),
            list_of_recipient_mentions: people.get_user_mentions_for_display(recipient_users, true),
        },
    );
}

type QuoteContext = "INCLUDE_SENDER" | "INCLUDE_SENDER_AND_RECIPIENT" | "INCLUDE_NOTHING";

// Returns what context the line before the quote block having the quoted message content
// should contain.
export function get_quote_context_for_message(info: {
    forward_message: boolean | undefined;
    current_message: Message;
    previous_message: Message | undefined;
    is_first_message_from_quote_chain: boolean | undefined;
}): QuoteContext {
    const {current_message, previous_message, forward_message, is_first_message_from_quote_chain} =
        info;
    if (is_first_message_from_quote_chain) {
        return "INCLUDE_SENDER_AND_RECIPIENT";
    }
    if (previous_message) {
        if (all_messages_have_same_recipient([current_message, previous_message])) {
            // We don't include the sender or the recipient details
            // for a message that has the same (sender, recipient) pair
            // as the previous message.
            if (current_message.sender_id === previous_message.sender_id) {
                return "INCLUDE_NOTHING";
            }
            // We include the sender context in case only the sender
            // differs compared to the previous message.
            return "INCLUDE_SENDER";
        }
        return "INCLUDE_SENDER_AND_RECIPIENT";
    }

    // This message is quoted individually and not is part
    // of some collection of quoted messages
    if (!forward_message) {
        return "INCLUDE_SENDER";
    }
    return "INCLUDE_SENDER_AND_RECIPIENT";
}

function generate_replace_content(info: ReplaceContentOpts): string {
    const {
        message,
        raw_content,
        forward_message,
        previous_message,
        is_first_message_from_quote_chain,
    } = info;
    const required_quote_context = get_quote_context_for_message({
        current_message: message,
        forward_message,
        previous_message,
        is_first_message_from_quote_chain,
    });

    let content;

    switch (required_quote_context) {
        case "INCLUDE_SENDER":
            content = generate_sender_only_quote_context(message);
            break;
        case "INCLUDE_SENDER_AND_RECIPIENT":
            if (message.type === "stream") {
                content = generate_channel_message_quote_context(message);
            } else {
                content = generate_private_message_quote_context(message);
            }
            break;
        case "INCLUDE_NOTHING":
            content = "";
            break;
    }

    // An absent quote context means we don't need a new line to
    // separate the context line from the quote content.
    content += required_quote_context === "INCLUDE_NOTHING" ? "" : "\n";
    const fence = fenced_code.get_unused_fence(raw_content);
    content += `${fence}quote\n${raw_content}\n${fence}`;
    return content;
}

function replace_quoting_placeholder_with(info: {
    content: string;
    forward_message: boolean | undefined;
    // When the user is quoting messages that belong
    // to the same channel. All messages must have
    // their `type` as `stream`.
    quoting_messages_from_same_channel?: boolean;
    // When the user is quoting messages that belong
    // to more than one DM conversations. All messages
    // must have their `type` as `private`.
    quoting_messages_from_dm_conversations?: boolean;
}): void {
    const {
        forward_message,
        quoting_messages_from_dm_conversations,
        quoting_messages_from_same_channel,
        content,
    } = info;

    // These cases require focus either in the topic/dm recipient
    // input or the channel/DM picker.
    /* eslint-disable @typescript-eslint/prefer-nullish-coalescing */
    const should_focus_recipient =
        forward_message ||
        quoting_messages_from_same_channel ||
        quoting_messages_from_dm_conversations ||
        false;
    /* eslint-enable @typescript-eslint/prefer-nullish-coalescing */
    const $textarea = get_textarea_to_quote(forward_message);
    compose_ui.replace_syntax(quoting_placeholder, content, $textarea, should_focus_recipient);
    compose_ui.autosize_textarea($textarea);

    if (!forward_message) {
        return;
    }
    const select_recipient_widget: tippy.ReferenceElement | undefined = $(
        "#compose_select_recipient_widget",
    )[0];
    if (select_recipient_widget !== undefined) {
        void select_recipient_widget._tippy?.popperInstance?.update();
    }
}

export function quote_messages(opts: QuoteMessageOpts): void {
    if (opts.message_id) {
        quote_single_message(opts);
        return;
    }
    const highlighted_message_ids = get_highlighted_message_ids();
    if (highlighted_message_ids === undefined) {
        quote_single_message(opts);
    } else if (highlighted_message_ids.length === 1) {
        opts.highlighted_message_ids = highlighted_message_ids;
        quote_single_message(opts);
    } else {
        opts.highlighted_message_ids = highlighted_message_ids;
        quote_multiple_messages(opts);
    }
}

function quote_single_message(opts: QuoteMessageOpts): void {
    const {message_id, message, quote_content} = get_quote_target_for_single_message(opts);

    if (opts.forward_message) {
        setup_compose_to_forward_single_message(message, opts);
    } else {
        setup_compose_to_quote_single_message(message_id, opts);
    }

    if (message && quote_content) {
        const content = generate_replace_content({
            message,
            raw_content: quote_content,
            forward_message: opts.forward_message,
        });
        replace_quoting_placeholder_with({content, forward_message: opts.forward_message});
        return;
    }

    message_fetch_raw_content.get_raw_content_for_single_message({
        message_id,
        on_success(raw_content) {
            const content = generate_replace_content({
                message,
                raw_content,
                forward_message: opts.forward_message,
            });
            replace_quoting_placeholder_with({content, forward_message: opts.forward_message});
        },
        // We set a timeout here to trigger usage of the fallback markdown via the
        // error callback below, which is much better UX than waiting for 10 seconds and
        // feeling that the quoting mechanism is broken.
        timeout_ms: 1000,
        on_error() {
            // We fall back to using the available message content and pass it
            // through the `paste_handler_converter` to generate the replacement
            // markdown, in case the request timed out or failed for another reason,
            // such as the client being offline.
            const message_html = message.content;
            // We try to access message.raw_content one last time here, just in case
            // it was populated during the waiting time.
            const md = message.raw_content ?? compose_paste.paste_handler_converter(message_html);
            const content = generate_replace_content({
                message,
                raw_content: md,
                forward_message: opts.forward_message,
            });
            replace_quoting_placeholder_with({content, forward_message: opts.forward_message});
        },
    });
}

export function all_messages_have_same_channel(messages: Message[]): boolean {
    assert(messages.length > 0);
    const first_message = messages[0]!;
    if (first_message.type !== "stream") {
        return false;
    }
    const target_stream_id = first_message.stream_id;
    return messages.every((msg) => msg.type === "stream" && msg.stream_id === target_stream_id);
}

export function all_messages_are_private(messages: Message[]): boolean {
    assert(messages.length > 0);
    return messages.every((msg) => msg.type === "private");
}

export function all_messages_have_same_recipient(messages: Message[]): boolean {
    assert(messages.length > 0);
    if (!message_lists.current?.data.filter.may_contain_multiple_conversations()) {
        // We are guaranteed that the highlighted messages
        // won't have more than one recipient.
        return true;
    }
    const first_message = messages[0]!;

    if (first_message.type === "private") {
        const target_user_ids = first_message.to_user_ids;

        return messages.every(
            (msg) => msg.type === "private" && msg.to_user_ids === target_user_ids,
        );
    }
    // Stream messages must match both the stream ID and the topic.
    const target_stream_id = first_message.stream_id;
    const target_topic = first_message.topic.toLowerCase();

    return messages.every(
        (msg) =>
            msg.type === "stream" &&
            msg.stream_id === target_stream_id &&
            msg.topic.toLowerCase() === target_topic,
    );
}

type MultipleMessageStatus =
    | "QUOTING_MESSAGES_FROM_SAME_CHANNEL_AND_MULTIPLE_TOPICS"
    | "QUOTING_MESSAGES_FROM_DIFFERENT_DM_CONVERSATIONS"
    | "FORWARDING_MESSAGES_FROM_SAME_CHANNEL_AND_MULTIPLE_TOPICS"
    | "MESSAGES_WITH_NOTHING_IN_COMMON"
    | "MESSAGES_WITH_SAME_RECIPIENT";

export function get_multi_message_quote_status(
    messages: Message[],
    is_forwarding: boolean | undefined,
): MultipleMessageStatus {
    const do_messages_have_same_recipient = all_messages_have_same_recipient(messages);
    if (do_messages_have_same_recipient) {
        return "MESSAGES_WITH_SAME_RECIPIENT";
    }

    const messages_belong_to_same_channel = all_messages_have_same_channel(messages);
    if (messages_belong_to_same_channel) {
        if (!is_forwarding) {
            return "QUOTING_MESSAGES_FROM_SAME_CHANNEL_AND_MULTIPLE_TOPICS";
        }
        return "FORWARDING_MESSAGES_FROM_SAME_CHANNEL_AND_MULTIPLE_TOPICS";
    }

    const messages_are_private = all_messages_are_private(messages);
    if (messages_are_private && !is_forwarding) {
        return "QUOTING_MESSAGES_FROM_DIFFERENT_DM_CONVERSATIONS";
    }
    return "MESSAGES_WITH_NOTHING_IN_COMMON";
}

type QuoteAsset = {
    message: Message;
    quote_content: string;
};

export function build_and_process_quote_assets_for_messages(
    message_ids: number[],
    callback: (quote_assets: QuoteAsset[]) => void,
): void {
    const messages: Message[] = [];
    for (const id of message_ids) {
        const message = message_store.get(id);
        assert(message !== undefined);
        messages.push(message);
    }

    const quote_assets: QuoteAsset[] = [];
    message_fetch_raw_content.get_raw_content_for_messages({
        message_ids,
        on_success(raw_content_arr) {
            for (const [i, message] of messages.entries()) {
                const raw_content = raw_content_arr[i]!;
                assert(raw_content !== undefined);
                quote_assets.push({message, quote_content: raw_content});
            }
            callback(quote_assets);
        },
        on_error() {
            for (const message of messages) {
                const fallback_markdown_content = compose_paste.paste_handler_converter(
                    message.content,
                );
                quote_assets.push({
                    message,
                    quote_content: message.raw_content ?? fallback_markdown_content,
                });
            }
            callback(quote_assets);
        },
        timeout_ms: 1000,
    });
}

function quote_multiple_messages(opts: QuoteMessageOpts): void {
    const highlighted_message_ids = opts.highlighted_message_ids;
    assert(highlighted_message_ids !== undefined && highlighted_message_ids.length > 1);
    build_and_process_quote_assets_for_messages(
        highlighted_message_ids,
        (quote_assets: QuoteAsset[]) => {
            const msg_for_compose_box = quote_assets[0]!.message;
            const messages = quote_assets.map((asset) => asset.message);
            const status = get_multi_message_quote_status(messages, opts.forward_message);
            switch (status) {
                case "QUOTING_MESSAGES_FROM_SAME_CHANNEL_AND_MULTIPLE_TOPICS":
                    // When quoting multiple topics from the same channel
                    // (e.g., from the channel feed), we put initial focus
                    // into the topic field, rather than in the message body.
                    setup_compose_for_same_channel_messages(msg_for_compose_box, opts);
                    break;
                case "FORWARDING_MESSAGES_FROM_SAME_CHANNEL_AND_MULTIPLE_TOPICS":
                    // When forwarding multiple topics from the same channel, we
                    // pop open the recipient picker (as for a single message).
                    setup_compose_to_forward_single_message(msg_for_compose_box, opts);
                    break;
                case "QUOTING_MESSAGES_FROM_DIFFERENT_DM_CONVERSATIONS":
                    // When quoting from multiple DM conversations (e.g., from the DM feed),
                    // we use DM as the recipient and put focus in the private recipient field
                    setup_compose_for_quoting_dm_conversations(opts);
                    break;
                case "MESSAGES_WITH_NOTHING_IN_COMMON":
                    // We cannot determine the recipients for messages that don't share
                    // a common recipient. So we let the user decide by opening the composebox
                    // in an "unset" state.
                    setup_compose_for_unknown_recipient(opts);
                    break;
                case "MESSAGES_WITH_SAME_RECIPIENT":
                    // All the highlighted messages have the same recipient
                    // so we can reuse the setup methods for quoting/forwarding
                    // a single message.
                    if (opts.forward_message) {
                        setup_compose_to_forward_single_message(msg_for_compose_box, opts);
                    } else {
                        setup_compose_to_quote_single_message(msg_for_compose_box.id, opts);
                    }
                    break;
            }

            const content_string = quote_assets
                .map((asset, i) => {
                    const {message, quote_content} = asset;
                    const info: ReplaceContentOpts = {
                        message,
                        raw_content: quote_content,
                        forward_message: opts.forward_message,
                        // Use the index to determine the previous message
                        previous_message: i > 0 ? quote_assets[i - 1]!.message : undefined,
                        is_first_message_from_quote_chain: i === 0,
                    };

                    return generate_replace_content(info);
                })
                .join("\n\n");

            replace_quoting_placeholder_with({
                content: content_string,
                forward_message: opts.forward_message,
                quoting_messages_from_dm_conversations:
                    status === "QUOTING_MESSAGES_FROM_DIFFERENT_DM_CONVERSATIONS",
                quoting_messages_from_same_channel:
                    status === "QUOTING_MESSAGES_FROM_SAME_CHANNEL_AND_MULTIPLE_TOPICS",
            });
        },
    );
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

export let get_message_selection = (selection = window.getSelection()): string => {
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
};

export function rewire_get_message_selection(value: typeof get_message_selection): void {
    get_message_selection = value;
}

export function initialize(): void {
    $("body").on("click", ".compose_reply_button", () => {
        respond_to_message({trigger: "reply button"});
    });
}
