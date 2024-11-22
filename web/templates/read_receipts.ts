import {html, to_html} from "../shared/src/html.ts";
import {to_array} from "../src/hbs_compat.ts";

export default function render_read_receipts(context) {
    const out = to_array(context.users).map(
        (user) => html`
            <li class="view_user_profile" data-user-id="${user.user_id}" tabindex="0" role="button">
                <img class="read_receipts_user_avatar" src="${user.avatar_url}" />
                <span>${user.full_name}</span>
            </li>
        `,
    );
    return to_html(out);
}
