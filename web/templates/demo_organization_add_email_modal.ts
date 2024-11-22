import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_demo_organization_add_email_modal(context) {
    const out = html`<form id="demo_organization_add_email_form">
        <div class="tip">
            ${$t({
                defaultMessage:
                    "If you haven't updated your name, it's a good idea to do so before inviting other users to join you!",
            })}
        </div>
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
            <label for="demo_organization_update_full_name" class="modal-field-label"
                >${$t({defaultMessage: "Name"})}</label
            >
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
