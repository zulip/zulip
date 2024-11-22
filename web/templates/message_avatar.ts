import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";

export default function render_message_avatar(context) {
    const out = html`<div
        class="u-${context.msg
            .sender_id} message-avatar sender_info_hover view_user_card_tooltip no-select"
        aria-hidden="true"
        data-is-bot="${context.sender_is_bot}"
    >
        <div
            class="inline_profile_picture ${to_bool(context.sender_is_guest)
                ? " guest-avatar"
                : ""}"
        >
            <img loading="lazy" src="${context.small_avatar_url}" alt="" class="no-drag" />
        </div>
    </div>`;
    return to_html(out);
}
