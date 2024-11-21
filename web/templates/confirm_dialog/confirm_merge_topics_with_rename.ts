import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_confirm_merge_topics_with_rename(context) {
    const out = html`<p>
        ${$html_t(
            {
                defaultMessage:
                    "The topic <z-topic-name>{topic_display_name}</z-topic-name> already exists in this channel. Are you sure you want to combine messages from these topics? This cannot be undone.",
            },
            {
                topic_display_name: context.topic_display_name,
                ["z-topic-name"]: (content) =>
                    html`<strong
                        class="white-space-preserve-wrap ${to_bool(context.is_empty_string_topic)
                            ? "empty-topic-display"
                            : ""}"
                        >${content}</strong
                    >`,
            },
        )}
    </p> `;
    return to_html(out);
}
