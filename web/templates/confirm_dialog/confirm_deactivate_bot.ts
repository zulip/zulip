import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_deactivate_bot() {
    const out = html`<p>
        ${$t({
            defaultMessage:
                "A deactivated bot cannot send messages, access data, or take any other action.",
        })}
    </p> `;
    return to_html(out);
}
