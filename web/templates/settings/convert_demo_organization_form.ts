import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_convert_demo_organization_form(context) {
    const out = html`<div id="convert-demo-organization-form">
        ${!to_bool(context.user_has_email_set)
            ? html` <div class="demo-organization-add-email-banner banner-wrapper"></div> `
            : ""}
        <p>
            ${$t({
                defaultMessage:
                    "Everyone will need to log in again at the new URL for your organization.",
            })}
        </p>
        <form class="subdomain-setting">
            <div class="input-group">
                <label for="string_id" class="inline-block modal-field-label"
                    >${$t({defaultMessage: "Organization URL"})}</label
                >
                <div id="subdomain_input_container">
                    <input
                        id="new_subdomain"
                        type="text"
                        class="modal_text_input"
                        autocomplete="off"
                        name="string_id"
                        placeholder="${$t({defaultMessage: "acme"})}"
                    />
                    <label for="string_id" class="domain_label">.${context.realm_domain}</label>
                </div>
            </div>
        </form>
    </div> `;
    return to_html(out);
}
