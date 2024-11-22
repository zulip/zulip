import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_delete_message() {
    const out = html`<p>
        ${$t({defaultMessage: "Deleting a message permanently removes it for everyone."})}
    </p> `;
    return to_html(out);
}
