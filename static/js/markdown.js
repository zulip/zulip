import * as markdown_parse from "./markdown_parse";

let webapp_helpers;

export function initialize(helper_config) {
    webapp_helpers = helper_config;
}

export function apply_markdown(message) {
    const raw_content = message.raw_content;
    const {content, flags} = markdown_parse.parse({raw_content, helper_config: webapp_helpers});
    message.content = content;
    message.flags = flags;
    message.is_me_message = markdown_parse.is_status_message(raw_content);
}

export function add_topic_links(message) {
    if (message.type !== "stream") {
        message.topic_links = [];
        return;
    }
    message.topic_links = markdown_parse.get_topic_links({
        topic: message.topic,
        get_linkifier_map: webapp_helpers.get_linkifier_map,
    });
}

export function contains_backend_only_syntax(content) {
    return markdown_parse.content_contains_backend_only_syntax({
        content,
        get_linkifier_map: webapp_helpers.get_linkifier_map,
    });
}

export function parse_non_message(raw_content) {
    // Occasionally we get markdown from the server that is not technically
    // a message, but we want to convert it to HTML. Note that we parse
    // raw_content exactly as if it were a Zulip message, so we will
    // handle things like mentions, stream links, and linkifiers.
    return markdown_parse.parse({raw_content, helper_config: webapp_helpers}).content;
}
