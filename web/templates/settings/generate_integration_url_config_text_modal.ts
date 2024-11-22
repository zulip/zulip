import {html, to_html} from "../../shared/src/html.ts";

export default function render_generate_integration_url_config_text_modal(context) {
    const out = html`<div class="input-group" id="integration-url-${context.key}-container">
        <label for="integration-url-${context.key}-text" class="modal-label-field"
            >${context.label}</label
        >
        <input
            type="text"
            id="integration-url-${context.key}-text"
            class="modal_text_input integration-url-parameter"
            value=""
        />
    </div> `;
    return to_html(out);
}
