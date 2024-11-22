import {html, to_html} from "../shared/src/html.ts";

export default function render_dropdown_disabled_state(context) {
    const out = html`<span class="setting-disabled-option">${context.name}</span> `;
    return to_html(out);
}
