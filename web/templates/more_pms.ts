import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
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
        <a class="dm-name trigger-click-on-enter" tabindex="0"
            >${$t({defaultMessage: "more conversations"})}</a
        >
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
