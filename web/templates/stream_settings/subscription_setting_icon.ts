import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";

export default function render_subscription_setting_icon(context) {
    const out = html`<div class="icon" style="background-color: ${context.color}">
        <div class="flex">
            ${to_bool(context.invite_only)
                ? html` <i class="zulip-icon zulip-icon-lock" aria-hidden="true"></i> `
                : to_bool(context.is_web_public)
                  ? html` <i class="zulip-icon zulip-icon-globe fa-lg" aria-hidden="true"></i> `
                  : html` <span class="zulip-icon zulip-icon-hashtag"></span> `}
        </div>
    </div> `;
    return to_html(out);
}
