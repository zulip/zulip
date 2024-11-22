import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_confirm_resend_invite(context) {
    const out = html`<p>
            ${$html_t(
                {
                    defaultMessage:
                        "Are you sure you want to resend the invitation to <z-email></z-email>?",
                },
                {["z-email"]: () => html`<strong>${context.email}</strong>`},
            )}
        </p>
        <p>
            ${$html_t({
                defaultMessage: "This will not change the expiration time for this invitation.",
            })}
        </p> `;
    return to_html(out);
}
