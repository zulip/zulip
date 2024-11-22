import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import render_status_emoji from "./status_emoji.ts";

export default function render_pm_list_item(context) {
    const out = html`<li
        class="${to_bool(context.is_active) ? "active-sub-filter" : ""} ${to_bool(context.is_zero)
            ? "zero-dm-unreads"
            : ""} dm-list-item bottom_left_row"
        data-user-ids-string="${context.user_ids_string}"
    >
        <div
            class="dm-box dm-user-status"
            data-user-ids-string="${context.user_ids_string}"
            data-is-group="${context.is_group}"
        >
            ${to_bool(context.is_group)
                ? html`
                      <span
                          class="conversation-partners-icon zulip-icon zulip-icon-triple-users"
                      ></span>
                  `
                : to_bool(context.is_bot)
                  ? html`
                        <span
                            class="conversation-partners-icon zulip-icon zulip-icon-bot"
                            aria-hidden="true"
                        ></span>
                    `
                  : html`
                        <span
                            class="conversation-partners-icon ${context.user_circle_class} user_circle"
                        ></span>
                    `}
            <a href="${context.url}" class="conversation-partners">
                <span class="conversation-partners-list">${context.recipients}</span>
                ${{__html: render_status_emoji(context.status_emoji_info)}}
            </a>
            <span class="unread_count ${to_bool(context.is_zero) ? "zero_count" : ""}">
                ${context.unread}
            </span>
        </div>
    </li> `;
    return to_html(out);
}
