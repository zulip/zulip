import {html, to_html} from "../../../shared/src/html.ts";
import {$t} from "../../../src/i18n.ts";

export default function render_user_card_popover_for_unknown_user(context) {
    const out = html`<div
        class="popover-menu user-card-popover-actions no-auto-hide-right-sidebar-overlay"
        id="user_card_popover"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <div class="popover-menu-user-header">
            <div class="popover-menu-user-avatar-container">
                <img class="popover-menu-user-avatar" src="${context.user_avatar}" />
            </div>
            <div class="popover-menu-user-info">
                <div
                    class="popover-menu-user-full-name"
                    data-tippy-content="${$t({defaultMessage: "Unknown user"})}"
                >
                    ${$t({defaultMessage: "Unknown user"})}
                </div>
            </div>
        </div>
        <ul role="menu" class="popover-menu-list" data-user-id="${context.user_id}">
            <li role="separator" class="popover-menu-separator hidden-for-spectators"></li>
            <li role="none" class="popover-menu-list-item link-item">
                <a
                    role="menuitem"
                    href="${context.sent_by_url}"
                    class="narrow_to_messages_sent popover-menu-link hidden-for-spectators"
                    tabindex="0"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-message-square"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "View messages sent"})}</span
                    >
                </a>
            </li>
        </ul>
    </div> `;
    return to_html(out);
}
