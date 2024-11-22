import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_change_email_modal(context) {
    const out = html`<form id="change_email_form">
        <label for="change-email-form-input-email" class="modal-field-label"
            >${$t({defaultMessage: "New email"})}</label
        >
        <input
            id="change-email-form-input-email"
            type="text"
            name="email"
            class="modal_text_input"
            value="${context.delivery_email}"
            autocomplete="off"
            spellcheck="false"
            autofocus="autofocus"
        />
    </form> `;
    return to_html(out);
}
