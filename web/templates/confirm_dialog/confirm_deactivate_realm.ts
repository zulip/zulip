import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_deactivate_realm() {
    const out = html`<p>
            ${$t({
                defaultMessage:
                    "This action is permanent and cannot be undone. All users will permanently lose access to their Zulip accounts.",
            })}
        </p>
        <p>${$t({defaultMessage: "Are you sure you want to deactivate this organization?"})}</p> `;
    return to_html(out);
}
