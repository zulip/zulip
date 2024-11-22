import {html, to_html} from "../../../shared/src/html.ts";
import {popover_hotkey_hints} from "../../../src/common.ts";
import {to_bool} from "../../../src/hbs_compat.ts";
import {$t} from "../../../src/i18n.ts";

export default function render_navbar_help_menu_popover(context) {
    const out = html`<div
        class="popover-menu"
        id="help-menu-dropdown"
        aria-labelledby="help-menu"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <ul role="menu" class="popover-menu-list">
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    href="/help/"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="navigate-link-on-enter popover-menu-link"
                >
                    <i class="popover-menu-icon zulip-icon zulip-icon-help" aria-hidden="true"></i>
                    <span class="popover-menu-label">${$t({defaultMessage: "Help center"})}</span>
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    tabindex="0"
                    class="navigate-link-on-enter popover-menu-link"
                    data-overlay-trigger="keyboard-shortcuts"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-keyboard"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Keyboard shortcuts"})}</span
                    >
                    ${popover_hotkey_hints("?")}
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item hidden-for-spectators">
                <a
                    role="menuitem"
                    tabindex="0"
                    class="navigate-link-on-enter popover-menu-link"
                    data-overlay-trigger="message-formatting"
                >
                    <i class="popover-menu-icon zulip-icon zulip-icon-edit" aria-hidden="true"></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Message formatting"})}</span
                    >
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    tabindex="0"
                    class="navigate-link-on-enter popover-menu-link"
                    data-overlay-trigger="search-operators"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-manage-search"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Search filters"})}</span
                    >
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item" id="gear_menu_about_zulip">
                <a
                    role="menuitem"
                    href="#about-zulip"
                    class="navigate-link-on-enter popover-menu-link"
                >
                    <i class="popover-menu-icon zulip-icon zulip-icon-info" aria-hidden="true"></i>
                    <span class="popover-menu-label">${$t({defaultMessage: "About Zulip"})}</span>
                </a>
            </li>
            ${to_bool(context.corporate_enabled)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              href="/help/contact-support"
                              target="_blank"
                              rel="noopener noreferrer"
                              class="navigate-link-on-enter popover-menu-link"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-life-buoy"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Contact support"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}
        </ul>
    </div> `;
    return to_html(out);
}
