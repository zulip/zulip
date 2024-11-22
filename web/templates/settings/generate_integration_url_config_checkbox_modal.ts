import {html, to_html} from "../../shared/src/html.ts";

export default function render_generate_integration_url_config_checkbox_modal(context) {
    const out = html`<div class="input-group" id="integration-url-${context.key}-container">
        <label class="checkbox">
            <input
                type="checkbox"
                id="integration-url-${context.key}-checkbox"
                class="integration-url-parameter"
            />
            <span class="rendered-checkbox"></span>
        </label>
        <label class="inline" for="integration-url-${context.key}-checkbox">${context.label}</label>
    </div> `;
    return to_html(out);
}
