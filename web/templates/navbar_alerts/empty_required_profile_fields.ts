import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_empty_required_profile_fields() {
    const out = html`<div data-step="1">
        <span>
            ${$t({defaultMessage: "Your profile is missing required fields."})}&nbsp;
            <a class="alert-link" href="#settings/profile"
                >${$t({defaultMessage: "Edit your profile"})}</a
            >
        </span>
    </div> `;
    return to_html(out);
}
