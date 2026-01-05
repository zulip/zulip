import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_view_all_subscribers(context) {
    const out = html`<a
        class="right-sidebar-wrappable-text-container"
        href="${context.stream_edit_hash}"
    >
        <span class="right-sidebar-wrappable-text-inner">
            ${$t({defaultMessage: "View all subscribers"})}
        </span>
    </a> `;
    return to_html(out);
}
