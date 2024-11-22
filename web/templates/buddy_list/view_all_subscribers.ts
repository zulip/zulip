import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_view_all_subscribers(context) {
    const out = html`<div class="buddy-list-user-link view-all-subscribers-link">
        <a class="buddy-list-user-link-text" href="${context.stream_edit_hash}"
            >${$t({defaultMessage: "View all subscribers"})}</a
        >
    </div> `;
    return to_html(out);
}
