import {html, to_html} from "../shared/src/html.ts";

export default function render_dropdown_current_value_not_in_options(context) {
    const out = html`<span class="dropdown-current-value-not-in-options">${context.name}</span> `;
    return to_html(out);
}
