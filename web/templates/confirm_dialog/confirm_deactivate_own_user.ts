import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_deactivate_own_user() {
    const out = html`<p>
            ${$t({
                defaultMessage: "By deactivating your account, you will be logged out immediately.",
            })}
        </p>
        <p>${$t({defaultMessage: "Note that any bots that you maintain will be disabled."})}</p>
        <p>${$t({defaultMessage: "Are you sure you want to deactivate your account?"})}</p> `;
    return to_html(out);
}
