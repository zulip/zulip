import {html, to_html} from "../src/html.ts";

export default function render_help_link_widget(context) {
    const out = html`<a
        class="help_link_widget"
        href="${context.link}"
        target="_blank"
        rel="noopener noreferrer"
    >
        <i class="fa fa-question-circle-o" aria-hidden="true"></i>
    </a> `;
    return to_html(out);
}
