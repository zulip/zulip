import {to_array} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$html_t} from "../src/i18n.ts";

export default function render_message_reminders(context) {
    const out = html`<div class="message-reminders">
        ${to_array(context.msg.reminders).map(
            (reminder) => html`
                <p class="message-reminder">
                    ${$html_t(
                        {
                            defaultMessage:
                                "<z-link>Reminder</z-link> scheduled for {formatted_delivery_time}.",
                        },
                        {
                            formatted_delivery_time: reminder.formatted_delivery_time,
                            ["z-link"]: (content) =>
                                html`<a
                                    href="#reminders"
                                    class="message-reminder-overlay-link"
                                    data-reminder-id="${reminder.reminder_id}"
                                >
                                    ${content}
                                </a>`,
                        },
                    )}
                </p>
            `,
        )}
    </div> `;
    return to_html(out);
}
