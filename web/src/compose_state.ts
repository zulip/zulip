import $ from "jquery";
import assert from "minimalistic-assert";

import * as compose_pm_pill from "./compose_pm_pill.ts";
import {$t} from "./i18n.ts";
import * as markdown from "./markdown.ts";
import * as narrow_state from "./narrow_state.ts";
import {postprocess_content} from "./postprocess_content.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";

let message_type: "stream" | "private" | undefined;
let recipient_edited_manually = false;
let is_content_unedited_restored_draft = false;
let last_focused_compose_type_input: HTMLTextAreaElement | undefined;
let preview_render_count = 0;
let is_processing_forward_message = false;

// We use this variable to keep track of whether user has viewed the topic resolved
// banner for the current compose session, for a narrow. This prevents the banner
// from popping up for every keystroke while composing.
// The variable is reset on sending a message, closing the compose box and changing
// the narrow and the user should still be able to see the banner once after
// performing these actions
let recipient_viewed_topic_resolved_banner = false;
let recipient_viewed_topic_moved_banner = false;
let recipient_guest_ids_for_dm_warning: number[] = [];

export function set_recipient_edited_manually(flag: boolean): void {
    recipient_edited_manually = flag;
}

export function is_recipient_edited_manually(): boolean {
    return recipient_edited_manually;
}

export function set_is_content_unedited_restored_draft(flag: boolean): void {
    is_content_unedited_restored_draft = flag;
}

export function get_is_content_unedited_restored_draft(): boolean {
    return is_content_unedited_restored_draft;
}

export function set_last_focused_compose_type_input(element: HTMLTextAreaElement): void {
    last_focused_compose_type_input = element;
}

export function get_last_focused_compose_type_input(): HTMLTextAreaElement | undefined {
    return last_focused_compose_type_input;
}

export function set_message_type(msg_type: "stream" | "private" | undefined): void {
    message_type = msg_type;
}

export function get_message_type(): "stream" | "private" | undefined {
    return message_type;
}

export function set_recipient_viewed_topic_resolved_banner(flag: boolean): void {
    recipient_viewed_topic_resolved_banner = flag;
}

export function has_recipient_viewed_topic_resolved_banner(): boolean {
    return recipient_viewed_topic_resolved_banner;
}

export function set_recipient_viewed_topic_moved_banner(flag: boolean): void {
    recipient_viewed_topic_moved_banner = flag;
}

export function has_recipient_viewed_topic_moved_banner(): boolean {
    return recipient_viewed_topic_moved_banner;
}

export function set_recipient_guest_ids_for_dm_warning(guest_ids: number[]): void {
    recipient_guest_ids_for_dm_warning = guest_ids;
}

export function get_recipient_guest_ids_for_dm_warning(): number[] {
    return recipient_guest_ids_for_dm_warning;
}

export function get_preview_render_count(): number {
    return preview_render_count;
}

export function set_preview_render_count(count: number): void {
    preview_render_count = count;
}

export function set_is_processing_forward_message(val: boolean): void {
    is_processing_forward_message = val;
}

export function get_is_processing_forward_message(): boolean {
    return is_processing_forward_message;
}

export function composing(): boolean {
    // This is very similar to get_message_type(), but it returns
    // a boolean.
    return Boolean(message_type);
}

function get_or_set(
    input_selector: string,
    // For the compose box, it's important to preserve leading spaces,
    // but not newlines.
    keep_leading_spaces?: boolean,
    no_trim?: boolean,
): (newval?: string) => string {
    // We can't hoist the assignment of '$elem' out of this lambda,
    // because the DOM element might not exist yet when get_or_set
    // is called.
    return function (newval) {
        const $elem = $<HTMLInputElement | HTMLTextAreaElement>(input_selector);
        const oldval = $elem.val()!;
        if (newval !== undefined) {
            $elem.val(newval);
        }
        if (no_trim) {
            return oldval;
        } else if (keep_leading_spaces) {
            return oldval.trimEnd().replace(/^(\r?\n)+/, "");
        }
        return oldval.trim();
    };
}

// selected_recipient_id is the current state for the stream picker widget:
// "" -> stream message but no stream is selected
// integer -> stream id of the selected stream.
// "direct" -> Direct message is selected.
export let selected_recipient_id: number | "direct" | "" = "";
export const DIRECT_MESSAGE_ID = "direct";

export function set_selected_recipient_id(recipient_id: number | "direct" | ""): void {
    selected_recipient_id = recipient_id;
}

export function stream_id(): number | undefined {
    const stream_id = selected_recipient_id;
    if (typeof stream_id === "number") {
        return stream_id;
    }
    return undefined;
}

export let stream_name = (): string => {
    const stream_id = selected_recipient_id;
    if (typeof stream_id === "number") {
        return sub_store.maybe_get_stream_name(stream_id) ?? "";
    }
    return "";
};

export function rewire_stream_name(value: typeof stream_name): void {
    stream_name = value;
}

