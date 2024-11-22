import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_status_emoji from "./status_emoji.ts";

export default function render_user_display_only_pill(context) {
    const out = html`<span
        class="pill-container display_only_pill ${to_bool(context.is_inline)
            ? "inline_with_text_pill"
            : ""}"
    >
        <a data-user-id="${context.user_id}" class="view_user_profile pill" tabindex="0">
            ${to_bool(context.img_src)
                ? html` <img class="pill-image" src="${context.img_src}" /> `
                : ""}
            <span class="pill-label ${to_bool(context.strikethrough) ? " strikethrough " : ""}">
                <span class="pill-value">${context.display_value}</span>
                ${to_bool(context.is_current_user)
                    ? html`<span class="my_user_status">${$t({defaultMessage: "(you)"})}</span>`
                    : ""}${to_bool(context.should_add_guest_user_indicator)
                    ? html`&nbsp;<i>(${$t({defaultMessage: "guest"})})</i>`
                    : ""}${to_bool(context.deactivated)
                    ? html`&nbsp;(${$t({defaultMessage: "deactivated"})})`
                    : ""}${to_bool(context.has_status)
                    ? {__html: render_status_emoji(context.status_emoji_info)}
                    : ""}</span
            >
        </a>
        ${!to_bool(context.is_active)
            ? html`
                  <i
                      class="fa fa-ban pill-deactivated deactivated-user-icon tippy-zulip-delayed-tooltip"
                      data-tippy-content="${to_bool(context.is_bot)
                          ? $t({defaultMessage: "Bot is deactivated"})
                          : $t({defaultMessage: "User is deactivated"})}"
                  ></i>
              `
            : ""}</span
    > `;
    return to_html(out);
}
