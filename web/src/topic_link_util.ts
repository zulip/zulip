import assert from "minimalistic-assert";

import * as internal_url from "../shared/src/internal_url.ts";

import * as stream_data from "./stream_data.ts";

const invalid_stream_topic_regex = /[`>*&]|(\$\$)/g;

export function will_produce_broken_stream_topic_link(word: string): boolean {
    return invalid_stream_topic_regex.test(word);
}

function get_stream_name_from_topic_link_syntax(syntax: string): string {
    const start = syntax.indexOf("#**");
    const end = syntax.lastIndexOf(">");
    return syntax.slice(start + 3, end);
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
        default:
            return text;
    }
}

export function html_escape_markdown_syntax_characters(text: string): string {
    return text.replaceAll(invalid_stream_topic_regex, escape_invalid_stream_topic_characters);
}

export function get_fallback_markdown_link(
    stream_name: string,
    topic_name?: string,
    message_id?: string,
): string {
    const stream = stream_data.get_sub(stream_name);
    const stream_id = stream?.stream_id;
    assert(stream_id !== undefined);
    const escape = html_escape_markdown_syntax_characters;
    if (topic_name !== undefined) {
        const stream_topic_url = internal_url.by_stream_topic_url(
            stream_id,
            topic_name,
            () => stream_name,
        );
        if (message_id !== undefined) {
            return `[#${escape(stream_name)} > ${escape(topic_name)} @ 💬](${stream_topic_url}/near/${message_id})`;
        }
        return `[#${escape(stream_name)} > ${escape(topic_name)}](${stream_topic_url})`;
    }
    return `[#${escape(stream_name)}](${internal_url.by_stream_url(stream_id, () => stream_name)})`;
}

export function get_stream_topic_link_syntax(
    typed_syntax_text: string,
    topic_name: string,
): string {
    const stream_name = get_stream_name_from_topic_link_syntax(typed_syntax_text);
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
