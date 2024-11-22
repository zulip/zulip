import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_confirm_reactivate_user(context) {
    const out = html`<p>
        ${$html_t(
            {
                defaultMessage:
                    "<z-user></z-user> will have the same role, channel subscriptions, user group memberships, and other settings and permissions as they did prior to deactivation.",
            },
            {["z-user"]: () => html`<strong>${context.username}</strong>`},
        )}
    </p> `;
    return to_html(out);
}
