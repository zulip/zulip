import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_status_emoji from "./status_emoji.ts";

export default function render_search_user_pill(context) {
    const out = html`<div class="user-pill-container pill" tabindex="0">
        <span class="pill-label">${to_bool(context.negated) ? "-" : ""}${context.operator}: </span>
        ${to_array(context.users).map(
            (user) => html`
                <div
                    class="pill${to_bool(user.deactivated) ? " deactivated-pill" : ""}"
                    data-user-id="${user.user_id}"
                >
                    <img class="pill-image" src="${user.img_src}" />
                    <span class="pill-label">
                        <span class="pill-value">${user.full_name}</span>${to_bool(
                            user.should_add_guest_user_indicator,
                        )
                            ? html`&nbsp;<i>(${$t({defaultMessage: "guest"})})</i>`
                            : ""}${to_bool(user.deactivated)
                            ? html`&nbsp;(${$t({defaultMessage: "deactivated"})})`
                            : ""}${to_bool(user.status_emoji_info)
                            ? {__html: render_status_emoji(user.status_emoji_info)}
                            : ""}</span
                    >
                    <div class="exit">
                        <a role="button" class="zulip-icon zulip-icon-close pill-close-button"></a>
                    </div>
                </div>
            `,
        )}
    </div> `;
    return to_html(out);
}
