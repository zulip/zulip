import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_stream_topic_widget from "../stream_topic_widget.ts";

export default function render_confirm_unstar_all_messages_in_topic(context) {
    const out = html`<p>
        ${$html_t(
            {
                defaultMessage:
                    "Are you sure you want to unstar all messages in <stream-topic></stream-topic>?  This action cannot be undone.",
            },
            {["stream-topic"]: () => ({__html: render_stream_topic_widget(context)})},
        )}
    </p> `;
    return to_html(out);
}
