import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_delete_user() {
    const out = html`<p>${$t({defaultMessage: "This action cannot be undone."})}</p> `;
    return to_html(out);
}
