import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_confirm_mute_user(context) {
    const out = html`<p>
        ${$html_t(
            {
                defaultMessage:
                    "Are you sure you want to mute <b>{user_name}</b>?  Messages sent by muted users will never trigger notifications, will be marked as read, and will be hidden.",
            },
            {user_name: context.user_name},
        )}
    </p> `;
    return to_html(out);
}
