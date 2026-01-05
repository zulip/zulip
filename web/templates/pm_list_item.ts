import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_status_emoji from "./status_emoji.ts";

export default function render_pm_list_item(context) {
    const out = html`<li
        class="${to_bool(context.is_active) ? "active-sub-filter" : ""} ${to_bool(context.is_zero)
            ? "zero-dm-unreads"
            : ""} dm-list-item bottom_left_row"
        data-user-ids-string="${context.user_ids_string}"
    >
        <a
            href="${context.url}"
            draggable="false"
            class="dm-box dm-user-status"
            data-user-ids-string="${context.user_ids_string}"
            data-is-group="${context.is_group}"
        >
            ${to_bool(context.is_group)
                ? html`
                      <span
                          class="conversation-partners-icon zulip-icon zulip-icon-dm-groups-3"
                      ></span>
                  `
                : html`
                      <span
                          class="conversation-partners-icon zulip-icon zulip-icon-${context.user_circle_class} ${context.user_circle_class} user-circle"
                      ></span>
                  `}
            <span class="conversation-partners">
                <span class="conversation-partners-list"
                    >${context.recipients}
                    ${to_bool(context.is_current_user)
                        ? html`<span class="my_user_status">${$t({defaultMessage: "(you)"})}</span>`
                        : ""}
                    ${{__html: render_status_emoji(context.status_emoji_info)}}${to_bool(
                        context.is_bot,
                    )
                        ? html`
                              <i
                                  class="zulip-icon zulip-icon-bot"
                                  aria-label="${$t({defaultMessage: "Bot"})}"
                              ></i>
                          `
                        : ""}
                </span>
            </span>
            <div class="dm-markers-and-unreads">
                ${to_bool(context.has_unread_mention)
                    ? html` <span class="unread_mention_info"> @ </span> `
                    : ""}
                <span class="unread_count ${to_bool(context.is_zero) ? "zero_count" : ""}">
                    ${context.unread}
                </span>
            </div>
        </a>
    </li> `;
    return to_html(out);
}
