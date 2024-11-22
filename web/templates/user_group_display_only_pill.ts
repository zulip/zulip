import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";

export default function render_user_group_display_only_pill(context) {
    const out = html`<span class="pill-container display_only_group_pill">
        <a data-user-group-id="${context.group_id}" class="view_user_group pill" tabindex="0">
            <i class="zulip-icon zulip-icon-triple-users no-presence-circle" aria-hidden="true"></i>
            <span class="pill-label ${to_bool(context.strikethrough) ? " strikethrough " : ""}">
                <span class="pill-value">${context.display_value}</span>
            </span>
        </a>
    </span> `;
    return to_html(out);
}
