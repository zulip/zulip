import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_intro_resolve_topic(context) {
    const out = $html_t(
        {
            defaultMessage:
                "You're marking the topic <z-highlight>{topic_name}</z-highlight> as resolved. This adds a ✔ at the beginning of the topic name to let everyone know that this conversation is done. <z-link>Learn more</z-link>",
        },
        {
            topic_name: context.topic_name,
            ["z-highlight"]: (content) => html`<b class="highlighted-element">${content}</b>`,
            ["z-link"]: (content) =>
                html`<a target="_blank" rel="noopener noreferrer" href="/help/resolve-a-topic"
                    >${content}</a
                >`,
        },
    );
    return to_html(out);
}
