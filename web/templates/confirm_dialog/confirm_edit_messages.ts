import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_confirm_edit_messages(context) {
    const out = html`<p>
        ${$html_t(
            {
                defaultMessage:
                    "Scrolling to the last message you sent will mark <b>{num_unread}</b> unread messages as read. Would you like to scroll to that message and edit it?",
            },
            {num_unread: context.num_unread},
        )}
    </p> `;
    return to_html(out);
}
