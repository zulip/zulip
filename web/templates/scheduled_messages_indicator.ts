import {html, to_html} from "../shared/src/html.ts";
import {$html_t} from "../src/i18n.ts";

export default function render_scheduled_messages_indicator(context) {
    const out = html`
        <div class="scheduled_message_indicator">
            ${$html_t(
                {
                    defaultMessage:
                        "You have <z-link>{scheduled_message_count, plural, =1 {1 scheduled message} other {# scheduled messages}}</z-link> for this conversation.",
                },
                {
                    scheduled_message_count: context.scheduled_message_count,
                    ["z-link"]: (content) => html`<a href="/#scheduled">${content}</a>`,
                },
            )}
        </div>
    `;
    return to_html(out);
}
