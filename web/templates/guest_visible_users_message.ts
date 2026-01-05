import {html, to_html} from "../src/html.ts";
import {$html_t} from "../src/i18n.ts";
import render_help_link_widget from "./help_link_widget.ts";

export default function render_guest_visible_users_message() {
    const out = html`<p id="guest_visible_users_message">
        ${$html_t(
            {
                defaultMessage:
                    "Guests will be able to see <z-user-count></z-user-count> users in their channels when they join.",
            },
            {
                ["z-user-count"]: () => html`
                    <span class="guest-visible-users-count" aria-hidden="true"></span>
                    <span class="guest_visible_users_loading"></span>
                `,
            },
        )}
        ${{
            __html: render_help_link_widget({
                link: "/help/guest-users#configure-whether-guests-can-see-all-other-users",
            }),
        }}
    </p> `;
    return to_html(out);
}
