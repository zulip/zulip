import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_unstar_all_messages() {
    const out = html`<p>
        ${$t({
            defaultMessage:
                "Are you sure you want to unstar all starred messages?  This action cannot be undone.",
        })}
    </p> `;
    return to_html(out);
}
