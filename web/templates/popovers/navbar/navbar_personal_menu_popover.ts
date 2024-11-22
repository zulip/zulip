import {html, to_html} from "../../../shared/src/html.ts";
import {to_bool} from "../../../src/hbs_compat.ts";
import {$t} from "../../../src/i18n.ts";

export default function render_navbar_personal_menu_popover(context) {
    const out = html`<div
        class="popover-menu"
        id="personal-menu-dropdown"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <nav class="personal-menu-nav">
            <header class="personal-menu-header">
                <div class="avatar">
                    <img
                        class="avatar-image${to_bool(context.user_is_guest) ? " guest-avatar" : ""}"
                        src="${context.user_avatar}"
                    />

                    ${to_bool(context.is_active)
                        ? html`
                              <span
                                  class="status-circle ${context.user_circle_class} user_circle hidden-for-spectators"
                                  data-tippy-placement="bottom"
                                  data-tippy-content="${context.user_last_seen_time_status}"
                              ></span>
                          `
                        : ""}
                </div>
                <div class="text-area">
                    <p class="full-name">${context.user_full_name}</p>
                    <p class="user-type">${context.user_type}</p>
                </div>
            </header>
            <section
                class="dropdown-menu-list-section personal-menu-actions"
                data-user-id="${context.user_id}"
            >
                <ul role="menu" class="popover-menu-list">
                    ${to_bool(context.status_content_available)
                        ? html`
                              <li role="none" class="text-item popover-menu-list-item">
                                  <span class="personal-menu-status-wrapper">
                                      ${to_bool(context.status_emoji_info)
                                          ? to_bool(context.status_emoji_info.emoji_alt_code)
                                              ? html`
                                                    <span class="emoji_alt_code"
                                                        >&nbsp;:${context.status_emoji_info
                                                            .emoji_name}:</span
                                                    >
                                                `
                                              : to_bool(context.status_emoji_info.url)
                                                ? html`
                                                      <img
                                                          src="${context.status_emoji_info.url}"
                                                          class="emoji status_emoji"
                                                      />
                                                  `
                                                : html`
                                                      <span
                                                          class="emoji status_emoji emoji-${context
                                                              .status_emoji_info.emoji_code}"
                                                      ></span>
                                                  `
                                          : ""}
                                      <span class="status_text personal-menu-status-text">
                                          ${to_bool(context.show_placeholder_for_status_text)
                                              ? html`
                                                    <i class="personal-menu-no-status-text"
                                                        >${$t({
                                                            defaultMessage: "No status text",
                                                        })}</i
                                                    >
                                                `
                                              : html` ${context.status_text} `}
                                      </span>
                                  </span>
                                  <a
                                      role="menuitem"
                                      tabindex="0"
                                      class="personal-menu-clear-status popover-menu-link"
                                      aria-label="${$t({defaultMessage: "Clear status"})}"
                                      data-tippy-content="${$t({
                                          defaultMessage: "Clear your status",
                                      })}"
                                  >
                                      <i
                                          class="personal-menu-clear-status-icon popover-menu-icon zulip-icon zulip-icon-x-circle"
                                          aria-hidden="true"
                                      ></i>
                                  </a>
                              </li>
                              ${/* Group 1 */ ""}
                              <li role="none" class="link-item popover-menu-list-item">
                                  <a
                                      role="menuitem"
                                      tabindex="0"
                                      class="update_status_text popover-menu-link"
                                  >
                                      <i
                                          class="popover-menu-icon zulip-icon zulip-icon-smile-smaller"
                                          aria-hidden="true"
                                      ></i>
                                      <span class="popover-menu-label"
                                          >${$t({defaultMessage: "Edit status"})}</span
                                      >
                                  </a>
                              </li>
                          `
                        : html`
                              <li
                                  role="none"
                                  class="link-item hidden-for-spectators popover-menu-list-item"
                              >
                                  <a
                                      role="menuitem"
                                      tabindex="0"
                                      class="update_status_text popover-menu-link"
                                  >
                                      <i
                                          class="popover-menu-icon zulip-icon zulip-icon-smile-smaller"
                                          aria-hidden="true"
                                      ></i>
                                      <span class="popover-menu-label"
                                          >${$t({defaultMessage: "Set status"})}</span
                                      >
                                  </a>
                              </li>
                          `}${to_bool(context.invisible_mode)
                        ? html`
                              <li
                                  role="none"
                                  class="link-item hidden-for-spectators popover-menu-list-item"
                              >
                                  <a
                                      role="menuitem"
                                      tabindex="0"
                                      class="invisible_mode_turn_off popover-menu-link"
                                  >
                                      <i
                                          class="popover-menu-icon zulip-icon zulip-icon-play-circle"
                                          aria-hidden="true"
                                      ></i>
                                      <span class="popover-menu-label"
                                          >${$t({defaultMessage: "Turn off invisible mode"})}</span
                                      >
                                  </a>
                              </li>
                          `
                        : html`
                              <li
                                  role="none"
                                  class="link-item hidden-for-spectators popover-menu-list-item"
                              >
                                  <a
                                      role="menuitem"
                                      tabindex="0"
                                      class="invisible_mode_turn_on popover-menu-link"
                                  >
                                      <i
                                          class="popover-menu-icon zulip-icon zulip-icon-stop-circle"
                                          aria-hidden="true"
                                      ></i>
                                      <span class="popover-menu-label"
                                          >${$t({defaultMessage: "Go invisible"})}</span
                                      >
                                  </a>
                              </li>
                          `}${/* Group 2 */ ""}
                    <li role="separator" class="popover-menu-separator"></li>
                    <li role="none" class="link-item popover-menu-list-item">
                        <a
                            role="menuitem"
                            href="#user/${context.user_id}"
                            tabindex="0"
                            class="view_full_user_profile popover-menu-link"
                        >
                            <i
                                class="popover-menu-icon zulip-icon zulip-icon-account"
                                aria-hidden="true"
                            ></i>
                            <span class="popover-menu-label"
                                >${$t({defaultMessage: "View your profile"})}</span
                            >
                        </a>
                    </li>
                    <li role="none" class="link-item popover-menu-list-item">
                        <a
                            role="menuitem"
                            tabindex="0"
                            class="narrow-self-direct-message popover-menu-link"
                        >
                            <i
                                class="popover-menu-icon zulip-icon zulip-icon-users"
                                aria-hidden="true"
                            ></i>
                            <span class="popover-menu-label"
                                >${$t({defaultMessage: "View messages with yourself"})}</span
                            >
                        </a>
                    </li>
                    <li role="none" class="link-item popover-menu-list-item">
                        <a
                            role="menuitem"
                            tabindex="0"
                            class="narrow-messages-sent popover-menu-link"
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
                    ${/* Group 3 */ ""}
                    <li role="separator" class="popover-menu-separator"></li>
                    <li role="none" class="link-item popover-menu-list-item">
                        <a
                            role="menuitem"
                            href="#settings/profile"
                            class="open-profile-settings popover-menu-link"
                        >
                            <i
                                class="popover-menu-icon zulip-icon zulip-icon-tool"
                                aria-hidden="true"
                            ></i>
                            <span class="popover-menu-label"
                                >${$t({defaultMessage: "Settings"})}</span
                            >
                        </a>
                    </li>
                    <li role="none" class="popover-menu-list-item">
                        <div
                            role="group"
                            class="tab-picker popover-menu-tab-group"
                            aria-label="${$t({defaultMessage: "App theme"})}"
                        >
                            <input
                                type="radio"
                                id="select-automatic-theme"
                                class="tab-option"
                                name="theme-select"
                                data-theme-code="${context.color_scheme_values.automatic.code}"
                                ${context.user_color_scheme ===
                                context.color_scheme_values.automatic.code
                                    ? "checked"
                                    : ""}
                            />
                            <label
                                role="menuitemradio"
                                class="tab-option-content tippy-zulip-delayed-tooltip"
                                for="select-automatic-theme"
                                aria-label="${$t({defaultMessage: "Select automatic theme"})}"
                                data-tooltip-template-id="automatic-theme-template"
                                tabindex="0"
                            >
                                <i class="zulip-icon zulip-icon-monitor" aria-hidden="true"></i>
                            </label>
                            <input
                                type="radio"
                                id="select-light-theme"
                                class="tab-option"
                                name="theme-select"
                                data-theme-code="${context.color_scheme_values.light.code}"
                                ${context.user_color_scheme ===
                                context.color_scheme_values.light.code
                                    ? "checked"
                                    : ""}
                            />
                            <label
                                role="menuitemradio"
                                class="tab-option-content tippy-zulip-delayed-tooltip"
                                for="select-light-theme"
                                aria-label="${$t({defaultMessage: "Select light theme"})}"
                                data-tippy-content="${$t({defaultMessage: "Light theme"})}"
                                tabindex="0"
                            >
                                <i class="zulip-icon zulip-icon-sun" aria-hidden="true"></i>
                            </label>
                            <input
                                type="radio"
                                id="select-dark-theme"
                                class="tab-option"
                                name="theme-select"
                                data-theme-code="${context.color_scheme_values.dark.code}"
                                ${context.user_color_scheme ===
                                context.color_scheme_values.dark.code
                                    ? "checked"
                                    : ""}
                            />
                            <label
                                role="menuitemradio"
                                class="tab-option-content tippy-zulip-delayed-tooltip"
                                for="select-dark-theme"
                                aria-label="${$t({defaultMessage: "Select dark theme"})}"
                                data-tippy-content="${$t({defaultMessage: "Dark theme"})}"
                                tabindex="0"
                            >
                                <i class="zulip-icon zulip-icon-moon" aria-hidden="true"></i>
                            </label>
                            <span class="slider"></span>
                        </div>
                    </li>
                    ${/* Group 4 */ ""}
                    <li role="separator" class="popover-menu-separator"></li>
                    <li role="none" class="link-item popover-menu-list-item">
                        <a
                            role="menuitem"
                            class="logout_button hidden-for-spectators popover-menu-link"
                            tabindex="0"
                        >
                            <i
                                class="popover-menu-icon zulip-icon zulip-icon-log-out"
                                aria-hidden="true"
                            ></i>
                            <span class="popover-menu-label"
                                >${$t({defaultMessage: "Log out"})}</span
                            >
                        </a>
                    </li>
                </ul>
            </section>
        </nav>
    </div> `;
    return to_html(out);
}
