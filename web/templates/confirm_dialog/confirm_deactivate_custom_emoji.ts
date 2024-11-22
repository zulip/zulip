import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_deactivate_custom_emoji() {
    const out = html`<p>
            ${$t({
                defaultMessage:
                    "A deactivated emoji will remain visible in existing messages and emoji reactions, but cannot be used on new messages.",
            })}
        </p>
        <p>${$t({defaultMessage: "This action cannot be undone."})}</p> `;
    return to_html(out);
}
