import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_view_all_users() {
    const out = html`<a class="right-sidebar-wrappable-text-container" href="#organization/users">
        <span class="right-sidebar-wrappable-text-inner">
            ${$t({defaultMessage: "View all users"})}
        </span>
    </a> `;
    return to_html(out);
}
