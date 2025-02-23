import assert from "minimalistic-assert";

import * as internal_url from "../shared/src/internal_url.ts";

import * as stream_data from "./stream_data.ts";

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
        const stream_topic_url = internal_url.by_stream_topic_url(
            stream_id,
            topic_name,
            () => stream_name,
        );
        if (message_id !== undefined) {
            return {
                text: `#${escape(stream_name)} > ${escape(topic_name)} @ 💬`,
                url: `${stream_topic_url}/near/${message_id}`,
            };
        }
        return {
            text: `#${escape(stream_name)} > ${escape(topic_name)}`,
            url: stream_topic_url,
        };
    }
    return {
        text: `#${escape(stream_name)}`,
        url: internal_url.by_stream_url(stream_id, () => stream_name),
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
