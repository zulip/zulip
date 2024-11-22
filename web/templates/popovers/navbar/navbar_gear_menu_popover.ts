import {html, to_html} from "../../../shared/src/html.ts";
import {to_bool} from "../../../src/hbs_compat.ts";
import {$t} from "../../../src/i18n.ts";

export default function render_navbar_gear_menu_popover(context) {
    const out = html`<div
        class="popover-menu"
        id="gear-menu-dropdown"
        aria-labelledby="settings-dropdown"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <div class="org-info-container">
            <div class="org-info org-name">${context.realm_name}</div>
            <div class="org-info org-url">${context.realm_url}</div>
            ${to_bool(context.is_self_hosted)
                ? html` <div class="org-info org-version">
                          <a href="#about-zulip" class="navigate-link-on-enter popover-menu-link"
                              >${context.version_display_string}</a
                          >
                      </div>
                      ${to_bool(context.server_needs_upgrade)
                          ? html`
                                <div class="org-info org-upgrade">
                                    <a
                                        href="https://zulip.readthedocs.io/en/stable/production/upgrade.html"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        class="navigate-link-on-enter popover-menu-link"
                                        >${$t({defaultMessage: "Upgrade to the latest release"})}</a
                                    >
                                </div>
                            `
                          : ""}`
                : html`
                      <div class="org-info org-plan hidden-for-spectators">
                          ${to_bool(context.is_plan_limited)
                              ? html`
                                    <a
                                        href="/plans/"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        class="navigate-link-on-enter popover-menu-link"
                                        >Zulip Cloud Free</a
                                    >
                                `
                              : to_bool(context.is_plan_standard)
                                ? html`
                                      <a
                                          href="/plans/"
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          class="navigate-link-on-enter popover-menu-link"
                                          >Zulip Cloud Standard</a
                                      >
                                  `
                                : to_bool(context.is_plan_standard_sponsored_for_free)
                                  ? html`
                                        <a
                                            href="/plans/"
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            class="navigate-link-on-enter popover-menu-link"
                                            >Zulip Cloud Standard (sponsored)</a
                                        >
                                    `
                                  : to_bool(context.is_plan_plus)
                                    ? html`
                                          <a
                                              href="/plans/"
                                              target="_blank"
                                              rel="noopener noreferrer"
                                              class="navigate-link-on-enter popover-menu-link"
                                              >Zulip Cloud Plus</a
                                          >
                                      `
                                    : ""}
                      </div>
                  `}${!to_bool(context.is_self_hosted) &&
            to_bool(context.user_has_billing_access) &&
            !to_bool(context.is_plan_standard_sponsored_for_free)
                ? to_bool(context.sponsorship_pending)
                    ? html`
                          <div class="org-info org-upgrade">
                              <a
                                  href="/sponsorship/"
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  class="navigate-link-on-enter popover-menu-link"
                                  >${$t({defaultMessage: "Sponsorship request pending"})}</a
                              >
                          </div>
                      `
                    : html`${to_bool(context.is_plan_limited)
                          ? html`
                                <div class="org-info org-upgrade">
                                    <a
                                        href="/upgrade/"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        class="navigate-link-on-enter popover-menu-link"
                                        >${$t(
                                            {defaultMessage: "Upgrade to {standard_plan_name}"},
                                            {standard_plan_name: context.standard_plan_name},
                                        )}</a
                                    >
                                </div>
                            `
                          : ""}${!to_bool(context.is_org_on_paid_plan)
                          ? to_bool(context.is_education_org)
                              ? html`
                                    <div class="org-info org-upgrade">
                                        <a
                                            href="/sponsorship/"
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            class="navigate-link-on-enter popover-menu-link"
                                            >${$t({defaultMessage: "Request education pricing"})}</a
                                        >
                                    </div>
                                `
                              : !to_bool(context.is_business_org)
                                ? html`
                                      <div class="org-info org-upgrade">
                                          <a
                                              href="/sponsorship/"
                                              target="_blank"
                                              rel="noopener noreferrer"
                                              class="navigate-link-on-enter popover-menu-link"
                                              >${$t({defaultMessage: "Request sponsorship"})}</a
                                          >
                                      </div>
                                  `
                                : ""
                          : ""}`
                : ""}
        </div>
        <ul role="menu" class="popover-menu-list">
            ${/* Group 1 */ ""}
            <li role="none" class="link-item popover-menu-list-item hidden-for-spectators">
                <a
                    role="menuitem"
                    href="#channels/subscribed"
                    class="navigate-link-on-enter popover-menu-link"
                >
                    <i class="popover-menu-icon zulip-icon zulip-icon-hash" aria-hidden="true"></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Channel settings"})}</span
                    >
                </a>
            </li>
            <li
                role="none"
                class="link-item popover-menu-list-item admin-menu-item hidden-for-spectators"
            >
                <a
                    role="menuitem"
                    href="#organization"
                    class="navigate-link-on-enter popover-menu-link"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-building"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Organization settings"})}</span
                    >
                </a>
            </li>
            ${!to_bool(context.is_guest)
                ? html`
                      <li
                          role="none"
                          class="link-item popover-menu-list-item hidden-for-spectators"
                      >
                          <a
                              role="menuitem"
                              href="#groups/your"
                              class="navigate-link-on-enter popover-menu-link"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-user-cog"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Group settings"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}
            <li role="none" class="link-item popover-menu-list-item hidden-for-spectators">
                <a
                    role="menuitem"
                    href="#settings"
                    class="navigate-link-on-enter popover-menu-link"
                >
                    <i class="popover-menu-icon zulip-icon zulip-icon-tool" aria-hidden="true"></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Personal settings"})}</span
                    >
                </a>
            </li>
            ${!to_bool(context.is_guest)
                ? html`
                      <li
                          role="none"
                          class="link-item popover-menu-list-item hidden-for-spectators"
                      >
                          <a
                              role="menuitem"
                              href="/stats"
                              target="_blank"
                              rel="noopener noreferrer"
                              class="navigate-link-on-enter popover-menu-link"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-bar-chart"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Usage statistics"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}
            <li role="none" class="popover-menu-list-item only-visible-for-spectators">
                <div
                    role="group"
                    class="theme-switcher tab-picker"
                    aria-label="${$t({defaultMessage: "App theme"})}"
                >
                    <input
                        type="radio"
                        id="select-automatic-theme"
                        class="tab-option"
                        name="theme-select"
                        data-theme-code="${context.color_scheme_values.automatic.code}"
                        ${context.user_color_scheme === context.color_scheme_values.automatic.code
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
                        ${context.user_color_scheme === context.color_scheme_values.light.code
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
                        ${context.user_color_scheme === context.color_scheme_values.dark.code
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
            <li role="none" class="link-item popover-menu-list-item only-visible-for-spectators">
                <a role="menuitem" tabindex="0" class="change-language-spectator popover-menu-link">
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-f-globe"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Select language"})}</span
                    >
                </a>
            </li>
            ${/* Group 2 */ ""}
            <li role="separator" class="popover-menu-separator"></li>
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    href="${context.apps_page_url}"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="navigate-link-on-enter popover-menu-link"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-monitor"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Desktop & mobile apps"})}</span
                    >
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    href="/integrations/"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="navigate-link-on-enter popover-menu-link"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-git-pull-request"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label">${$t({defaultMessage: "Integrations"})}</span>
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    href="/api/"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="navigate-link-on-enter popover-menu-link"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-file-text"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "API documentation"})}</span
                    >
                </a>
            </li>
            ${to_bool(context.show_billing)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              href="/billing/"
                              target="_blank"
                              rel="noopener noreferrer"
                              class="navigate-link-on-enter popover-menu-link"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-credit-card"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Billing"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}${to_bool(context.promote_sponsoring_zulip)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              href="https://zulip.com/help/support-zulip-project"
                              target="_blank"
                              rel="noopener noreferrer"
                              class="navigate-link-on-enter popover-menu-link"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-heart"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Support Zulip"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}${to_bool(context.show_remote_billing)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              href="/self-hosted-billing/"
                              id="open-self-hosted-billing"
                              target="_blank"
                              rel="noopener noreferrer"
                              class="navigate-link-on-enter popover-menu-link"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-rocket"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Plan management"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}${to_bool(context.show_plans)
                ? /* This will be hidden for self hosted realms since they will have corporate disabled. */ html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              href="/plans/"
                              target="_blank"
                              rel="noopener noreferrer"
                              class="navigate-link-on-enter popover-menu-link"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-rocket"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Plans and pricing"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}${/* Group 3 */ ""}${to_bool(context.can_invite_users_by_email) ||
            to_bool(context.can_create_multiuse_invite) ||
            to_bool(context.is_spectator) ||
            to_bool(context.show_webathena)
                ? html` <li role="separator" class="popover-menu-separator"></li> `
                : ""}${to_bool(context.can_invite_users_by_email) ||
            to_bool(context.can_create_multiuse_invite)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              tabindex="0"
                              class="invite-user-link popover-menu-link"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-user-plus"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Invite users"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}${to_bool(context.show_webathena)
                ? html`
                      <li
                          role="none"
                          class="link-item popover-menu-list-item"
                          title="${$t({
                              defaultMessage:
                                  "Grant Zulip the Kerberos tickets needed to run your Zephyr mirror via Webathena",
                          })}"
                          id="webathena_login_menu"
                      >
                          <a
                              role="menuitem"
                              href="#webathena"
                              class="webathena_login popover-menu-link"
                          >
                              <i class="popover-menu-icon fa fa-bolt" aria-hidden="true"></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Link with Webathena"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}
            <li role="none" class="link-item popover-menu-list-item only-visible-for-spectators">
                <a
                    role="menuitem"
                    href="${context.login_link}"
                    class="navigate-link-on-enter popover-menu-link"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-log-in"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label">${$t({defaultMessage: "Log in"})}</span>
                </a>
            </li>
        </ul>
    </div> `;
    return to_html(out);
}
