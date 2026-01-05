import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";

export default function render_stream_topic_widget(context) {
    const out = html`<strong>
        <span class="stream">${context.stream_name}</span> &gt;
        <span
            class="topic white-space-preserve-wrap ${to_bool(context.is_empty_string_topic)
                ? "empty-topic-display"
                : ""}"
            >${context.topic_display_name}</span
        >
    </strong> `;
    return to_html(out);
}
