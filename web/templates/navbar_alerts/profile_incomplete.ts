import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_profile_incomplete() {
    const out = html`<div data-step="1">
        ${$html_t(
            {
                defaultMessage:
                    "Complete your <z-link>organization profile</z-link>, which is displayed on your organization's registration and login pages.",
            },
            {
                ["z-link"]: (content) =>
                    html`<a class="alert-link" href="#organization/organization-profile"
                        >${content}</a
                    >`,
            },
        )}
    </div> `;
    return to_html(out);
}
