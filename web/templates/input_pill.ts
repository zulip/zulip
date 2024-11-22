import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_status_emoji from "./status_emoji.ts";

export default function render_input_pill(context) {
    const out = html`<div
        class="pill ${to_bool(context.deactivated) ? " deactivated-pill " : ""}"
        ${to_bool(context.user_id) ? html`data-user-id="${context.user_id}"` : ""}${to_bool(
            context.group_id,
        )
            ? html`data-user-group-id="${context.group_id}"`
            : ""}${to_bool(context.stream_id) ? html`data-stream-id="${context.stream_id}"` : ""}
        tabindex="0"
    >
        ${to_bool(context.has_image)
            ? html` <img class="pill-image" src="${context.img_src}" /> `
            : ""}
        <span class="pill-label">
            <span class="pill-value">
                ${to_bool(context.has_stream)
                    ? to_bool(context.stream.invite_only)
                        ? html`<i
                              class="zulip-icon zulip-icon-lock stream-privacy-type-icon"
                              aria-hidden="true"
                          ></i>`
                        : to_bool(context.stream.is_web_public)
                          ? html`<i
                                class="zulip-icon zulip-icon-globe stream-privacy-type-icon"
                                aria-hidden="true"
                            ></i>`
                          : html`<i
                                class="zulip-icon zulip-icon-hashtag stream-privacy-type-icon"
                                aria-hidden="true"
                            ></i>`
                    : ""}
                ${context.display_value} </span
            >${to_bool(context.should_add_guest_user_indicator)
                ? html`&nbsp;<i>(${$t({defaultMessage: "guest"})})</i>`
                : ""}${to_bool(context.deactivated)
                ? html`&nbsp;(${$t({defaultMessage: "deactivated"})})`
                : ""}${to_bool(context.has_status)
                ? {__html: render_status_emoji(context.status_emoji_info)}
                : ""}</span
        >
        <div class="exit">
            <a role="button" class="zulip-icon zulip-icon-close pill-close-button"></a>
        </div>
    </div> `;
    return to_html(out);
}
