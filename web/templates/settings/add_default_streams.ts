import {html, to_html} from "../../shared/src/html.ts";

export default function render_add_default_streams() {
    const out = html`<table class="default_stream_choices_table">
        <tbody id="default-stream-choices"></tbody>
    </table> `;
    return to_html(out);
}
