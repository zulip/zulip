import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_add_alert_word() {
    const out = html`<form id="add-alert-word-form">
        <label for="add-alert-word-name" class="modal-field-label"
            >${$t({defaultMessage: "Alert word"})}</label
        >
        <input
            type="text"
            name="alert-word-name"
            id="add-alert-word-name"
            class="required modal_text_input"
            maxlength="100"
            placeholder="${$t({defaultMessage: "Alert word"})}"
            value=""
        />
    </form> `;
    return to_html(out);
}
