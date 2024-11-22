import {html, to_html} from "../shared/src/html.ts";

export default function render_embedded_bot_config_item(context) {
    const out = html`<div
        class="input-group"
        name="${context.botname}"
        id="${context.botname}_${context.key}"
    >
        <label for="${context.botname}_${context.key}_input" class="modal-field-label"
            >${context.key}</label
        >
        <input
            type="text"
            name="${context.key}"
            id="${context.botname}_${context.key}_input"
            class="modal_text_input"
            maxlength="1000"
            placeholder="${context.value}"
            value=""
        />
    </div> `;
    return to_html(out);
}
