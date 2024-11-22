import {html, to_html} from "../shared/src/html.ts";

export default function render_stream_topic_widget(context) {
    const out = html`<strong>
        <span class="stream">${context.stream_name}</span> &gt;
        <span class="topic white-space-preserve-wrap">${context.topic}</span>
    </strong> `;
    return to_html(out);
}