export function set_stream_id(stream_id: number | ""): void {
    set_selected_recipient_id(stream_id);
}

export function set_compose_recipient_id(recipient_id: number | "direct"): void {
    set_selected_recipient_id(recipient_id);
}

// TODO: Break out setter and getter into their own functions.
export let topic = get_or_set("input#stream_message_recipient_topic");

export function rewire_topic(value: typeof topic): void {
    topic = value;
}

// We can't trim leading whitespace in `compose_textarea` because
// of the indented syntax for multi-line code blocks.
export const message_content = get_or_set("textarea#compose-textarea", true);

const untrimmed_message_content = get_or_set("textarea#compose-textarea", true, true);

function cursor_at_start_of_whitespace_in_compose(): boolean {
    const cursor_position = $("textarea#compose-textarea").caret();
    return message_content() === "" && cursor_position === 0;
}

export function get_message_with_raw_reply_content(
    $input_textarea: JQuery<HTMLTextAreaElement>,
): string {
    const content = $input_textarea.val()?.trimEnd();
    assert(content !== undefined);
    const $reply = $input_textarea
        .closest("#message-content-container, .edit-content-container")
        .find(".reply");
    if ($reply.length === 0) {
        return content;
    }

    const $user_mention = $reply.children(".user-mention");
    const user_id = $user_mention.attr("data-user-id");
    // The displayed username always carries a leading `@` in the reply UI,
    // so serialize from data-full-name rather than stripping the text.
    const full_name = $user_mention.attr("data-full-name") ?? "";
    const is_silent = $user_mention.hasClass("silent");
    const mention = is_silent ? `@_**${full_name}|${user_id}**` : `@**${full_name}|${user_id}**`;

    const $referenced_message_link = $reply.children(".referenced-message-link");
    const reply_content = $t(
        {defaultMessage: "{username} [{content}]({link_to_message})"},
        {
            username: mention,
            link_to_message: $referenced_message_link.attr("href"),
            content: serialize_reply_link_content($referenced_message_link),
        },
    );

    return reply_content + "\n\n" + content;
}

// Build the plain text that goes inside the reply snippet's `[...]`. Emoji
// are converted to Unicode characters here because the markdown processor
// doesn't reliably expand emoji shortcodes inside link text.
export function serialize_reply_link_content($link: JQuery): string {
    const link_el: unknown = $link[0];
    if (link_el === undefined) {
        return "";
    }
    if (link_el instanceof Element) {
        return convert_link_descendants_to_markdown_text(link_el);
    }
    // Fallback for zjquery's FakeElement in unit tests, which isn't a real
    // Element: use textContent without the emoji conversion.
    if (
        typeof link_el === "object" &&
        link_el !== null &&
        "textContent" in link_el &&
        typeof link_el.textContent === "string"
    ) {
        return link_el.textContent;
    }
    return "";
}

function convert_link_descendants_to_markdown_text(root: Element): string {
    let out = "";
    for (const node of root.childNodes) {
        if (node.nodeType === Node.TEXT_NODE) {
            out += node.textContent ?? "";
        } else if (node instanceof Element) {
            if (node.classList.contains("emoji")) {
                out += emoji_element_to_markdown_text(node);
            } else {
                out += convert_link_descendants_to_markdown_text(node);
            }
        }
    }
    return out;
}

function emoji_element_to_markdown_text(emoji_el: Element): string {
    // Unicode emoji render as <span class="emoji emoji-XXXX"> (or
    // `emoji-XXXX-YYYY` for multi-codepoint sequences); decode the
    // class-encoded codepoints back to characters.
    for (const cls of emoji_el.classList) {
        const match = /^emoji-([\da-f-]+)$/.exec(cls);
        if (!match) {
            continue;
        }
        try {
            return match[1]!
                .split("-")
                .map((p) => String.fromCodePoint(Number.parseInt(p, 16)))
                .join("");
        } catch {
            break;
        }
    }
    // Realm emoji <img> (or anything we can't decode): use the alt
    // attribute (`:name:`). Unlike Unicode emoji, realm emoji shortcodes
    // do survive markdown re-rendering.
    const alt = emoji_el.getAttribute("alt");
    if (alt !== null) {
        return alt;
    }
    return emoji_el.textContent ?? "";
}

// Captures a leading reply line — `@**Name|id** [snippet](url)`, or the silent
// `@_**…**` form — as (mention-prefix)(snippet text)(link target).
const reply_line_with_parts_pattern = /^(@_?\*\*[^*]+\*\*\s+)!?\[([^\]]+)\]\(([^)]+)\)/;

