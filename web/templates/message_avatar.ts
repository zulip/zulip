import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";

export default function render_message_avatar(context) {
    const out = html`<div
        class="u-${context.msg
            .sender_id} message-avatar sender_info_hover view_user_card_tooltip no-select"
        aria-hidden="true"
        data-is-bot="${context.sender_is_bot}"
    >
        <div class="inline-profile-picture-wrapper">
            <div
                class="inline_profile_picture ${to_bool(context.sender_is_guest)
                    ? " guest-avatar"
                    : ""} ${to_bool(context.sender_is_deactivated)
                    ? " deactivated "
                    : ""} ${to_bool(context.is_hidden) ? " muted-sender-avatar " : ""}"
            >
                <img loading="lazy" src="${context.small_avatar_url}" alt="" class="no-drag" />
                ${to_bool(context.sender_is_deactivated)
                    ? html` <i class="fa fa-ban deactivated-user-icon"></i> `
                    : ""}
            </div>
        </div>
    </div>`;
    return to_html(out);
}
