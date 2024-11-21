import {html, to_html} from "../../../src/html.ts";
import {$t} from "../../../src/i18n.ts";

export default function render_left_sidebar_stream_setting_popover() {
    const out = html`<div class="popover-menu" data-simplebar data-simplebar-tab-index="-1">
        <ul role="menu" class="popover-menu-list">
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    href="#channels/available"
                    role="menuitem"
                    class="popover-menu-link navigate_and_close_popover"
                    tabindex="0"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-browse-channels"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Browse channels"})}</span
                    >
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    href="#channels/new"
                    role="menuitem"
                    class="popover-menu-link navigate_and_close_popover"
                    tabindex="0"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-square-plus"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Create a channel"})}</span
                    >
                </a>
            </li>
        </ul>
    </div> `;
    return to_html(out);
}
