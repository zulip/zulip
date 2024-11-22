import {html, to_html} from "../shared/src/html.ts";
import {$html_t} from "../src/i18n.ts";

export default function render_message_moved_widget_body(context) {
    const out = html`<div>
        ${$html_t(
            {defaultMessage: "Message moved to <z-link>{stream_topic}</z-link>."},
            {
                stream_topic: context.stream_topic,
                ["z-link"]: (content) =>
                    html`<a class="white-space-preserve-wrap" href="${context.new_location_url}"
                        >${content}</a
                    >`,
            },
        )}
    </div> `;
    return to_html(out);
}
