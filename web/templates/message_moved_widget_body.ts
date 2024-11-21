import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$html_t} from "../src/i18n.ts";

export default function render_message_moved_widget_body(context) {
    const out = html`<div>
        ${$html_t(
            {defaultMessage: "Message moved to <z-link></z-link>."},
            {
                ["z-link"]: () =>
                    html`<a class="white-space-preserve-wrap" href="${context.new_location_url}"
                        >#${context.new_stream_name} &gt;
                        <span
                            ${to_bool(context.is_empty_string_topic)
                                ? html`class="empty-topic-display"`
                                : ""}
                            >${context.new_topic_display_name}</span
                        ></a
                    >`,
            },
        )}
    </div> `;
    return to_html(out);
}
