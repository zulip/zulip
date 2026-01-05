import {html, to_html} from "../src/html.ts";
import {$html_t} from "../src/i18n.ts";

export default function render_topics_required_error_message(context) {
    const out = $html_t(
        {
            defaultMessage:
                "Sending messages to the <z-empty-string-topic-display-name></z-empty-string-topic-display-name> topic is not allowed in this channel.",
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
