import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_buddy_list_popover() {
    const out = html`<div
        class="popover-menu"
        id="stream-actions-menu-popover"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <ul role="menu" class="popover-menu-list">
            <li role="none" class="link-item">
                <a class="invite-user-link popover-menu-link" role="menuitem" tabindex="0">
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-user-plus"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label">
                        ${$t({defaultMessage: "Invite users to organization"})}
                    </span>
                </a>
            </li>
        </ul>
    </div> `;
    return to_html(out);
}
