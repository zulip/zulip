import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_realm_topics_policy_label(context) {
    const out = $html_t(
        {
            defaultMessage:
                "Default <z-empty-string-topic-display-name></z-empty-string-topic-display-name> topic configuration for channels",
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
