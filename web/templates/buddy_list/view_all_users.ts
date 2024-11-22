import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_view_all_users() {
    const out = html`<div class="buddy-list-user-link view-all-users-link">
        <a class="buddy-list-user-link-text" href="#organization/users"
            >${$t({defaultMessage: "View all users"})}</a
        >
    </div> `;
    return to_html(out);
}
