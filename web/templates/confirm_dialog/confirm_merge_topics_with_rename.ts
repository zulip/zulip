import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_confirm_merge_topics_with_rename(context) {
    const out = html`<p>
        ${$html_t(
            {
                defaultMessage:
                    "The topic <z-topic-name>{topic_name}</z-topic-name> already exists in this channel. Are you sure you want to combine messages from these topics? This cannot be undone.",
            },
            {
                topic_name: context.topic_name,
                ["z-topic-name"]: (content) =>
                    html`<strong class="white-space-preserve-wrap">${content}</strong>`,
            },
        )}
    </p> `;
    return to_html(out);
}
