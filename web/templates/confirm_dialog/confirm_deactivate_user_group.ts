import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_deactivate_user_group() {
    const out = html`<p>
        ${$t({defaultMessage: "You can always reactivate this group later."})}
    </p> `;
    return to_html(out);
}
