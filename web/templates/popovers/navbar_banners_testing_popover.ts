import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_navbar_banners_testing_popover() {
    const out = html`<div
        class="popover-menu navbar-banners-testing-popover"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <ul role="menu" class="popover-menu-list">
            <li role="none" class="link-item popover-menu-list-item">
                <a role="menuitem" class="desktop-notifications popover-menu-link" tabindex="0">
                    <i class="popover-menu-icon zulip-icon zulip-icon-edit" aria-hidden="true"></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Desktop notifications"})}</span
                    >
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item">
                <a role="menuitem" class="configure-outgoing-mail popover-menu-link" tabindex="0">
                    <i class="popover-menu-icon zulip-icon zulip-icon-edit" aria-hidden="true"></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Configure outgoing mail"})}</span
                    >
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item">
                <a role="menuitem" class="insecure-desktop-app popover-menu-link" tabindex="0">
                    <i class="popover-menu-icon zulip-icon zulip-icon-edit" aria-hidden="true"></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Insecure desktop app"})}</span
                    >
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    class="profile-missing-required-fields popover-menu-link"
                    tabindex="0"
                >
                    <i class="popover-menu-icon zulip-icon zulip-icon-edit" aria-hidden="true"></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Profile missing required fields"})}</span
                    >
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    class="organization-profile-incomplete popover-menu-link"
                    tabindex="0"
                >
                    <i class="popover-menu-icon zulip-icon zulip-icon-edit" aria-hidden="true"></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Organization profile incomplete"})}</span
                    >
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item">
                <a role="menuitem" class="server-needs-upgrade popover-menu-link" tabindex="0">
                    <i class="popover-menu-icon zulip-icon zulip-icon-edit" aria-hidden="true"></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Server needs upgrade"})}</span
                    >
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item">
                <a role="menuitem" class="bankruptcy popover-menu-link" tabindex="0">
                    <i class="popover-menu-icon zulip-icon zulip-icon-edit" aria-hidden="true"></i>
                    <span class="popover-menu-label">${$t({defaultMessage: "Bankruptcy"})}</span>
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    class="demo-organization-deadline popover-menu-link"
                    tabindex="0"
                >
                    <i class="popover-menu-icon zulip-icon zulip-icon-edit" aria-hidden="true"></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Demo organization deadline"})}</span
                    >
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item">
                <a role="menuitem" class="time_zone_update_offer popover-menu-link" tabindex="0">
                    <i class="popover-menu-icon zulip-icon zulip-icon-edit" aria-hidden="true"></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Time zone update offer"})}</span
                    >
                </a>
            </li>
        </ul>
    </div> `;
    return to_html(out);
}
