// Keep this synchronized with zerver/lib/topic_link_util.py

import assert from "minimalistic-assert";

import * as hash_util from "./hash_util.ts";
import * as stream_data from "./stream_data.ts";
import * as util from "./util.ts";

const invalid_stream_topic_regex = /[`>*&[\]]|(\$\$)/g;

export function will_produce_broken_stream_topic_link(word: string): boolean {
    return invalid_stream_topic_regex.test(word);
}

export function escape_invalid_stream_topic_characters(text: string): string {
    switch (text) {
        case "`":
            return "&#96;";
        case ">":
            return "&gt;";
        case "*":
            return "&#42;";
        case "&":
            return "&amp;";
        case "$$":
            return "&#36;&#36;";
        case "[":
            return "&#91;";
        case "]":
            return "&#93;";
        default:
            return text;
    }
}

// This record should be kept in sync with the
// escape_invalid_stream_topic_characters function.
const escaped_to_original_mapping: Record<string, string> = {
    "&#96;": "`",
    "&gt;": ">",
    "&#42;": "*",
    "&amp;": "&",
    "&#36;&#36;": "$$",
    "&#91;": "[",
    "&#93;": "]",
};

export function html_unescape_invalid_stream_topic_characters(text: string): string {
    const unescape_regex = new RegExp(Object.keys(escaped_to_original_mapping).join("|"), "g");
    return text.replaceAll(unescape_regex, (match) => escaped_to_original_mapping[match] ?? match);
}

export function html_escape_markdown_syntax_characters(text: string): string {
    return text.replaceAll(invalid_stream_topic_regex, escape_invalid_stream_topic_characters);
}

export function get_topic_link_content(
    stream_name: string,
    topic_name?: string,
    message_id?: string,
): {text: string; url: string} {
    const stream = stream_data.get_sub(stream_name);
    const stream_id = stream?.stream_id;
    assert(stream_id !== undefined);
    const escape = html_escape_markdown_syntax_characters;
    if (topic_name !== undefined) {
        const stream_topic_url = hash_util.by_stream_topic_url(stream_id, topic_name);
        const topic_display_name = util.get_final_topic_display_name(topic_name);
        if (message_id !== undefined) {
            return {
                text: `#${escape(stream_name)} > ${escape(topic_display_name)} @ 💬`,
                url: `${stream_topic_url}/near/${message_id}`,
            };
        }
        return {
            text: `#${escape(stream_name)} > ${escape(topic_display_name)}`,
            url: stream_topic_url,
        };
    }
    return {
        text: `#${escape(stream_name)}`,
        url: hash_util.channel_url_by_user_setting(stream_id),
    };
}

export function as_markdown_link_syntax(text: string, url: string): string {
    return `[${text}](${url})`;
}

export function as_html_link_syntax_unsafe(text: string, url: string): string {
    // The caller is responsible for making sure that the `text`
    // parameter is properly escaped.
    return `<a href="${url}">${text}</a>`;
}

export function get_fallback_markdown_link(
    stream_name: string,
    topic_name?: string,
    message_id?: string,
): string {
    // Helper that should only be called by other methods in this file.

    // Generates the vanilla markdown link syntax for a stream/topic/message link, as
    // a fallback for cases where the nicer Zulip link syntax would not
    // render properly due to special characters in the channel or topic name.
    const {text, url} = get_topic_link_content(stream_name, topic_name, message_id);
    return as_markdown_link_syntax(text, url);
}

export function get_stream_topic_link_syntax(stream_name: string, topic_name: string): string {
    // If the topic name is such that it will generate an invalid #**stream>topic** syntax,
    // we revert to generating the normal markdown syntax for a link.
    if (
        will_produce_broken_stream_topic_link(topic_name) ||
        will_produce_broken_stream_topic_link(stream_name)
    ) {
        return get_fallback_markdown_link(stream_name, topic_name);
    }
    return `#**${stream_name}>${topic_name}**`;
}

export function get_stream_link_syntax(stream_name: string): string {
    // If the topic name is such that it will generate an invalid #**stream>topic** syntax,
    // we revert to generating the normal markdown syntax for a link.
    if (will_produce_broken_stream_topic_link(stream_name)) {
        return get_fallback_markdown_link(stream_name);
    }
    return `#**${stream_name}**`;
}