// Turn a quoted reply message's leading reply pointer into plain text. The
// reply line's snippet is a markdown link to the referenced message; inside a
// quote it would render as a stray blue link (the feed only styles it as a
// dimmed reply line at the top level). De-linking keeps the snippet text and
// the body intact while dropping the link. We only touch a genuine reply line,
// identified by its link targeting a specific message (`/near/<id>`) — the same
// signal the renderer uses — so ordinary text that opens with a mention and a
// link is left alone.
export function delink_leading_reply_snippet(content: string): string {
    const match = reply_line_with_parts_pattern.exec(content);
    if (match === null || !/\/near\/\d+/.test(match[3]!)) {
        return content;
    }
    return match[1]! + match[2]! + content.slice(match[0].length);
}

export function render_reply_and_get_parsed_message(
    message: string,
    $container?: JQuery,
    include_reply_action_buttons = true,
): string {
    const reply_pattern = /^@(_?)(?:\*\*([^*]+)\*\*)\s+!?\[([^\]]+)\]\(([^)]+)\)/;
    let stream = stream_name();
    let topic_name = topic();
    if ($container?.hasClass("message-edit-reply-container")) {
        stream = narrow_state.stream_name() ?? "";
        topic_name = narrow_state.topic() ?? "";
    }

    const message_content_html = postprocess_content(
        markdown.render(message).content,
        stream,
        topic_name,
        include_reply_action_buttons,
    );
    const inertDocument = new DOMParser().parseFromString("", "text/html");
    const template = inertDocument.createElement("template");
    template.innerHTML = message_content_html;
    const reply_html = template.content.querySelector(".reply");
    if (reply_html) {
        // The strip must not depend on $container: message-edit first calls
        // this without one to get the stripped body for the textarea, and
        // only later passes a container to populate the reply UI. Gating the
        // strip on $container would leave the reply markdown in the textarea
        // and duplicate it on every save.
        if ($container) {
            $container.html(reply_html.outerHTML);
        }
        return message.replace(reply_pattern, "").trimStart();
    }

    return message;
}

export function focus_in_formatting_buttons(): boolean {
    const is_focused_formatting_button =
        document.activeElement?.classList.contains("compose_control_button");
    if (is_focused_formatting_button) {
        return true;
    }
    return false;
}

export function focus_in_empty_compose(
    consider_start_of_whitespace_message_empty = false,
): boolean {
    // A user trying to press arrow keys in an empty compose is mostly
    // likely trying to navigate messages. This helper function
    // decides whether the compose box is empty for this purpose.
    if (!composing()) {
        return false;
    }

    // We treat the compose box as empty if it's completely empty, or
    // if the caller requested, if it contains only whitespace and we're
    // at the start of te compose box.
    const treat_compose_as_empty =
        untrimmed_message_content() === "" ||
        (consider_start_of_whitespace_message_empty && cursor_at_start_of_whitespace_in_compose());
    if (!treat_compose_as_empty) {
        return false;
    }

    const focused_element_id = document.activeElement?.id;
    if (focused_element_id === "compose-textarea") {
        // Focus will be in the compose textarea after sending a
        // message; this is the most common situation.
        return true;
    }

    // If the current focus is in one of the recipient inputs, we need
    // to check whether the input is empty, to avoid accidentally
    // overriding the browser feature where the Up/Down arrow keys jump
    // you to the start/end of a non-empty text input.
    //
    // Check whether the current input element is empty for each input type.
    switch (focused_element_id) {
        case "private_message_recipient":
            return private_message_recipient_ids().length === 0;
        case "stream_message_recipient_topic":
            return topic() === "";
        case "compose_select_recipient_widget_wrapper":
            return stream_id() === undefined;
    }

    return false;
}

export function private_message_recipient_emails(): string {
    return compose_pm_pill.get_emails();
}

export function private_message_recipient_ids(): number[] {
    return compose_pm_pill.get_user_ids();
}

// This sets new user ids with `skip_pill_callbacks=true`.
// If anything in `UserPillWidget.onPillCreate` is desired, call
// that directly after calling `set_private_message_recipient_ids`.
export function set_private_message_recipient_ids(value: number[]): void {
    compose_pm_pill.set_from_user_ids(value, true);
}

export function has_message_content(): boolean {
    return message_content() !== "";
}

export function has_novel_message_content(): boolean {
    return message_content() !== "" && !get_is_content_unedited_restored_draft();
}

const MINIMUM_MESSAGE_LENGTH_TO_SAVE_DRAFT = 2;
export function has_savable_message_content(): boolean {
    return message_content().length > MINIMUM_MESSAGE_LENGTH_TO_SAVE_DRAFT;
}

export function has_full_recipient(): boolean {
    if (message_type === "stream") {
        const has_topic = topic() !== "" || stream_data.can_use_empty_topic(stream_id());
        return stream_id() !== undefined && has_topic;
    }
    return private_message_recipient_ids().length > 0;
}

let _can_restore_drafts = true;
export function prevent_draft_restoring(): void {
    _can_restore_drafts = false;
}

export function allow_draft_restoring(): void {
    _can_restore_drafts = true;
}

export function can_restore_drafts(): boolean {
    return _can_restore_drafts;
}
