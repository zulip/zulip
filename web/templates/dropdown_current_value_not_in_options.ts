import {html, to_html} from "../src/html.ts";

export default function render_dropdown_current_value_not_in_options(context) {
    const out = html`<span class="dropdown-current-value-not-in-options">${context.name}</span> `;
    return to_html(out);
}
