import {html, to_html} from "../src/html.ts";

export default function render_compose_limit_indicator(context) {
    const out = html`${context.remaining_characters} `;
    return to_html(out);
}
