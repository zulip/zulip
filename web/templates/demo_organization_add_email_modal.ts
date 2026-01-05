import {to_array} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_help_link_widget from "./help_link_widget.ts";

export default function render_demo_organization_add_email_modal(context) {
    const out = html`<form id="demo_organization_add_email_form">
        <div class="input-group">
            <label for="demo_organization_add_email" class="modal-field-label"
                >${$t({defaultMessage: "Email"})}</label
            >
            <input
                id="demo_organization_add_email"
                type="text"
                name="email"
                class="modal_text_input"
                value="${context.delivery_email}"
                autocomplete="off"
                spellcheck="false"
                autofocus="autofocus"
            />
        </div>
        <div class="input-group">
            <label for="demo_owner_email_address_visibility" class="modal-field-label">
                ${$t({defaultMessage: "Who can access your email address"})}
                ${{__html: render_help_link_widget({link: "/help/configure-email-visibility"})}}
            </label>
            <select
                id="demo_owner_email_address_visibility"
                name="demo_owner_email_address_visibility"
                class="modal_select bootstrap-focus-style"
            >
                ${to_array(context.email_address_visibility_values).map(
                    (visibility) => html`
                        <option value="${visibility.code}">${visibility.description}</option>
                    `,
                )}
            </select>
        </div>
        <div class="input-group">
            <label for="demo_organization_update_full_name" class="modal-field-label"
                >${$t({defaultMessage: "Name"})}</label
            >
            <p id="demo-owner-update-email-field-hint">
                ${$t({
                    defaultMessage:
                        "If you haven't updated your name, consider doing so before inviting others to join.",
                })}
            </p>
            <input
                id="demo_organization_update_full_name"
                name="full_name"
                type="text"
                class="modal_text_input"
                value="${context.full_name}"
                maxlength="60"
            />
        </div>
    </form> `;
    return to_html(out);
}
