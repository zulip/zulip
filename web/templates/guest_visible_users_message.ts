import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";
import render_help_link_widget from "./help_link_widget.ts";

export default function render_guest_visible_users_message(context) {
    const out = html`<p id="guest_visible_users_message">
        ${$t(
            {
                defaultMessage:
                    "Guests will be able to see {user_count} users in their channels when they join.",
            },
            {user_count: context.user_count},
        )}
        ${{
            __html: render_help_link_widget({
                link: "/help/guest-users#configure-whether-guests-can-see-all-other-users",
            }),
        }}
    </p> `;
    return to_html(out);
}
