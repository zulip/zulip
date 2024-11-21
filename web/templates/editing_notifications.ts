import {html, to_html} from "../src/html.ts";

export default function render_editing_notifications() {
    const out = html`<div class="message-editing-animation">
        <span class="y-animated-dot"></span>
        <span class="y-animated-dot"></span>
        <span class="y-animated-dot"></span>
    </div> `;
    return to_html(out);
}
