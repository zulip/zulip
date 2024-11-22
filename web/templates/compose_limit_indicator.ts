import {html, to_html} from "../shared/src/html.ts";

export default function render_compose_limit_indicator(context) {
    const out = html`${context.remaining_characters} `;
    return to_html(out);
}
