import {html, to_html} from "../shared/src/html.ts";

export default function render_empty_list_widget_for_list(context) {
    const out = html`<li class="empty-list-message">${context.empty_list_message}</li> `;
    return to_html(out);
}
