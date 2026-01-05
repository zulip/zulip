import {html, to_html} from "../src/html.ts";
import {$html_t} from "../src/i18n.ts";

export default function render_topic_not_mandatory_placeholder_text(context) {
    const out = $html_t(
        {
            defaultMessage:
                "Enter a topic (skip for <z-empty-string-topic-display-name></z-empty-string-topic-display-name>)",
        },
        {
            ["z-empty-string-topic-display-name"]: () =>
                html`<span class="empty-topic-display"
                    >${context.empty_string_topic_display_name}</span
                >`,
        },
    );
    return to_html(out);
}
