import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_more_pms(context) {
    const out = html`<li
        id="show-more-direct-messages"
        class="dm-list-item dm-box bottom_left_row ${!to_bool(
            context.more_conversations_unread_count,
        )
            ? "zero-dm-unreads"
            : ""}"
    >
        <a class="dm-name" tabindex="0">${$t({defaultMessage: "more conversations"})}</a>
        <span
            class="unread_count ${!to_bool(context.more_conversations_unread_count)
                ? "zero_count"
                : ""}"
        >
            ${context.more_conversations_unread_count}
        </span>
    </li> `;
    return to_html(out);
}
